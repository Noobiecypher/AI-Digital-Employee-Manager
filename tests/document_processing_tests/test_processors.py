"""Mocked tests for the five domain processors and processor_registry —
no live LLM calls required."""

import json
from unittest.mock import patch

import pytest

from backend.document_processing import (
    hr_processor,
    performance_processor,
    recruitment_processor,
    research_processor,
    sales_processor,
)
from backend.document_processing.base_processor import OutputValidationError
from backend.document_processing.document_models import (
    BusinessDomain,
    ClassificationResult,
    DocumentMetadata,
    DocumentOutcome,
    DocumentStatus,
    ProcessingResult,
)
from backend.document_processing.processor_registry import get_processor_class


def _fake_response(payload: dict):
    class _Resp:
        content = json.dumps(payload)
    return _Resp()


def _metadata(document_type: str, business_domain: BusinessDomain) -> DocumentMetadata:
    return DocumentMetadata(
        document_id="doc-1",
        original_filename="test.pdf",
        content_type="application/pdf",
        size_bytes=100,
        uploaded_by="tester",
        uploaded_at="2026-07-03T00:00:00Z",
        status=DocumentStatus.CLASSIFIED,
        document_type=document_type,
        business_domain=business_domain,
    )


def _classification(business_domain: BusinessDomain) -> ClassificationResult:
    return ClassificationResult(
        document_id="doc-1",
        document_type="whatever",
        business_domain=business_domain,
        outcome=DocumentOutcome.WORKFLOW_SOURCE,
        target_business_entity=None,
        review_required=False,
        confidence=0.9,
        classified_at="2026-07-03T00:00:00Z",
    )


# ---------------- registry routing ----------------

@pytest.mark.parametrize("domain, expected_cls", [
    (BusinessDomain.RECRUITMENT, recruitment_processor.RecruitmentProcessor),
    (BusinessDomain.HR, hr_processor.HRProcessor),
    (BusinessDomain.SALES, sales_processor.SalesProcessor),
    (BusinessDomain.RESEARCH, research_processor.ResearchProcessor),
    (BusinessDomain.PERFORMANCE, performance_processor.PerformanceProcessor),
])
def test_registry_routes_all_domains(domain, expected_cls):
    assert get_processor_class(_classification(domain)) is expected_cls


# ---------------- RecruitmentProcessor ----------------

