import json
import tempfile
import unittest
from pathlib import Path

from z0archy_core.graph import zid
from z0archy_core.runtime_evidence import (
    compile_runtime_evidence,
    runtime_input_fingerprint,
)


class RuntimeEvidenceTests(unittest.TestCase):
    def test_tokenomics_trace_is_aggregated_without_sensitive_payloads(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "events.jsonl"
            events = [
                {
                    "schema": "tokenomics.event.v0",
                    "kind": "llm",
                    "name": "omp.root",
                    "trace_id": "a" * 32,
                    "span_id": "1" * 16,
                    "event_id": "evt-1",
                    "harness": "omp",
                    "role": "root",
                    "status": "ok",
                    "ts": 10.0,
                    "started_at": 10.0,
                    "ended_at": 11.0,
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "attribution": "incremental",
                        "source": "provider",
                    },
                    "economics": {"cost_usd": 0.12, "measured_tokens_avoided": 400},
                    "context": {"spilled_bytes": 4096, "retrieval_calls": 2},
                    "extra": {
                        "prompt": "PRIVATE PROMPT",
                        "tool_result": "PRIVATE RESULT",
                    },
                },
                {
                    "schema": "tokenomics.event.v0",
                    "kind": "verification",
                    "name": "pytest",
                    "trace_id": "a" * 32,
                    "span_id": "2" * 16,
                    "parent_span_id": "1" * 16,
                    "event_id": "evt-2",
                    "harness": "omp",
                    "role": "verifier",
                    "status": "ok",
                    "ts": 12.0,
                    "outcome": {
                        "verified_success": True,
                        "verification_source": "pytest",
                    },
                },
            ]
            path.write_text("\n".join(json.dumps(row) for row in events) + "\n")

            graph = compile_runtime_evidence(tokenomics_paths=[path], generated_at="fixed")
            trace = next(node for node in graph["nodes"] if node["type"] == "runtime_trace")
            self.assertEqual(trace["attributes"]["usage"]["input_tokens"], 100)
            self.assertEqual(trace["attributes"]["usage"]["output_tokens"], 20)
            self.assertEqual(trace["attributes"]["context"]["spilled_bytes"], 4096)
            self.assertEqual(trace["attributes"]["costUsd"], 0.12)
            self.assertTrue(trace["attributes"]["verifiedSuccess"])

            serialized = json.dumps(graph)
            self.assertNotIn("PRIVATE PROMPT", serialized)
            self.assertNotIn("PRIVATE RESULT", serialized)

            event = next(
                node for node in graph["nodes"]
                if node["type"] == "runtime_event" and node["attributes"]["event_id"] == "evt-1"
            )
            self.assertEqual(event["provenance"][0]["class"], "observed")
            self.assertTrue(any(
                edge["target"] == zid("harness", "omp")
                for edge in graph["edges"]
            ))

    def test_agenttrace_report_keeps_only_metadata_fields(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "agenttrace.json"
            path.write_text(json.dumps({
                "recent_sessions": [{
                    "id": "session-1",
                    "source": "hermes",
                    "model": "model-x",
                    "health_score": 91,
                    "duration_ms": 1200,
                    "cost_usd": 0.5,
                    "prompt": "DO NOT COPY ME",
                    "content": "DO NOT COPY THIS EITHER",
                }]
            }))
            graph = compile_runtime_evidence(agenttrace_paths=[path], generated_at="fixed")
            session = next(node for node in graph["nodes"] if node["type"] == "runtime_session")
            self.assertEqual(session["attributes"]["health_score"], 91)
            serialized = json.dumps(graph)
            self.assertNotIn("DO NOT COPY ME", serialized)
            self.assertNotIn("DO NOT COPY THIS EITHER", serialized)
            self.assertTrue(any(
                edge["target"] == zid("harness", "hermes")
                for edge in graph["edges"]
            ))

    def test_aodl_intent_and_observed_topology_remain_distinct(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "world.json"
            topology = {
                "nodes": [
                    {
                        "id": "executor",
                        "kind": "executor",
                        "harness": "omp",
                        "ports": [],
                        "capabilities": ["code"],
                    },
                    {
                        "id": "verifier",
                        "kind": "verifier",
                        "ports": [],
                        "capabilities": ["test"],
                    },
                ],
                "edges": [{
                    "id": "verify",
                    "relation": "verification",
                    "from": "executor",
                    "to": "verifier",
                    "fromPort": "out",
                    "toPort": "in",
                    "delivery": {"order": "ordered", "idempotent": True},
                    "authority": {"grant": [], "delegationDepth": 0},
                    "provenance": {"sourceHash": "b" * 64},
                }],
            }
            path.write_text(json.dumps({
                "specVersion": "0.2",
                "graphId": "demo",
                "revision": 4,
                "intentGraph": topology,
                "observedGraph": {
                    "nodes": topology["nodes"][:1],
                    "edges": [],
                },
                "policies": {},
                "constraints": {"budgets": {}, "termination": {}},
                "provenance": {"sourceHash": "a" * 64},
                "plan": {
                    "status": "compiled",
                    "harness": "omp",
                    "prompt": "PRIVATE PLAN BODY",
                },
            }))

            graph = compile_runtime_evidence(aodl_paths=[path], generated_at="fixed")
            types = {node["type"] for node in graph["nodes"]}
            self.assertIn("runtime_intent_topology", types)
            self.assertIn("runtime_observed_topology", types)
            self.assertIn("runtime_plan", types)
            relations = {edge["type"] for edge in graph["edges"]}
            self.assertIn("compiled_to", relations)
            self.assertIn("observed_as", relations)
            self.assertNotIn("PRIVATE PLAN BODY", json.dumps(graph))

    def test_runtime_input_fingerprint_tracks_file_changes(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "events.jsonl"
            path.write_text("one\n")
            first = runtime_input_fingerprint([path])
            second = runtime_input_fingerprint([path])
            self.assertEqual(first, second)
            path.write_text("two-two\n")
            third = runtime_input_fingerprint([path])
            self.assertNotEqual(first, third)


if __name__ == "__main__":
    unittest.main()
