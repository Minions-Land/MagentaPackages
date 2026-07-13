"""Vision-backed figure assessment with deterministic image preflight."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import signal
import subprocess
import tempfile
import warnings
from pathlib import Path

from PIL import Image, ImageStat, UnidentifiedImageError

_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_VERDICT_LINE = re.compile(r"^(PASS|WARN|FAIL):[ \t]+([^\r\n]{12,2000})$")
_PLACEHOLDER_PHRASES = (
    "cannot view",
    "can't view",
    "unable to view",
    "cannot access the image",
    "can't access the image",
    "image was not provided",
    "no image was provided",
    "no image attached",
    "vision unavailable",
    "placeholder",
    "as a text-based",
)
_VISION_TIMEOUT_SECONDS = 60
_TERM_GRACE_SECONDS = 2
_MAX_IMAGE_PIXELS = 16_000_000
_VISION_SYSTEM_PROMPT = """You are a strict scientific figure quality-control evaluator. You MUST inspect the pixels in the attached image, answer the supplied question, and compare against the expectation when present. Reply with exactly one plain-text line and nothing else: `PASS: <reason>`, `WARN: <reason>`, or `FAIL: <reason>`. PASS means the requested criterion is satisfied without a major rendering issue. WARN means the image is inspectable but ambiguous or has a minor issue. FAIL means the criterion is not satisfied or there is a major artifact. The reason must cite at least two specific image-visible details separated by a semicolon. Never guess or claim success if you cannot inspect the attachment."""


class VisionUnavailableError(RuntimeError):
    """Raised when a real vision verdict cannot be obtained and validated."""


def _fail(path: Path, question: str, expectation: str | None, reason: str) -> dict[str, object]:
    return {
        "success": False,
        "verdict": "FAIL",
        "analysis": reason,
        "file_path": str(path),
        "model": "pillow-preflight",
        "reason": reason,
        "observations": [],
        "status": "FAIL",
        "filePath": str(path),
        "question": question,
        "expectation": expectation,
        "visionBacked": False,
    }


def _decode_and_check(path: Path, question: str, expectation: str | None) -> tuple[Image.Image, dict[str, object]] | dict[str, object]:
    if not path.is_file():
        return _fail(path, question, expectation, "image file does not exist or is not a regular file")
    if path.stat().st_size == 0:
        return _fail(path, question, expectation, "image file is empty")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as opened:
                width, height = opened.size
                if width <= 0 or height <= 0:
                    return _fail(path, question, expectation, "decoded image has invalid dimensions")
                if width * height > _MAX_IMAGE_PIXELS:
                    return _fail(
                        path,
                        question,
                        expectation,
                        f"image exceeds the {_MAX_IMAGE_PIXELS}-pixel safety limit ({width}x{height})",
                    )
                opened.verify()
            with Image.open(path) as opened:
                opened.seek(0)
                image = opened.convert("RGBA")
                source_format = opened.format or "unknown"
                source_mode = opened.mode
                frame_count = getattr(opened, "n_frames", 1)
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as error:
        return _fail(path, question, expectation, f"image decode failed: {error}")
    alpha = image.getchannel("A")
    alpha_extrema = alpha.getextrema()
    if alpha_extrema == (0, 0):
        return _fail(path, question, expectation, "image is fully transparent")

    canvas = Image.new("RGB", image.size, "white")
    canvas.paste(image.convert("RGB"), mask=alpha)
    grayscale = canvas.convert("L")
    statistics = ImageStat.Stat(grayscale)
    extrema = grayscale.getextrema()
    entropy = float(grayscale.entropy())
    standard_deviation = float(statistics.stddev[0])
    dynamic_range = int(extrema[1] - extrema[0])
    if not all(math.isfinite(value) for value in (entropy, standard_deviation)):
        return _fail(path, question, expectation, "pixel statistics are not finite")
    if dynamic_range <= 1 or standard_deviation < 0.5 or entropy < 0.05:
        return _fail(
            path,
            question,
            expectation,
            "image is effectively uniform after transparency compositing "
            f"(dynamicRange={dynamic_range}, stddev={standard_deviation:.3f}, entropy={entropy:.3f})",
        )
    return canvas, {
        "width": width,
        "height": height,
        "format": source_format,
        "mode": source_mode,
        "frames": frame_count,
        "fileSizeBytes": path.stat().st_size,
        "dynamicRange": dynamic_range,
        "standardDeviation": round(standard_deviation, 4),
        "entropy": round(entropy, 4),
        "alphaExtrema": list(alpha_extrema),
    }


def _validated_verdict(output: str) -> tuple[str, str]:
    cleaned = _ANSI_ESCAPE.sub("", output).strip()
    if not cleaned:
        raise VisionUnavailableError("Magenta vision evaluator returned empty output")
    lowered = cleaned.lower()
    if any(phrase in lowered for phrase in _PLACEHOLDER_PHRASES):
        raise VisionUnavailableError("Magenta evaluator reported that it could not inspect the image")
    match = _VERDICT_LINE.fullmatch(cleaned)
    if match is None:
        raise VisionUnavailableError(
            "Magenta evaluator violated the one-line PASS:/WARN:/FAIL: output protocol"
        )
    status, reason = match.groups()
    if ";" not in reason:
        raise VisionUnavailableError(
            "Magenta evaluator did not provide two semicolon-separated image-visible details"
        )
    return status, reason.strip()


def _terminate_then_kill(process: subprocess.Popen[str]) -> tuple[str, str]:
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except OSError:
            process.terminate()
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        return process.communicate(timeout=_TERM_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            except OSError:
                process.kill()
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        return process.communicate()


def _configured_model() -> tuple[str | None, str | None, str]:
    agent_dir = Path(os.environ.get("MAGENTA_CODING_AGENT_DIR", Path.home() / ".magenta" / "agent"))
    try:
        settings = json.loads((agent_dir / "settings.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None, None, "magenta-cli/default"
    provider = settings.get("defaultProvider")
    model = settings.get("defaultModel")
    if not isinstance(provider, str) or not provider or not isinstance(model, str) or not model:
        return None, None, "magenta-cli/default"
    return provider, model, f"{provider}/{model}"


def _vision_evaluate(image_path: Path, question: str, expectation: str | None) -> tuple[str, str, str]:
    if os.environ.get("MAGENTA_VISION_EVALUATOR_DEPTH"):
        raise VisionUnavailableError("recursive Magenta vision evaluation was blocked")
    executable = shutil.which("magenta")
    if executable is None:
        raise VisionUnavailableError("Magenta CLI is not available on PATH for vision evaluation")
    user_prompt = f"Visual QC question: {question.strip()}\n"
    user_prompt += f"Expected visual result: {(expectation or 'No explicit expectation supplied.').strip()}"
    provider, model, model_label = _configured_model()
    command = [
        executable,
        "--print",
        "--no-session",
        "--no-extensions",
        "--no-skills",
        "--no-prompt-templates",
        "--no-context-files",
        "--thinking",
        "low",
        "--no-tools",
        "--no-approve",
        "--system-prompt",
        _VISION_SYSTEM_PROMPT,
    ]
    if provider is not None and model is not None:
        command.extend(["--provider", provider, "--model", model])
    command.extend([f"@{image_path.resolve()}", user_prompt])
    child_env = os.environ.copy()
    child_env["MAGENTA_VISION_EVALUATOR_DEPTH"] = "1"
    child_env["MAGENTA_HARNESS_PACKAGES"] = ""
    child_env["PI_HARNESS_PACKAGES"] = ""
    process_options: dict[str, object] = {}
    if os.name == "nt":
        process_options["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        process_options["start_new_session"] = True
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=child_env,
            **process_options,
        )
    except OSError as error:
        raise VisionUnavailableError(f"Magenta vision evaluator could not start: {error}") from error
    try:
        stdout, stderr = process.communicate(timeout=_VISION_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired as error:
        _terminate_then_kill(process)
        raise VisionUnavailableError(
            f"Magenta vision evaluator timed out after {_VISION_TIMEOUT_SECONDS}s and was terminated"
        ) from error
    if process.returncode != 0:
        diagnostic = (stderr or stdout or "no diagnostic output").strip()
        raise VisionUnavailableError(
            f"Magenta vision evaluator exited with code {process.returncode}: {diagnostic[:1000]}"
        )
    status, reason = _validated_verdict(stdout)
    return status, reason, model_label


def observe_figure(file_path: str, question: str, expectation: str | None = None) -> dict[str, object]:
    """Return a real vision-backed PASS/WARN/FAIL after deterministic preflight."""
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("file_path must be a non-empty string")
    if not isinstance(question, str) or not question.strip():
        raise ValueError("question must be a non-empty string")
    if expectation is not None and not isinstance(expectation, str):
        raise ValueError("expectation must be a string")
    path = Path(file_path).expanduser().absolute()
    checked = _decode_and_check(path, question, expectation)
    if isinstance(checked, dict):
        return checked
    preview, inspection = checked

    temporary_path: Path | None = None
    try:
        preview.thumbnail((1568, 1568), Image.Resampling.LANCZOS)
        with tempfile.NamedTemporaryFile(prefix="magenta-figure-", suffix=".png", delete=False) as handle:
            temporary_path = Path(handle.name)
        preview.save(temporary_path, format="PNG", optimize=True)
        status, reason, model = _vision_evaluate(temporary_path, question, expectation)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return {
        "success": True,
        "verdict": status,
        "analysis": reason,
        "file_path": str(path),
        "model": model,
        "reason": reason,
        "observations": [detail.strip() for detail in reason.split(";") if detail.strip()],
        "status": status,
        "filePath": str(path),
        "question": question,
        "expectation": expectation,
        "visionBacked": True,
        "inspection": inspection,
        "agent": "magenta-cli",
    }
