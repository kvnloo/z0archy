import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "generate_ref_evidence", Path(__file__).parents[1] / "scripts" / "generate_ref_evidence.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RefEvidenceTests(unittest.TestCase):
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
