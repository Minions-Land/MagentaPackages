#!/usr/bin/env python3
"""Build one platform-specific, relocatable Magenta package release artifact."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import os
import stat
import subprocess
import tarfile
import tempfile
import tomllib
import uuid
from pathlib import Path

from validate_packages import HcpClientisportablepackageid, HcpClientisstrictsemver


ROOT = Path(__file__).resolve().parents[1]
HcpClientpackageplatforms = {
    "linux-x64",
    "macos-arm64",
    "macos-x64",
    "windows-x64",
}
HcpClientreleasesensitivefilenames = {
    ".env",
    ".envrc",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "credentials.json",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "id_rsa",
    "service-account.json",
    "service_account.json",
}
HcpClientreleasesensitivesuffixes = {".key", ".p12", ".pem", ".pfx"}
HcpClientreleaseenvtemplates = {".env.example", ".env.sample", ".env.template"}
HcpClientnativereleases = {
    "AutOmicScience": Path("tools/bio-api/rust/target/release/aose-bio-mcp"),
}


def HcpClienttarfilter(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = 0
    info.gid = 0
    info.uname = ""
    info.gname = ""
    info.mtime = 0
    if info.isdir():
        info.mode = 0o755
    elif info.isfile():
        info.mode = 0o755 if info.mode & 0o111 else 0o644
    return info


def HcpClientsha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


HcpClientFileSignature = tuple[int, int, int, int, int, int]


def HcpClientfilesignature(file_stat: os.stat_result) -> HcpClientFileSignature:
    return (
        file_stat.st_dev,
        file_stat.st_ino,
        file_stat.st_size,
        file_stat.st_mtime_ns,
        file_stat.st_ctime_ns,
        stat.S_IMODE(file_stat.st_mode),
    )


def HcpClientassertregularfile(path: Path, label: str) -> os.stat_result:
    file_stat = os.lstat(path)
    if not stat.S_ISREG(file_stat.st_mode):
        raise ValueError(f"{label} must be a regular file: {path}")
    return file_stat


def HcpClientopensafefile(path: Path, label: str) -> tuple[int, os.stat_result]:
    path_stat = HcpClientassertregularfile(path, label)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ValueError(f"Unable to open {label}: {path}: {error}") from error
    opened_stat = os.fstat(descriptor)
    if HcpClientfilesignature(opened_stat) != HcpClientfilesignature(path_stat):
        os.close(descriptor)
        raise ValueError(f"{label} changed while it was opened: {path}")
    return descriptor, opened_stat


def HcpClientsnapshotregularfile(path: Path, label: str) -> tuple[HcpClientFileSignature, str]:
    descriptor, opened_stat = HcpClientopensafefile(path, label)
    digest = hashlib.sha256()
    with os.fdopen(descriptor, "rb", closefd=True) as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
        final_descriptor_stat = os.fstat(source.fileno())
    if HcpClientfilesignature(final_descriptor_stat) != HcpClientfilesignature(opened_stat):
        raise ValueError(f"{label} changed while it was read: {path}")
    final_path_stat = HcpClientassertregularfile(path, label)
    if HcpClientfilesignature(final_path_stat) != HcpClientfilesignature(final_descriptor_stat):
        raise ValueError(f"{label} was replaced while it was read: {path}")
    return HcpClientfilesignature(final_descriptor_stat), digest.hexdigest()


def HcpClientcopyregularfile(
    source: Path,
    destination: Path,
    expected_signature: HcpClientFileSignature,
    expected_digest: str,
    label: str,
    mode: int,
) -> None:
    descriptor, opened_stat = HcpClientopensafefile(source, label)
    if HcpClientfilesignature(opened_stat) != expected_signature:
        os.close(descriptor)
        raise ValueError(f"{label} changed before it was copied: {source}")
    digest = hashlib.sha256()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with destination.open("xb") as output:
            with os.fdopen(descriptor, "rb", closefd=True) as source_stream:
                for chunk in iter(lambda: source_stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                    output.write(chunk)
                final_descriptor_stat = os.fstat(source_stream.fileno())
        if HcpClientfilesignature(final_descriptor_stat) != expected_signature or digest.hexdigest() != expected_digest:
            raise ValueError(f"{label} changed while it was copied: {source}")
        final_path_stat = HcpClientassertregularfile(source, label)
        if HcpClientfilesignature(final_path_stat) != expected_signature:
            raise ValueError(f"{label} was replaced while it was copied: {source}")
        os.chmod(destination, mode)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        destination.unlink(missing_ok=True)
        raise


def HcpClientgittrackedentries(repo_root: Path, package: str) -> list[tuple[str, int, str]]:
    package_prefix = f"{package}/"
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--stage", "--full-name", "-z", "--", package_prefix],
            cwd=repo_root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        raise ValueError("Package release builds require a Git worktree") from error

    entries: list[tuple[str, int, str]] = []
    for record in result.stdout.split(b"\0"):
        if not record:
            continue
        metadata, raw_path = record.split(b"\t", 1)
        mode_text, object_id, stage_text = metadata.decode("ascii").split(" ")
        path = os.fsdecode(raw_path)
        path_parts = Path(path).parts
        if not path.startswith(package_prefix) or Path(path).is_absolute() or ".." in path_parts:
            raise ValueError(f"Git tracked package path escapes its package root: {path}")
        mode = int(mode_text, 8)
        if mode not in (0o100644, 0o100755) or stage_text != "0":
            raise ValueError(f"Git tracked package path is not a regular file or symlink: {path}")
        entries.append((path, mode, object_id))
    if not entries:
        raise ValueError(f"Package has no Git tracked files: {package}")
    return entries


def HcpClientassertsamegitentries(repo_root: Path, package: str, expected: list[tuple[str, int, str]]) -> None:
    if HcpClientgittrackedentries(repo_root, package) != expected:
        raise ValueError("Git tracked package file set changed during artifact construction")


def HcpClientcopytrackedpackage(
    repo_root: Path,
    package: str,
    package_root: Path,
    staged_package: Path,
    expected_entries: list[tuple[str, int, str]] | None = None,
) -> list[str]:
    entries = HcpClientgittrackedentries(repo_root, package)
    if expected_entries is not None and entries != expected_entries:
        raise ValueError("Git tracked package file set changed before artifact construction")
    expected_paths: list[str] = []
    for relative_name, mode, _object_id in entries:
        relative_path = Path(relative_name)
        name = relative_path.name.lower()
        if (
            name in HcpClientreleasesensitivefilenames
            or (name.startswith(".env.") and name not in HcpClientreleaseenvtemplates)
            or relative_path.suffix.lower() in HcpClientreleasesensitivesuffixes
        ):
            raise ValueError(f"package release contains a sensitive file (tracked): {relative_name}")
        source = repo_root / relative_path
        current = package_root
        for component in relative_path.relative_to(package).parts:
            current /= component
            if current.is_symlink():
                raise ValueError(f"Git tracked package path cannot contain a symlink: {relative_name}")
        signature, digest = HcpClientsnapshotregularfile(source, f"Git tracked package file {relative_name}")
        destination = staged_package / relative_path.relative_to(package)
        HcpClientcopyregularfile(
            source,
            destination,
            signature,
            digest,
            f"Git tracked package file {relative_name}",
            0o755 if mode == 0o100755 else 0o644,
        )
        expected_paths.append(destination.relative_to(staged_package).as_posix())
    HcpClientassertsamegitentries(repo_root, package, entries)
    return expected_paths


def HcpClientassertstagedpackage(staged_package: Path, expected_paths: list[str]) -> None:
    actual_paths: list[str] = []
    for path in staged_package.rglob("*"):
        if path.is_dir() and not path.is_symlink():
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"Staged package contains a non-regular path: {path}")
        actual_paths.append(path.relative_to(staged_package).as_posix())
    if sorted(actual_paths) != sorted(expected_paths):
        raise ValueError("Staged package contains files outside the Git tracked release allowlist")


def HcpClientfsyncdirectory(path: Path) -> None:
    if os.name == "nt":
        return
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    directory_fd = os.open(path, flags)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)


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
    package_root_path = resolved_root / package
    package_root = package_root_path.resolve()
    manifest_path = package_root / "package.toml"
    if package_root.parent != resolved_root or package_root_path.is_symlink() or not package_root.is_dir():
        raise ValueError(f"package root is missing or invalid: {package_root}")
    tracked_entries = HcpClientgittrackedentries(resolved_root, package)
    tracked_names = {entry[0] for entry in tracked_entries}
    if f"{package}/package.toml" not in tracked_names:
        raise ValueError(f"package manifest is not a Git tracked regular file: {manifest_path}")
    with manifest_path.open("rb") as handle:
        manifest = tomllib.load(handle)
    if manifest.get("id") != package:
        raise ValueError(f"package manifest id does not match release package: {manifest.get('id')!r}")
    if manifest.get("version") != version:
        raise ValueError(f"package manifest version does not match release version: {manifest.get('version')!r}")
    native_destination = HcpClientnativereleases.get(package)
    if native_destination is not None:
        if native_binary is None:
            raise ValueError(f"{package} requires its native binary for {platform}")
    elif native_binary is not None:
        raise ValueError(f"{package} does not declare a native release binary")

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact = output_dir / f"{package}-v{version}-{platform}.tar.gz"
    checksum = output_dir / f"{artifact.name}.sha256"

    # Build beside the destination and commit the complete artifact/checksum
    # pair only after both files are durable. A failed build must not erase the
    # last known-good release output used by a local publisher or retry.
    with tempfile.TemporaryDirectory(prefix=".magenta-package-release-", dir=output_dir) as temp:
        stage_root = Path(temp)
        staged_package = stage_root / package
        staged_artifact = stage_root / artifact.name
        staged_checksum = stage_root / checksum.name
        tracked_paths = HcpClientcopytrackedpackage(
            resolved_root,
            package,
            package_root,
            staged_package,
            tracked_entries,
        )

        if native_destination is not None and native_binary is not None:
            destination = staged_package / native_destination
            if platform == "windows-x64":
                destination = destination.with_suffix(".exe")
            native_signature, native_digest = HcpClientsnapshotregularfile(native_binary, "Native release binary")
            HcpClientcopyregularfile(
                native_binary,
                destination,
                native_signature,
                native_digest,
                "Native release binary",
                0o755,
            )
            destination_name = destination.relative_to(staged_package).as_posix()
            if destination_name not in tracked_paths:
                tracked_paths.append(destination_name)

        HcpClientassertstagedpackage(staged_package, tracked_paths)

        with staged_artifact.open("wb") as compressed_output:
            with gzip.GzipFile(filename="", mode="wb", fileobj=compressed_output, mtime=0) as gzip_output:
                with tarfile.open(fileobj=gzip_output, mode="w", format=tarfile.PAX_FORMAT) as archive:
                    archive.add(staged_package, arcname=package, filter=HcpClienttarfilter)

        digest = HcpClientsha256(staged_artifact)
        # Release checksums are consumed on every host. Force LF even when the
        # artifact is built by a Windows runner so `shasum -c` does not retain a
        # trailing carriage return in the referenced filename.
        staged_checksum.write_text(f"{digest}  {artifact.name}\n", encoding="utf-8", newline="\n")
        if b"\r" in staged_checksum.read_bytes():
            raise RuntimeError(f"release checksum must use LF line endings: {staged_checksum}")
        with staged_artifact.open("rb") as handle:
            os.fsync(handle.fileno())
        with staged_checksum.open("rb") as handle:
            os.fsync(handle.fileno())

        rollback_id = uuid.uuid4().hex
        backup_artifact = output_dir / f".{artifact.name}.{rollback_id}.rollback"
        backup_checksum = output_dir / f".{checksum.name}.{rollback_id}.rollback"
        artifact_backed_up = False
        checksum_backed_up = False
        artifact_installed = False
        checksum_installed = False
        try:
            if os.path.lexists(artifact):
                os.replace(artifact, backup_artifact)
                artifact_backed_up = True
            if os.path.lexists(checksum):
                os.replace(checksum, backup_checksum)
                checksum_backed_up = True
            os.replace(staged_artifact, artifact)
            artifact_installed = True
            os.replace(staged_checksum, checksum)
            checksum_installed = True
            HcpClientfsyncdirectory(output_dir)
        except Exception as activation_error:
            rollback_errors: list[str] = []
            if artifact_installed and os.path.lexists(artifact):
                try:
                    artifact.unlink()
                except OSError as error:
                    rollback_errors.append(f"remove new artifact: {error}")
            if checksum_installed and os.path.lexists(checksum):
                try:
                    checksum.unlink()
                except OSError as error:
                    rollback_errors.append(f"remove new checksum: {error}")
            if artifact_backed_up and os.path.lexists(backup_artifact):
                try:
                    os.replace(backup_artifact, artifact)
                except OSError as error:
                    rollback_errors.append(f"restore previous artifact: {error}")
            if checksum_backed_up and os.path.lexists(backup_checksum):
                try:
                    os.replace(backup_checksum, checksum)
                except OSError as error:
                    rollback_errors.append(f"restore previous checksum: {error}")
            try:
                HcpClientfsyncdirectory(output_dir)
            except OSError as error:
                rollback_errors.append(f"persist rollback: {error}")
            if rollback_errors:
                preserved = [str(path) for path in [backup_artifact, backup_checksum] if os.path.lexists(path)]
                recovery_note = f" Previous files remain at {', '.join(preserved)}." if preserved else ""
                raise RuntimeError(
                    f"Package artifact activation failed ({activation_error}) and rollback was incomplete: "
                    f"{'; '.join(rollback_errors)}.{recovery_note}"
                ) from activation_error
            raise
        backup_artifact.unlink(missing_ok=True)
        backup_checksum.unlink(missing_ok=True)
        HcpClientfsyncdirectory(output_dir)
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
