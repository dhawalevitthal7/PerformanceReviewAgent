# CurrentReview Workflow Modification Plan

## Objective
Align `currentreview` backend and frontend workflow with the `REVIEW_AGENT` SRS:
- Evidence-based review generation
- AI-assisted contextual check-ins
- Explicit workflow stages that map to SRS layers
- Azure OpenAI integration using the provided client configuration

## Target Scope
- Backend: `currentreview/backend`
- Frontend: `currentreview/perform-for-you`
- Do not modify `review1`

## Planned Backend Changes
1. **Azure OpenAI configuration**
   - Add Azure OpenAI settings in backend config.
   - Support env override while retaining requested defaults.

2. **LLM service module**
   - Add a dedicated service wrapping:
     - `client = AzureOpenAI(api_key=..., api_version=..., azure_endpoint=...)`
   - Expose methods for:
     - Check-in draft generation (period summary + suggested text)
     - Review synthesis (summary, strengths, improvements, score rationale)

3. **SRS workflow helpers**
   - Add backend workflow utility to produce:
     - Evidence inputs from OKRs/assessments/check-ins
     - Structured prompts for empirical and bias-aware outputs

4. **API updates**
   - Extend check-ins API with an AI draft endpoint.
   - Upgrade reviews generation endpoint to use Azure OpenAI and evidence context.
   - Include workflow metadata in response where relevant.

5. **Dependencies**
   - Add `openai` to backend requirements.

## Planned Frontend Changes
1. **API client updates**
   - Add typed method for check-in draft endpoint.
   - Extend review response typing for workflow/evidence fields.

2. **Hooks**
   - Add React Query mutation hook for AI check-in draft generation.

3. **Check-in page**
   - Add “Draft with AI” action to prefill weekly update fields from backend AI draft.

4. **Review page**
   - Surface evidence/workflow metadata to align with SRS narrative.

## Validation Steps
1. Run lint checks on changed backend and frontend files.
2. Run lightweight backend import check.
3. Run frontend type/lint command (if available in project scripts).
