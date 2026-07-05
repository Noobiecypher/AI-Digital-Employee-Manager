"""
document_registry.py
=====================
Single source of truth for supported document metadata.

This module is PURE CONFIGURATION. It answers exactly one question:

    "Given a document_type, what business domain does it belong to,
     how is its processed output used downstream, what business entity
     does it target when applicable, does it require human review,
     and which file formats are accepted for it?"

It deliberately does NOT answer "which processor handles this document
type?" — that mapping belongs to processor_registry.py (a later
milestone). Keeping processor objects out of this module is what lets
document_registry.py be imported by the classifier, the API layer, and
the processor registry alike without ever importing LLM code, prompts,
or processing logic.

Responsibilities
-----------------
- Use the shared BusinessDomain and DocumentOutcome vocabularies.
- Define the FileFormat vocabulary used by document configuration.
- Define DocumentTypeConfig, one immutable record per supported
  document type.
- Expose DOCUMENT_TYPE_REGISTRY, the flat configuration table.
- Expose small, side-effect-free lookup helpers over that table.

Explicitly NOT this module's responsibility
--------------------------------------------
- Routing a document to a processor instance (processor_registry.py).
- Determining document type from raw content (document_classifier.py).
- Any MongoDB access, LLM calls, or business rules.

Extending the registry
-----------------------
Adding a new supported document type is a one-line addition to
DOCUMENT_TYPE_REGISTRY below — no code elsewhere needs to change.
"""

from __future__ import annotations

from enum import Enum

from backend.document_processing.document_models import (
    BusinessDomain,
    DocumentOutcome,
)

from pydantic import BaseModel, ConfigDict, Field


# ==============================================================
# CLOSED VOCABULARIES
# ==============================================================

class FileFormat(str, Enum):
    """File formats the ingestion pipeline is able to accept for upload."""

    PDF = "pdf"
    DOC = "doc"
    DOCX = "docx"
    TXT = "txt"
    CSV = "csv"
    XLSX = "xlsx"
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"


# ==============================================================
# CONFIG RECORD
# ==============================================================

class DocumentTypeConfig(BaseModel):
    """
    Immutable configuration record describing one supported document type.

    Instances are frozen: registry entries are fixed at import time and
    must never be mutated at runtime. Code that wants a "different"
    configuration should add a new document_type entry, not mutate an
    existing one.
    """

    model_config = ConfigDict(frozen=True)

    document_type: str = Field(
        description="Unique key identifying this document type, e.g. 'resume'.",
    )
    business_domain: BusinessDomain = Field(
        description="Business domain this document type belongs to.",
    )
    outcome: DocumentOutcome = Field(
        description="How processed output is used downstream.",
    )

    target_business_entity: str | None = Field(
        default=None,
        description=(
            "Target business entity for ENTITY_IMPORT and ENTITY_EVIDENCE. "
            "None for WORKFLOW_SOURCE."
        ),
    )
    required_target_context_fields: list[str] = Field(
        default_factory=list,
        description=(
            "Target-context fields that must be supplied when uploading "
            "this document type."
        ),
    )
    review_required: bool = Field(
        default=True,
        description=(
            "Whether the processed document requires human review "
            "before its downstream use."
        ),
    )
    supported_formats: list[FileFormat] = Field(
        description="File formats accepted for this document type.",
    )


# ==============================================================
# REGISTRY TABLE
# ==============================================================

