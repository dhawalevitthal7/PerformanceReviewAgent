from __future__ import annotations

from typing import Any


def compute_okr_progress_metrics(okrs: list[Any]) -> dict[str, float | int]:
    """Compute objective-level progress metrics from OKRs and key results."""
    total_progress = 0.0
    okr_count = 0
    total_key_results = 0
    completed_key_results = 0

    for okr in okrs:
        key_results = getattr(okr, "key_results", []) or []
        if not key_results:
            continue

        kr_progresses: list[float] = []
        for kr in key_results:
            total_key_results += 1
            target = float(getattr(kr, "target", 0) or 0)
            current = float(getattr(kr, "current", 0) or 0)
            title = (getattr(kr, "title", "") or "").lower()

            if target <= 0:
                continue

            if "reduce" in title or "downtime" in title:
                progress = min(100.0, max(0.0, (target / current) * 100.0)) if current > 0 else 0.0
            else:
                progress = min(100.0, max(0.0, (current / target) * 100.0))

            if progress >= 100.0:
                completed_key_results += 1
            kr_progresses.append(progress)

        if kr_progresses:
            total_progress += sum(kr_progresses) / len(kr_progresses)
            okr_count += 1

    avg_progress = (total_progress / okr_count) if okr_count else 0.0
    completion_rate = (completed_key_results / total_key_results * 100.0) if total_key_results else 0.0

    return {
        "okr_count": okr_count,
        "avg_progress": round(avg_progress, 1),
        "total_key_results": total_key_results,
        "completed_key_results": completed_key_results,
        "key_result_completion_rate": round(completion_rate, 1),
    }


def build_review_evidence_payload(
    okr_metrics: dict[str, float | int],
    assessment: Any | None,
    checkin_count: int,
) -> dict[str, Any]:
    """Build normalized evidence payload used by the AI review generator."""
    return {
        "okr_metrics": okr_metrics,
        "assessment": {
            "self_rating": getattr(assessment, "self_rating", None),
            "strengths": getattr(assessment, "strengths", None),
            "improvements": getattr(assessment, "improvements", None),
            "notes": getattr(assessment, "notes", None),
        }
        if assessment
        else None,
        "checkin_count": checkin_count,
        "workflow_metadata": {
            "workflow_model": "SRS_V1_AGENTIC",
            "stages": {
                "data_integration": True,
                "okr_kpi_evidence_analysis": True,
                "continuous_feedback_context_fusion": True,
                "ai_review_generation": True,
            },
        },
    }

