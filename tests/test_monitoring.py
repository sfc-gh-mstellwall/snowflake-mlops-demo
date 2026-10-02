import unittest
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from credit_default.monitoring import (
    advance_replay,
    attach_outcome,
    recommended_action,
)


class DelayedOutcomeTests(unittest.TestCase):
    def test_pending_label_is_unknown_not_negative(self) -> None:
        prediction = {
            "prediction_id": "P1",
            "ACCOUNT_ID": "ACC-1",
            "OBSERVATION_DATE": "2026-04-01",
        }
        outcomes = [
            {
                "ACCOUNT_ID": "ACC-1",
                "OBSERVATION_DATE": "2026-04-01",
                "OUTCOME_FINALITY_DATE": "2026-07-01",
                "DEFAULT_WITHIN_90D": 1,
            }
        ]
        attached = attach_outcome(prediction, outcomes, replay_date="2026-06-01")
        self.assertEqual(attached["label_status"], "pending")
        self.assertFalse(attached["treated_as_negative"])

    def test_unmatched_outcome_is_unknown(self) -> None:
        prediction = {
            "prediction_id": "P2",
            "ACCOUNT_ID": "ACC-2",
            "OBSERVATION_DATE": "2026-04-01",
        }
        attached = attach_outcome(prediction, [], replay_date="2026-09-01")
        self.assertEqual(attached["match_status"], "unmatched")
        self.assertEqual(attached["label_status"], "unknown")
        self.assertFalse(attached["treated_as_negative"])

    def test_replay_cannot_pass_generated_horizon(self) -> None:
        self.assertEqual(
            advance_replay("2026-08-01", 31, "2026-09-01"),
            "2026-09-01",
        )
        with self.assertRaisesRegex(ValueError, "generated-data horizon"):
            advance_replay("2026-09-01", 1, "2026-09-01")

    def test_action_does_not_mutate_incumbent(self) -> None:
        action = recommended_action(
            drift_detected=True,
            performance_degraded=False,
            coverage={"matched_final": 10, "pending": 2, "unmatched": 0},
        )
        self.assertEqual(action["action"], "investigate")
        self.assertFalse(action["launches_training"])
        self.assertFalse(action["changes_incumbent"])
        self.assertTrue(action["drift_is_not_performance"])


if __name__ == "__main__":
    unittest.main()
