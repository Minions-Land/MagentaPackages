from __future__ import annotations

import hashlib
import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from build_release_artifact import HcpClientbuildreleaseartifact as HcpClientbuildreleaseartifact_impl


def HcpClientinitializegit(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)


def HcpClientbuildreleaseartifact(*args: object, **kwargs: object):
    repo_root = kwargs.get("repo_root")
    if repo_root is None and len(args) >= 6:
        repo_root = args[5]
    if not isinstance(repo_root, Path):
        raise AssertionError("test build helper requires a temporary Git root")
    HcpClientinitializegit(repo_root)
    return HcpClientbuildreleaseartifact_impl(*args, **kwargs)


class BuildReleaseArtifactTests(unittest.TestCase):
    def test_build_is_reproducible_across_source_timestamp_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "Biomni"
            package.mkdir()
            manifest = package / "package.toml"
            manifest.write_text(
                'schema_version = "magenta.package.v2"\nid = "Biomni"\nversion = "1.0.0"\n',
                encoding="utf-8",
            )
            payload = package / "payload.txt"
            payload.write_text("stable bytes\n", encoding="utf-8")
            output = root / "out"

            first_artifact, first_checksum = HcpClientbuildreleaseartifact(
                "Biomni", "1.0.0", "linux-x64", None, output, root
            )
            first_bytes = first_artifact.read_bytes()
            first_checksum_bytes = first_checksum.read_bytes()
            os.utime(manifest, (1_700_000_000, 1_700_000_000))
            os.utime(payload, (1_800_000_000, 1_800_000_000))

            second_artifact, second_checksum = HcpClientbuildreleaseartifact(
                "Biomni", "1.0.0", "linux-x64", None, output, root
            )
            self.assertEqual(second_artifact.read_bytes(), first_bytes)
            self.assertEqual(second_checksum.read_bytes(), first_checksum_bytes)
            with tarfile.open(second_artifact, "r:gz") as archive:
                self.assertTrue(all(member.mtime == 0 for member in archive.getmembers()))

    def test_embeds_only_the_requested_native_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "AutOmicScience"
            rust = package / "tools/bio-api/rust"
            (rust / "target/debug").mkdir(parents=True)
            (rust / "target/debug/garbage").write_text("debug", encoding="utf-8")
            (package / ".gitignore").write_text("target/\n", encoding="utf-8")
            (package / "package.toml").write_text(
                'schema_version = "magenta.package.v2"\nid = "AutOmicScience"\nversion = "1.0.0"\n',
                encoding="utf-8",
            )
            binary = root / "aose-bio-mcp"
            binary.write_bytes(b"native-binary")

            artifact, checksum = HcpClientbuildreleaseartifact(
                "AutOmicScience",
                "1.0.0",
                "linux-x64",
                binary,
                root / "out",
                root,
            )

            self.assertTrue(checksum.is_file())
            checksum_bytes = checksum.read_bytes()
            self.assertNotIn(b"\r", checksum_bytes)
            digest, name = checksum_bytes.decode("utf-8").strip().split("  ", 1)
            self.assertEqual(name, artifact.name)
            self.assertEqual(digest, hashlib.sha256(artifact.read_bytes()).hexdigest())
            with tarfile.open(artifact, "r:gz") as archive:
                names = set(archive.getnames())
                native_name = "AutOmicScience/tools/bio-api/rust/target/release/aose-bio-mcp"
                self.assertIn(native_name, names)
                self.assertNotIn("AutOmicScience/tools/bio-api/rust/target/debug/garbage", names)
                native = archive.getmember(native_name)
                self.assertEqual(native.mode & 0o111, 0o111)

    def test_windows_native_binary_has_exe_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "AutOmicScience"
            package.mkdir()
            (package / "package.toml").write_text(
                'id = "AutOmicScience"\nversion = "1.0.0"\n',
                encoding="utf-8",
            )
            binary = root / "aose-bio-mcp.exe"
            binary.write_bytes(b"windows-native")

            artifact, _checksum = HcpClientbuildreleaseartifact(
                "AutOmicScience",
                "1.0.0",
                "windows-x64",
                binary,
                root / "out",
                root,
            )

            with tarfile.open(artifact, "r:gz") as archive:
                names = set(archive.getnames())
            self.assertIn(
                "AutOmicScience/tools/bio-api/rust/target/release/aose-bio-mcp.exe",
                names,
            )
            self.assertNotIn(
                "AutOmicScience/tools/bio-api/rust/target/release/aose-bio-mcp",
                names,
            )

    def test_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "Biomni"
            package.mkdir()
            (package / "package.toml").write_text('id = "Biomni"\nversion = "1.0.0"\n', encoding="utf-8")
            (package / "link").symlink_to(package / "package.toml")

            with self.assertRaisesRegex(ValueError, "regular file or symlink"):
                HcpClientbuildreleaseartifact(
                    "Biomni",
                    "1.0.0",
                    "linux-x64",
                    None,
                    root / "out",
                    root,
                )

    def test_rejects_sensitive_files_but_allows_env_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "Biomni"
            package.mkdir()
            (package / "package.toml").write_text(
                'id = "Biomni"\nversion = "1.0.0"\n',
                encoding="utf-8",
            )
            (package / ".env.example").write_text("TOKEN=replace-me\n", encoding="utf-8")
            secret = package / ".env"
            secret.write_text("TOKEN=do-not-publish\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "sensitive file"):
                HcpClientbuildreleaseartifact(
                    "Biomni",
                    "1.0.0",
                    "linux-x64",
                    None,
                    root / "out",
                    root,
                )

            secret.unlink()
            artifact, _checksum = HcpClientbuildreleaseartifact(
                "Biomni",
                "1.0.0",
                "linux-x64",
                None,
                root / "out",
                root,
            )
            with tarfile.open(artifact, "r:gz") as archive:
                self.assertIn("Biomni/.env.example", archive.getnames())

    def test_requires_the_native_binary_for_automic_science(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "AutOmicScience"
            package.mkdir()
            (package / "package.toml").write_text(
                'id = "AutOmicScience"\nversion = "1.0.0"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "requires its native binary"):
                HcpClientbuildreleaseartifact(
                    "AutOmicScience",
                    "1.0.0",
                    "windows-x64",
                    None,
                    root / "out",
                    root,
                )

    def test_rejects_manifest_identity_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "Biomni"
            package.mkdir()
            (package / "package.toml").write_text(
                'id = "Other"\nversion = "2.0.0"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "manifest id does not match"):
                HcpClientbuildreleaseartifact(
                    "Biomni",
                    "1.0.0",
                    "linux-x64",
                    None,
                    root / "out",
                    root,
                )

            (package / "package.toml").write_text(
                'id = "Biomni"\nversion = "2.0.0"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "manifest version does not match"):
                HcpClientbuildreleaseartifact(
                    "Biomni",
                    "1.0.0",
                    "linux-x64",
                    None,
                    root / "out",
                    root,
                )

    def test_preserves_previous_artifact_pair_when_rebuild_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "Biomni"
            package.mkdir()
            (package / "package.toml").write_text('id = "Biomni"\nversion = "1.0.0"\n', encoding="utf-8")
            output = root / "out"
            output.mkdir()
            artifact = output / "Biomni-v1.0.0-linux-x64.tar.gz"
            checksum = output / f"{artifact.name}.sha256"
            artifact.write_bytes(b"previous artifact")
            checksum.write_text("previous checksum\n", encoding="utf-8")

            import build_release_artifact

            with patch.object(build_release_artifact.tarfile, "open", side_effect=RuntimeError("tar failed")):
                with self.assertRaisesRegex(RuntimeError, "tar failed"):
                    HcpClientbuildreleaseartifact("Biomni", "1.0.0", "linux-x64", None, output, root)

            self.assertEqual(artifact.read_bytes(), b"previous artifact")
            self.assertEqual(checksum.read_text(encoding="utf-8"), "previous checksum\n")

    def test_preserves_a_recovery_copy_when_rollback_restore_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "Biomni"
            package.mkdir()
            (package / "package.toml").write_text('id = "Biomni"\nversion = "1.0.0"\n', encoding="utf-8")
            output = root / "out"
            output.mkdir()
            artifact = output / "Biomni-v1.0.0-linux-x64.tar.gz"
            checksum = output / f"{artifact.name}.sha256"
            artifact.write_bytes(b"previous artifact")
            checksum.write_text("previous checksum\n", encoding="utf-8")

            import build_release_artifact

            real_replace = build_release_artifact.os.replace

            def fail_activation_and_artifact_restore(source: object, destination: object) -> None:
                source_path = Path(source)
                destination_path = Path(destination)
                if destination_path == checksum and not source_path.name.endswith(".rollback"):
                    raise OSError("checksum activation failed")
                if destination_path == artifact and source_path.name.endswith(".rollback"):
                    raise OSError("artifact restore failed")
                real_replace(source, destination)

            with patch.object(build_release_artifact.os, "replace", side_effect=fail_activation_and_artifact_restore):
                with self.assertRaisesRegex(RuntimeError, "rollback was incomplete"):
                    HcpClientbuildreleaseartifact("Biomni", "1.0.0", "linux-x64", None, output, root)

            recovery_files = list(output.glob(f".{artifact.name}.*.rollback"))
            self.assertEqual(len(recovery_files), 1)
            self.assertEqual(recovery_files[0].read_bytes(), b"previous artifact")
            self.assertEqual(checksum.read_text(encoding="utf-8"), "previous checksum\n")

    def test_directory_fsync_failure_rolls_back_the_previous_pair(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "Biomni"
            package.mkdir()
            (package / "package.toml").write_text(
                'schema_version = "magenta.package.v2"\nid = "Biomni"\nversion = "1.0.0"\n',
                encoding="utf-8",
            )
            output = root / "out"
            output.mkdir()
            artifact = output / "Biomni-v1.0.0-linux-x64.tar.gz"
            checksum = output / f"{artifact.name}.sha256"
            artifact.write_bytes(b"previous artifact")
            checksum.write_text("previous checksum\n", encoding="utf-8")

            import build_release_artifact

            calls = 0

            def fail_first_directory_sync(_path: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise OSError("simulated directory fsync EIO")

            with patch.object(
                build_release_artifact,
                "HcpClientfsyncdirectory",
                side_effect=fail_first_directory_sync,
            ):
                with self.assertRaisesRegex(OSError, "simulated directory fsync EIO"):
                    HcpClientbuildreleaseartifact("Biomni", "1.0.0", "linux-x64", None, output, root)

            self.assertEqual(artifact.read_bytes(), b"previous artifact")
            self.assertEqual(checksum.read_text(encoding="utf-8"), "previous checksum\n")

    def test_excludes_local_and_generated_directories(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "Biomni"
            package.mkdir()
            (package / "package.toml").write_text(
                'id = "Biomni"\nversion = "1.0.0"\n',
                encoding="utf-8",
            )
            for directory in (".git", ".magenta", ".tmp", "tmp", "dist", "scratch"):
                path = package / directory
                path.mkdir()
                (path / "secret.txt").write_text("do not publish", encoding="utf-8")
            (package / ".gitignore").write_text(
                "\n".join(f"{directory}/" for directory in (".git", ".magenta", ".tmp", "tmp", "dist", "scratch"))
                + "\n",
                encoding="utf-8",
            )

            artifact, _checksum = HcpClientbuildreleaseartifact(
                "Biomni",
                "1.0.0",
                "linux-x64",
                None,
                root / "out",
                root,
            )

            with tarfile.open(artifact, "r:gz") as archive:
                names = archive.getnames()
            for directory in (".git", ".magenta", ".tmp", "tmp", "dist", "scratch"):
                self.assertFalse(any(name.startswith(f"Biomni/{directory}/") for name in names), directory)

    def test_packages_only_git_tracked_files_and_excludes_ignored_phi_and_local_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "Cardiomni"
            package.mkdir()
            (package / "package.toml").write_text('id = "Cardiomni"\nversion = "0.1.0"\n', encoding="utf-8")
            (package / "tracked.md").write_text("tracked release content\n", encoding="utf-8")
            (package / ".gitignore").write_text(".example/\n.claude/\n", encoding="utf-8")
            (package / ".example/case").mkdir(parents=True)
            (package / ".example/case/Patient-Name.dcm").write_bytes(b"patient imaging bytes")
            (package / ".claude").mkdir()
            (package / ".claude/settings.local.json").write_text('{"token":"must not ship"}\n', encoding="utf-8")

            artifact, _checksum = HcpClientbuildreleaseartifact(
                "Cardiomni", "0.1.0", "linux-x64", None, root / "out", root
            )
            with tarfile.open(artifact, "r:gz") as archive:
                names = archive.getnames()
            self.assertIn("Cardiomni/tracked.md", names)
            self.assertNotIn("Cardiomni/.example/case/Patient-Name.dcm", names)
            self.assertNotIn("Cardiomni/.claude/settings.local.json", names)

    def test_rejects_a_tracked_file_that_changes_during_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "Biomni"
            package.mkdir()
            (package / "package.toml").write_text('id = "Biomni"\nversion = "1.0.0"\n', encoding="utf-8")
            payload = package / "payload.txt"
            payload.write_text("before\n", encoding="utf-8")
            HcpClientinitializegit(root)

            import build_release_artifact

            real_copy = build_release_artifact.HcpClientcopyregularfile
            changed = False

            def race_copy(source: Path, *args: object, **kwargs: object) -> None:
                nonlocal changed
                if source.resolve() == payload.resolve() and not changed:
                    changed = True
                    payload.write_text("after\n", encoding="utf-8")
                real_copy(source, *args, **kwargs)

            with patch.object(build_release_artifact, "HcpClientcopyregularfile", side_effect=race_copy):
                with self.assertRaisesRegex(ValueError, "changed"):
                    HcpClientbuildreleaseartifact(
                        "Biomni", "1.0.0", "linux-x64", None, root / "out", root
                    )


if __name__ == "__main__":
    unittest.main()
