"""
base_processor.py
==================
Defines the processor contract for the Document Upload & AI Document
Ingestion subsystem.

BaseProcessor is intentionally simpler than BaseAgent (backend/base_agent.py).
It exists purely to standardize how a domain processor turns raw document
content into a typed ProcessingResult.

Responsibilities
-----------------
- Common processor interface (extract()).
- A public run() entry point that wraps extract() and standardizes failures.
- Shared helper utilities (require_field, build_result).
- Output validation (validate_output).
- Standardized processing exceptions (ProcessorError and subclasses).

Explicitly NOT this module's responsibility
--------------------------------------------
- Upload orchestration                  -> DocumentService (later milestone)
- Draft creation / persistence          -> import_draft_repository.py
- Human review                          -> DocumentService / review routes
- Business import                       -> BusinessImportService
- MongoDB access of any kind            -> repositories only
- Routing / determining supported types -> document_registry.py + the
                                            future processor_registry.py

Every domain processor (RecruitmentProcessor, HRProcessor, SalesProcessor,
ResearchProcessor, PerformanceProcessor) will subclass BaseProcessor and
implement extract(). No domain processors are implemented in this module.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from backend.document_processing.document_models import DocumentMetadata, ProcessingResult


# ==========================================================
# STANDARDIZED PROCESSING EXCEPTIONS
# ==========================================================

class ProcessorError(Exception):
    """
    Base exception for all document processor failures.

    Every exception raised out of BaseProcessor.run() is guaranteed to
    be a ProcessorError (or a subclass), so callers such as the future
    DocumentService can catch one type regardless of which processor
    or which internal step failed.
    """


class ExtractionError(ProcessorError):
    """
    Raised when a processor fails to extract structured data from a
    document — e.g. an LLM call fails, the response is unparseable, or
    an unexpected exception occurs anywhere inside extract().

    Carries processor_name, document_type, and the original cause so
    the failure can be logged and diagnosed without inspecting a raw
    traceback.
    """

    def __init__(
        self,
        processor_name: str,
        document_type: str,
        cause: Exception,
    ) -> None:
        self.processor_name = processor_name
        self.document_type = document_type
        self.cause = cause

        super().__init__(
            f"[{processor_name}] Extraction failed for "
            f"document_type='{document_type}': {cause}"
        )


class OutputValidationError(ProcessorError):
    """
    Raised when a processor's extracted output fails validation —
    either the default structural check in validate_output(), a
    required-field check via require_field(), or a processor's own
    overridden validation logic.

    Carries processor_name, document_type, and a human-readable reason.
    """

    def __init__(
        self,
        processor_name: str,
        document_type: str,
        reason: str,
    ) -> None:
        self.processor_name = processor_name
        self.document_type = document_type
        self.reason = reason

        super().__init__(
            f"[{processor_name}] Output validation failed for "
            f"document_type='{document_type}': {reason}"
        )


# ==========================================================
# BASE PROCESSOR
# ==========================================================

class BaseProcessor(ABC):
    """
    Abstract base class for all document domain processors.

    - Receives document content plus its DocumentMetadata.
    - Returns a typed ProcessingResult — never mutates DocumentMetadata,
      never writes to any repository, never triggers review or import.
    - extract() raises standard exceptions; run() wraps unexpected
      failures as ExtractionError so callers always receive a
      consistent failure type.
    """

    def __init__(self, processor_name: str, business_domain: str) -> None:
        """
        Args:
            processor_name: Human-readable identifier for this processor,
                             used in error messages and in ProcessingResult
                             (e.g. "RecruitmentProcessor").
            business_domain: Domain this processor owns, matching the
                              BusinessDomain values in document_registry.py
                              (e.g. "recruitment").
        """
        self.processor_name = processor_name
        self.business_domain = business_domain

    # ----------------------------------------------------------
    # PUBLIC ENTRY POINT
    # ----------------------------------------------------------

    def run(self, content: str, metadata: DocumentMetadata) -> ProcessingResult:
        """
        Public entry point for extracting structured data from a document.

        Wraps extract() so any unexpected exception is re-raised as a
        standardized ExtractionError, then validates the result before
        returning it.

        Args:
            content:  Raw text content of the document (already
                      extracted from the underlying file by an upstream
                      component — parsing binary formats is out of
                      scope for BaseProcessor).
            metadata: DocumentMetadata describing the document, including
                      its resolved document_type and business_domain.

        Returns:
            A validated ProcessingResult.

        Raises:
            ExtractionError:       If extract() raises any exception.
            OutputValidationError: If the returned result fails validation.
        """
        try:
            result = self.extract(content, metadata)
        except ProcessorError:
            # Already a standardized processor error — let it propagate.
            raise
        except Exception as exc:
            raise ExtractionError(
                processor_name=self.processor_name,
                document_type=metadata.document_type or "unknown",
                cause=exc,
            ) from exc

        self.validate_output(result)
        return result

    # ----------------------------------------------------------
    # ABSTRACT INTERFACE
    # ----------------------------------------------------------

    @abstractmethod
    def extract(self, content: str, metadata: DocumentMetadata) -> ProcessingResult:
        """
        Extract structured data from document content and return a
        ProcessingResult.

        Implementations typically build a prompt from `content`, call
        the shared LLM (see backend/agent_nodes/llm.py), parse the
        response, and return self.build_result(metadata, extracted_data).

        Args:
            content:  Raw text content of the document.
            metadata: DocumentMetadata describing the document.

        Returns:
            A ProcessingResult carrying the extracted data.

        Raises:
            OutputValidationError: If required fields cannot be extracted.
            Exception:             Any other failure; run() will wrap it
                                    as ExtractionError.
        """
        ...

    # ----------------------------------------------------------
    # OUTPUT VALIDATION
    # ----------------------------------------------------------

    def validate_output(self, result: ProcessingResult) -> None:
        """
        Baseline validation applied to every processor's output.

        Confirms the result is a ProcessingResult with non-empty
        extracted_data. Subclasses may override to add stricter,
        domain-specific checks — call super().validate_output(result)
        first to keep this baseline guarantee.

        Raises:
            OutputValidationError: If result is not a ProcessingResult,
                                    or extracted_data is empty.
        """
        if not isinstance(result, ProcessingResult):
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=getattr(result, "document_type", "unknown"),
                reason="extract() must return a ProcessingResult instance",
            )

        if not result.extracted_data:
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=result.document_type,
                reason="extracted_data must not be empty",
            )

    # ----------------------------------------------------------
    # SHARED HELPERS
    # ----------------------------------------------------------

    def require_field(
        self,
        data: dict[str, Any],
        field: str,
        document_type: str,
    ) -> Any:
        """
        Retrieve a required field from an extracted-data dict.

        Prefer this over direct dict access inside extract() — the
        error carries processor and document-type context, making
        missing or empty fields easy to diagnose in logs.

        Args:
            data:          The extracted-data dict being validated.
            field:         The key that must be present and non-empty.
            document_type: The document type being processed, used only
                            for the error message.

        Returns:
            The value stored at `field`.

        Raises:
            OutputValidationError: If `field` is missing or empty.

        Example:
            name = self.require_field(extracted, "candidate_name", metadata.document_type)
        """
        value = data.get(field)
        if value in (None, "", []):
            raise OutputValidationError(
                processor_name=self.processor_name,
                document_type=document_type,
                reason=f"Missing required field '{field}' in extracted data",
            )
        return value

    def build_result(
        self,
        metadata: DocumentMetadata,
        extracted_data: dict[str, Any],
        confidence: float | None = None,
        ai_summary: str | None = None,
    ) -> ProcessingResult:
        """
        Construct a ProcessingResult with the boilerplate fields filled
        in consistently, so extract() implementations only need to
        supply the extracted data itself.

        Args:
            metadata:       DocumentMetadata for the document being processed.
            extracted_data: The structured data extracted from the document.
            confidence:     Optional confidence score for the extraction.

        Returns:
            A fully populated ProcessingResult.

        Example:
            return self.build_result(metadata, {"candidate_name": name})
        """
        return ProcessingResult(
            document_id=metadata.document_id,
            document_type=metadata.document_type or "unknown",
            business_domain=metadata.business_domain or self.business_domain,
            processor_name=self.processor_name,
            extracted_data=extracted_data,
            confidence=confidence,
            processed_at=datetime.now(timezone.utc).isoformat(),
            ai_summary=ai_summary,
        )
