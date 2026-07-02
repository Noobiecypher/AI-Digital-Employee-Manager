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
- Instantiating processors — DocumentService constructs the instance
  once this registry has told it which class to use.
- Performing extraction (BaseProcessor / domain processors).
- Performing classification (document_classifier.py).
- Any MongoDB access or business entity import.

Milestone 2 state: intentionally empty routing table
-------------------------------------------------------
No domain processor classes (RecruitmentProcessor, HRProcessor,
SalesProcessor, ResearchProcessor, PerformanceProcessor) exist yet —
they are introduced in Milestone 3. Routing is explicitly owned by this
file, the same way document metadata is explicitly owned by
document_registry.py: there is no self-registration mechanism, no
import-time side effects, and no processor module reaches into this
registry on its own. Until Milestone 3, _PROCESSOR_REGISTRY is simply
empty, and get_processor_class() raises a clear "not implemented yet"
error for every domain.

Milestone 3 plan
-----------------
Once the concrete domain processors exist, _PROCESSOR_REGISTRY will be
populated as an explicit literal mapping directly in this file —
mirroring the style of document_registry.DOCUMENT_TYPE_REGISTRY:

    from backend.document_processing.recruitment_processor import RecruitmentProcessor
    from backend.document_processing.hr_processor import HRProcessor
    from backend.document_processing.sales_processor import SalesProcessor
    from backend.document_processing.research_processor import ResearchProcessor
    from backend.document_processing.performance_processor import PerformanceProcessor

    _PROCESSOR_REGISTRY: dict[BusinessDomain, type[BaseProcessor]] = {
        BusinessDomain.RECRUITMENT: RecruitmentProcessor,
        BusinessDomain.HR: HRProcessor,
        BusinessDomain.SALES: SalesProcessor,
        BusinessDomain.RESEARCH: ResearchProcessor,
        BusinessDomain.PERFORMANCE: PerformanceProcessor,
    }

No registration function, no import-time wiring — the registry itself
remains the single source of routing truth.

Usage (by the future DocumentService)
----------------------------------------
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

# ==============================================================
# ROUTING TABLE
# ==============================================================
# Intentionally empty for Milestone 2. Populated as an explicit literal
# mapping once concrete domain processors exist (see the Milestone 3
# plan in the module docstring above).

# Milestone 3
#
# _PROCESSOR_REGISTRY = {
#     BusinessDomain.RECRUITMENT: RecruitmentProcessor,
#     BusinessDomain.HR: HRProcessor,
#     BusinessDomain.SALES: SalesProcessor,
#     BusinessDomain.RESEARCH: ResearchProcessor,
#     BusinessDomain.PERFORMANCE: PerformanceProcessor,
# }

_PROCESSOR_REGISTRY: dict[BusinessDomain, type[BaseProcessor]] = {}


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
        NotImplementedError: If no processor has been implemented yet
                              for that business domain. This is the
                              expected outcome for every domain until
                              Milestone 3 adds concrete processors and
                              populates _PROCESSOR_REGISTRY.
    """
    business_domain = classification.business_domain
    processor_class = _PROCESSOR_REGISTRY.get(business_domain)

    if processor_class is None:
        raise NotImplementedError(
            f"No processor has been implemented yet for business domain "
            f"'{business_domain.value}'. Domain processors are introduced "
            f"in Milestone 3."
        )

    return processor_class
