from __future__ import annotations

import hashlib
import tarfile
import tempfile
import unittest
from pathlib import Path

from build_release_artifact import HcpClientbuildreleaseartifact


class BuildReleaseArtifactTests(unittest.TestCase):
    def test_embeds_only_the_requested_native_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "AutOmicScience"
            rust = package / "tools/bio-api/rust"
            (rust / "target/debug").mkdir(parents=True)
            (rust / "target/debug/garbage").write_text("debug", encoding="utf-8")
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

            with self.assertRaisesRegex(ValueError, "cannot contain symlinks"):
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


if __name__ == "__main__":
    unittest.main()
