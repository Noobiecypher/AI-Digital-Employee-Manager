"""
hr_processor.py
================
HRProcessor — domain processor for `hr_metrics_report` documents.

Owns BusinessDomain.HR.

Extracts structured HR metrics compatible with hr_agent.py's existing
_collect_hr_metrics() task (performance_report workflow, t1), which
currently sources those metrics from a mock `defaults` dict and builds
HRMetrics (models.HRMetrics: `metrics: dict`). This processor does not
call the HR Agent, does not construct HRMetrics itself, and does not
aggregate cross-domain data. It only produces a WORKFLOW_SOURCE
ProcessingResult.extracted_data artifact; wiring that artifact into t1
is Processor -> Agent integration work for a later milestone, owned by
other developers, and is out of scope here.

Metric vocabulary mirrors the concrete keys hr_agent._collect_hr_metrics()
already knows how to consume:
    employee_count, average_performance_rating, goal_completion_rate,
    employee_satisfaction_score, attrition_rate,
    training_completion_rate, internal_promotions, report_period

Field types were checked against that agent's existing defaults dict
and match here without alteration: goal_completion_rate,
attrition_rate, and training_completion_rate are strings there (e.g.
"82%"); employee_count and internal_promotions are ints;
average_performance_rating and employee_satisfaction_score are floats.

Any additional metric the source document reports that isn't in that
fixed vocabulary is preserved under `additional_metrics` rather than
silently dropped or forced into an invented top-level field.

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

_HR_CONFIDENCE_WEIGHTS = {
    "report_period": 0.10,
    "employee_count": 0.15,
    "average_performance_rating": 0.15,
    "goal_completion_rate": 0.15,
    "employee_satisfaction_score": 0.10,
    "attrition_rate": 0.15,
    "training_completion_rate": 0.10,
    "internal_promotions": 0.05,
    "additional_metrics": 0.05,
}

class _ExtractedHRMetrics(BaseModel):
    """
    Internal strict validation contract for HR metrics extraction.

    All fields optional: this is a WORKFLOW_SOURCE document with no
    human review gate, so a future consumer must be able to fall back
    to its own defaults for any metric the report doesn't cover, rather
    than processing failing outright.
    """

    report_period: str | None = None
    employee_count: int | None = None
    average_performance_rating: float | None = None
    goal_completion_rate: str | None = None
    employee_satisfaction_score: float | None = None
    attrition_rate: str | None = None
    training_completion_rate: str | None = None
    internal_promotions: int | None = None
    additional_metrics: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None


_PROMPT_TEMPLATE = """
You are an HR analytics assistant. Read the HR metrics report below and
extract structured workforce metrics.

Report Content:
{content}

Return ONLY a JSON object, no extra text, no markdown fences, in exactly
this shape:

{{
  "report_period": "<reporting period covered, e.g. 'Q2 2026', or null>",
  "employee_count": <integer total headcount, or null>,
  "average_performance_rating": <numeric average rating, or null>,
  "goal_completion_rate": "<e.g. '82%', or null>",
  "employee_satisfaction_score": <numeric score, or null>,
  "attrition_rate": "<e.g. '5%', or null>",
  "training_completion_rate": "<e.g. '91%', or null>",
  "internal_promotions": <integer count, or null>,
  "additional_metrics": {{"<any other named metric found>": "<its value>"}},
  "summary": "<2-3 sentence summary of the major workforce trends in this report>"
}}

Use null for any metric not present in the report. Do not fabricate
numbers. Put any additional metric the report names but that isn't
listed above into "additional_metrics".
"""


class HRProcessor(BaseProcessor):
    """Domain processor for BusinessDomain.HR (`hr_metrics_report`)."""

    def __init__(self) -> None:
        super().__init__(
            processor_name="HRProcessor",
            business_domain=BusinessDomain.HR.value,
        )

    def extract(self, content: str, metadata: DocumentMetadata) -> ProcessingResult:
        document_type = metadata.document_type or "unknown"

        if document_type != "hr_metrics_report":
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason=(
                    f"HRProcessor does not support document_type "
                    f"'{document_type}'; only 'hr_metrics_report' is supported."
                ),
            )

        prompt = _PROMPT_TEMPLATE.format(content=content)
        raw = self._invoke_and_parse(prompt, document_type)

        try:
            extracted = _ExtractedHRMetrics(**raw)
        except ValidationError as exc:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason=f"Extracted HR metrics failed schema validation: {exc}",
            ) from exc

        extracted_data: dict[str, Any] = {
            "report_period": extracted.report_period,
            "employee_count": extracted.employee_count,
            "average_performance_rating": extracted.average_performance_rating,
            "goal_completion_rate": extracted.goal_completion_rate,
            "employee_satisfaction_score": extracted.employee_satisfaction_score,
            "attrition_rate": extracted.attrition_rate,
            "training_completion_rate": extracted.training_completion_rate,
            "internal_promotions": extracted.internal_promotions,
            "additional_metrics": extracted.additional_metrics,
        }

        confidence = calculate_field_completeness(
            extracted_data,
            _HR_CONFIDENCE_WEIGHTS,
        )

        core_values = {
            k: v for k, v in extracted_data.items()
            if k != "additional_metrics" and v is not None
        }
        if not core_values and not extracted.additional_metrics:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason="No HR metrics could be extracted from the document.",
            )

        ai_summary = extracted.summary or (
            "HR metrics report processed; see extracted_data for figures."
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