import copy
import tempfile
import unittest
from pathlib import Path

from z0archy_core.graph import compile_graph
from z0archy_core.history import (
    export_history_snapshots,
    history_index,
    record_architecture_snapshot,
)


class HistoryTests(unittest.TestCase):
    def graph(self):
        return compile_graph(
            {"components": {
                "a": {
                    "name": "A", "repo": "o/a", "kind": "runtime",
                    "depends_on": [], "integrates_with": [],
                    "provides": [], "consumes": [],
                }
            }},
            {"interfaces": {}},
            {"profiles": {}},
            {},
            generated_at="2026-01-01T00:00:00Z",
        )

    def test_content_addressed_runs_dedupe_and_link_history(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "history.sqlite3"
            first = record_architecture_snapshot(self.graph(), db)
            same = record_architecture_snapshot(self.graph(), db)
            self.assertTrue(first["created"])
            self.assertFalse(same["created"])
            self.assertEqual(first["runId"], same["runId"])

            changed_graph = copy.deepcopy(self.graph())
            changed_graph["nodes"].append({
                "id": "z0://derived/example",
                "type": "derived",
                "label": "Example",
                "attributes": {"value": 1},
                "provenance": [{
                    "class": "derived", "source": "test", "ref": "fixture",
                    "path": "test", "field": "example",
                }],
            })
            changed = record_architecture_snapshot(changed_graph, db)
            self.assertTrue(changed["created"])
            self.assertEqual(changed["previousRunId"], first["runId"])

            index = history_index(db)
            self.assertEqual(len(index["entries"]), 2)
            self.assertEqual(index["entries"][1]["parentRunId"], first["runId"])

            out = Path(td) / "history"
            exported = export_history_snapshots(db, out)
            self.assertEqual(len(exported["entries"]), 2)
            self.assertTrue((out / f"{first['hash']}.json").is_file())
            self.assertTrue((out / f"{changed['hash']}.json").is_file())


if __name__ == "__main__":
    unittest.main()
