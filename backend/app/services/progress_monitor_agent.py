"""Optional AI helper for progress submission context (coaching copy)."""

from __future__ import annotations

from typing import Any

from app.services.azure_openai_service import AzureOpenAIService


def suggest_coaching_from_submission_context(evidence_payload: dict[str, Any]) -> dict[str, Any]:
    """
    Given submission + light history context, return coaching_note and flags from the model.
    """
    return AzureOpenAIService().coach_progress_submission(evidence_payload)
