"""
Agent Router
============

Single responsibility: map ``task.agent`` to the concrete ``BaseAgent``
subclass instance that knows how to execute that task.

This module is a pure dispatch table. It performs NO task execution,
NO state mutation, NO approval handling, NO data access, and NO
business/enrichment logic. All of that lives in the agent
implementations themselves (see ``agent_responsibilities.md`` and
``task_contracts.md``) or in the Workflow Executor
(``workflow_state.md``).

Contract
--------
    def get_agent(task: Task) -> BaseAgent

The Workflow Executor's ``_execute_loop`` calls ``get_agent(task)`` for
every task whose ``agent`` field is NOT ``"human"`` (human approval
gates are identified and handled directly by the executor — see
``workflow_state.md``, Section 6.1, and ``agent_responsibilities.md``,
Section 6).

Raises
------
ValueError
    - If ``task.agent == "human"``. Human gates are not agents and
      must never reach this router.
    - If ``task.agent`` is any other string not present in
      ``_AGENT_MAP``.

Both ``ValueError`` cases are caught by the Workflow Executor's
execution loop and converted into a terminal ``"failed"`` state
*before* any agent is invoked (``workflow_state.md``, Section 8.2).
"""

from backend.models import Task

from backend.agent_nodes.base_agent import BaseAgent
from backend.agent_nodes.recruitment_agent import RecruitmentAgent
from backend.agent_nodes.hr_agent import HRAgent
from backend.agent_nodes.sales_agent import SalesAgent
from backend.agent_nodes.research_agent import ResearchAgent
from backend.agent_nodes.reporting_agent import ReportingAgent

# ==========================================================
# AGENT TYPE -> AGENT CLASS MAPPING
# ==========================================================
#
# Keys are the literal values that appear in Task.agent across
# workflow_definitions.py:
#
#   "recruitment" -> hire_employee
#   "hr"          -> onboard_employee, performance_report, performance_review
#   "sales"       -> sales_outreach, performance_report
#   "research"    -> sales_outreach, market_research
#   "reporting"   -> all six workflows
#
# "human" is intentionally NOT a key here. It identifies the
# manager_approval gate (hire_employee / t6), which is a Workflow
# Executor checkpoint, not an agent (agent_responsibilities.md,
# Section 6; workflow_state.md, Section 6.1). It is rejected
# explicitly in get_agent() below rather than falling through to the
# generic "unknown agent type" error, so the failure message is
# unambiguous.

_AGENT_MAP: dict[str, type[BaseAgent]] = {
    "recruitment": RecruitmentAgent,
    "hr": HRAgent,
    "sales": SalesAgent,
    "research": ResearchAgent,
    "reporting": ReportingAgent,
}


# ==========================================================
# PUBLIC ENTRY POINT
# ==========================================================

def get_agent(task: Task) -> BaseAgent:
    """
    Resolve a Task to the BaseAgent subclass instance responsible for
    executing it.

    This function performs routing only. It does not call
    ``agent.run()``, inspect ``task.action``, or touch ``AgentState`` —
    that is the Workflow Executor's job once it has the returned agent.

    Instantiation strategy (MVP): a fresh, stateless instance is
    created on every call. Agents hold no per-call state of their own;
    all context flows through the ``AgentState`` argument passed to
    ``run()`` by the executor.

    Args:
        task: The Task about to be dispatched. Only ``task.agent`` (and,
            for error messages, ``task.task_id``) are inspected.

    Returns:
        A new instance of the ``BaseAgent`` subclass matching
        ``task.agent``.

    Raises:
        ValueError: If ``task.agent == "human"`` — human approval gates
            are handled by the Workflow Executor, not routed here.
        ValueError: If ``task.agent`` does not match any key in
            ``_AGENT_MAP``.
    """
    if task.agent == "human":
        raise ValueError(
            f"Task '{task.task_id}' has agent='human' — human approval "
            "gates are handled by the Workflow Executor and must not be "
            "routed through get_agent()."
        )

    agent_class = _AGENT_MAP.get(task.agent)

    if agent_class is None:
        raise ValueError(
            f"Unknown agent type: '{task.agent}' for task '{task.task_id}'. "
            f"Expected one of: {sorted(_AGENT_MAP.keys())}."
        )

    return agent_class()