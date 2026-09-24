"""
Labeled Grounding Benchmark Evaluation Suite for KruschLaw
Evaluates two-pass assertion verifier against golden labeled propositions.
Headline Metric: false_support_rate MUST BE 0.0%.
"""

import json
import os
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.backend.rag import (
    verify_assertion_grounding,
    enforce_generation_citation_constraints,
)


class TestLabeledGroundingEval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        golden_path = Path(__file__).resolve().parent.parent.parent / "data" / "eval" / "labeled_grounding_golden.json"
        with open(golden_path, "r", encoding="utf-8") as f:
            cls.dataset = json.load(f)

    def test_golden_eval_zero_false_support(self):
        """
        Headline Evaluation Metric:
        False Support Rate must be strictly 0.0% across all negative / failure cases.
        """
        total = len(self.dataset)
        correct = 0
        false_support_count = 0
        non_supported_count = 0

        for case in self.dataset:
            claim = case["claim"]
            laws = case["retrieved_laws"]
            matter_facts = case.get("matter_facts")
            expected_status = case["expected_status"]
            expected_verdict = case["expected_verdict"]
            expected_refused = case["expected_refused"]

            is_grounded, claims, notice, stats = verify_assertion_grounding(
                analysis_text=claim,
                laws=laws,
                matter_facts=matter_facts
            )

            self.assertEqual(len(claims), 1, f"Case {case['id']} did not yield exactly 1 claim record.")
            record = claims[0]

            # Track false supports
            if expected_status != "supported":
                non_supported_count += 1
                if record["status"] == "supported" or not record["refused"]:
                    false_support_count += 1

            # Assertions for DTO contract
            self.assertIn("quote_span", record)
            self.assertIn("entailment_score", record)
            self.assertIn("human_review_flag", record)

            # Verification of classification
            self.assertEqual(
                record["status"],
                expected_status,
                f"Case {case['id']} expected status '{expected_status}', got '{record['status']}' (reason: {record['reason']})"
            )
            self.assertEqual(
                record["verdict"],
                expected_verdict,
                f"Case {case['id']} expected verdict '{expected_verdict}', got '{record['verdict']}'"
            )
            self.assertEqual(
                record["refused"],
                expected_refused,
                f"Case {case['id']} expected refused={expected_refused}, got {record['refused']}"
            )

            if expected_status == "abstain":
                self.assertTrue(record["human_review_flag"], f"Case {case['id']} must set human_review_flag=True for abstain.")

            correct += 1

        accuracy = (correct / total) * 100.0
        false_support_rate = (false_support_count / non_supported_count) * 100.0 if non_supported_count > 0 else 0.0

        print(f"\n[EVAL RESULTS] Total Cases: {total} | Accuracy: {accuracy:.1f}% | False Support Rate: {false_support_rate:.2f}%")
        self.assertEqual(false_support_rate, 0.0, "Critical Failure: False support rate must be 0.0% in legal software.")
        self.assertEqual(accuracy, 100.0, "All golden labeled benchmark propositions must classify accurately.")

    def test_enforce_generation_citation_constraints(self):
        """
        Generation constraints must strip unretrieved bare section numbers while preserving authorized ones.
        """
        authorized_laws = [
            {
                "section": "Section 8.22.030",
                "title": "Oakland Notice Requirements",
                "content": "Landlords must provide notice."
            }
        ]

        # Case 1: Text with unauthorized bare section
        raw_draft = (
            "Pursuant to OMC Section 8.22.030, notice is required. "
            "However, pursuant to OMC Section 999.99 and Cal. Civ. Code Section 4040.1, penalties apply."
        )
        constrained = enforce_generation_citation_constraints(raw_draft, authorized_laws)

        # Section 8.22.030 must remain intact
        self.assertIn("OMC Section 8.22.030", constrained)
        # Unauthorized sections must be stripped with banner
        self.assertIn("[UNAUTHORIZED CITATION STRIPPED: OMC Section 999.99]", constrained)
        self.assertIn("[UNAUTHORIZED CITATION STRIPPED: Cal. Civ. Code Section 4040.1]", constrained)

        # Case 2: Verify that stripped text fails Pass A mechanical check
        is_g, claims, notice, stats = verify_assertion_grounding(constrained, authorized_laws)
        stripped_records = [c for c in claims if "999.99" in c.get("reason", "") or "4040.1" in c.get("reason", "")]
        for sr in stripped_records:
            self.assertEqual(sr["status"], "invented_citation")
            self.assertTrue(sr["refused"])


if __name__ == "__main__":
    unittest.main()
