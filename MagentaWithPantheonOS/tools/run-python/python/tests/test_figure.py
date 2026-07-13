from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from magenta_with_pantheon_runtime import figure
from magenta_with_pantheon_runtime.figure import VisionUnavailableError, observe_figure


def make_figure(path: Path) -> None:
    image = Image.new("RGB", (256, 160), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 30, 110, 130), fill="navy")
    draw.ellipse((140, 35, 225, 125), fill="orange")
    image.save(path)


def test_blank_image_fails_before_vision(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "blank.png"
    Image.new("RGB", (100, 100), "white").save(path)
    monkeypatch.setattr(figure, "_vision_evaluate", lambda *_args: pytest.fail("vision should not run"))
    result = observe_figure(str(path), "Is there a visible plot?")
    assert result["status"] == "FAIL"
    assert result["visionBacked"] is False
    assert result["verdict"] == "FAIL"
    assert "uniform" in str(result["analysis"])
    assert result["file_path"] == str(path)
    assert result["model"] == "pillow-preflight"


def test_real_vision_result_is_forwarded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "figure.png"
    make_figure(path)
    monkeypatch.setattr(
        figure,
        "_vision_evaluate",
        lambda preview, question, expectation: (
            "PASS",
            "A navy rectangle appears on the left; an orange circle appears on the right.",
            "test-provider/test-vision-model",
        ),
    )
    result = observe_figure(str(path), "Are two shapes separated?", "Two separated shapes")
    assert result["status"] == "PASS"
    assert result["visionBacked"] is True
    assert result["verdict"] == "PASS"
    assert "navy rectangle" in result["analysis"]
    assert result["file_path"] == str(path)
    assert result["model"] == "test-provider/test-vision-model"
    assert result["inspection"]["width"] == 256


def test_vision_unavailability_is_not_downgraded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "figure.png"
    make_figure(path)

    def unavailable(*_args):
        raise VisionUnavailableError("no vision model")

    monkeypatch.setattr(figure, "_vision_evaluate", unavailable)
    with pytest.raises(VisionUnavailableError, match="no vision model"):
        observe_figure(str(path), "Can this be assessed?")


@pytest.mark.parametrize(
    "output",
    [
        "",
        "not a verdict",
        "PASS: Only one image detail is present",
        "WARN: I cannot view the image attachment; no pixels were available.",
        "PASS: a navy rectangle is left; an orange circle is right.\nextra protocol",
    ],
)
def test_evaluator_rejects_empty_malformed_and_placeholder_output(output: str) -> None:
    with pytest.raises(VisionUnavailableError):
        figure._validated_verdict(output)


def test_evaluator_accepts_grounded_schema() -> None:
    status, reason = figure._validated_verdict(
        "WARN: Three labeled curves are present; two labels overlap at upper right."
    )
    assert status == "WARN"
    assert "overlap" in reason


def test_oversized_image_is_rejected_before_pixel_allocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "oversized.png"
    path.write_bytes(b"image fixture")

    class OversizedImage:
        size = (5000, 4000)

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def verify(self):
            pytest.fail("oversized image must fail before verify/decode")

    monkeypatch.setattr(figure.Image, "open", lambda _path: OversizedImage())
    result = figure._decode_and_check(path, "Can this be inspected?", None)
    assert isinstance(result, dict)
    assert result["verdict"] == "FAIL"
    assert "pixel safety limit" in result["analysis"]


def test_configured_model_reports_and_pins_provenance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "settings.json").write_text(
        '{"defaultProvider":"anthropic","defaultModel":"vision-model"}', encoding="utf-8"
    )
    monkeypatch.setenv("MAGENTA_CODING_AGENT_DIR", str(tmp_path))
    assert figure._configured_model() == ("anthropic", "vision-model", "anthropic/vision-model")


def test_vision_cli_uses_direct_absolute_image_argv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    image_path = tmp_path / "figure.png"
    make_figure(image_path)
    captured = {}

    class FakeProcess:
        returncode = 0

        def communicate(self, timeout=None):
            captured["timeout"] = timeout
            return (
                "PASS: a navy rectangle is visible on the left; an orange circle is visible on the right.\n",
                "",
            )

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.delenv("MAGENTA_VISION_EVALUATOR_DEPTH", raising=False)
    monkeypatch.setattr(figure.shutil, "which", lambda name: "/usr/local/bin/magenta")
    monkeypatch.setattr(
        figure,
        "_configured_model",
        lambda: ("anthropic", "vision-model", "anthropic/vision-model"),
    )
    monkeypatch.setattr(figure.subprocess, "Popen", fake_popen)
    status, _reason, model = figure._vision_evaluate(image_path, "Are shapes separated?", "two shapes")
    command = captured["command"]
    assert status == "PASS"
    assert model == "anthropic/vision-model"
    assert "--no-tools" in command
    assert "--tools" not in command
    assert command[command.index("--thinking") + 1] == "low"
    assert command[command.index("--provider") + 1] == "anthropic"
    assert command[command.index("--model") + 1] == "vision-model"
    assert f"@{image_path.resolve()}" in command
    assert captured["timeout"] == 60
    assert isinstance(command, list)
    assert "shell" not in captured["kwargs"]
    if figure.os.name == "nt":
        assert "creationflags" in captured["kwargs"]
    else:
        assert captured["kwargs"]["start_new_session"] is True


def test_windows_timeout_termination_always_targets_process_tree(monkeypatch: pytest.MonkeyPatch) -> None:
    commands = []

    class FakeProcess:
        pid = 1234

        def communicate(self, timeout=None):
            return ("", "")

        def terminate(self):
            pytest.fail("taskkill should be used for the Windows process tree")

    def fake_run(command, **_kwargs):
        commands.append(command)

    monkeypatch.setattr(figure.os, "name", "nt")
    monkeypatch.setattr(figure.subprocess, "run", fake_run)
    figure._terminate_then_kill(FakeProcess())
    assert commands == [["taskkill", "/PID", "1234", "/T"]]
