"""
recruitment_processor.py
=========================
RecruitmentProcessor — domain processor for `resume` documents.

Owns BusinessDomain.RECRUITMENT.

Extracts Candidate-like data for the later ENTITY_IMPORT flow (per
document_registry.py: resume -> target_business_entity="candidate").
Field selection mirrors business_schemas.CandidateCreateRequest
field-for-field, minus fields that are never processor-derived:

    candidate_id  - repository-generated UUID4
                    (BusinessDataRepository.create_candidate())
    match_score   - workflow-managed, computed by
                    recruitment_agent._shortlist_candidates() against a
                    specific job's required_skills; a document processor
                    has no job context to score against

A resume may legitimately omit business fields (role_applied, skills,
experience_years, email, phone) that a human reviewer can complete
later in the ImportDraft review step (a future milestone). Only `name`
is required — a document with no identifiable candidate name is not a
usable resume extraction and processing fails rather than producing an
empty/placeholder candidate.

The complete extracted resume content is passed to the LLM; this
processor performs no truncation. An extremely large document that
exceeds the shared LLM's context window will surface as a real
extraction failure rather than a silently partial result.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError

from backend.agent_nodes.llm import llm
from backend.document_processing._processor_utils import (
    calculate_field_completeness,
    parse_llm_json,
)
from backend.document_processing.base_processor import (
    BaseProcessor,
    OutputValidationError,
)
from backend.document_processing.document_models import (
    BusinessDomain,
    DocumentMetadata,
    ProcessingResult,
)

_RESUME_CONFIDENCE_WEIGHTS = {
    "name": 0.30,
    "role_applied": 0.10,
    "skills": 0.20,
    "experience_years": 0.15,
    "email": 0.15,
    "phone": 0.10,
}


class _ExtractedCandidate(BaseModel):
    """
    Internal strict validation contract for resume extraction.

    Mirrors business_schemas.CandidateCreateRequest field-for-field
    (name, role_applied, skills, experience_years, email, phone) so a
    future ImportDraft -> BusinessImportService.create_candidate() path
    requires no field translation. candidate_id and match_score are
    intentionally absent — see module docstring.
    """

    name: str
    role_applied: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience_years: int | None = None
    email: str | None = None
    phone: str | None = None
    summary: str | None = Field(
        default=None,
        description="Short candidate profile used to build ai_summary.",
    )



_PROMPT_TEMPLATE = """
You are a resume-parsing assistant. Read the resume text below and extract
structured candidate information.

Resume Content:
{content}

Return ONLY a JSON object, no extra text, no markdown fences, in exactly
this shape:

{{
  "name": "<candidate full name, or null if truly not present>",
  "role_applied": "<role/title the candidate appears to be targeting, or null>",
  "skills": ["<skill 1>", "<skill 2>"],
  "experience_years": <integer total years of professional experience, or null>,
  "email": "<email address, or null>",
  "phone": "<phone number, or null>",
  "summary": "<2-3 sentence candidate profile summarizing background and strengths>"
}}

If a field cannot be determined from the resume, use null (or an empty
list for skills) rather than guessing.
"""


class RecruitmentProcessor(BaseProcessor):
    """Domain processor for BusinessDomain.RECRUITMENT (`resume`)."""

    def __init__(self) -> None:
        super().__init__(
            processor_name="RecruitmentProcessor",
            business_domain=BusinessDomain.RECRUITMENT.value,
        )

    def extract(self, content: str, metadata: DocumentMetadata) -> ProcessingResult:
        document_type = metadata.document_type or "unknown"

        if document_type != "resume":
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason=(
                    f"RecruitmentProcessor does not support document_type "
                    f"'{document_type}'; only 'resume' is supported."
                ),
            )

        prompt = _PROMPT_TEMPLATE.format(content=content)
        raw = self._invoke_and_parse(prompt, document_type)

        try:
            extracted = _ExtractedCandidate(**raw)
        except ValidationError as exc:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason=f"Extracted candidate data failed schema validation: {exc}",
            ) from exc

        if not extracted.name or not extracted.name.strip():
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason="Could not identify a candidate name in the resume.",
            )

        extracted_data: dict[str, Any] = {
            "name": extracted.name.strip(),
            "role_applied": extracted.role_applied,
            "skills": extracted.skills,
            "experience_years": extracted.experience_years,
            "email": extracted.email,
            "phone": extracted.phone,
        }

        confidence = calculate_field_completeness(
            extracted_data,
            _RESUME_CONFIDENCE_WEIGHTS,
        )

        ai_summary = extracted.summary or (
            f"Candidate {extracted.name}"
            + (f" applying for {extracted.role_applied}" if extracted.role_applied else "")
            + "."
        )

        return self.build_result(
            metadata=metadata,
            extracted_data=extracted_data,
            confidence=confidence,
            ai_summary=ai_summary,
        )

    def _invoke_and_parse(self, prompt: str, document_type: str) -> dict[str, Any]:
        """Call the shared LLM and parse its JSON response, raising a
        standardized OutputValidationError on malformed output."""
        response = llm.invoke(prompt)
        try:
            return parse_llm_json(response.content)
        except ValueError as exc:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason=f"LLM did not return valid JSON: {exc}",
            ) from exc