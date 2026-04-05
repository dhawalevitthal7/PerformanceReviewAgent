from __future__ import annotations

import json
from datetime import date
from typing import Any

from app.core.config import settings


class AzureOpenAIService:
    """Wrapper around Azure OpenAI for SRS-aligned outputs."""

    def __init__(self) -> None:
        try:
            from openai import AzureOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "Missing dependency 'openai'. Install it with: pip install openai>=1.51.0"
            ) from exc

        self.client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        )
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT

    def _complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        content = (response.choices[0].message.content or "{}").strip()
        return json.loads(content)

    def draft_checkin(self, evidence_payload: dict[str, Any], cadence: str) -> dict[str, str]:
        system_prompt = (
            "You are an employee performance assistant. "
            "Draft concise, factual check-in text from evidence. "
            "Return strict JSON with keys: update, wins, blockers, next_week_goals."
        )
        user_prompt = (
            f"Cadence: {cadence}\n"
            f"Evidence JSON:\n{json.dumps(evidence_payload)}\n\n"
            "Generate realistic first-person employee draft content. "
            "If evidence is missing for a section, keep it short and neutral."
        )
        return self._complete_json(system_prompt, user_prompt)

    def generate_okr_suggestion(
        self,
        department_name: str,
        message: str,
        conversation_history: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        Generate structured OKR data from a natural language manager message.

        Supports multi-turn conversation via conversation_history.
        Returns JSON with keys: reply, has_suggestion, okr_suggestion.
        """
        today = date.today().isoformat()
        system_prompt = (
            f"You are an expert OKR coach helping a manager create Department OKRs "
            f"for the '{department_name}' department. Today's date is {today}.\n\n"
            "Your role:\n"
            "1. Engage in a short, friendly conversation to understand the manager's goals.\n"
            "2. Ask clarifying questions if the quarter, targets, or due dates are unclear.\n"
            "3. When you have enough information, generate a complete OKR with 2-4 measurable key results.\n\n"
            "ALWAYS respond with a JSON object using this exact structure:\n"
            "{\n"
            '  "reply": "<your conversational response>",\n'
            '  "has_suggestion": true | false,\n'
            '  "okr_suggestion": {\n'
            '    "objective": "<clear objective statement>",\n'
            '    "quarter": "<e.g. Q2-2025>",\n'
            '    "due_date": "<YYYY-MM-DD end of that quarter>",\n'
            '    "key_results": [\n'
            '      { "title": "<measurable KR>", "target": <number>, "unit": "<%, pts, $, units…>", "due_date": "<YYYY-MM-DD>" }\n'
            "    ]\n"
            "  } | null\n"
            "}\n\n"
            "Rules:\n"
            "- Set has_suggestion to false and okr_suggestion to null when asking questions.\n"
            "- Set has_suggestion to true and populate okr_suggestion once all details are clear.\n"
            "- Key result targets must be numeric. Units must be short (%, pts, $, units, etc.).\n"
            "- due_date format: YYYY-MM-DD. Quarter format: Q[1-4]-YYYY (e.g. Q2-2025).\n"
            "- Keep the reply concise and encouraging."
        )

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": message})

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.7,
            max_tokens=4000,
            response_format={"type": "json_object"},
        )
        content = (response.choices[0].message.content or "{}").strip()
        return json.loads(content)

    def cascade_okr_suggestion(
        self,
        department_name: str,
        parent_objective: str,
        parent_key_results: list[dict[str, Any]],
        message: str,
        conversation_history: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        Help an employee personalise a cascaded OKR from a department goal.

        Returns JSON with keys: reply, has_suggestion, okr_suggestion.
        """
        today = date.today().isoformat()
        kr_lines = "\n".join(
            f"  - {kr.get('title')} (target: {kr.get('target')} {kr.get('unit')})"
            for kr in parent_key_results
        )
        system_prompt = (
            f"You are an expert OKR coach helping an employee in the '{department_name}' "
            f"department personalise a cascaded goal. Today's date is {today}.\n\n"
            f"The parent department OKR is:\n"
            f"  Objective: {parent_objective}\n"
            f"  Key Results:\n{kr_lines}\n\n"
            "Your role:\n"
            "1. Help the employee customise the objective and key results to their role.\n"
            "2. Ask clarifying questions if needed.\n"
            "3. When ready, produce a personal OKR aligned with the department goal.\n\n"
            "ALWAYS respond with a JSON object using this exact structure:\n"
            "{\n"
            '  "reply": "<your conversational response>",\n'
            '  "has_suggestion": true | false,\n'
            '  "okr_suggestion": {\n'
            '    "objective": "<personalised objective>",\n'
            '    "due_date": "<YYYY-MM-DD>",\n'
            '    "key_results": [\n'
            '      { "title": "<measurable KR>", "target": <number>, "unit": "<unit>", "due_date": "<YYYY-MM-DD>" }\n'
            "    ]\n"
            "  } | null\n"
            "}\n\n"
            "Rules:\n"
            "- Set has_suggestion=false and okr_suggestion=null when asking questions.\n"
            "- Set has_suggestion=true once all details are clear.\n"
            "- Key result targets must be numeric. due_date: YYYY-MM-DD.\n"
            "- Make the employee's OKR specific to their individual contribution.\n"
            "- Keep reply concise and encouraging."
        )

        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append({"role": "user", "content": message})

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        content = (response.choices[0].message.content or "{}").strip()
        return json.loads(content)

    def generate_okr_alignment_check(
        self,
        org_objective: str,
        org_key_results: list[dict[str, Any]],
        department_objective: str,
        department_key_results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Compare department OKR to company OKR. Returns JSON with aligned, gaps, recommendation.
        """
        system_prompt = (
            "You are an OKR alignment reviewer. Compare a department OKR to a company OKR. "
            "Return strict JSON with keys: aligned (boolean), gaps (array of short strings), "
            "recommendation (one short paragraph)."
        )
        user_prompt = (
            "Company OKR:\n"
            f"  Objective: {org_objective}\n"
            f"  Key results: {json.dumps(org_key_results)}\n\n"
            "Department OKR:\n"
            f"  Objective: {department_objective}\n"
            f"  Key results: {json.dumps(department_key_results)}\n"
        )
        return self._complete_json(system_prompt, user_prompt)

    def coach_progress_submission(self, evidence_payload: dict[str, Any]) -> dict[str, Any]:
        """Short coaching suggestion from progress submission context."""
        system_prompt = (
            "You are a concise engineering manager coach. Given progress submission context, "
            "suggest a short coaching note for the employee. "
            "Return strict JSON with keys: coaching_note (string), flags (array of short strings)."
        )
        user_prompt = f"Context JSON:\n{json.dumps(evidence_payload)}"
        return self._complete_json(system_prompt, user_prompt)

    def progress_assist(
        self,
        kr_context: dict[str, Any],
        message: str,
        conversation_history: list[dict[str, str]],
    ) -> dict[str, Any]:
        """
        Conversational assistant to help employees submit progress.
        Returns JSON with keys:
          - reply: assistant response
          - has_suggestion: bool
          - suggestion: { value: number, note: string } | null
        """
        system_prompt = (
            "You are a helpful OKR progress assistant for employees. "
            "Use the key result context to ask clarifying questions. "
            "When you have enough information, propose a numeric 'value' update "
            "and a short 'note' (1-2 sentences) summarizing progress. "
            "ALWAYS return strict JSON with:\n"
            "{\n"
            '  "reply": "<your conversational response>",\n'
            '  "has_suggestion": true | false,\n'
            '  "suggestion": { "value": <number>, "note": "<short summary>" } | null\n'
            "}\n"
        )
        context_str = json.dumps(kr_context)
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        messages.extend(conversation_history)
        messages.append(
            {
                "role": "user",
                "content": f"Key result context JSON:\n{context_str}\n\nUser says: {message}",
            }
        )

        response = self.client.chat.completions.create(
            model=self.deployment,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.5,
            response_format={"type": "json_object"},
        )
        content = (response.choices[0].message.content or "{}").strip()
        return json.loads(content)

    def generate_review(self, evidence_payload: dict[str, Any]) -> dict[str, Any]:
        system_prompt = (
            "You are an evidence-based performance review agent. "
            "Use only provided evidence, avoid recency bias claims without evidence, and be constructive. "
            "Return strict JSON with keys: summary, strengths, improvements, score_rationale."
        )
        user_prompt = (
            f"Evidence JSON:\n{json.dumps(evidence_payload)}\n\n"
            "Requirements:\n"
            "- summary: 2-4 sentences\n"
            "- strengths: array of 2-4 strings\n"
            "- improvements: array of 2-4 strings\n"
            "- score_rationale: one sentence\n"
        )
        return self._complete_json(system_prompt, user_prompt)

