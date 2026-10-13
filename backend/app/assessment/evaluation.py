from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any

TOKEN_RE = re.compile(r"\b[a-zA-Z0-9_+-]+\b")
ABSTENTION_MARKERS = (
    "not enough information",
    "cannot determine",
    "not available in the provided material",
    "the source does not say",
    "i don't know",
    "i do not know",
    "could not find this in the provided material",
)

def tokenize(text:str)->set[str]:
    """Return normalized word tokens for lightweight offline comparisons."""
    return {token.lower() for token in TOKEN_RE.findall(text or "")}

def ratio(numerator:float, denominator:float)->float:
    return numerator / denominator if denominator else 0.0

def safe_divide(numerator: float, denominator: float) -> float:
    """Divide safely; return zero if denominator is zero."""
    return numerator / denominator if denominator else 0.0


def retrieval_metrics(retrieved_ids:list[str], relevant_ids:list[str])->dict[str, float]:
    """
    Evaluate retrieved source/unit IDs against manually labeled relevant IDs.

    Precision@k = relevant retrieved items / all retrieved items.
    Recall@k = relevant retrieved items / all expected relevant items.
    """
    retrieved = list(retrieved_ids)
    relevant = set(relevant_ids)
    hits = sum(1 for item in retrieved if item in relevant)

    return {
        "precision_at_k": round(safe_divide(hits, len(retrieved)), 4),
        "recall_at_k": round(ratio(hits, len(relevant)), 4),
        "relevant_hits": hits,
        "retrieved_count": len(retrieved),
        "expected_relevant_count": len(relevant),
    }

def search_match_id(match:dict[str, Any])->str:
    """Build a stable label from the fields exposed by StudyService.search."""
    document_id = str(match.get("document_id", ""))
    chunk_index = match.get("chunk_index", "")
    return f"{document_id}:{chunk_index}"

def evaluate_live_retrieval_case(service:Any, case:dict[str, Any])->dict[str, Any]:
    """
    Run one real query against StudyService.search().

    Case fields:
      question: query passed to the retriever
      top_k: number of matches requested
      relevant_source_names: optional exact source filenames
      expected_terms: optional terms expected in retrieved text
    """
    question = str(case.get("question", "")).strip()
    if not question:
        raise ValueError("Each retrieval case requires a non-empty question.")

    matches = service.search(question, top_k=int(case.get("top_k", 5)))
    relevant_names = {
        str(name).casefold()
        for name in case.get("relevant_source_names", [])
    }
    expected_terms = {
        str(term).casefold()
        for term in case.get("expected_terms", [])
    }

    per_match = []
    relevant_hits = 0
    all_retrieved_ids = []

    for match in matches:
        source_name = str(match.get("source", ""))
        passage = str(match.get("text", ""))
        match_id = search_match_id(match)
        all_retrieved_ids.append(match_id)

        source_match = (
            bool(relevant_names)
            and source_name.casefold() in relevant_names
        )
        passage_tokens = tokens(passage)
        matched_terms = sorted(
            term for term in expected_terms
            if term in passage_tokens
        )
        term_match = bool(matched_terms) if expected_terms else False

        is_relevant = (
            source_match or term_match
            if relevant_names or expected_terms
            else None
        )

        if is_relevant:
            relevant_hits += 1

        per_match.append({
            "id": match_id,
            "source": source_name,
            "is_relevant_by_label": is_relevant,
            "matched_expected_terms": matched_terms,
            "distance": match.get("distance"),
            "location": {
                "page_number": match.get("page_number"),
                "location_number": match.get("location_number"),
                "start_seconds": match.get("start_seconds"),
                "end_seconds": match.get("end_seconds"),
                "location_type": match.get("location_type"),
            },
        })

    labeled = bool(relevant_names or expected_terms)
    precision = ratio(relevant_hits, len(matches)) if labeled else None
    expected_term_coverage = (
        ratio(
            len({
                term
                for item in per_match
                for term in item["matched_expected_terms"]
            }),
            len(expected_terms),
        )
        if expected_terms
        else None
    )

    return {
        "case_id": case.get("case_id", "unnamed"),
        "question": question,
        "retrieved_count": len(matches),
        "labeled_relevant_count": relevant_hits,
        "precision_at_k": round(precision, 4) if precision is not None else None,
        "expected_term_coverage": (
            round(expected_term_coverage, 4)
            if expected_term_coverage is not None
            else None
        ),
        "retrieved_ids": all_retrieved_ids,
        "matches": per_match,
        "passed": (
            len(matches) > 0
            and (precision is None or precision >= float(case.get("minimum_precision", 0.0)))
            and (
                expected_term_coverage is None
                or expected_term_coverage >= float(case.get("minimum_term_coverage", 0.0))
            )
        ),
        "labels_available": labeled,
    }


def answer_context_metrics(answer:str, context:str, reference_answer:str | None = None)->dict[str, Any]:
    """
    Calculate simple lexical indicators.

    These are diagnostic signals, not semantic truth or proof of faithfulness.
    """
    answer_tokens = tokenize(answer)
    context_tokens = tokenize(context)

    answer_context_overlap = safe_divide(
        len(answer_tokens & context_tokens),
        len(answer_tokens),
    )

    result: dict[str, Any] = {
        "answer_token_count": len(answer_tokens),
        "context_token_count": len(context_tokens),
        "answer_context_token_overlap": round(answer_context_overlap, 4),
        "answer_empty": not bool(answer.strip()),
        "context_empty": not bool(context.strip()),
    }

    if reference_answer is not None:
        reference_tokens = tokenize(reference_answer)
        result["reference_token_recall"] = round(
            safe_divide(
                len(reference_tokens & answer_tokens),
                len(reference_tokens),
            ),
            4,
        )

    return result

