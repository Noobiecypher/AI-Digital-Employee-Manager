"""
workflow_document_resolution.py
================================
M6.6 — Executor-owned document ID resolution for AgentState.document_ids.

Called ONLY by workflow_executor.py:
  - resolve_initial_document_ids()                  at initialize_state()
  - resolve_hire_employee_shortlist_documents()      after t3 completes

This is the single place workflow-specific document resolution policy
lives, so state mutation stays centralized instead of scattered across
agents or _execute_loop. No AgentState mutation happens here — every
function is a pure "params/output in, list[str] document_ids out"
resolver. The executor is the sole writer that assigns the result to
state.document_ids.

Two resolution mechanisms (ref: M6.6 architecture):
  A. Entity-linked  -> BusinessDataRepository lookup, then
     DocumentContextService.validate_entity_linked_ids() (silently drops
     stale/invalid IDs; never fails workflow init).
  B. Explicit workflow-source selection -> DocumentContextService.
     validate_workflow_source_selection() (atomic failure on ANY
     invalid supplied ID — raises before workflow execution begins).
"""

from __future__ import annotations

from backend.database.business_data_repository import BusinessDataRepository
from backend.services.document_context_service import DocumentContextService
from backend.models import (
    SalesOutreachParams,
    MarketResearchParams,
    PerformanceReviewParams,
    PerformanceReportParams,
)

# ------------------------------------------------------------------
# DOCUMENT TYPE ELIGIBILITY — workflow-source slots only.
# ------------------------------------------------------------------
# 'market_research_report' is specified directly by the M6.6 spec.
#
# COMPATIBILITY FLAG: the HR/Sales metrics type strings below are a
# best-effort default (document_registry.py was not available to confirm
# exact registry values). Update ONLY this dict once confirmed — no
# other M6.6 code needs to change.
MARKET_RESEARCH_ALLOWED_TYPES = {"market_research_report"}
PERFORMANCE_REPORT_HR_ALLOWED_TYPES = {"hr_metrics_report"}
PERFORMANCE_REPORT_SALES_ALLOWED_TYPES = {"sales_performance_report"}


_business_repo = BusinessDataRepository()
_document_context_service = DocumentContextService()


# ------------------------------------------------------------------
# INITIAL RESOLUTION (workflow initialization time)
# ------------------------------------------------------------------

def resolve_sales_outreach_documents(params: SalesOutreachParams) -> list[str]:
    """Entity-linked: Product.source_document_ids -> validated IMPORTED IDs.
    No linked Product documents is valid and returns []."""
    if not params.product_name:
        return []
    try:
        linked_ids = _business_repo.get_product_source_document_ids(params.product_name)
    except ValueError:
        return []
    return _document_context_service.validate_entity_linked_ids(
        linked_ids, workflow_slot="sales_outreach.product"
    )


def resolve_market_research_documents(params: MarketResearchParams) -> list[str]:
    """Explicit workflow-source selection. Empty selection is valid (runs
    exactly as before). Any invalid supplied ID fails atomically."""
    return _document_context_service.validate_workflow_source_selection(
        list(params.document_ids),
        workflow_slot="market_research",
        allowed_document_types=MARKET_RESEARCH_ALLOWED_TYPES,
    )


def resolve_performance_review_documents(params: PerformanceReviewParams) -> list[str]:
    """Entity-linked: evidence attached to the EXACT Goal for
    employee_name + review_period only. No evidence is valid and returns []."""
    try:
        evidence_ids = _business_repo.get_goal_evidence_document_ids(
            params.employee_name, params.review_period
        )
    except ValueError:
        return []
    return _document_context_service.validate_entity_linked_ids(
        evidence_ids, workflow_slot="performance_review.goal_evidence"
    )


def resolve_performance_report_documents(params: PerformanceReportParams) -> list[str]:
    """Explicit workflow-source selection, two independently and atomically
    validated slots (hr_document_ids, sales_document_ids), combined and
    deduplicated for storage in state.document_ids. Task routing (which
    slot goes to t1 vs t2) is done by the HR/Sales agents reading
    params.hr_document_ids / params.sales_document_ids directly — this
    combined list only grants access via DataLoader."""
    hr_ids = _document_context_service.validate_workflow_source_selection(
        list(params.hr_document_ids),
        workflow_slot="performance_report.hr",
        allowed_document_types=PERFORMANCE_REPORT_HR_ALLOWED_TYPES,
    )
    sales_ids = _document_context_service.validate_workflow_source_selection(
        list(params.sales_document_ids),
        workflow_slot="performance_report.sales",
        allowed_document_types=PERFORMANCE_REPORT_SALES_ALLOWED_TYPES,
    )
    return list(dict.fromkeys([*hr_ids, *sales_ids]))


