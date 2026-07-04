"""
test_milestone6_6_document_access.py
====================================
Focused tests for M6.6 — Workflow Document Access / Selection.

Suggested location:
    tests/document_processing_tests/test_milestone6_6_document_access.py

Covers:
- explicit workflow-source selection;
- atomic rejection of invalid selections;
- entity-linked resolution;
- correct Performance Report type restrictions;
- hire_employee shortlisted-resume resolution;
- t5 lightweight resume-summary helper;
- DataLoader selected-document access enforcement.

These tests use mocks only and should not require MongoDB, file storage,
or a real LLM.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from backend.models import (
    AgentState,
    MarketResearchParams,
    PerformanceReportParams,
    SalesOutreachParams,
)
from backend.services.document_access_exceptions import (
    DocumentNotSelectedError,
)
from backend.execution import workflow_document_resolution as resolution


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state(*, document_ids: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        workflow_id="wf_test",
        document_ids=document_ids or [],
    )


# ---------------------------------------------------------------------------
# workflow_document_resolution.py
# ---------------------------------------------------------------------------

def test_market_research_uses_explicit_selection_and_correct_allowed_type():
    params = MarketResearchParams(
        research_topic="AI adoption",
        competitors=["Competitor A"],
        focus_areas=["market size"],
        output_format="report",
        document_ids=["doc_1", "doc_2"],
    )

    with patch.object(
        resolution._document_context_service,
        "validate_workflow_source_selection",
        return_value=["doc_1", "doc_2"],
    ) as validate:
        result = resolution.resolve_market_research_documents(params)

    assert result == ["doc_1", "doc_2"]
    validate.assert_called_once_with(
        ["doc_1", "doc_2"],
        workflow_slot="market_research",
        allowed_document_types={"market_research_report"},
    )


def test_market_research_invalid_explicit_selection_fails_atomically():
    params = MarketResearchParams(
        research_topic="AI adoption",
        competitors=["Competitor A"],
        focus_areas=["market size"],
        output_format="report",
        document_ids=["good_doc", "bad_doc"],
    )

    with patch.object(
        resolution._document_context_service,
        "validate_workflow_source_selection",
        side_effect=ValueError("invalid supplied document"),
    ):
        with pytest.raises(ValueError, match="invalid supplied document"):
            resolution.resolve_market_research_documents(params)


def test_performance_report_uses_registry_sales_type_and_deduplicates():
    params = PerformanceReportParams(
        report_period="Q2 2026",
        departments=["HR", "Sales"],
        metrics_to_include=["headcount", "revenue"],
        report_type="quarterly",
        hr_document_ids=["hr_1", "shared"],
        sales_document_ids=["sales_1", "shared"],
    )

    def validate(ids, *, workflow_slot, allowed_document_types):
        if workflow_slot == "performance_report.hr":
            assert allowed_document_types == {"hr_metrics_report"}
            return ["hr_1", "shared"]
        assert workflow_slot == "performance_report.sales"
        assert allowed_document_types == {"sales_performance_report"}
        return ["sales_1", "shared"]

    with patch.object(
        resolution._document_context_service,
        "validate_workflow_source_selection",
        side_effect=validate,
    ):
        result = resolution.resolve_performance_report_documents(params)

    assert result == ["hr_1", "shared", "sales_1"]


def test_sales_outreach_resolves_product_linked_ids():
    params = SalesOutreachParams(
        target_segment="Mid-market HR teams",
        outreach_channels=["email"],
        campaign_goal="Book product demos",
        product_name="HRTech Pro",
    )

    with (
        patch.object(
            resolution._business_repo,
            "get_product_source_document_ids",
            return_value=["doc_1", "stale_doc"],
        ),
        patch.object(
            resolution._document_context_service,
            "validate_entity_linked_ids",
            return_value=["doc_1"],
        ) as validate,
    ):
        result = resolution.resolve_sales_outreach_documents(params)

    assert result == ["doc_1"]
    validate.assert_called_once_with(
        ["doc_1", "stale_doc"],
        workflow_slot="sales_outreach.product",
    )


def test_sales_outreach_missing_product_is_non_fatal():
    params = SalesOutreachParams(
        target_segment="Mid-market HR teams",
        outreach_channels=["email"],
        campaign_goal="Book product demos",
        product_name="Missing Product",
    )

    with patch.object(
        resolution._business_repo,
        "get_product_source_document_ids",
        side_effect=ValueError("not found"),
    ):
        assert resolution.resolve_sales_outreach_documents(params) == []


def test_hire_employee_resolves_only_shortlisted_candidate_documents():
    shortlisted = [
        {"candidate_id": "cand_1", "name": "Alice"},
        {"candidate_id": "", "name": "Legacy Candidate"},
        {"candidate_id": "cand_2", "name": "Bob"},
    ]

    def linked_ids(candidate_id):
        return {
            "cand_1": ["resume_1", "shared"],
            "cand_2": ["shared", "resume_2"],
        }[candidate_id]

    with (
        patch.object(
            resolution._business_repo,
            "get_candidate_source_document_ids",
            side_effect=linked_ids,
        ),
        patch.object(
            resolution._document_context_service,
            "validate_entity_linked_ids",
            return_value=["resume_1", "shared", "resume_2"],
        ) as validate,
    ):
        result = resolution.resolve_hire_employee_shortlist_documents(shortlisted)

    assert result == ["resume_1", "shared", "resume_2"]
    validate.assert_called_once_with(
        ["resume_1", "shared", "resume_2"],
        workflow_slot="hire_employee.shortlisted_resumes",
    )


def test_hire_employee_candidate_without_source_ids_does_not_fail():
    shortlisted = [{"candidate_id": "cand_1", "name": "Alice"}]

    with (
        patch.object(
            resolution._business_repo,
            "get_candidate_source_document_ids",
            return_value=[],
        ),
        patch.object(
            resolution._document_context_service,
            "validate_entity_linked_ids",
            return_value=[],
        ),
    ):
        assert resolution.resolve_hire_employee_shortlist_documents(shortlisted) == []


def test_resume_summary_helper_only_reads_selected_resume_documents():
    state = _state(document_ids=["resume_1"])
    shortlisted = [
        {"candidate_id": "cand_1", "name": "Alice"},
        {"candidate_id": "cand_2", "name": "Bob"},
    ]

    def linked_ids(candidate_id):
        return {
            "cand_1": ["resume_1"],
            "cand_2": ["resume_2"],
        }[candidate_id]

    with (
        patch.object(
            resolution._business_repo,
            "get_candidate_source_document_ids",
            side_effect=linked_ids,
        ),
        patch(
            "backend.planner.data_loader.get_document_context",
            return_value={"ai_summary": "Strong Python candidate"},
        ) as get_context,
    ):
        result = resolution.build_shortlisted_resume_summaries(
            state,
            shortlisted,
        )

    assert result == {
        "cand_1": {"ai_summary": "Strong Python candidate"}
    }
    get_context.assert_called_once_with(state, "resume_1")


# ---------------------------------------------------------------------------
# data_loader.py access boundary
# ---------------------------------------------------------------------------

def test_data_loader_rejects_document_not_selected_for_workflow():
    from backend.planner import data_loader

    state = _state(document_ids=["allowed_doc"])

    with pytest.raises(DocumentNotSelectedError):
        data_loader.get_document_context(state, "other_doc")


def test_data_loader_allows_selected_document_context():
    from backend.planner import data_loader

    state = _state(document_ids=["doc_1"])
    expected = {
        "document_id": "doc_1",
        "document_type": "market_research_report",
        "ai_summary": "Summary",
        "structured_data": {"finding": "x"},
    }

    with patch.object(
        data_loader._document_context_service,
        "get_lightweight_context",
        return_value=expected,
    ) as get_context:
        result = data_loader.get_document_context(state, "doc_1")

    assert result == expected
    get_context.assert_called_once_with(
        "doc_1",
        allowed_document_ids=["doc_1"],
        workflow_id="wf_test",
    )


# ---------------------------------------------------------------------------
# Initial resolver dispatch
# ---------------------------------------------------------------------------

def test_unknown_objective_has_no_document_resolution():
    assert resolution.resolve_initial_document_ids(
        "onboard_employee",
        SimpleNamespace(),
    ) == []
