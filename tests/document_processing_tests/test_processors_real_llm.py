"""
Real-LLM integration tests for Milestone 5 domain processors.

These tests:
- call the actual shared LLM
- validate all 8 supported document types
- are intentionally excluded from normal unit-test runs

Run manually with:

    py -m pytest backend/document_processing/tests/test_processors_real_llm.py -v -s

Requirements:
- shared LLM must be available
- Ollama/model configuration must be working
"""

import pytest

from backend.document_processing.document_models import DocumentMetadata
from backend.document_processing.hr_processor import HRProcessor
from backend.document_processing.performance_processor import PerformanceProcessor
from backend.document_processing.recruitment_processor import RecruitmentProcessor
from backend.document_processing.research_processor import ResearchProcessor
from backend.document_processing.sales_processor import SalesProcessor


# ==============================================================
# TEST DATA
# ==============================================================

RESUME_CONTENT = """
Arjun Mehta
Email: arjun.mehta@example.com
Phone: +91 98765 43210

Professional Summary:
Software engineer with 4 years of experience building backend systems
and AI-powered applications.

Skills:
Python, FastAPI, MongoDB, Docker, Git, REST APIs, Machine Learning

Experience:
Backend Engineer at TechNova Solutions — 2022 to Present
Developed REST APIs using FastAPI and MongoDB.
Built document-processing and AI automation systems.

Junior Software Engineer at CodeWorks — 2020 to 2022
Worked on Python backend services and database integrations.

Target Role:
Senior Backend Engineer
"""


PRODUCT_CONTENT = """
Product Name: SalesFlow AI

SalesFlow AI is an AI-powered sales automation platform for B2B teams.
It helps sales teams identify prospects, generate personalized outreach,
track campaigns, and improve conversion rates.

Customer Pain Points:
- Manual prospect research takes too much time
- Sales outreach is difficult to personalize at scale
- Teams struggle to track campaign performance

Target Industries:
SaaS, Financial Services, E-commerce

Category:
Sales Automation Software

Price Range:
₹40,000 to ₹1,50,000 per month depending on company size.
"""


HR_METRICS_CONTENT = """
HR Performance Report — Q2 2026

Total employee count: 245

The average employee performance rating was 4.1 out of 5.
The organization achieved an 84% goal completion rate.

Employee satisfaction improved to 8.3 out of 10.

Quarterly attrition rate was 4.5%.
Training completion reached 92%.

There were 18 internal promotions during the quarter.

Additional finding:
Average employee tenure increased to 3.8 years.
"""


SALES_REPORT_CONTENT = """
Sales Performance Report — Q2 2026

Total revenue for the quarter was ₹1.8 crore.

The sales team closed 42 deals.

The active sales pipeline is currently valued at ₹4.2 crore.

Overall win rate was 24%.

The team sent 3,400 outreach messages and booked 186 product demos.

Compared with Q1, revenue increased by 16%.
"""


MARKET_RESEARCH_CONTENT = """
Market Research Report: AI Sales Automation Market in India

The AI sales automation market is growing rapidly as B2B companies
seek to reduce manual prospecting and improve outreach personalization.

Major competitors mentioned in the market include Salesforce,
HubSpot, Apollo.io, and Zoho CRM.

Key findings:
- Mid-sized SaaS companies are adopting AI outreach tools rapidly.
- Buyers value CRM integration and personalized messaging.
- Data privacy remains a major concern for enterprise customers.
- Companies prefer platforms that combine research, outreach,
  and analytics.

Important focus areas include market growth, competitor positioning,
customer adoption, pricing, and data privacy.
"""


PERFORMANCE_REVIEW_CONTENT = """
Employee Performance Review — Q2 2026

The employee delivered all major backend milestones on schedule and
showed strong ownership of the document ingestion project.

Strengths:
- Strong backend architecture skills
- Reliable delivery
- Good debugging ability
- Effective collaboration with team members

Weaknesses:
- Technical documentation should be updated more consistently
- Task estimation can improve

Goals referenced:
- Complete document ingestion backend
- Improve automated test coverage

Overall Rating: 4.3 out of 5
"""


SELF_ASSESSMENT_CONTENT = """
Employee Self Assessment — Q2 2026

During this review period, I completed the authentication and RBAC
system, MongoDB migration, workflow approval improvements, and the
document ingestion architecture.

My main achievements were:
- Completing backend milestones on time
- Improving workflow reliability
- Adding automated tests
- Solving several integration issues

My strengths are backend problem solving, persistence, and learning
new systems quickly.

I want to improve my frontend knowledge, technical documentation,
and effort estimation.
"""