def citation_metrics(citations:list[dict[str, Any]], known_source_ids:set[str] | None = None)->dict[str, Any]:
    """
    Check citation structure and optionally verify source IDs.

    Supported location fields:
    - page: PDF page
    - slide: presentation slide
    - timestamp: video timestamp

    Expected citation examples:
      {"source_id": "...", "source_type": "pdf", "page": 4}
      {"source_id": "...", "source_type": "pptx", "slide": 7}
      {"source_id": "...", "source_type": "video", "timestamp": "00:01:20"}
    """
    valid_indices: list[int] = []
    malformed_indices: list[int] = []
    unknown_source_indices: list[int] = []

    for index, citation in enumerate(citations):
        source_id = str(citation.get("source_id", "")).strip()
        source_type = str(citation.get("source_type", "")).lower().strip()

        if source_type == "pdf":
            has_location = citation.get("page") is not None
        elif source_type in {"pptx", "powerpoint", "slide"}:
            has_location = citation.get("slide") is not None
        elif source_type in {"video", "lecture_video"}:
            has_location = citation.get("timestamp") is not None
        else:
            has_location = any(
                citation.get(field) is not None
                for field in ("page", "slide", "timestamp", "location_number")
            )

        if not source_id or not has_location:
            malformed_indices.append(index)
            continue

        if known_source_ids is not None and source_id not in known_source_ids:
            unknown_source_indices.append(index)
            continue

        valid_indices.append(index)

    total = len(citations)
    return {
        "citation_count": total,
        "valid_count": len(valid_indices),
        "validity_rate": round(ratio(len(valid_indices), total), 4),
        "malformed_indices": malformed_indices,
        "unknown_source_indices": unknown_source_indices,
    }

def personalization_metrics(topic_mastery:dict[str, float], recommended_topic:str | None, repeated_question_count: int = 0, total_question_count: int = 0, mastery_before:dict[str, float] | None = None, mastery_after: dict[str, float]| None=None)->dict[str, Any]:
    """Measure whether recommendations target weak topics and track mastery."""
    weak_topics = {
        topic for topic, score in topic_mastery.items()
        if score < 0.70
    }

    recommendation_targets_weak_topic = (
        recommended_topic in weak_topics
        if recommended_topic is not None
        else False
    )

    repeated_question_rate = safe_divide(
        repeated_question_count,
        total_question_count,
    )

    gains: dict[str, float] = {}
    if mastery_before is not None and mastery_after is not None:
        for topic in set(mastery_before) & set(mastery_after):
            gains[topic] = round(
                float(mastery_after[topic]) - float(mastery_before[topic]),
                4,
            )

    return {
        "weak_topic_count": len(weak_topics),
        "weak_topics": sorted(weak_topics),
        "recommended_topic": recommended_topic,
        "recommendation_targets_weak_topic": recommendation_targets_weak_topic,
        "repeated_question_rate": round(repeated_question_rate, 4),
        "mastery_gains": gains,
        "average_mastery_gain": round(
            safe_divide(sum(gains.values()), len(gains)),
            4,
        ),
    }

def evaluate_recorded_answer(case:dict[str, Any])->dict[str, Any]:
    """
    Evaluate a recorded tutor answer without calling the model.

    Use this for saved outputs from your Gemini tutor. The record must include
    the actual answer and the exact retrieved context used to produce it.
    """
    answer = str(case.get("answer", ""))
    context = str(case.get("context", ""))

    answer_signals = answer_context_metrics(
        answer=answer,
        context=context,
        reference_answer=case.get("reference_answer"),
    )
    citations = citation_metrics(
        case.get("citations", []),
        set(case["known_source_ids"])
        if "known_source_ids" in case
        else None,
    )

    checks = {
        "answer_not_empty": not answer_signals["answer_empty"],
        "context_present_when_required": (
            not answer_signals["context_empty"]
            if case.get("context_required", True)
            else True
        ),
        "citations_valid_when_required": (
            citations["validity_rate"] == 1.0
            if citations["citation_count"] > 0
            else not case.get("citations_required", False)
        ),
    }

    if case.get("expect_abstention", False):
        checks["abstention_signaled"] = any(
            marker in answer.casefold()
            for marker in ABSTENTION_MARKERS
        )

    return {
        "case_id": case.get("case_id", "unnamed"),
        "checks": checks,
        "passed": all(checks.values()),
        "answer_signals": answer_signals,
        "citations": citations,
    }


def evaluate_dataset(path: str | Path) -> dict[str, Any]:
    """Evaluate recorded answer cases from a JSON array."""
    dataset_path = Path(path)
    with dataset_path.open("r", encoding="utf-8") as file:
        cases = json.load(file)

    if not isinstance(cases, list):
        raise ValueError("Evaluation dataset must be a JSON array.")

    results = [evaluate_recorded_answer(case) for case in cases]
    passed = sum(1 for result in results if result["passed"])

    return {
        "dataset": dataset_path.name,
        "total_cases": len(results),
        "passed_cases": passed,
        "failed_cases": len(results) - passed,
        "pass_rate": round(ratio(passed, len(results)), 4),
        "results": results,
        "limitations": [
            "Token overlap is a heuristic, not semantic faithfulness.",
            "Citation structure does not prove that a cited source supports a claim.",
            "Recorded answer cases do not call the live Gemini model.",
        ],
    }


def save_report(report: dict[str, Any], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    ) 

def tokens(text: str) -> set[str]:
    """Compatibility helper for retrieval evaluation."""
    return tokenize(text)