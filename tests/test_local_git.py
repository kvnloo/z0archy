import subprocess
import tempfile
import unittest
from pathlib import Path

from z0archy_core.introspection import inspect_repository
from z0archy_core.local_git import build_local_snapshot, normalize_remote
from z0archy_core.sources import LocalGitSource


class LocalGitTests(unittest.TestCase):
    def test_normalize_remote(self):
        self.assertEqual(normalize_remote("git@github.com:kvnloo/z0.git"), "kvnloo/z0")
        self.assertEqual(normalize_remote("https://github.com/kvnloo/z0.git"), "kvnloo/z0")
        self.assertIsNone(normalize_remote("https://example.com/a/b.git"))

    def test_worktrees_are_distinct_checkouts_of_one_repo(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td) / "repo"
            wt = Path(td) / "wt"
            subprocess.run(["git", "init", "-q", "-b", "main", str(base)], check=True)
            subprocess.run(["git", "-C", str(base), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(base), "config", "user.name", "Test"], check=True)
            (base / "a.txt").write_text("a\n")
            subprocess.run(["git", "-C", str(base), "add", "a.txt"], check=True)
            subprocess.run(["git", "-C", str(base), "commit", "-qm", "init"], check=True)
            subprocess.run(["git", "-C", str(base), "remote", "add", "origin", "git@github.com:kvnloo/demo.git"], check=True)
            subprocess.run(["git", "-C", str(base), "worktree", "add", "-qb", "feature", str(wt)], check=True)
            data = build_local_snapshot([td])
            self.assertIn("kvnloo/demo", data["repositories"])
            paths = {w["path"] for w in data["repositories"]["kvnloo/demo"]["worktrees"]}
            self.assertEqual(paths, {str(base.resolve()), str(wt.resolve())})


    def test_worktree_introspection_reads_dirty_files(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            (repo / "README.md").write_text("# committed\n")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "init"], check=True)
            (repo / "README.md").write_text("# dirty architecture evidence\n")

            source = LocalGitSource({"kvnloo/demo": repo})
            pack = inspect_repository(
                source,
                "kvnloo/demo",
                "WORKTREE",
                resolved_ref="worktree-fixture",
            )
            artifact = next(
                n for n in pack["nodes"]
                if n["type"] == "source_artifact" and n["attributes"]["path"] == "README.md"
            )
            self.assertGreater(artifact["attributes"]["bytes"], len("# committed\n"))
            self.assertEqual(artifact["provenance"][0]["class"], "implemented")


if __name__ == "__main__":
    unittest.main()
