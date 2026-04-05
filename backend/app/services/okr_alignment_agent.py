"""Thin wrapper for OKR alignment checks (company vs department)."""

from __future__ import annotations

from typing import Any

from app.services.azure_openai_service import AzureOpenAIService


def run_okr_alignment_check(
    org_objective: str,
    org_key_results: list[dict[str, Any]],
    department_objective: str,
    department_key_results: list[dict[str, Any]],
) -> dict[str, Any]:
    return AzureOpenAIService().generate_okr_alignment_check(
        org_objective=org_objective,
        org_key_results=org_key_results,
        department_objective=department_objective,
        department_key_results=department_key_results,
    )