DOCUMENT_TYPE_REGISTRY: dict[str, DocumentTypeConfig] = {

    "resume": DocumentTypeConfig(
        document_type="resume",
        business_domain=BusinessDomain.RECRUITMENT,
        outcome=DocumentOutcome.ENTITY_IMPORT,
        target_business_entity="candidate",
        review_required=True,
        supported_formats=[FileFormat.PDF, FileFormat.DOC, FileFormat.DOCX],
    ),

    "product_information": DocumentTypeConfig(
        document_type="product_information",
        business_domain=BusinessDomain.SALES,
        outcome=DocumentOutcome.ENTITY_IMPORT,
        target_business_entity="product",
        review_required=True,
        supported_formats=[FileFormat.PDF, FileFormat.DOCX, FileFormat.TXT],
    ),

    "performance_review": DocumentTypeConfig(
        document_type="performance_review",
        business_domain=BusinessDomain.PERFORMANCE,
        outcome=DocumentOutcome.ENTITY_EVIDENCE,
        target_business_entity="goal",
        required_target_context_fields=["employee_name", "review_period"],
        review_required=False,
        supported_formats=[FileFormat.PDF, FileFormat.DOCX],
    ),

    "self_assessment": DocumentTypeConfig(
        document_type="self_assessment",
        business_domain=BusinessDomain.PERFORMANCE,
        outcome=DocumentOutcome.ENTITY_EVIDENCE,
        target_business_entity="goal",
        required_target_context_fields=["employee_name", "review_period"],
        review_required=False,
        supported_formats=[FileFormat.PDF, FileFormat.DOCX],
    ),

    "manager_evaluation": DocumentTypeConfig(
        document_type="manager_evaluation",
        business_domain=BusinessDomain.PERFORMANCE,
        outcome=DocumentOutcome.ENTITY_EVIDENCE,
        target_business_entity="goal",
        required_target_context_fields=["employee_name", "review_period"],
        review_required=False,
        supported_formats=[FileFormat.PDF, FileFormat.DOCX],
    ),

    "hr_metrics_report": DocumentTypeConfig(
        document_type="hr_metrics_report",
        business_domain=BusinessDomain.HR,
        outcome=DocumentOutcome.WORKFLOW_SOURCE,
        target_business_entity=None,
        review_required=False,
        supported_formats=[FileFormat.PDF, FileFormat.XLSX, FileFormat.CSV],
    ),

    "sales_performance_report": DocumentTypeConfig(
        document_type="sales_performance_report",
        business_domain=BusinessDomain.SALES,
        outcome=DocumentOutcome.WORKFLOW_SOURCE,
        target_business_entity=None,
        review_required=False,
        supported_formats=[FileFormat.PDF, FileFormat.XLSX, FileFormat.CSV],
    ),

    "market_research_report": DocumentTypeConfig(
        document_type="market_research_report",
        business_domain=BusinessDomain.RESEARCH,
        outcome=DocumentOutcome.WORKFLOW_SOURCE,
        target_business_entity=None,
        review_required=False,
        supported_formats=[FileFormat.PDF, FileFormat.DOCX, FileFormat.TXT],
    ),
}


# ==============================================================
# LOOKUP HELPERS
# ==============================================================
# Pure, side-effect-free reads over DOCUMENT_TYPE_REGISTRY. These are
# accessors, not business logic — they perform no validation beyond
# "does this key exist" and never reach out to Mongo, the LLM, or any
# other subsystem.

def get_document_type_config(document_type: str) -> DocumentTypeConfig:
    """
    Look up the configuration for a supported document type.

    Args:
        document_type: Registry key, e.g. "resume".

    Returns:
        The matching DocumentTypeConfig.

    Raises:
        ValueError: If document_type is not present in the registry.
    """
    config = DOCUMENT_TYPE_REGISTRY.get(document_type)
    if config is None:
        raise ValueError(
            f"Unsupported document_type '{document_type}'. "
            f"Supported types: {sorted(DOCUMENT_TYPE_REGISTRY)}"
        )
    return config


def list_document_types(
    business_domain: BusinessDomain | None = None,
) -> list[str]:
    """
    List all registered document type keys, optionally filtered by domain.

    Args:
        business_domain: If provided, only document types belonging to
                          this domain are returned.

    Returns:
        Sorted list of document_type keys.
    """
    if business_domain is None:
        return sorted(DOCUMENT_TYPE_REGISTRY)

    return sorted(
        document_type
        for document_type, config in DOCUMENT_TYPE_REGISTRY.items()
        if config.business_domain == business_domain
    )


def is_file_format_supported(document_type: str, file_format: FileFormat) -> bool:
    """
    Check whether a given file format is accepted for a document type.

    Args:
        document_type: Registry key, e.g. "resume".
        file_format:   Format to check, e.g. FileFormat.PDF.

    Returns:
        True if file_format is in that document type's supported_formats.

    Raises:
        ValueError: If document_type is not present in the registry.
    """
    return file_format in get_document_type_config(document_type).supported_formats
