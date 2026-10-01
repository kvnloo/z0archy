from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "selections" / "unified-memory-ledger-optmem-v0.json"
CONTRACT = ROOT / "selections" / "unified-memory-contract-v1.json"


class UnifiedMemorySnapshotTests(unittest.TestCase):
    def test_ledger_snapshot_keeps_one_z0int_branch_and_supporting_repos(self):
        doc = json.loads(LEDGER.read_text(encoding="utf-8"))
        self.assertEqual(doc["version"], 1)
        self.assertEqual(
            doc["repos"]["kvnloo/z0intelligence"]["ref"],
            "feat/memory-optmem-tree-v0",
        )
        self.assertEqual(doc["repos"]["kvnloo/OptMem"]["ref"], "main")
        self.assertEqual(doc["repos"]["kvnloo/hermes-lcm"]["ref"], "main")
        self.assertEqual(doc["repos"]["kvnloo/z0evals"]["ref"], "main")

    def test_contract_snapshot_stays_separate_from_ledger_stack(self):
        doc = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(
            set(doc["repos"]),
            {"kvnloo/z0intelligence", "kvnloo/z0evals"},
        )
        self.assertEqual(
            doc["repos"]["kvnloo/z0intelligence"]["ref"],
            "feat/memory-contract-v1-66-preview",
        )
        self.assertNotIn("kvnloo/OptMem", doc["repos"])

    def test_selected_z0int_refs_are_non_default_lab_refs(self):
        for path in (LEDGER, CONTRACT):
            doc = json.loads(path.read_text(encoding="utf-8"))
            ref = doc["repos"]["kvnloo/z0intelligence"]["ref"]
            self.assertNotIn(ref, {"main", "master", "preview"})


if __name__ == "__main__":
    unittest.main()
