"""
sales_processor.py
===================
SalesProcessor — domain processor for `product_information` and
`sales_performance_report` documents.

Owns BusinessDomain.SALES. Both document types are sales-domain
sources but have unrelated downstream shapes and outcomes, so this
processor dispatches to document-type-specific extraction methods and
internal Pydantic models rather than forcing a single generic schema:

    product_information       (ENTITY_IMPORT  -> Product)
    sales_performance_report  (WORKFLOW_SOURCE -> SalesMetrics, via
                                sales_agent._collect_sales_metrics(),
                                a future milestone's integration point)

product_information extraction
-------------------------------
Field selection mirrors business_schemas.ProductCreateRequest
field-for-field: product_name, description, pain_points,
target_industries, category, price_range. Only product_name is
required — category/price_range/etc. are legitimately completable
later during ImportDraft review (a future milestone).

sales_performance_report extraction
-------------------------------------
Metric vocabulary mirrors the concrete keys sales_agent
._collect_sales_metrics() already knows how to consume (revenue,
deals_won, pipeline, win_rate, outreach_sent, demos_booked,
report_period). Field types were checked against that agent's existing
code and match here without alteration: revenue/pipeline/win_rate are
strings there (via the local `_inr()` helper and `f"{...}%"`
formatting), while deals_won/outreach_sent/demos_booked are ints. Extra
named metrics are kept under additional_metrics rather than invented
or dropped.

The complete extracted document content is passed to the LLM for both
document types; this processor performs no truncation. An extremely
large document that exceeds the shared LLM's context window will
surface as a real extraction failure rather than a silently partial
result.
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

_PRODUCT_CONFIDENCE_WEIGHTS = {
    "product_name": 0.30,
    "description": 0.20,
    "pain_points": 0.15,
    "target_industries": 0.15,
    "category": 0.10,
    "price_range": 0.10,
}


_SALES_METRICS_CONFIDENCE_WEIGHTS = {
    "report_period": 0.10,
    "revenue": 0.20,
    "deals_won": 0.15,
    "pipeline": 0.15,
    "win_rate": 0.15,
    "outreach_sent": 0.10,
    "demos_booked": 0.10,
    "additional_metrics": 0.05,
}


# ==============================================================
# INTERNAL EXTRACTION MODELS
# ==============================================================

class _ExtractedProduct(BaseModel):
    """Internal contract for product_information extraction, mirroring
    business_schemas.ProductCreateRequest field-for-field."""

    product_name: str
    description: str | None = None
    pain_points: list[str] = Field(default_factory=list)
    target_industries: list[str] = Field(default_factory=list)
    category: str | None = None
    price_range: str | None = None
    summary: str | None = None


class _ExtractedSalesMetrics(BaseModel):
    """Internal contract for sales_performance_report extraction,
    mirroring the metric keys sales_agent._collect_sales_metrics()
    already knows how to consume."""

    report_period: str | None = None
    revenue: str | None = None
    deals_won: int | None = None
    pipeline: str | None = None
    win_rate: str | None = None
    outreach_sent: int | None = None
    demos_booked: int | None = None
    additional_metrics: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None


# ==============================================================
# PROMPTS
# ==============================================================

_PRODUCT_PROMPT_TEMPLATE = """
You are a product-marketing assistant. Read the product information
document below and extract structured product data.

Document Content:
{content}

Return ONLY a JSON object, no extra text, no markdown fences, in exactly
this shape:

{{
  "product_name": "<product name, required>",
  "description": "<product description, or null>",
  "pain_points": ["<customer pain point 1>", "<customer pain point 2>"],
  "target_industries": ["<industry 1>", "<industry 2>"],
  "category": "<product category, or null>",
  "price_range": "<indicative pricing, e.g. '$500-$2000/mo', or null>",
  "summary": "<2-3 sentence product positioning summary>"
}}

If a field cannot be determined, use null (or an empty list for
pain_points/target_industries) rather than guessing.
"""

_SALES_REPORT_PROMPT_TEMPLATE = """
You are a sales analytics assistant. Read the sales performance report
below and extract structured sales metrics.

Report Content:
{content}

Return ONLY a JSON object, no extra text, no markdown fences, in exactly
this shape:

