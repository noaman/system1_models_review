"""Models and example questions shown in the playground."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    """A System 1 backend the playground can call."""

    id: str
    name: str
    subtitle: str
    kind: str
    summary: str

    def public_dict(self) -> dict:
        ready, status = model_status(self.id)
        return {
            "id": self.id,
            "name": self.name,
            "subtitle": self.subtitle,
            "kind": self.kind,
            "summary": self.summary,
            "ready": ready,
            "status": status,
        }


# Add a model by appending a ModelSpec and a matching runner in runners.py.
MODELS: tuple[ModelSpec, ...] = (
    ModelSpec(
        id="typesafe",
        name="TypeSafe",
        subtitle="JEV",
        kind="Hosted",
        summary="Hosted judgments through the TypeSafe API.",
    ),
    ModelSpec(
        id="laya",
        name="Laya",
        subtitle="Local router",
        kind="Local",
        summary="Loaded when the playground starts and kept in memory.",
    ),
)

QUESTION_TYPES: tuple[dict, ...] = (
    {
        "id": "choice",
        "name": "Choice",
        "summary": "Pick one option from a fixed list.",
    },
    {
        "id": "score",
        "name": "Score",
        "summary": "Place the answer on an ordered scale.",
    },
    {
        "id": "noul",
        "name": "Noul",
        "summary": "Probability that a statement is true.",
    },
)

_BILLING_STATE = (
    "Hi, we were charged twice for March. Please  accept this complaint and help to fix "
    "the duplicate today or we will cancel our plan. In our organization all customer "
    "qeuries are first routed to care"
)

_REFUND_STATE = """{
  "ticket": {
    "subject": "Duplicate charge",
    "messages": [
      {"from": "customer", "text": "I was charged twice for order A-104. Please refund the duplicate."},
      {"from": "support", "text": "We are checking the charges."}
    ]
  },
  "order": {
    "id": "A-104",
    "charges": [
      {"amount_usd": 49, "status": "captured"},
      {"amount_usd": 49, "status": "captured"}
    ]
  },
  "refund_policy": "Duplicate charges are eligible for a refund."
}"""


def _choice_department() -> dict:
    return {
        "id": "department",
        "type": "choice",
        "instructions": "Which department should handle this?",
        "choice_options": [
            {"key": "billing", "description": "All fixes on the billing system"},
            {"key": "care", "description": "Customer queries, complaints, and feedback"},
            {"key": "technical", "description": "Bugs, outages, and system errors"},
            {"key": "other", "description": "Everything else"},
        ],
        "score_levels": [],
        "noul_true": "",
        "noul_false": "",
        "expected": None,
    }


def _score_urgency() -> dict:
    return {
        "id": "urgency",
        "type": "score",
        "instructions": "How urgent is this?",
        "choice_options": [],
        "score_levels": ["Not urgent", "Soon", "Blocking", "Critical"],
        "noul_true": "",
        "noul_false": "",
        "expected": None,
    }


def _noul_churn() -> dict:
    return {
        "id": "churn_risk",
        "type": "noul",
        "instructions": "Does the user threaten to cancel or leave?",
        "choice_options": [],
        "score_levels": [],
        "noul_true": "The user says they will cancel, leave, or stop paying.",
        "noul_false": "The user does not threaten to end the relationship.",
        "expected": True,
    }


PRESETS: tuple[dict, ...] = (
    {
        "id": "billing_triage",
        "name": "Billing triage",
        "description": "Choice, score, and noul on one support message.",
        "state_format": "text",
        "state": _BILLING_STATE,
        "questions": [_choice_department(), _score_urgency(), _noul_churn()],
    },
    {
        "id": "choice_only",
        "name": "Choice",
        "description": "Route one message to a department.",
        "state_format": "text",
        "state": _BILLING_STATE,
        "questions": [_choice_department()],
    },
    {
        "id": "score_only",
        "name": "Score",
        "description": "Place urgency on an ordered scale.",
        "state_format": "text",
        "state": _BILLING_STATE,
        "questions": [_score_urgency()],
    },
    {
        "id": "noul_only",
        "name": "Noul",
        "description": "Yes or no, returned as a probability.",
        "state_format": "text",
        "state": _BILLING_STATE,
        "questions": [_noul_churn()],
    },
    {
        "id": "structured_refund",
        "name": "JSON state",
        "description": "Noul questions that point at fields in a JSON state.",
        "state_format": "json",
        "state": _REFUND_STATE.strip(),
        "questions": [
            {
                "id": "refund_requested",
                "type": "noul",
                "instructions": "Does `ticket.messages[0].text` request a refund?",
                "choice_options": [],
                "score_levels": [],
                "noul_true": "The customer asks for money back.",
                "noul_false": "The customer does not ask for money back.",
                "expected": True,
            },
            {
                "id": "policy_supports_refund",
                "type": "noul",
                "instructions": (
                    "Does `refund_policy` support the refund requested in "
                    "`ticket.messages[0].text`, given `order.charges`?"
                ),
                "choice_options": [],
                "score_levels": [],
                "noul_true": "The policy covers this refund.",
                "noul_false": "The policy does not cover this refund.",
                "expected": True,
            },
        ],
    },
)


def model_ids() -> set[str]:
    return {spec.id for spec in MODELS}


def model_by_id(model_id: str) -> ModelSpec:
    for spec in MODELS:
        if spec.id == model_id:
            return spec
    raise KeyError(model_id)


def model_status(model_id: str) -> tuple[bool, str]:
    if model_id == "typesafe":
        if os.environ.get("JEV_APIKEY"):
            return True, "API key loaded"
        return False, "JEV_APIKEY missing"
    if model_id == "laya":
        from playground.runners import laya_memory_status

        return laya_memory_status()
    return False, "Unknown model"


def build_catalog() -> dict:
    return {
        "models": [spec.public_dict() for spec in MODELS],
        "question_types": list(QUESTION_TYPES),
        "presets": list(PRESETS),
    }
