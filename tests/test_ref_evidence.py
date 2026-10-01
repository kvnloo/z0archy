import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "generate_ref_evidence", Path(__file__).parents[1] / "scripts" / "generate_ref_evidence.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RefEvidenceTests(unittest.TestCase):
    def test_bounded_targets_include_defaults_recent_and_selection_refs(self):
        index = {
            "repositories": {
                "o/a": {
                    "defaultBranch": "main",
                    "defaultHead": "0" * 40,
                    "branches": [
                        {"name": "main", "oid": "0" * 40},
                        {"name": "feat/new", "oid": "1" * 40},
                        {"name": "feat/mid", "oid": "2" * 40},
                        {"name": "feat/old", "oid": "3" * 40},
                    ],
                }
            }
        }
        targets, unresolved = mod.bounded_branch_targets(
            index,
            branch_limit_per_repo=2,
            selection_docs=[(
                "lab.json",
                {"repos": {"o/a": {"source": "github", "ref": "feat/old"}}},
            )],
        )
        self.assertFalse(unresolved)
        self.assertEqual(
            set(targets["o/a"]),
            {"0" * 40, "1" * 40, "3" * 40},
        )
        self.assertIn("feat/old", targets["o/a"]["3" * 40]["branchHints"])

    def test_unresolved_selection_ref_is_reported_not_synthesized(self):
        index = {
            "repositories": {
                "o/a": {
                    "defaultBranch": "main",
                    "defaultHead": "0" * 40,
                    "branches": [{"name": "main", "oid": "0" * 40}],
                }
            }
        }
        targets, unresolved = mod.bounded_branch_targets(
            index,
            branch_limit_per_repo=0,
            selection_docs=[(
                "lab.json",
                {"repos": {"o/a": {"source": "github", "ref": "missing"}}},
            )],
        )
        self.assertEqual(set(targets["o/a"]), {"0" * 40})
        self.assertEqual(
            unresolved,
            [{"selection": "lab.json", "repo": "o/a", "ref": "missing"}],
        )

    def test_structural_manifest_path_prefers_explicit_manifest(self):
        pack = {
            "nodes": [
                {
                    "type": "implementation_manifest",
                    "attributes": {"manifestPath": "zer0.repo.yaml"},
                }
            ]
        }
        self.assertEqual(mod.structural_manifest_path(pack), "zer0.repo.yaml")
        self.assertIsNone(mod.structural_manifest_path({"nodes": []}))

    def test_manifest_coverage_excludes_idea_stage_from_expected_gaps(self):
        index = {
            "repos": {
                "o/a": {
                    "pins": [{
                        "component": "a",
                        "ref": "a" * 40,
                        "status": "experimental",
                        "resolved": True,
                        "manifestPath": "zer0.repo.yaml",
                        "structuralManifest": True,
                    }]
                },
                "o/b": {
                    "pins": [{
                        "component": "b",
                        "ref": "b" * 40,
                        "status": "experimental",
                        "resolved": True,
                        "manifestPath": None,
                        "structuralManifest": False,
                    }]
                },
                "o/idea": {
                    "pins": [{
                        "component": "idea",
                        "ref": "c" * 40,
                        "status": "idea",
                        "resolved": True,
                        "manifestPath": None,
                        "structuralManifest": False,
                    }]
                },
            }
        }
        coverage = mod.manifest_coverage(index)
        self.assertEqual(coverage["expectedPins"], 2)
        self.assertEqual(coverage["expectedWithStructuralManifest"], 1)
        self.assertEqual([row["component"] for row in coverage["missingExpected"]], ["b"])

    def test_canonical_component_pins_are_kept_exact(self):
        graph = {
            "nodes": [
                {
                    "id": "z0://component/a",
                    "type": "component",
                    "label": "A",
                    "attributes": {
                        "component_id": "a",
                        "repo": "o/a",
                        "status": "experimental",
                        "kind": "runtime",
                        "install": {
                            "branch": "main",
                            "ref": "a" * 40,
                        },
                    },
                },
                {
                    "id": "z0://harness/h",
                    "type": "harness",
                    "label": "H",
                    "attributes": {"repo": "o/h"},
                },
            ]
        }
        pins = mod.canonical_pins(graph)
        self.assertEqual(pins["o/a"][0]["ref"], "a" * 40)
        self.assertEqual(pins["o/a"][0]["branch"], "main")
        self.assertNotIn("o/h", pins)


if __name__ == "__main__":
    unittest.main()