_INITIAL_RESOLVERS = {
    "sales_outreach": resolve_sales_outreach_documents,
    "market_research": resolve_market_research_documents,
    "performance_review": resolve_performance_review_documents,
    "performance_report": resolve_performance_report_documents,
}


def resolve_initial_document_ids(objective_id: str, params) -> list[str]:
    """
    Dispatch to the correct resolver at workflow initialization.

    hire_employee is NOT handled here (shortlisted Candidates are unknown
    until t3 — see resolve_hire_employee_shortlist_documents).
    onboard_employee has no M6.6 document integration and is also absent.
    Any other objective_id returns [] (no document resolution defined).
    """
    resolver = _INITIAL_RESOLVERS.get(objective_id)
    if resolver is None:
        return []
    return resolver(params)


# ------------------------------------------------------------------
# HIRE EMPLOYEE — POST-T3 RESOLUTION
# ------------------------------------------------------------------

def resolve_hire_employee_shortlist_documents(
    shortlisted_candidates: list[dict],
) -> list[str]:
    """
    Entity-linked: resume/source document IDs for ONLY the shortlisted
    Candidates from t3's output — never all applicants, never rejected
    candidates, never loaded before t3 completes.

    Args:
        shortlisted_candidates: state.outputs["t3"]["shortlisted_candidates"],
                                  each a Candidate.model_dump() dict carrying
                                  "candidate_id" (M6.6 addition to the
                                  Candidate output model).

    Returns:
        Deduplicated, order-preserved, IMPORTED-validated document IDs.
        [] if no shortlisted candidate has resolvable resume documents
        (this is the current expected outcome until Candidate creation
        starts stamping source_document_ids — see BusinessDataRepository.
        get_candidate_source_document_ids docstring).
    """
    all_ids: list[str] = []

    for candidate in shortlisted_candidates:
        candidate_id = candidate.get("candidate_id")
        if not candidate_id:
            # No stable identity available (legacy/mock candidate record) —
            # nothing trusted to resolve against; skip rather than guess.
            continue
        try:
            linked_ids = _business_repo.get_candidate_source_document_ids(candidate_id)
        except ValueError:
            continue
        all_ids.extend(linked_ids)

    deduped = list(dict.fromkeys(all_ids))
    return _document_context_service.validate_entity_linked_ids(
        deduped, workflow_slot="hire_employee.shortlisted_resumes"
    )


# ------------------------------------------------------------------
# HIRE EMPLOYEE — T5 HUMAN GATE RESUME SUMMARIES
# ------------------------------------------------------------------
#
# NOTE: this helper is self-contained and ready to call, but wiring its
# output into the actual t5 human-approval API response requires the
# human-approval context builder file, which was not part of this pass.
# Call it from wherever that response is assembled, passing the current
# AgentState.

def build_shortlisted_resume_summaries(state, shortlisted_candidates: list[dict]) -> dict[str, dict]:
    """
    Build a candidate_id -> lightweight resume context map for the t5
    human review gate. Never includes full resume text or file bytes —
    only AI summary + structured data, via DataLoader's lightweight
    context path. Candidates with no resolvable resume document (no
    candidate_id, or no linked/valid document) are simply absent from
    the map rather than raising, since resume context is supplementary
    to the shortlist itself.

    Args:
        state: The current AgentState (post-t3), already carrying the
                resolved shortlist resume IDs in state.document_ids.
        shortlisted_candidates: t3's output list of Candidate dicts.

    Returns:
        {candidate_id: lightweight_context_dict, ...} — only for
        candidates whose resume document is present and valid.
    """
    from backend.planner.data_loader import get_document_context

    summaries: dict[str, dict] = {}
    for candidate in shortlisted_candidates:
        candidate_id = candidate.get("candidate_id")
        if not candidate_id:
            continue
        try:
            linked_ids = _business_repo.get_candidate_source_document_ids(candidate_id)
        except ValueError:
            continue
        for doc_id in linked_ids:
            if doc_id not in state.document_ids:
                continue
            try:
                summaries[candidate_id] = get_document_context(state, doc_id)
            except Exception:
                continue
            break  # one resume summary per candidate is enough for the gate
    return summaries
