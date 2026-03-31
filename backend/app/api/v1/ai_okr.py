"""
AI OKR Generation Router
========================
Exposes a conversational endpoint that lets a manager describe their goals
in plain English and receive a fully structured Department OKR suggestion
that can be applied directly to the creation form on the frontend.
"""

from __future__ import annotations

import logging
import traceback

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.v1.dependencies import get_current_user
from app.db.models import User
from app.services.azure_openai_service import AzureOpenAIService

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class ConversationMessage(BaseModel):
    """A single message in the conversation history."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class GenerateOKRRequest(BaseModel):
    """Payload sent by the manager's chat input."""
    message: str = Field(..., min_length=1, max_length=2000)
    department_name: str = Field(..., min_length=1)
    conversation_history: list[ConversationMessage] = Field(default_factory=list)


class AIKeyResult(BaseModel):
    """A single measurable key result from the AI suggestion."""
    title: str
    target: float
    unit: str
    due_date: str  # YYYY-MM-DD


class AIOKRSuggestion(BaseModel):
    """Structured OKR data ready to populate the creation form."""
    objective: str
    quarter: str = ""  # optional for personal OKRs
    due_date: str  # YYYY-MM-DD
    key_results: list[AIKeyResult]


class ParentKR(BaseModel):
    """Minimal key result info from the parent department OKR."""
    title: str
    target: float
    unit: str


class CascadeOKRRequest(BaseModel):
    """Payload for employee cascade AI assistance."""
    department_name: str = Field(..., min_length=1)
    parent_objective: str = Field(..., min_length=1)
    parent_key_results: list[ParentKR] = Field(default_factory=list)
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_history: list[ConversationMessage] = Field(default_factory=list)


class GenerateOKRResponse(BaseModel):
    """Response from the AI — always includes a reply, optionally an OKR suggestion."""
    reply: str
    okr_suggestion: AIOKRSuggestion | None = None


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/generate-okr", response_model=GenerateOKRResponse)
async def generate_okr(
    request: GenerateOKRRequest,
    current_user: User = Depends(get_current_user),
) -> GenerateOKRResponse:
    """
    Conversational AI endpoint to generate a structured Department OKR.

    - Accepts a natural language message and optional conversation history.
    - Uses Azure OpenAI (GPT-4) to parse intent and produce an OKR suggestion.
    - The suggestion can be applied directly to the creation form fields.
    """
    # Initialise the AI service (raises 503 if openai package is missing)
    try:
        service = AzureOpenAIService()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # Build conversation history as plain dicts for the service layer
    history = [{"role": m.role, "content": m.content} for m in request.conversation_history]

    try:
        raw = service.generate_okr_suggestion(
            department_name=request.department_name,
            message=request.message,
            conversation_history=history,
        )
    except Exception as exc:
        # Log full traceback so the root cause is visible in the server console
        logger.error("AI OKR generation failed:\n%s", traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"AI generation failed: {type(exc).__name__}: {str(exc)}",
        )

    # Parse the structured suggestion if the AI decided to include one
    suggestion: AIOKRSuggestion | None = None
    if raw.get("has_suggestion") and raw.get("okr_suggestion"):
        raw_okr = raw["okr_suggestion"]
        try:
            suggestion = AIOKRSuggestion(
                objective=raw_okr.get("objective", ""),
                quarter=raw_okr.get("quarter", ""),
                due_date=raw_okr.get("due_date", ""),
                key_results=[
                    AIKeyResult(
                        title=kr.get("title", ""),
                        target=float(kr.get("target", 0)),
                        unit=kr.get("unit", ""),
                        due_date=kr.get("due_date", ""),
                    )
                    for kr in raw_okr.get("key_results", [])
                ],
            )
        except Exception:
            # Malformed AI response — return just the reply without a suggestion
            suggestion = None

    return GenerateOKRResponse(
        reply=raw.get("reply", "I understand! Let me help you build that OKR."),
        okr_suggestion=suggestion,
    )


# ── Cascade OKR endpoint ─────────────────────────────────────────────────────

@router.post("/cascade-okr", response_model=GenerateOKRResponse)
async def cascade_okr(
    request: CascadeOKRRequest,
    current_user: User = Depends(get_current_user),
) -> GenerateOKRResponse:
    """
    AI endpoint for employees cascading a department OKR.

    Uses the parent department OKR context to help the employee personalise
    the objective and key results to their individual role.
    """
    try:
        service = AzureOpenAIService()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    history = [{"role": m.role, "content": m.content} for m in request.conversation_history]
    parent_krs = [{"title": kr.title, "target": kr.target, "unit": kr.unit} for kr in request.parent_key_results]

    try:
        raw = service.cascade_okr_suggestion(
            department_name=request.department_name,
            parent_objective=request.parent_objective,
            parent_key_results=parent_krs,
            message=request.message,
            conversation_history=history,
        )
    except Exception as exc:
        logger.error("AI cascade OKR generation failed:\n%s", traceback.format_exc())
        raise HTTPException(
            status_code=500,
            detail=f"AI generation failed: {type(exc).__name__}: {str(exc)}",
        )

    suggestion: AIOKRSuggestion | None = None
    if raw.get("has_suggestion") and raw.get("okr_suggestion"):
        raw_okr = raw["okr_suggestion"]
        try:
            okr_due = raw_okr.get("due_date", "")
            suggestion = AIOKRSuggestion(
                objective=raw_okr.get("objective", ""),
                quarter=raw_okr.get("quarter", ""),
                due_date=okr_due,
                key_results=[
                    AIKeyResult(
                        title=kr.get("title", ""),
                        target=float(kr.get("target", 0)),
                        unit=kr.get("unit", ""),
                        due_date=kr.get("due_date", "") or okr_due,
                    )
                    for kr in raw_okr.get("key_results", [])
                ],
            )
        except Exception:
            suggestion = None

    return GenerateOKRResponse(
        reply=raw.get("reply", "Let me help you personalise this goal!"),
        okr_suggestion=suggestion,
    )
