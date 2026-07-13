from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
import tomllib
import types
import unittest
from pathlib import Path
from unittest.mock import patch


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SKILLS_ROOT = PACKAGE_ROOT / "skills"
LEGACY_TERMS = (
    "call_agent",
    "file_manager",
    "notify_user",
    "observe_images",
    "integrated_notebook",
    "integrated notebook",
    "python_interpreter",
    "manage_kernel",
    "WebFetch",
    ".pantheon",
)
GENE_PANEL_REQUIRED_TOOLS = {
    "run_python",
    "create_notebook",
    "add_cell",
    "observe_figure",
    "read",
    "write",
    "edit",
    "find",
    "grep",
    "sub_agent",
}


def load_manifest() -> dict:
    with (PACKAGE_ROOT / "package.toml").open("rb") as handle:
        return tomllib.load(handle)


def load_gene_panel_helpers():
    helper_path = (
        SKILLS_ROOT
        / "gene-panel"
        / "PantheonOS"
        / "assets"
        / "references"
        / "scripts"
        / "gene_panel_helpers.py"
    )
    spec = importlib.util.spec_from_file_location("pantheonos_gene_panel_helpers", helper_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {helper_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PackageContractTests(unittest.TestCase):
    def test_manifest_declares_the_11_hcp_isomorphic_skills(self) -> None:
        manifest = load_manifest()
        self.assertEqual(manifest["schema_version"], "magenta.package.v2")
        self.assertEqual(manifest["id"], "PantheonOS")
        self.assertEqual(manifest["source"], "PantheonOS")

        components = manifest["components"]
        skill_components = [component for component in components if component["kind"] == "skill"]
        self.assertEqual(len(skill_components), 11)
        self.assertEqual(len({component["name"] for component in skill_components}), 11)
        self.assertIn(
            {
                "kind": "runtime-tests",
                "name": "pantheonos_package_tests",
                "source": "PantheonOS",
                "path": "tests",
            },
            components,
        )

        for component in skill_components:
            with self.subTest(skill=component["name"]):
                self.assertEqual(component["kind"], "skill")
                self.assertEqual(component["source"], "PantheonOS")
                source_dir = PACKAGE_ROOT / component["path"]
                module_dir = source_dir.parent
                self.assertTrue((source_dir / "SKILL.md").is_file())
                self.assertTrue((source_dir / "HcpMagnet.ts").is_file())
                self.assertTrue((module_dir / "HcpServer.ts").is_file())

    def test_all_markdown_links_are_package_local_and_resolve(self) -> None:
        link_pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
        package_root = PACKAGE_ROOT.resolve()
        failures: list[str] = []

        for markdown_path in PACKAGE_ROOT.rglob("*.md"):
            text = markdown_path.read_text(encoding="utf-8")
            prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
            prose = re.sub(r"`[^`\n]*`", "", prose)
            for raw_target in link_pattern.findall(prose):
                target = raw_target.strip().split("#", 1)[0]
                if not target or "://" in target or target.startswith("mailto:"):
                    continue
                resolved = (markdown_path.parent / target).resolve()
                if not resolved.is_relative_to(package_root):
                    failures.append(f"{markdown_path.relative_to(PACKAGE_ROOT)} escapes package: {raw_target}")
                elif not resolved.exists():
                    failures.append(f"{markdown_path.relative_to(PACKAGE_ROOT)} missing: {raw_target}")

        self.assertEqual(failures, [], "\n".join(failures))

    def test_legacy_pantheonos_interfaces_are_not_referenced(self) -> None:
        failures: list[str] = []
        for markdown_path in PACKAGE_ROOT.rglob("*.md"):
            text = markdown_path.read_text(encoding="utf-8")
            for term in LEGACY_TERMS:
                if term in text:
                    failures.append(f"{markdown_path.relative_to(PACKAGE_ROOT)}: {term}")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_gene_panel_declares_the_frozen_companion_tool_contract(self) -> None:
        skill_path = SKILLS_ROOT / "gene-panel" / "PantheonOS" / "SKILL.md"
        text = skill_path.read_text(encoding="utf-8")
        match = re.search(r"^requiredTools:\n((?:^- [^\n]+\n?)+)", text, flags=re.MULTILINE)
        self.assertIsNotNone(match)
        tools = {line.removeprefix("- ") for line in match.group(1).splitlines()}
        self.assertEqual(tools, GENE_PANEL_REQUIRED_TOOLS)

    def test_nf_core_declares_native_web_tools(self) -> None:
        skill_path = SKILLS_ROOT / "nf-core" / "PantheonOS" / "SKILL.md"
        text = skill_path.read_text(encoding="utf-8")
        match = re.search(r"^requiredTools:\n((?:^- [^\n]+\n?)+)", text, flags=re.MULTILINE)
        self.assertIsNotNone(match)
        tools = {line.removeprefix("- ") for line in match.group(1).splitlines()}
        self.assertEqual(tools, {"web-search", "web-fetch"})

    def test_gene_panel_records_visual_and_delegation_boundaries(self) -> None:
        skill_path = SKILLS_ROOT / "gene-panel" / "PantheonOS" / "SKILL.md"
        text = skill_path.read_text(encoding="utf-8")
        self.assertIn('packages: ["PantheonOS", "MagentaWithPantheonOS"]', text)
        self.assertIn("`teammate_agent` currently has no `packages` parameter", text)
        self.assertIn("real vision-backed evaluation", text)
        self.assertIn("Accept the visual gate only on `PASS`", text)
        self.assertIn("current vision-capable model receives real ImageContent", text)
        self.assertIn("Use `show` only when a host preview is useful", text)
        self.assertNotIn("deterministic QC only", text)
        self.assertNotIn("Never cite `observe_figure` alone as semantic evidence", text)

    def test_readme_requires_both_harness_packages(self) -> None:
        readme = (PACKAGE_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("--harness-package PantheonOS", readme)
        self.assertIn("--harness-package MagentaWithPantheonOS", readme)
        self.assertIn("github:Minions-Land/Magenta-CLI/PantheonOS@0.1.0", readme)
        self.assertIn("github:Minions-Land/Magenta-CLI/MagentaWithPantheonOS@0.1.0", readme)


class GenePanelRuntimeGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.helpers = load_gene_panel_helpers()

    def estimate(self, *, n_cells: int, n_genes: int, **kwargs):
        fake_adata = types.SimpleNamespace(n_obs=n_cells, n_vars=n_genes)
        fake_anndata = types.SimpleNamespace(read_h5ad=lambda _path, backed: fake_adata)
        with tempfile.NamedTemporaryFile(suffix=".h5ad") as handle:
            with patch.dict(sys.modules, {"anndata": fake_anndata}):
                return self.helpers.estimate_spapros_runtime(handle.name, **kwargs)

    def test_runtime_gate_classifies_fast_slow_and_very_slow(self) -> None:
        fast = self.estimate(n_cells=10_000, n_genes=3_000)
        slow = self.estimate(n_cells=20_000, n_genes=3_000)
        very_slow = self.estimate(n_cells=100_000, n_genes=3_000)

        self.assertEqual(fast["severity"], "fast")
        self.assertEqual(slow["severity"], "slow")
        self.assertEqual(very_slow["severity"], "very_slow")
        self.assertEqual(fast["estimated_minutes"], 4.0)

    def test_runtime_gate_honors_custom_thresholds(self) -> None:
        estimate = self.estimate(
            n_cells=20_000,
            n_genes=3_000,
            warning_minutes=10.0,
            skip_minutes=20.0,
        )
        self.assertEqual(estimate["severity"], "fast")


if __name__ == "__main__":
    unittest.main()