def test_recruitment_success():
    metadata = _metadata("resume", BusinessDomain.RECRUITMENT)
    payload = {"name": "Jane Doe", "role_applied": "Engineer", "skills": ["Python"],
               "experience_years": 5, "email": "jane@x.com", "phone": "123",
               "summary": "Experienced engineer.",}
    with patch.object(recruitment_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response(payload)
        result = recruitment_processor.RecruitmentProcessor().run("resume text", metadata)
    assert isinstance(result, ProcessingResult)
    assert result.extracted_data["name"] == "Jane Doe"
    assert result.confidence == pytest.approx(1.0)


def test_recruitment_wrong_document_type():
    metadata = _metadata("hr_metrics_report", BusinessDomain.RECRUITMENT)
    with pytest.raises(OutputValidationError):
        recruitment_processor.RecruitmentProcessor().run("text", metadata)


def test_recruitment_missing_name_fails():
    metadata = _metadata("resume", BusinessDomain.RECRUITMENT)
    payload = {"name": "", "skills": [], "confidence": 50}
    with patch.object(recruitment_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response(payload)
        with pytest.raises(OutputValidationError):
            recruitment_processor.RecruitmentProcessor().run("resume text", metadata)


def test_recruitment_malformed_llm_output():
    metadata = _metadata("resume", BusinessDomain.RECRUITMENT)
    with patch.object(recruitment_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response.__wrapped__ if False else type(
            "R", (), {"content": "not json"}
        )()
        with pytest.raises(OutputValidationError):
            recruitment_processor.RecruitmentProcessor().run("resume text", metadata)

def test_recruitment_normalizes_missing_optional_business_fields():
    metadata = _metadata("resume", BusinessDomain.RECRUITMENT)
    payload = {
        "name": "John Smith",
        "role_applied": None,
        "skills": [],
        "experience_years": None,
        "email": None,
        "phone": None,
        "summary": "Candidate profile.",
    }

    with patch.object(recruitment_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response(payload)
        result = recruitment_processor.RecruitmentProcessor().run(
            "resume text",
            metadata,
        )

    assert result.extracted_data == {
        "name": "John Smith",
        "role_applied": None,
        "skills": [],
        "experience_years": 0,
        "email": "",
        "phone": "",
    }


def test_recruitment_preserves_extracted_optional_business_values():
    metadata = _metadata("resume", BusinessDomain.RECRUITMENT)
    payload = {
        "name": "Jane Doe",
        "role_applied": "Engineer",
        "skills": ["Python"],
        "experience_years": 5,
        "email": "jane@example.com",
        "phone": "+91 98765 43210",
        "summary": "Experienced engineer.",
    }

    with patch.object(recruitment_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response(payload)
        result = recruitment_processor.RecruitmentProcessor().run(
            "resume text",
            metadata,
        )

    assert result.extracted_data["experience_years"] == 5
    assert result.extracted_data["email"] == "jane@example.com"
    assert result.extracted_data["phone"] == "+91 98765 43210"

# ---------------- HRProcessor ----------------

def test_hr_success():
    metadata = _metadata("hr_metrics_report", BusinessDomain.HR)
    payload = {"employee_count": 120, "confidence": 80}
    with patch.object(hr_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response(payload)
        result = hr_processor.HRProcessor().run("report text", metadata)
    assert result.extracted_data["employee_count"] == 120


def test_hr_empty_metrics_fails():
    metadata = _metadata("hr_metrics_report", BusinessDomain.HR)
    payload = {"confidence": 50}
    with patch.object(hr_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response(payload)
        with pytest.raises(OutputValidationError):
            hr_processor.HRProcessor().run("report text", metadata)


def test_hr_wrong_document_type():
    metadata = _metadata("sales_performance_report", BusinessDomain.HR)
    with pytest.raises(OutputValidationError):
        hr_processor.HRProcessor().run("text", metadata)


# ---------------- SalesProcessor ----------------

def test_sales_product_success():
    metadata = _metadata("product_information", BusinessDomain.SALES)
    payload = {"product_name": "Acme Suite", "confidence": 70}
    with patch.object(sales_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response(payload)
        result = sales_processor.SalesProcessor().run("doc text", metadata)
    assert result.extracted_data["product_name"] == "Acme Suite"


def test_sales_product_missing_name_fails():
    metadata = _metadata("product_information", BusinessDomain.SALES)
    payload = {"product_name": "", "confidence": 50}
    with patch.object(sales_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response(payload)
        with pytest.raises(OutputValidationError):
            sales_processor.SalesProcessor().run("doc text", metadata)


def test_sales_report_success():
    metadata = _metadata("sales_performance_report", BusinessDomain.SALES)
    payload = {"revenue": "₹1.2Cr", "deals_won": 24, "confidence": 85}
    with patch.object(sales_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response(payload)
        result = sales_processor.SalesProcessor().run("report text", metadata)
    assert result.extracted_data["revenue"] == "₹1.2Cr"
    assert result.extracted_data["deals_won"] == 24


def test_sales_report_empty_metrics_fails():
    metadata = _metadata("sales_performance_report", BusinessDomain.SALES)
    payload = {"confidence": 50}
    with patch.object(sales_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response(payload)
        with pytest.raises(OutputValidationError):
            sales_processor.SalesProcessor().run("report text", metadata)


def test_sales_unsupported_type():
    metadata = _metadata("resume", BusinessDomain.SALES)
    with pytest.raises(OutputValidationError):
        sales_processor.SalesProcessor().run("text", metadata)


# ---------------- ResearchProcessor ----------------

def test_research_success():
    metadata = _metadata("market_research_report", BusinessDomain.RESEARCH)
    payload = {"key_findings": ["Finding one"], "confidence": 75}
    with patch.object(research_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response(payload)
        result = research_processor.ResearchProcessor().run("report text", metadata)
    assert result.extracted_data["key_findings"] == ["Finding one"]


def test_research_empty_findings_fails():
    metadata = _metadata("market_research_report", BusinessDomain.RESEARCH)
    payload = {"confidence": 50}
    with patch.object(research_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response(payload)
        with pytest.raises(OutputValidationError):
            research_processor.ResearchProcessor().run("report text", metadata)


# ---------------- PerformanceProcessor ----------------

@pytest.mark.parametrize("doc_type, payload", [
    ("performance_review", {"strengths": ["Good communicator"], "confidence": 80}),
    ("self_assessment", {"self_reported_achievements": ["Shipped feature X"], "confidence": 80}),
    ("manager_evaluation", {"manager_comments": "Solid quarter.", "confidence": 80}),
])
def test_performance_success(doc_type, payload):
    metadata = _metadata(doc_type, BusinessDomain.PERFORMANCE)
    with patch.object(performance_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response(payload)
        result = performance_processor.PerformanceProcessor().run("doc text", metadata)
    assert isinstance(result, ProcessingResult)


@pytest.mark.parametrize("doc_type", ["performance_review", "self_assessment", "manager_evaluation"])
def test_performance_empty_evidence_fails(doc_type):
    metadata = _metadata(doc_type, BusinessDomain.PERFORMANCE)
    payload = {"confidence": 50}
    with patch.object(performance_processor, "llm") as mock_llm:
        mock_llm.invoke.return_value = _fake_response(payload)
        with pytest.raises(OutputValidationError):
            performance_processor.PerformanceProcessor().run("doc text", metadata)


def test_performance_unsupported_type():
    metadata = _metadata("resume", BusinessDomain.PERFORMANCE)
    with pytest.raises(OutputValidationError):
        performance_processor.PerformanceProcessor().run("text", metadata)