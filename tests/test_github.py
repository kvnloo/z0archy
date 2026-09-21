import unittest

from z0archy_core.github import fetch_branch_index


class FakeClient:
    def __init__(self):
        self.calls = []
    def query(self, query, variables):
        self.calls.append((query, variables))
        data = {"rateLimit": {"cost": 1, "remaining": 4999, "resetAt": "later"}}
        i = 0
        while f"owner{i}" in variables:
            repo = f"{variables[f'owner{i}']}/{variables[f'name{i}']}"
            data[f"r{i}"] = {
                "nameWithOwner": repo,
                "defaultBranchRef": {"name": "main", "target": {"oid": "abc", "committedDate": "2026-01-01T00:00:00Z"}},
                "refs": {
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                    "nodes": [
                        {"name": "main", "target": {"oid": "abc", "committedDate": "2026-01-01T00:00:00Z"}},
                        {"name": "feat/x", "target": {"oid": "def", "committedDate": "2026-01-02T00:00:00Z"}},
                    ],
                },
            }
            i += 1
        return {"data": data}


class GithubTests(unittest.TestCase):
    def test_repos_are_batched(self):
        client = FakeClient()
        out = fetch_branch_index(["o/a", "o/b"], client)
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(out["o/a"]["defaultBranch"], "main")
        self.assertEqual([b["name"] for b in out["o/b"]["branches"]], ["main", "feat/x"])


if __name__ == "__main__":
    unittest.main()
