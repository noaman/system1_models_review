import unittest

from playground.normalize import normalize_response
from playground.questions import ChoiceOption, QuestionInput, RunInput, prepare_run
from playground.scoring import build_report


KNOWN = {"typesafe", "laya"}


def question(**overrides):
    base = {
        "id": "department",
        "type": "choice",
        "instructions": "Which department should handle this?",
        "choice_options": [
            ChoiceOption(key="billing", description="Payments"),
            ChoiceOption(key="care", description=""),
        ],
    }
    base.update(overrides)
    return QuestionInput(**base)


def run_input(**overrides):
    base = {
        "mode": "single",
        "model_ids": ["typesafe"],
        "state_format": "text",
        "state": "We were charged twice.",
        "questions": [question()],
    }
    base.update(overrides)
    return RunInput(**base)


class PrepareRunTests(unittest.TestCase):
    def test_choice_wire_and_blank_description(self):
        prepared = prepare_run(run_input(), KNOWN)
        wire = prepared.wire_questions()["department"]
        self.assertEqual(wire["criteria"]["billing"], "Payments")
        self.assertIsNone(wire["criteria"]["care"])
        self.assertEqual(prepared.state, "We were charged twice.")

    def test_json_state(self):
        prepared = prepare_run(run_input(state_format="json", state='{"ticket": "refund"}'), KNOWN)
        self.assertEqual(prepared.state, {"ticket": "refund"})

    def test_single_mode_rejects_two_models(self):
        with self.assertRaises(ValueError):
            prepare_run(run_input(model_ids=["typesafe", "laya"]), KNOWN)

    def test_compare_accepts_one_or_more(self):
        prepared = prepare_run(run_input(mode="compare", model_ids=["laya"]), KNOWN)
        self.assertEqual(prepared.model_ids, ["laya"])

    def test_score_expected_must_sit_on_the_scale(self):
        payload = run_input(questions=[question(
            id="urgency",
            type="score",
            instructions="How urgent is this?",
            choice_options=[],
            score_levels=["Low", "High"],
            expected=4,
        )])
        with self.assertRaises(ValueError):
            prepare_run(payload, KNOWN)

    def test_noul_expected_yes(self):
        payload = run_input(questions=[question(
            id="churn_risk",
            type="noul",
            instructions="Does the user threaten to cancel?",
            choice_options=[],
            noul_true="They will leave.",
            expected="yes",
        )])
        prepared = prepare_run(payload, KNOWN)
        self.assertIs(prepared.questions[0]["expected"], True)
        self.assertEqual(prepared.questions[0]["wire"]["criteria"]["true"], "They will leave.")


class ReportTests(unittest.TestCase):
    def test_normalize_choice_and_score(self):
        questions = [
            {"id": "department", "type": "choice", "criteria": [
                {"key": "billing", "label": "Payments"},
                {"key": "care", "label": "Care"},
            ]},
            {"id": "urgency", "type": "score", "criteria": [
                {"key": "0", "label": "Low"},
                {"key": "1", "label": "High"},
            ]},
        ]
        raw = {
            "model": "jev-latest",
            "usage": {"input_tokens": 12, "output_tokens": 3},
            "answers": {
                "department": {"choice": "billing", "confidence": 0.8, "probabilities": {"billing": 0.8, "care": 0.2}},
                "urgency": {"score": 0.75, "confidence": 0.6, "probabilities": {0: 0.25, 1: 0.75}},
            },
        }
        normalized = normalize_response(raw, questions)
        self.assertEqual(normalized["answers"]["department"]["headline"], "billing")
        self.assertEqual(normalized["answers"]["urgency"]["subhead"], "High")
        self.assertEqual(normalized["backend_model"], "jev-latest")
        self.assertEqual(normalized["usage"]["input_tokens"], 12)

    def test_comparison_and_expected_noul(self):
        from playground.questions import PreparedRun

        prepared = PreparedRun(
            mode="compare",
            model_ids=["typesafe", "laya"],
            state="cancel",
            score_tolerance=0.5,
            questions=[{
                "id": "churn_risk",
                "type": "noul",
                "instructions": "Does the user threaten to cancel?",
                "criteria": [],
                "expected": True,
                "expected_label": "Yes",
                "wire": {"type": "noul", "instructions": "Does the user threaten to cancel?"},
            }],
        )
        results = [
            {"id": "typesafe", "name": "TypeSafe", "elapsed_ms": 100, "error": None, "answers": {
                "churn_risk": {"type": "noul", "value": 0.91, "decision": "yes", "headline": "Yes", "subhead": "0.91"},
            }},
            {"id": "laya", "name": "Laya", "elapsed_ms": 40, "error": None, "answers": {
                "churn_risk": {"type": "noul", "value": 0.2, "decision": "no", "headline": "No", "subhead": "0.2"},
            }},
        ]
        report = build_report(prepared, results)
        self.assertTrue(report["results"][0]["answers"]["churn_risk"]["evaluation"]["matched"])
        self.assertFalse(report["results"][1]["answers"]["churn_risk"]["evaluation"]["matched"])
        self.assertFalse(report["questions"][0]["agreement"]["agreed"])
        self.assertIn("Split", report["questions"][0]["agreement"]["detail"])
        self.assertIn("1 of 2", report["summary"]["sentence"])


if __name__ == "__main__":
    unittest.main()
