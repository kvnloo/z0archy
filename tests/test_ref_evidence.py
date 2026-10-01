import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "generate_ref_evidence", Path(__file__).parents[1] / "scripts" / "generate_ref_evidence.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RefEvidenceTests(unittest.TestCase):
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
