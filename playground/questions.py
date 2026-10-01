"""Validate a playground run and turn it into model questions."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_MAX_QUESTIONS = 12
_MAX_OPTIONS = 12
_MAX_STATE_CHARS = 100_000


class ChoiceOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = ""
    description: str = ""


class QuestionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: Literal["choice", "score", "noul"]
    instructions: str
    choice_options: list[ChoiceOption] = Field(default_factory=list)
    score_levels: list[str] = Field(default_factory=list)
    noul_true: str | None = None
    noul_false: str | None = None
    expected: Any = None


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["single", "compare"]
    model_ids: list[str]
    state_format: Literal["text", "json"]
    state: str
    questions: list[QuestionInput]
    score_tolerance: float = 0.5


@dataclass
class PreparedRun:
    mode: str
    model_ids: list[str]
    state: Any
    questions: list[dict]
    score_tolerance: float

    def wire_questions(self) -> dict[str, dict]:
        return {question["id"]: question["wire"] for question in self.questions}


def prepare_run(payload: RunInput, known_model_ids: set[str]) -> PreparedRun:
    """Validate the form payload and build the question dict both models accept."""
    model_ids = _model_ids(payload, known_model_ids)
    state = _state(payload)
    tolerance = _tolerance(payload.score_tolerance)
    questions = _questions(payload.questions)
    return PreparedRun(
        mode=payload.mode,
        model_ids=model_ids,
        state=state,
        questions=questions,
        score_tolerance=tolerance,
    )


def _model_ids(payload: RunInput, known_model_ids: set[str]) -> list[str]:
    if not payload.model_ids:
        raise ValueError("Select at least one model.")
    if len(payload.model_ids) != len(set(payload.model_ids)):
        raise ValueError("Select each model once.")
    unknown = [model_id for model_id in payload.model_ids if model_id not in known_model_ids]
    if unknown:
        raise ValueError(f"Unknown model: {', '.join(unknown)}.")
    if payload.mode == "single" and len(payload.model_ids) != 1:
        raise ValueError("Single mode runs exactly one model.")
    return list(payload.model_ids)


def _state(payload: RunInput) -> Any:
    text = payload.state.strip()
    if not text:
        raise ValueError("Add a state for the model to judge.")
    if len(text) > _MAX_STATE_CHARS:
        raise ValueError("State is too long.")
    if payload.state_format == "text":
        return text
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"State is not valid JSON: {exc.msg}.") from exc
    if not isinstance(parsed, (dict, list, str)):
        raise ValueError("JSON state must be an object, an array, or a string.")
    return parsed


def _tolerance(value: float) -> float:
    if isinstance(value, bool) or value < 0 or value > 5:
        raise ValueError("Score tolerance must be between 0 and 5.")
    return float(value)


def _questions(questions: list[QuestionInput]) -> list[dict]:
    if not questions:
        raise ValueError("Add at least one question.")
    if len(questions) > _MAX_QUESTIONS:
        raise ValueError(f"Use at most {_MAX_QUESTIONS} questions.")
    seen: set[str] = set()
    prepared: list[dict] = []
    for question in questions:
        question_id = question.id.strip()
        if not _IDENTIFIER.match(question_id):
            raise ValueError(f"Question id {question.id!r} should look like department or churn_risk.")
        if question_id in seen:
            raise ValueError(f"Question id {question_id} is used more than once.")
        seen.add(question_id)
        instructions = question.instructions.strip()
        if not instructions:
            raise ValueError(f"{question_id} needs instructions.")
        if question.type == "choice":
            prepared.append(_choice(question_id, instructions, question))
        elif question.type == "score":
            prepared.append(_score(question_id, instructions, question))
        else:
            prepared.append(_noul(question_id, instructions, question))
    return prepared


def _choice(question_id: str, instructions: str, question: QuestionInput) -> dict:
    criteria: dict[str, str | None] = {}
    labels: list[dict[str, str]] = []
    seen: set[str] = set()
    for option in question.choice_options:
        key = option.key.strip()
        description = option.description.strip()
        if not key and not description:
            continue
        if not _IDENTIFIER.match(key):
            raise ValueError(f"{question_id} has a choice key that should look like billing or care.")
        if key in seen:
            raise ValueError(f"{question_id} uses the choice {key} more than once.")
        seen.add(key)
        criteria[key] = description or None
        labels.append({"key": key, "label": description or key})
    if len(criteria) < 2:
        raise ValueError(f"{question_id} needs at least two choices.")
    if len(criteria) > _MAX_OPTIONS:
        raise ValueError(f"{question_id} has too many choices.")
    expected = _choice_expected(question_id, question.expected, set(criteria))
    return _prepared(
        question_id,
        "choice",
        instructions,
        {"type": "choice", "instructions": instructions, "criteria": criteria},
        labels,
        expected,
        expected,
    )


def _score(question_id: str, instructions: str, question: QuestionInput) -> dict:
    levels = [level.strip() for level in question.score_levels]
    if any(not level for level in levels):
        raise ValueError(f"{question_id} has an empty score level.")
    if len(levels) < 2:
        raise ValueError(f"{question_id} needs at least two score levels.")
    if len(levels) > _MAX_OPTIONS:
        raise ValueError(f"{question_id} has too many score levels.")
    labels = [{"key": str(index), "label": level} for index, level in enumerate(levels)]
    expected = _score_expected(question_id, question.expected, len(levels) - 1)
    expected_label = None if expected is None else format_number(expected)
    return _prepared(
        question_id,
        "score",
        instructions,
        {"type": "score", "instructions": instructions, "criteria": levels},
        labels,
        expected,
        expected_label,
    )


def _noul(question_id: str, instructions: str, question: QuestionInput) -> dict:
    true_text = (question.noul_true or "").strip()
    false_text = (question.noul_false or "").strip()
    wire: dict[str, Any] = {"type": "noul", "instructions": instructions}
    criteria: dict[str, str] = {}
    if true_text:
        criteria["true"] = true_text
    if false_text:
        criteria["false"] = false_text
    if criteria:
        wire["criteria"] = criteria
    labels = [
        {"key": "yes", "label": true_text or "Yes"},
        {"key": "no", "label": false_text or "No"},
    ]
    expected = _noul_expected(question_id, question.expected)
    expected_label = None if expected is None else ("Yes" if expected else "No")
    return _prepared(question_id, "noul", instructions, wire, labels, expected, expected_label)


def _prepared(
    question_id: str,
    question_type: str,
    instructions: str,
    wire: dict,
    criteria: list[dict[str, str]],
    expected: Any,
    expected_label: str | None,
) -> dict:
    return {
        "id": question_id,
        "type": question_type,
        "instructions": instructions,
        "criteria": criteria,
        "expected": expected,
        "expected_label": expected_label,
        "wire": wire,
    }


def _choice_expected(question_id: str, expected: Any, keys: set[str]) -> str | None:
    if _missing(expected):
        return None
    if not isinstance(expected, str) or expected.strip() not in keys:
        raise ValueError(f"{question_id} expected choice must be one of: {', '.join(sorted(keys))}.")
    return expected.strip()


def _score_expected(question_id: str, expected: Any, max_score: int) -> float | None:
    if _missing(expected):
        return None
    if isinstance(expected, bool) or not isinstance(expected, (int, float)):
        raise ValueError(f"{question_id} expected score must be a number from 0 to {max_score}.")
    value = float(expected)
    if value != value or value < 0 or value > max_score:
        raise ValueError(f"{question_id} expected score must be a number from 0 to {max_score}.")
    return value


def _noul_expected(question_id: str, expected: Any) -> bool | None:
    if _missing(expected):
        return None
    if isinstance(expected, bool):
        return expected
    if isinstance(expected, str):
        lowered = expected.strip().lower()
        if lowered in {"yes", "true"}:
            return True
        if lowered in {"no", "false"}:
            return False
    raise ValueError(f"{question_id} expected answer must be yes or no.")


def _missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def format_number(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")
