import copy
import tempfile
import unittest
from pathlib import Path

from z0archy_core.counterfactual import fork_counterfactual_world
from z0archy_core.graph import compile_graph
from z0archy_core.history import (
    export_history_snapshots,
    history_index,
    record_architecture_snapshot,
)


class CounterfactualWorldTests(unittest.TestCase):
    def graph(self, *, generated_at="2026-01-01T00:00:00Z"):
        return compile_graph(
            {"components": {
                "a": {
                    "name": "A",
                    "repo": "o/a",
                    "kind": "runtime",
                    "depends_on": [],
                    "integrates_with": [],
                    "provides": [],
                    "consumes": [],
                }
            }},
            {"interfaces": {}},
            {"profiles": {}},
            {},
            generated_at=generated_at,
        )

    def target_graph(self):
        target = copy.deepcopy(self.graph(generated_at="2026-01-01T00:01:00Z"))
        target["nodes"].append({
            "id": "z0://derived/counterfactual",
            "type": "derived",
            "label": "Alternative implementation",
            "attributes": {"choice": "feature-branch"},
            "provenance": [{
                "class": "derived",
                "source": "test",
                "ref": "feature",
                "path": "selection",
                "field": "choice",
            }],
        })
        target["nodes"].sort(key=lambda node: node["id"])
        target["snapshot"] = {
            "generatedAt": "2026-01-01T00:01:00Z",
            "truthClass": "derived",
            "source": {"repo": "z0archy", "ref": "virtual"},
            "selection": {
                "version": 1,
                "repos": {"o/a": {"source": "github", "ref": "feature"}},
            },
        }
        return target

    def test_counterfactual_is_activegraph_fork_with_snapshot_and_diff(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "history.sqlite3"
            first = record_architecture_snapshot(self.graph(), db)
            result = fork_counterfactual_world(
                self.target_graph(),
                db,
                parent_run_id=first["runId"],
                label="feature world",
            )
            self.assertTrue(result["created"])
            self.assertEqual(result["parentRunId"], first["runId"])
            self.assertGreater(result["sharedEvents"], 0)
            self.assertGreater(result["forkOnlyEvents"], 0)
            self.assertGreater(result["divergentObjects"], 0)

            same = fork_counterfactual_world(
                self.target_graph(),
                db,
                parent_run_id=first["runId"],
                label="feature world",
            )
            self.assertFalse(same["created"])
            self.assertEqual(same["runId"], result["runId"])

            index = history_index(db)
            kinds = [entry["kind"] for entry in index["entries"]]
            self.assertEqual(kinds.count("canonical"), 1)
            self.assertEqual(kinds.count("counterfactual"), 1)
            fork_entry = next(
                entry for entry in index["entries"]
                if entry["kind"] == "counterfactual"
            )
            self.assertEqual(fork_entry["parentRunId"], first["runId"])
            self.assertTrue(fork_entry["viewKey"].startswith("cf-"))
            self.assertTrue(fork_entry["hasSnapshot"])
            self.assertEqual(
                fork_entry["selection"]["repos"]["o/a"]["ref"],
                "feature",
            )

            out = Path(td) / "history"
            export_history_snapshots(db, out)
            self.assertTrue((out / f"{fork_entry['viewKey']}.json").is_file())

    def test_new_canonical_state_does_not_descend_from_counterfactual(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "history.sqlite3"
            first = record_architecture_snapshot(self.graph(), db)
            fork = fork_counterfactual_world(
                self.target_graph(),
                db,
                parent_run_id=first["runId"],
            )
            self.assertTrue(fork["created"])

            later = self.graph(generated_at="2026-01-02T00:00:00Z")
            later["nodes"].append({
                "id": "z0://declared/new",
                "type": "derived",
                "label": "Canonical next",
                "attributes": {"value": 2},
                "provenance": [{
                    "class": "declared",
                    "source": "z0",
                    "ref": "main",
                    "path": "registry/test.yaml",
                    "field": "new",
                }],
            })
            later["nodes"].sort(key=lambda node: node["id"])
            recorded = record_architecture_snapshot(later, db)
            self.assertEqual(recorded["previousRunId"], first["runId"])


if __name__ == "__main__":
    unittest.main()
