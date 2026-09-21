import subprocess
import tempfile
import unittest
from pathlib import Path

from z0archy_core.local_git import build_local_snapshot, normalize_remote


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


if __name__ == "__main__":
    unittest.main()
