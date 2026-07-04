"""
Real-LLM integration tests for DocumentClassifier.

Validates the document-verification boundary:

1. Clearly supported documents must classify successfully.
2. Clearly unrelated documents must be rejected as unsupported.
3. Ambiguous business content should be rejected rather than forced
   into the closest supported document type.

Run manually with:

    py -m pytest backend/document_processing/tests/test_classifier_real_llm.py -v -s

These tests call the real shared LLM.
"""

from datetime import datetime, timezone

import pytest

from backend.document_processing.document_classifier import (
    ClassificationError,
    DocumentClassifier,
)
from backend.document_processing.document_models import (
    ClassificationResult,
    DocumentMetadata,
    DocumentStatus,
)


# ==============================================================
# METADATA HELPER
# ==============================================================

def make_metadata(filename: str) -> DocumentMetadata:
    return DocumentMetadata(
        document_id=f"real-classifier-test-{filename}",
        original_filename=filename,
        content_type="text/plain",
        size_bytes=1000,
        uploaded_by="integration-test",
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        status=DocumentStatus.UPLOADED,
    )


# ==============================================================
# SUPPORTED DOCUMENTS
# ==============================================================

SUPPORTED_CASES = [
    (
        "resume.txt",
        """
        Arjun Mehta
        Email: arjun.mehta@example.com

        Professional Summary:
        Software engineer with 4 years of backend development experience.

        Skills:
        Python, FastAPI, MongoDB, Docker

        Experience:
        Backend Engineer at TechNova Solutions — 2022 to Present.

        Target Role:
        Senior Backend Engineer
        """,
        "resume",
    ),
    (
        "hr_q2_report.txt",
        """
        HR Performance Report — Q2 2026

        Total employee count: 245.
        Average employee performance rating: 4.1 out of 5.
        Goal completion rate: 84%.
        Employee satisfaction score: 8.3 out of 10.
        Quarterly attrition rate: 4.5%.
        Training completion rate: 92%.
        Internal promotions: 18.
        """,
        "hr_metrics_report",
    ),
    (
        "product_overview.txt",
        """
        Product Name: SalesFlow AI

        SalesFlow AI is an AI-powered sales automation platform for
        B2B teams.

        Customer Pain Points:
        - Manual prospect research takes too much time.
        - Outreach is difficult to personalize at scale.

        Target Industries:
        SaaS, Financial Services, E-commerce

        Category:
        Sales Automation Software

        Price Range:
        ₹40,000 to ₹1,50,000 per month.
        """,
        "product_information",
    ),
]


@pytest.mark.integration
@pytest.mark.parametrize(
    "filename,content,expected_type",
    SUPPORTED_CASES,
)
def test_supported_document_is_classified(
    filename: str,
    content: str,
    expected_type: str,
):
    classifier = DocumentClassifier()

    result = classifier.classify(
        content,
        make_metadata(filename),
    )

    print("\n")
    print("=" * 80)
    print(f"SUPPORTED DOCUMENT: {filename}")
    print("=" * 80)
    print(result.model_dump_json(indent=2))

    assert isinstance(result, ClassificationResult)
    assert result.document_type == expected_type
    assert 0.0 <= result.confidence <= 1.0
    assert result.confidence >= 0.60


# ==============================================================
# CLEARLY UNSUPPORTED DOCUMENTS
# ==============================================================

