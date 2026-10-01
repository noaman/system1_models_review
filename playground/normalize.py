"""Turn TypeSafe and Laya responses into one answer shape."""

from __future__ import annotations

from typing import Any

from playground.questions import format_number


def normalize_response(raw: Any, questions: list[dict]) -> dict:
    """Read a system_one payload into answers, model name, routing, and usage."""
    payload = raw.model_dump(mode="json") if hasattr(raw, "model_dump") else raw
    if not isinstance(payload, dict):
        raise ValueError("The model response was not an object.")
    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise ValueError("The model response did not include answers.")

    normalized: dict[str, dict] = {}
    for question in questions:
        question_id = question["id"]
        if question_id not in answers:
            raise ValueError(f"The response did not include an answer for {question_id}.")
        answer = answers[question_id]
        if hasattr(answer, "model_dump"):
            answer = answer.model_dump(mode="json")
        if not isinstance(answer, dict):
            raise ValueError(f"The answer for {question_id} was not an object.")
        normalized[question_id] = normalize_answer(question, answer)

    routing = payload.get("routing") if isinstance(payload.get("routing"), dict) else {}
    backend_model = routing.get("model") or payload.get("model")
    return {
        "answers": normalized,
        "backend_model": str(backend_model) if backend_model else None,
        "routing_reason": routing.get("reason") if isinstance(routing.get("reason"), str) else None,
        "usage": _plain_usage(payload.get("usage")),
    }


def normalize_answer(question: dict, raw: dict) -> dict:
    question_type = question["type"]
    if question_type == "choice":
        return _choice(question, raw)
    if question_type == "score":
        return _score(question, raw)
    return _noul(question, raw)


def _choice(question: dict, raw: dict) -> dict:
    selected = raw.get("choice")
    if not isinstance(selected, str) or not selected:
        raise ValueError(f"{question['id']} did not include a choice.")
    probabilities = _probabilities(raw.get("probabilities"))
    rows = []
    label_by_key = {item["key"]: item["label"] for item in question["criteria"]}
    for item in question["criteria"]:
        key = item["key"]
        rows.append(
            {
                "key": key,
                "label": item["label"],
                "probability": probabilities.get(key),
                "selected": key == selected,
            }
        )
    if selected not in label_by_key:
        rows.append(
            {
                "key": selected,
                "label": selected,
                "probability": probabilities.get(selected),
                "selected": True,
            }
        )
    return {
        "type": "choice",
        "value": selected,
        "decision": None,
        "headline": selected,
        "subhead": label_by_key.get(selected, selected),
        "confidence": _optional_float(raw.get("confidence")),
        "meter": None,
        "rows": rows,
    }


def _score(question: dict, raw: dict) -> dict:
    if "score" not in raw:
        raise ValueError(f"{question['id']} did not include a score.")
    score = _required_float(raw.get("score"), f"{question['id']} score")
    probabilities = _probabilities(raw.get("probabilities"))
    rows = []
    for item in question["criteria"]:
        rows.append(
            {
                "key": item["key"],
                "label": item["label"],
                "probability": probabilities.get(item["key"]),
                "selected": False,
            }
        )
    if rows:
        index = max(0, min(len(rows) - 1, int(round(score))))
        rows[index]["selected"] = True
        nearest = rows[index]["label"]
        meter = score / (len(rows) - 1)
    else:
        nearest = format_number(score)
        meter = None
    return {
        "type": "score",
        "value": score,
        "decision": None,
        "headline": format_number(score),
        "subhead": nearest,
        "confidence": _optional_float(raw.get("confidence")),
        "meter": meter,
        "rows": rows,
    }


def _noul(question: dict, raw: dict) -> dict:
    if "noul" not in raw:
        raise ValueError(f"{question['id']} did not include a noul probability.")
    probability = _required_float(raw.get("noul"), f"{question['id']} noul")
    decision = "yes" if probability >= 0.5 else "no"
    subhead = f"{format_number(probability)} probability"
    if 0.35 <= probability <= 0.65:
        subhead += " · uncertain"
    return {
        "type": "noul",
        "value": probability,
        "decision": decision,
        "headline": "Yes" if decision == "yes" else "No",
        "subhead": subhead,
        "confidence": None,
        "meter": probability,
        "rows": [],
    }


def _probabilities(raw: Any) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    parsed: dict[str, float] = {}
    for key, value in raw.items():
        try:
            parsed[str(key)] = _required_float(value, "probability")
        except ValueError:
            continue
    return parsed


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return _required_float(value, "confidence")


def _required_float(value: Any, label: str) -> float:
    if isinstance(value, bool) or value is None:
        raise ValueError(f"{label} was not a number.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} was not a number.") from exc
    if number != number or number in (float("inf"), float("-inf")):
        raise ValueError(f"{label} was not a finite number.")
    return number


def _plain_usage(usage: Any) -> dict | None:
    if not isinstance(usage, dict):
        return None
    clean: dict[str, Any] = {}
    for key, value in usage.items():
        if isinstance(value, bool) or isinstance(value, (str, int, float)) or value is None:
            clean[str(key)] = value
    return clean or None
