from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PRESET = ROOT / "selections" / "agentweb-emma-z0-v0.json"


class AgentWebIntegrationSnapshotTest(unittest.TestCase):
    def test_preset_is_fork_only_and_branch_scoped(self):
        doc = json.loads(PRESET.read_text(encoding="utf-8"))
        self.assertEqual(doc["version"], 1)
        self.assertEqual(
            set(doc["repos"]),
            {
                "kvnloo/z0",
                "kvnloo/aodl",
                "kvnloo/agentweb",
                "kvnloo/z0intelligence",
                "kvnloo/z0evals",
            },
        )
        for repo, spec in doc["repos"].items():
            self.assertTrue(repo.startswith("kvnloo/"))
            self.assertEqual(spec["source"], "github")
            self.assertNotIn(spec["ref"], {"main", "master", "develop"})
        self.assertEqual(doc["repos"]["kvnloo/agentweb"]["ref"], "lab/z0-agentweb-emma-v0")
        self.assertEqual(doc["repos"]["kvnloo/z0evals"]["ref"], "study/agentweb-emma-z0-v0")


if __name__ == "__main__":
    unittest.main()
