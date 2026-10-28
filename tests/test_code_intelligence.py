import unittest

from z0archy_core.code_intelligence import normalize_code_intelligence_snapshot


class CodeIntelligenceNormalizationTests(unittest.TestCase):
    def snapshot(self):
        return {
            "version": 1,
            "provider": "fixture-index",
            "sourceRevision": "abc123",
            "inputFingerprint": "sha256:fixture",
            "confidence": "structural",
            "symbols": [
                {
                    "id": "demo.foo",
                    "name": "foo",
                    "kind": "function",
                    "path": "src/demo.py",
                    "line": 3,
                    "endLine": 5,
                    "signature": "def foo():",
                },
                {
                    "id": "demo.bar",
                    "name": "bar",
                    "kind": "function",
                    "path": "src/demo.py",
                    "line": 8,
                    "endLine": 10,
                },
            ],
            "relations": [
                {
                    "kind": "calls",
                    "source": "demo.bar",
                    "target": "demo.foo",
                    "path": "src/demo.py",
                    "line": 9,
                },
                {
                    "kind": "verified_by",
                    "source": "demo.foo",
                    "target": "test_demo.test_foo",
                    "path": "tests/test_demo.py",
                    "line": 4,
                },
            ],
            "testSymbols": [
                {
                    "id": "test_demo.test_foo",
                    "name": "test_foo",
                    "kind": "test",
                    "path": "tests/test_demo.py",
                    "line": 3,
                    "endLine": 5,
                }
            ],
        }

    def test_normalization_is_deterministic_and_source_backed(self):
        first = normalize_code_intelligence_snapshot(
            self.snapshot(), repo="kvnloo/demo", resolved_ref="abc123"
        )
        second = normalize_code_intelligence_snapshot(
            self.snapshot(), repo="kvnloo/demo", resolved_ref="abc123"
        )

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "current")
        self.assertEqual(len(first["nodes"]), 3)
        self.assertEqual(len(first["edges"]), 2)

        foo = next(node for node in first["nodes"] if node["label"] == "foo")
        self.assertEqual(foo["type"], "code_symbol")
        self.assertEqual(foo["attributes"]["provider"], "fixture-index")
        self.assertEqual(foo["attributes"]["inputFingerprint"], "sha256:fixture")
        self.assertEqual(foo["attributes"]["confidence"], "structural")
        self.assertEqual(foo["attributes"]["externalId"], "demo.foo")
        self.assertEqual(foo["provenance"][0]["source"], "kvnloo/demo")
        self.assertEqual(foo["provenance"][0]["ref"], "abc123")
        self.assertEqual(foo["provenance"][0]["path"], "src/demo.py")
        self.assertEqual(foo["provenance"][0]["provider"], "fixture-index")
        self.assertEqual(foo["provenance"][0]["confidence"], "structural")

    def test_stale_source_revision_is_not_materialized(self):
        snapshot = self.snapshot()
        snapshot["sourceRevision"] = "old456"

        result = normalize_code_intelligence_snapshot(
            snapshot, repo="kvnloo/demo", resolved_ref="abc123"
        )

        self.assertEqual(result["status"], "stale")
        self.assertEqual(result["nodes"], [])
        self.assertEqual(result["edges"], [])
        self.assertEqual(result["diagnostics"][0]["code"], "source_revision_mismatch")

    def test_unknown_relation_endpoint_fails_open_without_inventing_edge(self):
        snapshot = self.snapshot()
        snapshot["relations"].append(
            {
                "kind": "references",
                "source": "demo.bar",
                "target": "demo.missing",
                "path": "src/demo.py",
                "line": 9,
            }
        )

        result = normalize_code_intelligence_snapshot(
            snapshot, repo="kvnloo/demo", resolved_ref="abc123"
        )

        self.assertEqual(len(result["edges"]), 2)
        unresolved = [
            row for row in result["diagnostics"]
            if row["code"] == "unresolved_relation"
        ]
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0]["target"], "demo.missing")

    def test_unsupported_relation_kind_is_not_materialized(self):
        snapshot = self.snapshot()
        snapshot["relations"].append(
            {
                "kind": "provider_magic",
                "source": "demo.bar",
                "target": "demo.foo",
            }
        )

        result = normalize_code_intelligence_snapshot(
            snapshot, repo="kvnloo/demo", resolved_ref="abc123"
        )

        self.assertEqual(len(result["edges"]), 2)
        self.assertIn(
            "unsupported_relation_kind",
            {row["code"] for row in result["diagnostics"]},
        )

    def test_provider_fingerprint_and_confidence_are_required(self):
        missing_provider = self.snapshot()
        missing_provider["provider"] = ""
        with self.assertRaisesRegex(ValueError, "provider"):
            normalize_code_intelligence_snapshot(
                missing_provider, repo="kvnloo/demo", resolved_ref="abc123"
            )

        missing_confidence = self.snapshot()
        missing_confidence.pop("confidence")
        with self.assertRaisesRegex(ValueError, "confidence"):
            normalize_code_intelligence_snapshot(
                missing_confidence, repo="kvnloo/demo", resolved_ref="abc123"
            )

        missing_fingerprint = self.snapshot()
        missing_fingerprint.pop("inputFingerprint")
        with self.assertRaisesRegex(ValueError, "inputFingerprint"):
            normalize_code_intelligence_snapshot(
                missing_fingerprint, repo="kvnloo/demo", resolved_ref="abc123"
            )


if __name__ == "__main__":
    unittest.main()