{{
  "report_period": "<reporting period covered, or null>",
  "revenue": "<e.g. '₹1.2Cr', or null>",
  "deals_won": <integer count, or null>,
  "pipeline": "<e.g. '₹3.0Cr', or null>",
  "win_rate": "<e.g. '21%', or null>",
  "outreach_sent": <integer count, or null>,
  "demos_booked": <integer count, or null>,
  "additional_metrics": {{"<any other named metric found>": "<its value>"}},
  "summary": "<2-3 sentence summary of the major sales trends in this report>"
}}

Use null for any metric not present in the report. Do not fabricate
numbers. Put any additional metric the report names but that isn't
listed above into "additional_metrics".
"""


class SalesProcessor(BaseProcessor):
    """Domain processor for BusinessDomain.SALES (`product_information`,
    `sales_performance_report`)."""

    _SUPPORTED_TYPES = ("product_information", "sales_performance_report")

    def __init__(self) -> None:
        super().__init__(
            processor_name="SalesProcessor",
            business_domain=BusinessDomain.SALES.value,
        )

    def extract(self, content: str, metadata: DocumentMetadata) -> ProcessingResult:
        document_type = metadata.document_type or "unknown"

        if document_type == "product_information":
            return self._extract_product(content, metadata)
        if document_type == "sales_performance_report":
            return self._extract_sales_report(content, metadata)

        raise OutputValidationError(
            processor_name=self.processor_name,
            document_type=document_type,
            reason=(
                f"SalesProcessor does not support document_type "
                f"'{document_type}'; supported types are "
                f"{self._SUPPORTED_TYPES}."
            ),
        )

    # ----------------------------------------------------------
    # product_information
    # ----------------------------------------------------------

    def _extract_product(self, content: str, metadata: DocumentMetadata) -> ProcessingResult:
        document_type = "product_information"
        prompt = _PRODUCT_PROMPT_TEMPLATE.format(content=content)
        raw = self._invoke_and_parse(prompt, document_type)

        try:
            extracted = _ExtractedProduct(**raw)
        except ValidationError as exc:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason=f"Extracted product data failed schema validation: {exc}",
            ) from exc

        if not extracted.product_name or not extracted.product_name.strip():
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason="Could not identify a product name in the document.",
            )

        extracted_data: dict[str, Any] = {
            "product_name": extracted.product_name.strip(),
            "description": extracted.description,
            "pain_points": extracted.pain_points,
            "target_industries": extracted.target_industries,
            "category": extracted.category,
            "price_range": extracted.price_range,
        }

        confidence = calculate_field_completeness(
            extracted_data,
            _PRODUCT_CONFIDENCE_WEIGHTS,
        )

        ai_summary = extracted.summary or f"Product information for {extracted.product_name}."

        return self.build_result(
            metadata=metadata,
            extracted_data=extracted_data,
            confidence=confidence,
            ai_summary=ai_summary,
        )

    # ----------------------------------------------------------
    # sales_performance_report
    # ----------------------------------------------------------

    def _extract_sales_report(self, content: str, metadata: DocumentMetadata) -> ProcessingResult:
        document_type = "sales_performance_report"
        prompt = _SALES_REPORT_PROMPT_TEMPLATE.format(content=content)
        raw = self._invoke_and_parse(prompt, document_type)

        try:
            extracted = _ExtractedSalesMetrics(**raw)
        except ValidationError as exc:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason=f"Extracted sales metrics failed schema validation: {exc}",
            ) from exc

        extracted_data: dict[str, Any] = {
            "report_period": extracted.report_period,
            "revenue": extracted.revenue,
            "deals_won": extracted.deals_won,
            "pipeline": extracted.pipeline,
            "win_rate": extracted.win_rate,
            "outreach_sent": extracted.outreach_sent,
            "demos_booked": extracted.demos_booked,
            "additional_metrics": extracted.additional_metrics,
        }

        confidence = calculate_field_completeness(
            extracted_data,
            _SALES_METRICS_CONFIDENCE_WEIGHTS,
        )

        core_values = {
            k: v for k, v in extracted_data.items()
            if k != "additional_metrics" and v is not None
        }
        if not core_values and not extracted.additional_metrics:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason="No sales metrics could be extracted from the document.",
            )

        ai_summary = extracted.summary or (
            "Sales performance report processed; see extracted_data for figures."
        )

        return self.build_result(
            metadata=metadata,
            extracted_data=extracted_data,
            confidence=confidence,
            ai_summary=ai_summary,
        )

    # ----------------------------------------------------------
    # SHARED HELPER
    # ----------------------------------------------------------

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