MANAGER_EVALUATION_CONTENT = """
Manager Evaluation — Q2 2026

The employee performed strongly during the quarter and completed
several important backend milestones.

Strengths:
- Strong technical ownership
- Good debugging and problem-solving ability
- Consistent delivery
- Learns unfamiliar systems quickly

Concerns:
- Documentation should be maintained more consistently
- Estimates should include more time for integration testing

Recommended Rating: 4.2 out of 5

The employee is ready to take ownership of larger backend features.
"""


# ==============================================================
# METADATA HELPER
# ==============================================================

from datetime import datetime, timezone

from backend.document_processing.document_models import (
    DocumentMetadata,
    DocumentStatus,
)


def make_metadata(document_type: str) -> DocumentMetadata:
    return DocumentMetadata(
        document_id=f"real-llm-test-{document_type}",
        original_filename=f"{document_type}.txt",
        content_type="text/plain",
        size_bytes=1000,
        uploaded_by="integration-test",
        uploaded_at=datetime.now(timezone.utc).isoformat(),
        status=DocumentStatus.CLASSIFIED,
        document_type=document_type,
    )


# ==============================================================
# ASSERTION HELPER
# ==============================================================

def assert_valid_result(result, expected_document_type: str):
    print("\n")
    print("=" * 80)
    print(f"DOCUMENT TYPE: {expected_document_type}")
    print("=" * 80)
    print(result.model_dump_json(indent=2))

    assert result.document_type == expected_document_type
    assert result.extracted_data
    assert isinstance(result.extracted_data, dict)
    assert result.ai_summary
    assert result.ai_summary.strip()

    if result.confidence is not None:
        assert 0.0 <= result.confidence <= 1.0


# ==============================================================
# REAL LLM TESTS
# ==============================================================

@pytest.mark.integration
def test_real_llm_resume():
    result = RecruitmentProcessor().run(
        RESUME_CONTENT,
        make_metadata("resume"),
    )

    assert_valid_result(result, "resume")

    assert result.extracted_data["name"]
    assert result.extracted_data["skills"]


@pytest.mark.integration
def test_real_llm_product_information():
    result = SalesProcessor().run(
        PRODUCT_CONTENT,
        make_metadata("product_information"),
    )

    assert_valid_result(result, "product_information")

    assert result.extracted_data["product_name"]


@pytest.mark.integration
def test_real_llm_hr_metrics_report():
    result = HRProcessor().run(
        HR_METRICS_CONTENT,
        make_metadata("hr_metrics_report"),
    )

    assert_valid_result(result, "hr_metrics_report")

    assert any(
        value is not None and value != {} and value != []
        for value in result.extracted_data.values()
    )


@pytest.mark.integration
def test_real_llm_sales_performance_report():
    result = SalesProcessor().run(
        SALES_REPORT_CONTENT,
        make_metadata("sales_performance_report"),
    )

    assert_valid_result(result, "sales_performance_report")

    assert any(
        value is not None and value != {} and value != []
        for value in result.extracted_data.values()
    )


@pytest.mark.integration
def test_real_llm_market_research_report():
    result = ResearchProcessor().run(
        MARKET_RESEARCH_CONTENT,
        make_metadata("market_research_report"),
    )

    assert_valid_result(result, "market_research_report")

    assert (
        result.extracted_data["key_findings"]
        or result.extracted_data["market_overview"]
    )


@pytest.mark.integration
def test_real_llm_performance_review():
    result = PerformanceProcessor().run(
        PERFORMANCE_REVIEW_CONTENT,
        make_metadata("performance_review"),
    )

    assert_valid_result(result, "performance_review")

    assert (
        result.extracted_data["strengths"]
        or result.extracted_data["weaknesses"]
    )


@pytest.mark.integration
def test_real_llm_self_assessment():
    result = PerformanceProcessor().run(
        SELF_ASSESSMENT_CONTENT,
        make_metadata("self_assessment"),
    )

    assert_valid_result(result, "self_assessment")

    assert (
        result.extracted_data["self_reported_achievements"]
        or result.extracted_data["self_identified_strengths"]
        or result.extracted_data["self_identified_growth_areas"]
    )


@pytest.mark.integration
def test_real_llm_manager_evaluation():
    result = PerformanceProcessor().run(
        MANAGER_EVALUATION_CONTENT,
        make_metadata("manager_evaluation"),
    )

    assert_valid_result(result, "manager_evaluation")

    assert (
        result.extracted_data["manager_comments"]
        or result.extracted_data["strengths"]
        or result.extracted_data["concerns"]
    )