import unittest

from z0archy_core.runtime import normalize_tokenomics_report


class RuntimeOverlayTests(unittest.TestCase):
    def test_tokenomics_tiers_remain_separate_and_sources_are_redacted(self):
        report = {
            "schema": "tokenomics.report.v1",
            "range": "7d",
            "sources": ["/home/private/events.jsonl"],
            "n_events": 10,
            "totals": {
                "baseline_tokens": 1000,
                "actual_frontier_tokens": 600,
                "measured_tokens_avoided": 300,
                "estimated_tokens_avoided": 100,
                "unknown_or_no_baseline_tokens": 50,
                "reduction_vs_baseline": 0.4,
            },
            "savings": {
                "tiers": {
                    "measured": {"events": 2, "tokens_avoided": 300},
                    "estimated": {"events": 1, "tokens_avoided": 100},
                    "unknown": {"events": 1, "tokens_observed_without_baseline": 50},
                },
                "rule": "Never collapse measured and estimated savings.",
            },
            "verified_outcomes": {
                "verified_tasks": 4,
                "tokens_per_verified_task": 150,
                "baseline_tokens_per_verified_task": 250,
                "reduction_per_verified": 0.4,
            },
            "by_mechanism": [{"mechanism": "context_compression", "tokens_avoided": 200}],
            "by_harness": [{"harness": "omp", "tokens_avoided": 200}],
            "prepare_funnel": {"consumed": 3, "latency_hidden_ms": 1200},
            "economics": {"observed_cost_usd": 1.2, "baseline_cost_usd": 2.0},
            "data_quality": {"events_with_baseline": 4},
        }
        overlay = normalize_tokenomics_report(report, source_path="/private/report.json")
        self.assertEqual(overlay["truthClass"], "observed")
        self.assertEqual(overlay["totals"]["measured_tokens_avoided"], 300)
        self.assertEqual(overlay["totals"]["estimated_tokens_avoided"], 100)
        self.assertEqual(overlay["savings"]["measured"]["tokens_avoided"], 300)
        self.assertEqual(overlay["savings"]["estimated"]["tokens_avoided"], 100)
        self.assertNotIn("/home/private/events.jsonl", str(overlay))
        self.assertTrue(overlay["provenance"]["sourcePathsRedacted"])

    def test_wrong_schema_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_tokenomics_report({"schema": "not-tokenomics"})


if __name__ == "__main__":
    unittest.main()
