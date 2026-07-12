#!/usr/bin/env python3
"""Build one platform-specific, relocatable Magenta package release artifact."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import tarfile
import tempfile
import tomllib
from pathlib import Path

from validate_packages import HcpClientisportablepackageid, HcpClientisstrictsemver


ROOT = Path(__file__).resolve().parents[1]
HcpClientpackageplatforms = {
    "linux-x64",
    "macos-arm64",
    "macos-x64",
    "windows-x64",
}
HcpClientreleaseignoreddirs = {
    ".git",
    ".magenta",
    ".mypy_cache",
    ".pixi",
    ".pytest_cache",
    ".ruff_cache",
    ".tmp",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "scratch",
    "target",
    "tmp",
    "venv",
}
HcpClientnativereleases = {
    "AutOmicScience": Path("tools/bio-api/rust/target/release/aose-bio-mcp"),
}


def HcpClientreleaseignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in HcpClientreleaseignoreddirs}


def HcpClienttarfilter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    return info


def HcpClientbuildreleaseartifact(
    package: str,
    version: str,
    platform: str,
    native_binary: Path | None,
    output_dir: Path,
    repo_root: Path = ROOT,
) -> tuple[Path, Path]:
    if not HcpClientisportablepackageid(package):
        raise ValueError(f"unsafe package id: {package!r}")
    if not HcpClientisstrictsemver(version):
        raise ValueError(f"invalid semantic version: {version!r}")
    if platform not in HcpClientpackageplatforms:
        raise ValueError(f"unsupported package platform: {platform!r}")

    resolved_root = repo_root.resolve()
    package_root = (resolved_root / package).resolve()
    manifest_path = package_root / "package.toml"
    if package_root.parent != resolved_root or not manifest_path.is_file():
        raise ValueError(f"package root is missing or invalid: {package_root}")
    with manifest_path.open("rb") as handle:
        manifest = tomllib.load(handle)
    if manifest.get("id") != package:
        raise ValueError(f"package manifest id does not match release package: {manifest.get('id')!r}")
    if manifest.get("version") != version:
        raise ValueError(f"package manifest version does not match release version: {manifest.get('version')!r}")
    for source_path in package_root.rglob("*"):
        if source_path.is_symlink():
            raise ValueError(f"package releases cannot contain symlinks: {source_path}")

    native_destination = HcpClientnativereleases.get(package)
    if native_destination is not None:
        if native_binary is None or not native_binary.is_file():
            raise ValueError(f"{package} requires its native binary for {platform}")
    elif native_binary is not None:
        raise ValueError(f"{package} does not declare a native release binary")

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / f"{package}-v{version}-{platform}.tar.gz"
    checksum = output_dir / f"{artifact.name}.sha256"
    artifact.unlink(missing_ok=True)
    checksum.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix="magenta-package-release-") as temp:
        stage_root = Path(temp)
        staged_package = stage_root / package
        shutil.copytree(package_root, staged_package, ignore=HcpClientreleaseignore)

        if native_destination is not None and native_binary is not None:
            destination = staged_package / native_destination
            if platform == "windows-x64":
                destination = destination.with_suffix(".exe")
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(native_binary, destination)
            destination.chmod(0o755)

        with tarfile.open(artifact, "w:gz", format=tarfile.PAX_FORMAT) as archive:
            archive.add(staged_package, arcname=package, filter=HcpClienttarfilter)

    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    checksum.write_text(f"{digest}  {artifact.name}\n", encoding="utf-8")
    return artifact, checksum


def HcpClientparsearguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--platform", required=True, choices=sorted(HcpClientpackageplatforms))
    parser.add_argument("--native-binary", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    return parser.parse_args()


def main() -> int:
    args = HcpClientparsearguments()
    artifact, checksum = HcpClientbuildreleaseartifact(
        package=args.package,
        version=args.version,
        platform=args.platform,
        native_binary=args.native_binary,
        output_dir=args.output_dir,
    )
    print(artifact)
    print(checksum)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
