"""
processor_registry.py
======================
Routing layer for the Document Upload & AI Document Ingestion subsystem.

ProcessorRegistry answers exactly one question: "given a classified
document's business domain, which processor CLASS is responsible for
extracting data from it?" It owns routing only — it never instantiates
a processor, never performs extraction or classification, and never
touches Mongo or business entities.

Responsibilities
-----------------
- Hold the routing table mapping BusinessDomain to a processor class.
- Resolve that mapping from a ClassificationResult (the classifier's
  output), so callers never need to unpack business_domain themselves.

Explicitly NOT this module's responsibility
--------------------------------------------
- Instantiating processors. Processor instantiation belongs to the
  future processing orchestration layer; this registry's
  responsibility ends once it has resolved the processor class.
- Performing extraction (BaseProcessor / domain processors).
- Performing classification (document_classifier.py).
- Any MongoDB access or business entity import.
- Wiring processor output into workflow agents — that is a later,
  separate Processor -> Agent integration milestone owned by other
  developers. This registry's job ends at "which processor class."

Current state (Milestone 5): routing table populated
-------------------------------------------------------
All five domain processors are implemented and wired in below as an
explicit literal mapping, mirroring the style of
document_registry.DOCUMENT_TYPE_REGISTRY. There is no self-registration
mechanism, no import-time side effects beyond importing the five
processor classes, and no processor module reaches into this registry
on its own.

Usage (by future processing orchestration)
--------------------------------------------
    processor_class = get_processor_class(classification_result)
    processor = processor_class(...)
    result = processor.run(content, metadata)
"""

from __future__ import annotations

from backend.document_processing.base_processor import BaseProcessor
from backend.document_processing.document_models import (
    BusinessDomain,
    ClassificationResult,
)
from backend.document_processing.hr_processor import HRProcessor
from backend.document_processing.performance_processor import PerformanceProcessor
from backend.document_processing.recruitment_processor import RecruitmentProcessor
from backend.document_processing.research_processor import ResearchProcessor
from backend.document_processing.sales_processor import SalesProcessor

# ==============================================================
# ROUTING TABLE
# ==============================================================

_PROCESSOR_REGISTRY: dict[BusinessDomain, type[BaseProcessor]] = {
    BusinessDomain.RECRUITMENT: RecruitmentProcessor,
    BusinessDomain.HR: HRProcessor,
    BusinessDomain.SALES: SalesProcessor,
    BusinessDomain.RESEARCH: ResearchProcessor,
    BusinessDomain.PERFORMANCE: PerformanceProcessor,
}


# ==============================================================
# RESOLUTION
# ==============================================================

def get_processor_class(classification: ClassificationResult) -> type[BaseProcessor]:
    """
    Resolve the processor class responsible for a classified document.

    Args:
        classification: The ClassificationResult produced by
                         DocumentClassifier.classify().

    Returns:
        The BaseProcessor subclass registered for
        classification.business_domain.

    Raises:
        NotImplementedError: If no processor is registered for that
                              business domain. With all five domains
                              wired in above, this should not occur for
                              any currently supported document type.
    """
    business_domain = classification.business_domain
    processor_class = _PROCESSOR_REGISTRY.get(business_domain)

    if processor_class is None:
        raise NotImplementedError(
            f"No processor has been implemented yet for business domain "
            f"'{business_domain.value}'."
        )

    return processor_class