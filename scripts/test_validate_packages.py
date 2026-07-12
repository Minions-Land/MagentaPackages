from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from validate_packages import (
    check_repo_hygiene,
    check_packages,
    HcpClientisportablepackageid,
    HcpClientisstrictsemver,
    HcpClientvalidatestringarray,
    HcpClientvalidatepackagemagnet,
    validate_component,
)


def HcpClientvalidmagnet(module: str, kind: str, source: str, product: str) -> str:
    return f'''export class HcpMagnet {{
    static readonly module = "{module}";
    static readonly kind = "{kind}";
    static readonly source = "{source}";
    static build(_context: unknown) {{ return new HcpMagnet(); }}
    {product}() {{ return {{ kind: "{kind}", name: "demo", content: "ok" }}; }}
}}
'''


class HcpClientpackagevalidatortests(unittest.TestCase):
    def test_portable_ids_and_strict_semver(self) -> None:
        for invalid in ("CON", "nul.txt", "COM1", "foo.", "..", "bad/name"):
            self.assertFalse(HcpClientisportablepackageid(invalid), invalid)
        self.assertTrue(HcpClientisportablepackageid("AutOmicScience"))

        for invalid in ("1.0.0-01", "1.0.0-alpha..1", "01.0.0", "v1.0.0"):
            self.assertFalse(HcpClientisstrictsemver(invalid), invalid)
        for valid in ("1.0.0", "1.0.0-alpha.1", "1.0.0-01a", "1.0.0+build.7"):
            self.assertTrue(HcpClientisstrictsemver(valid), valid)

    def test_comments_cannot_spoof_a_product_method(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Pkg"
            source = root / "skills/demo/Pkg"
            source.mkdir(parents=True)
            text = HcpClientvalidmagnet("skills/demo", "skill", "Pkg", "toResource")
            (source / "HcpMagnet.ts").write_text(
                text.replace(
                    '    toResource() { return { kind: "skill", name: "demo", content: "ok" }; }',
                    '    // toResource() { return { kind: "skill" }; }',
                ),
                encoding="utf-8",
            )
            errors: list[str] = []
            HcpClientvalidatepackagemagnet(root, "Pkg", "demo", "skill", "Pkg", source, errors)
            self.assertTrue(any("exactly toResource" in error for error in errors), errors)

    def test_rejects_implements_and_multiple_product_methods(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Pkg"
            source = root / "skills/demo/Pkg"
            source.mkdir(parents=True)
            text = HcpClientvalidmagnet("skills/demo", "skill", "Pkg", "toResource")
            text = text.replace("export class HcpMagnet {", "export class HcpMagnet implements Contract {")
            text = text.replace("    toResource()", "    toTool() { return {}; }\n    toResource()")
            (source / "HcpMagnet.ts").write_text(text, encoding="utf-8")
            errors: list[str] = []
            HcpClientvalidatepackagemagnet(root, "Pkg", "demo", "skill", "Pkg", source, errors)
            self.assertTrue(any("bare export class" in error for error in errors), errors)
            self.assertTrue(any("exactly toResource" in error for error in errors), errors)

    def test_detects_multiple_product_methods_on_one_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Pkg"
            source = root / "tools/demo/Pkg"
            source.mkdir(parents=True)
            text = HcpClientvalidmagnet("tools/demo", "tool", "Pkg", "toTool")
            text = text.replace(
                '    toTool() { return { kind: "tool", name: "demo", content: "ok" }; }',
                "    toTool() { return {}; } toResource() { return {}; }",
            )
            (source / "HcpMagnet.ts").write_text(text, encoding="utf-8")
            errors: list[str] = []
            HcpClientvalidatepackagemagnet(root, "Pkg", "demo", "tool", "Pkg", source, errors)
            self.assertTrue(any("exactly toTool" in error for error in errors), errors)

    def test_tool_requires_to_tool_not_descriptor(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Pkg"
            source = root / "tools/demo/Pkg"
            source.mkdir(parents=True)
            (source / "HcpMagnet.ts").write_text(
                HcpClientvalidmagnet("tools/demo", "tool", "Pkg", "descriptor"),
                encoding="utf-8",
            )
            errors: list[str] = []
            HcpClientvalidatepackagemagnet(root, "Pkg", "demo", "tool", "Pkg", source, errors)
            self.assertTrue(any("exactly toTool" in error for error in errors), errors)

    def test_profile_arrays_reject_wrong_types_empty_and_duplicates(self) -> None:
        errors: list[str] = []
        self.assertEqual(
            HcpClientvalidatestringarray(["science", "", "science", 1], "Pkg: profiles", errors),
            [],
        )
        self.assertTrue(any("array of names" in error for error in errors), errors)

        errors = []
        self.assertEqual(
            HcpClientvalidatestringarray(["science", "", "science"], "Pkg: profiles", errors),
            ["science"],
        )
        self.assertTrue(any("empty name" in error for error in errors), errors)
        self.assertTrue(any("duplicate name science" in error for error in errors), errors)

        errors = []
        HcpClientvalidatestringarray(
            ["base", "base"],
            "Pkg: profile science extends",
            errors,
            item_name="parent",
        )
        self.assertTrue(any("duplicate parent base" in error for error in errors), errors)

    def test_v2_rejects_unknown_component_kind(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Pkg"
            component = root / "unknown"
            component.mkdir(parents=True)
            errors: list[str] = []
            validate_component(
                root,
                "Pkg",
                {"kind": "mystery", "name": "demo", "path": "unknown"},
                set(),
                "magenta.package.v2",
                errors,
            )
            self.assertTrue(any("unsupported v2 component kind" in error for error in errors), errors)

    def test_brand_config_version_matches_package_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Pkg"
            source = root / "brand/Pkg"
            source.mkdir(parents=True)
            (source / "HcpMagnet.ts").write_text(
                HcpClientvalidmagnet("brand", "brand", "Pkg", "toResource"),
                encoding="utf-8",
            )
            (source.parent / "HcpServer.ts").write_text(
                'export class HcpServer {\n    readonly moduleName = "brand";\n}\n',
                encoding="utf-8",
            )
            (source / "brand.toml").write_text(
                'kind = "brand"\nname = "Pkg"\nconfig_path = "Pkg.brand.ts"\n',
                encoding="utf-8",
            )
            (source / "Pkg.brand.ts").write_text(
                'export const BRAND_CONFIG = { version: "0.1.0" } as const;\n',
                encoding="utf-8",
            )
            errors: list[str] = []
            validate_component(
                root,
                "Pkg",
                {
                    "kind": "brand",
                    "name": "Pkg",
                    "source": "Pkg",
                    "path": "brand/Pkg",
                },
                set(),
                "magenta.package.v2",
                errors,
                package_version="1.0.0",
            )
            self.assertTrue(any("must match package version" in error for error in errors), errors)

    def test_v2_component_identity_includes_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "Pkg"
            for source_name in ("First", "Second"):
                source = package / f"skills/demo/{source_name}"
                source.mkdir(parents=True)
                (source / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
                (source / "HcpMagnet.ts").write_text(
                    HcpClientvalidmagnet("skills/demo", "skill", source_name, "toResource"),
                    encoding="utf-8",
                )
            (package / "skills/demo/HcpServer.ts").write_text(
                'export class HcpServer {\n    readonly moduleName = "skills/demo";\n}\n',
                encoding="utf-8",
            )
            manifest = '''schema_version = "magenta.package.v2"
id = "Pkg"
name = "Pkg"
version = "1.0.0"
source = "First"
default_profiles = []

[[components]]
kind = "skill"
name = "demo"
source = "First"
path = "skills/demo/First"

[[components]]
kind = "skill"
name = "demo"
source = "Second"
path = "skills/demo/Second"
'''
            (package / "package.toml").write_text(manifest, encoding="utf-8")

            import validate_packages

            original_root = validate_packages.ROOT
            validate_packages.ROOT = root
            try:
                errors: list[str] = []
                check_packages(errors)
                self.assertFalse(any("duplicate component" in error for error in errors), errors)

                (package / "package.toml").write_text(
                    manifest.replace('source = "Second"\npath = "skills/demo/Second"', 'source = "First"\npath = "skills/demo/First"'),
                    encoding="utf-8",
                )
                errors = []
                check_packages(errors)
                self.assertTrue(any("duplicate component skill:demo:First" in error for error in errors), errors)
            finally:
                validate_packages.ROOT = original_root

    def test_v2_rejects_missing_identity_and_unselectable_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "Pkg"
            source = package / "skills/demo/Pkg"
            source.mkdir(parents=True)
            (source / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
            (source / "HcpMagnet.ts").write_text(
                HcpClientvalidmagnet("skills/demo", "skill", "Pkg", "toResource"),
                encoding="utf-8",
            )
            (source.parent / "HcpServer.ts").write_text(
                'export class HcpServer {\n    readonly moduleName = "skills/demo";\n}\n',
                encoding="utf-8",
            )
            (package / "package.toml").write_text(
                '''schema_version = "magenta.package.v2"
id = "Pkg"
name = ""
version = "1.0.0"
source = ""
default_profiles = []

[[profiles]]
name = "not selectable"
extends = []

[[components]]
kind = "skill"
name = "bad:name"
source = "bad source"
path = "skills/demo/Pkg"
''',
                encoding="utf-8",
            )

            import validate_packages

            original_root = validate_packages.ROOT
            validate_packages.ROOT = root
            try:
                errors: list[str] = []
                check_packages(errors)
            finally:
                validate_packages.ROOT = original_root

            self.assertTrue(any("non-empty name" in error for error in errors), errors)
            self.assertTrue(any("non-empty source" in error for error in errors), errors)
            self.assertTrue(any("profile name must be a portable identifier" in error for error in errors), errors)
            self.assertTrue(any("component name must be a portable identifier" in error for error in errors), errors)
            self.assertTrue(any("component source must be a portable identifier" in error for error in errors), errors)

    def test_v2_rejects_nonportable_manifest_name_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "Pkg"
            package.mkdir()
            (package / "package.toml").write_text(
                '''schema_version = "magenta.package.v2"
id = "Pkg"
name = "Display Name"
version = "1.0.0"
source = "bad:source"
default_profiles = []

[[components]]
kind = "env"
name = "pixi"
source = "Pkg"
path = "pixi.toml"
''',
                encoding="utf-8",
            )
            (package / "pixi.toml").write_text("[project]\nname = \"Pkg\"\n", encoding="utf-8")

            import validate_packages

            original_root = validate_packages.ROOT
            validate_packages.ROOT = root
            try:
                errors: list[str] = []
                check_packages(errors)
            finally:
                validate_packages.ROOT = original_root

            self.assertTrue(any("package name must be a portable identifier" in error for error in errors), errors)
            self.assertTrue(any("package source must be a portable identifier" in error for error in errors), errors)

    def test_repo_hygiene_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target.txt"
            link = root / "link.txt"
            target.write_text("target", encoding="utf-8")
            link.symlink_to(target)

            import validate_packages

            original_root = validate_packages.ROOT
            validate_packages.ROOT = root
            try:
                errors: list[str] = []
                check_repo_hygiene([link], errors)
            finally:
                validate_packages.ROOT = original_root

            self.assertEqual(
                errors,
                ["link.txt is a symlink; package releases must contain regular files only"],
            )

    def test_prompt_template_runs_the_v2_hcp_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "Pkg"
            source = root / "prompt-templates/demo/Pkg"
            source.mkdir(parents=True)
            (source / "HcpMagnet.ts").write_text(
                HcpClientvalidmagnet("prompt-templates/demo", "prompt-template", "Pkg", "toResource"),
                encoding="utf-8",
            )
            (source.parent / "HcpServer.ts").write_text(
                'export class HcpServer {\n    readonly moduleName = "prompt-templates/demo";\n}\n',
                encoding="utf-8",
            )
            errors: list[str] = []
            validate_component(
                root,
                "Pkg",
                {
                    "kind": "prompt-template",
                    "name": "demo",
                    "source": "Pkg",
                    "path": "prompt-templates/demo/Pkg",
                },
                set(),
                "magenta.package.v2",
                errors,
            )
            self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