UNSUPPORTED_CASES = [
    (
        "pasta_recipe.txt",
        """
        Creamy Garlic Pasta Recipe

        Ingredients:
        - 250 grams pasta
        - 4 cloves garlic
        - 2 tablespoons butter
        - 1 cup cream
        - Parmesan cheese
        - Salt and pepper

        Instructions:
        Boil the pasta until al dente. Melt butter in a pan and sauté
        the garlic. Add cream and simmer. Mix in the pasta and finish
        with Parmesan cheese.
        """,
    ),
    (
        "invoice_1042.txt",
        """
        INVOICE #1042

        Seller: ABC Office Supplies
        Customer: Sunrise Technologies

        Invoice Date: 2 July 2026

        Items:
        10 Wireless Keyboards     ₹25,000
        10 Wireless Mice          ₹12,000
        5 USB-C Hubs              ₹15,000

        Subtotal: ₹52,000
        GST: ₹9,360
        Total Amount Due: ₹61,360

        Payment Terms: Net 30 days
        """,
    ),
    (
        "python_source_code.txt",
        """
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/health")
        def health_check():
            return {
                "status": "healthy",
                "service": "example-api"
            }

        @app.get("/users/{user_id}")
        def get_user(user_id: str):
            return {"user_id": user_id}
        """,
    ),
    (
        "history_essay.txt",
        """
        The Industrial Revolution transformed manufacturing and society
        during the eighteenth and nineteenth centuries.

        The introduction of steam power enabled factories to produce
        goods at a scale that had previously been impossible. Cities
        grew rapidly as workers moved from rural areas to industrial
        centers.

        These changes also created difficult working conditions and
        contributed to the development of labor reform movements.
        """,
    ),
    (
        "news_article.txt",
        """
        Heavy rainfall affected several districts on Thursday, causing
        traffic delays and temporary disruptions to public transport.

        Local authorities advised residents to avoid waterlogged roads.
        Emergency teams were deployed to several affected areas.

        Weather officials said conditions are expected to improve over
        the next two days.
        """,
    ),
]


@pytest.mark.integration
@pytest.mark.parametrize(
    "filename,content",
    UNSUPPORTED_CASES,
)
def test_unwanted_document_is_rejected(
    filename: str,
    content: str,
):
    classifier = DocumentClassifier()

    print("\n")
    print("=" * 80)
    print(f"UNSUPPORTED DOCUMENT: {filename}")
    print("=" * 80)

    try:
        result = classifier.classify(
            content,
            make_metadata(filename),
        )
    except ClassificationError as exc:
        print(f"REJECTED: {exc}")
        return

    print("INCORRECTLY ACCEPTED:")
    print(result.model_dump_json(indent=2))

    pytest.fail(
        f"Expected '{filename}' to be rejected, but it was classified "
        f"as '{result.document_type}' with confidence {result.confidence:.2f}"
    )


# ==============================================================
# AMBIGUOUS DOCUMENTS
# ==============================================================

AMBIGUOUS_CASES = [
    (
        "company_brochure.txt",
        """
        NovaCore Technologies

        We help modern businesses improve efficiency through cloud
        technology, automation, analytics, and consulting services.

        Our teams work with organizations across multiple industries.
        We focus on innovation, customer success, and long-term digital
        transformation.

        Contact our team to learn more about our capabilities.
        """,
    ),
    (
        "business_notes.txt",
        """
        Meeting Notes

        The team discussed growth opportunities for the next quarter.

        Customer engagement needs improvement.
        Several competitors are becoming more active.
        The company should improve internal efficiency and explore new
        markets.

        More analysis is required before making a final decision.
        """,
    ),
    (
        "employee_profile.txt",
        """
        Priya Sharma works in the engineering department.

        She enjoys solving technical problems and has experience with
        Python and databases. Her colleagues describe her as reliable
        and collaborative.

        Priya joined the organization several years ago and currently
        works on internal technology projects.
        """,
    ),
]


@pytest.mark.integration
@pytest.mark.parametrize(
    "filename,content",
    AMBIGUOUS_CASES,
)
def test_ambiguous_document_is_rejected(
    filename: str,
    content: str,
):
    classifier = DocumentClassifier()

    print("\n")
    print("=" * 80)
    print(f"AMBIGUOUS DOCUMENT: {filename}")
    print("=" * 80)

    try:
        result = classifier.classify(
            content,
            make_metadata(filename),
        )
    except ClassificationError as exc:
        print(f"REJECTED: {exc}")
        return

    print("INCORRECTLY ACCEPTED:")
    print(result.model_dump_json(indent=2))

    pytest.fail(
        f"Expected '{filename}' to be rejected, but it was classified "
        f"as '{result.document_type}' with confidence {result.confidence:.2f}"
    )