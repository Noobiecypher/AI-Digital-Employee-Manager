"""
research_processor.py
=======================
ResearchProcessor — domain processor for `market_research_report`
documents.

Owns BusinessDomain.RESEARCH.

Extracts reusable research context compatible with the existing Market
Research workflow's t1 (research_agent._gather_research_data). Per the
frozen architecture, this document is prior grounded context — it does
not replace the research agent's live get_market_context() /
get_competitors() tools, nor the workflow's own research_topic /
competitors / focus_areas parameters (models.MarketResearchParams,
models.ResearchData). This processor does not call those tools, does
not build ResearchData itself, and does not decide how a future
milestone merges document context with workflow params — it only
produces a WORKFLOW_SOURCE ProcessingResult.extracted_data artifact;
wiring it into t1 is Processor -> Agent integration for a later
milestone owned by other developers.

The complete extracted report content is passed to the LLM; this
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

_RESEARCH_CONFIDENCE_WEIGHTS = {
    "topic": 0.15,
    "competitors_mentioned": 0.15,
    "focus_areas": 0.15,
    "key_findings": 0.30,
    "market_overview": 0.25,
}


class _ExtractedResearchContext(BaseModel):
    """
    Internal strict validation contract for market research report
    extraction.

    Shaped to complement, not duplicate, the workflow's own
    MarketResearchParams (research_topic, competitors, focus_areas) and
    ResearchData: this model captures what the *document* independently
    reports, so a future milestone can merge document context with
    user-supplied workflow params rather than one silently overriding
    the other.
    """

    topic: str | None = None
    competitors_mentioned: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    key_findings: list[str] = Field(default_factory=list)
    market_overview: str | None = None
    summary: str | None = None


_PROMPT_TEMPLATE = """
You are a market research analyst assistant. Read the market research
report below and extract reusable research context.

Report Content:
{content}

Return ONLY a JSON object, no extra text, no markdown fences, in exactly
this shape:

{{
  "topic": "<the research topic this report covers, or null>",
  "competitors_mentioned": ["<competitor 1>", "<competitor 2>"],
  "focus_areas": ["<focus area 1>", "<focus area 2>"],
  "key_findings": ["<finding 1>", "<finding 2>", "<finding 3>"],
  "market_overview": "<2-4 sentence overview of the market context described>",
  "summary": "<2-3 sentence summary of the key market findings>"
}}

If a field cannot be determined from the report, use null (or an empty
list for competitors_mentioned/focus_areas/key_findings) rather than
guessing.
"""


class ResearchProcessor(BaseProcessor):
    """Domain processor for BusinessDomain.RESEARCH
    (`market_research_report`)."""

    def __init__(self) -> None:
        super().__init__(
            processor_name="ResearchProcessor",
            business_domain=BusinessDomain.RESEARCH.value,
        )

    def extract(self, content: str, metadata: DocumentMetadata) -> ProcessingResult:
        document_type = metadata.document_type or "unknown"

        if document_type != "market_research_report":
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason=(
                    f"ResearchProcessor does not support document_type "
                    f"'{document_type}'; only 'market_research_report' is supported."
                ),
            )

        prompt = _PROMPT_TEMPLATE.format(content=content)
        raw = self._invoke_and_parse(prompt, document_type)

        try:
            extracted = _ExtractedResearchContext(**raw)
        except ValidationError as exc:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason=f"Extracted research context failed schema validation: {exc}",
            ) from exc

        if not extracted.key_findings and not extracted.market_overview:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason="No usable research findings or market overview could be extracted.",
            )

        extracted_data: dict[str, Any] = {
            "topic": extracted.topic,
            "competitors_mentioned": extracted.competitors_mentioned,
            "focus_areas": extracted.focus_areas,
            "key_findings": extracted.key_findings,
            "market_overview": extracted.market_overview,
        }

        confidence = calculate_field_completeness(
            extracted_data,
            _RESEARCH_CONFIDENCE_WEIGHTS,
        )

        ai_summary = extracted.summary or (
            "Market research report processed; see extracted_data for key findings."
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