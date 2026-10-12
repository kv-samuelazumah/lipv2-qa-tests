import sys
import unittest
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parents[1]))

import main


class FakePipeline:
    def process(self, payload, *, run_until_stage, skip_pre_agentic):
        if payload.line_item_raw == "bad row":
            raise ValueError("synthetic item failure")
        return type(
            "Result",
            (),
            {
                "as_dict": lambda self: {
                    "stage": "MATCH_OBTAINED",
                    "pre_agentic_result": None,
                    "identify_search_result": None,
                    "retrieval_result": None,
                    "evaluation_result": None,
                    "final_result": {"resolved_by": "TEST"},
                }
            },
        )()


class MainCliTests(unittest.TestCase):
    def test_run_input_json_isolates_batch_item_failures(self):
        raw_input = """
        [
          {"orgId": "org-1", "supplier": "Acme Ltd", "lineItemText": "good row"},
          {"orgId": "org-1", "supplier": "Broken Ltd", "lineItemText": "bad row"},
          {"orgId": "org-1", "supplier": "Acme Ltd", "lineItemText": "good row 2"}
        ]
        """

        results = main._run_input_json(
            FakePipeline(),
            raw_input,
            run_until_stage="full",
            skip_pre_agentic=False,
        )

        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]["result"]["final_result"]["resolved_by"], "TEST")
        self.assertEqual(results[1]["error"]["type"], "ValueError")
        self.assertEqual(results[1]["cli"]["batch_index"], 1)
        self.assertEqual(results[1]["result"], None)
        self.assertEqual(results[2]["result"]["final_result"]["resolved_by"], "TEST")


if __name__ == "__main__":
    unittest.main()
