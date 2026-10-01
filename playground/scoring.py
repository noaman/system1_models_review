"""Score answers against an expected value and compare models."""

from __future__ import annotations

from playground.questions import PreparedRun, format_number


def build_report(prepared: PreparedRun, results: list[dict]) -> dict:
    for result in results:
        if result.get("error"):
            continue
        for question in prepared.questions:
            answer = result.get("answers", {}).get(question["id"])
            if answer is not None:
                answer["evaluation"] = evaluate_answer(question, answer, prepared.score_tolerance)

    questions = []
    for question in prepared.questions:
        agreement = None
        if prepared.mode == "compare":
            agreement = compare_question(question, results, prepared.score_tolerance)
        questions.append(
            {
                "id": question["id"],
                "type": question["type"],
                "instructions": question["instructions"],
                "expected_label": question["expected_label"],
                "agreement": agreement,
            }
        )

    summary = _summary(prepared.mode, questions, results)
    return {
        "mode": prepared.mode,
        "score_tolerance": prepared.score_tolerance,
        "summary": summary,
        "questions": questions,
        "results": results,
    }


def evaluate_answer(question: dict, answer: dict, score_tolerance: float) -> dict | None:
    expected = question["expected"]
    if expected is None:
        return None
    question_type = question["type"]
    if question_type == "choice":
        matched = answer["value"] == expected
        if matched:
            detail = f"Matches expected {expected}."
        else:
            detail = f"Expected {expected}. Model selected {answer['value']}."
        return {"matched": matched, "detail": detail}
    if question_type == "score":
        delta = abs(float(answer["value"]) - float(expected))
        matched = delta <= score_tolerance
        actual = format_number(float(answer["value"]))
        target = format_number(float(expected))
        window = format_number(score_tolerance)
        if matched:
            detail = f"Score {actual} is within {window} of expected {target}."
        else:
            detail = f"Score {actual} is {format_number(delta)} away from expected {target}."
        return {"matched": matched, "detail": detail}
    probability = float(answer["value"])
    decision = answer["decision"]
    expected_label = "yes" if expected else "no"
    matched = decision == expected_label
    shown = f"{answer['headline']} ({format_number(probability)})"
    if matched:
        detail = f"{shown} matches expected {expected_label}."
    else:
        detail = f"{shown} does not match expected {expected_label}."
    return {"matched": matched, "detail": detail}


def compare_question(question: dict, results: list[dict], score_tolerance: float) -> dict:
    usable: list[tuple[dict, dict]] = []
    for result in results:
        if result.get("error"):
            continue
        answer = result.get("answers", {}).get(question["id"])
        if answer is None:
            continue
        usable.append((result, answer))
    if len(usable) < 2:
        return {
            "comparable": False,
            "agreed": None,
            "detail": "At least two successful models are needed for a comparison.",
        }

    if question["type"] == "choice":
        return _compare_choice(usable)
    if question["type"] == "score":
        return _compare_score(usable, score_tolerance)
    return _compare_noul(usable)


def _compare_choice(usable: list[tuple[dict, dict]]) -> dict:
    values = [answer["value"] for _, answer in usable]
    agreed = len(set(values)) == 1
    if agreed:
        detail = f"All models selected {values[0]}."
    else:
        detail = "Split: " + ", ".join(f"{result['name']} {answer['value']}" for result, answer in usable) + "."
    return {"comparable": True, "agreed": agreed, "detail": detail}


def _compare_score(usable: list[tuple[dict, dict]], score_tolerance: float) -> dict:
    scores = [float(answer["value"]) for _, answer in usable]
    span = max(scores) - min(scores)
    agreed = span <= score_tolerance
    rendered = ", ".join(f"{result['name']} {answer['headline']}" for result, answer in usable)
    window = format_number(score_tolerance)
    if agreed:
        detail = f"Within {window}. {rendered}."
    else:
        detail = f"Spread of {format_number(span)} is outside {window}. {rendered}."
    return {"comparable": True, "agreed": agreed, "detail": detail}


def _compare_noul(usable: list[tuple[dict, dict]]) -> dict:
    decisions = [answer["decision"] for _, answer in usable]
    agreed = len(set(decisions)) == 1
    parts = [
        f"{result['name']} {answer['headline']} ({format_number(float(answer['value']))})"
        for result, answer in usable
    ]
    if agreed:
        detail = f"All models say {decisions[0]}. " + ", ".join(parts) + "."
    else:
        detail = "Split: " + ", ".join(parts) + "."
        probabilities = [float(answer["value"]) for _, answer in usable]
        if max(probabilities) - min(probabilities) <= 0.15:
            detail += " Probabilities are close."
    return {"comparable": True, "agreed": agreed, "detail": detail}


def _summary(mode: str, questions: list[dict], results: list[dict]) -> dict:
    match_count = 0
    check_count = 0
    for result in results:
        if result.get("error"):
            continue
        for answer in result.get("answers", {}).values():
            evaluation = answer.get("evaluation")
            if not evaluation:
                continue
            check_count += 1
            if evaluation["matched"]:
                match_count += 1

    compared = [question["agreement"] for question in questions if question.get("agreement")]
    comparison_count = sum(1 for item in compared if item.get("comparable"))
    agreement_count = sum(1 for item in compared if item.get("agreed") is True)
    elapsed = [result.get("elapsed_ms") or 0 for result in results]
    failed = [result["name"] for result in results if result.get("error")]

    parts: list[str] = []
    if check_count:
        parts.append(f"{match_count} of {check_count} expected checks matched")
    else:
        parts.append("No expected answers to score")
    if mode == "compare" and comparison_count:
        parts.append(f"models agreed on {agreement_count} of {comparison_count}")
    elif mode == "compare":
        parts.append("at least two successful models are needed for a comparison")
    if failed:
        parts.append(f"{', '.join(failed)} failed")

    return {
        "sentence": _sentence(parts),
        "match_count": match_count,
        "check_count": check_count,
        "agreement_count": agreement_count,
        "comparison_count": comparison_count,
        "slowest_ms": max(elapsed) if elapsed else 0,
    }


def _sentence(parts: list[str]) -> str:
    cleaned: list[str] = []
    for part in parts:
        text = part.strip().rstrip(".")
        if text and text[0].isalpha():
            text = text[0].upper() + text[1:]
        cleaned.append(text)
    return ". ".join(cleaned) + "."
