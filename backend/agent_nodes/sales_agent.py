"""
backend/agent_nodes/sales_agent.py
==================================
Sales Agent (Person 3).

Per workflow_definitions.py, the "sales" agent owns these actions:

  sales_outreach:
    t3 create_outreach_strategy -> {"outreach_strategy": OutreachStrategy}
    t4 generate_email_sequence  -> {"email_sequence": list[str]}
    t5 generate_call_scripts    -> {"call_scripts": list[str]}
  performance_report:
    t2 collect_sales_metrics    -> {"sales_metrics": SalesMetrics}

(gather_market_data / analyze_competitors in sales_outreach belong to the
research agent; generate_campaign_summary belongs to the reporting agent.)

Inherits BaseAgent. The executor calls run(task, state); we return the plain
output dict per task_contracts.md and never mutate AgentState.
"""

import json
import re

from backend.agent_nodes.base_agent import BaseAgent
from backend.agent_nodes.llm import llm
from backend.models import (
    AgentState, Task, OutreachStrategy, SalesMetrics,
)


def _extract_json(raw: str) -> dict:
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    return json.loads(raw[raw.find("{"): raw.rfind("}") + 1])


def _ask_json(prompt: str, fallback: dict) -> dict:
    try:
        return _extract_json(llm.invoke(prompt).content)
    except Exception:
        return fallback


def _ask_text(prompt: str, fallback: str) -> str:
    try:
        out = llm.invoke(prompt).content
        return out.strip() if isinstance(out, str) and out.strip() else fallback
    except Exception:
        return fallback


class SalesAgent(BaseAgent):

    def __init__(self) -> None:
        super().__init__("sales")

    def execute(self, task: Task, state: AgentState) -> dict:
        handlers = {
            "create_outreach_strategy": self._create_outreach_strategy,
            "generate_email_sequence":  self._generate_email_sequence,
            "generate_call_scripts":    self._generate_call_scripts,
            "collect_sales_metrics":    self._collect_sales_metrics,
        }
        handler = handlers.get(task.action)
        if not handler:
            raise NotImplementedError(f"SalesAgent: unknown action '{task.action}'")
        return handler(task, state)

    # ===================== sales_outreach =====================

    # t3
    def _create_outreach_strategy(self, task: Task, state: AgentState) -> dict:
        ca = self.get_output(state, "t2")["competitor_analysis"]
        p = state.params  # SalesOutreachParams
        prompt = (
            "Create an outreach strategy. Return JSON with 'key_messages' "
            "(list of 3-5 short positioning statements) only.\n\n"
            f"Campaign goal: {p.campaign_goal}\nChannels: {list(p.outreach_channels)}\n"
            f"Segment: {p.target_segment}\nProduct: {p.product_name}\n"
            f"Competitor analysis: {ca}\nReturn ONLY the JSON object."
        )
        messages = _ask_json(prompt, {"key_messages": [
            f"Cut manual work for {p.target_segment} with AI employees.",
            "Faster time-to-value than incumbent suites.",
            "Human stays in control on sensitive actions.",
        ]}).get("key_messages", [])
        strategy = OutreachStrategy(
            campaign_goal=p.campaign_goal,
            channels=list(p.outreach_channels),
            key_messages=list(messages),
        )
        return {"outreach_strategy": strategy.model_dump()}

    # t4
    def _generate_email_sequence(self, task: Task, state: AgentState) -> dict:
        strat = self.get_output(state, "t3")["outreach_strategy"]
        msgs = strat.get("key_messages", [])
        prompt = (
            "Write a 3-email cold outreach sequence based on this strategy. Return JSON: "
            "{\"email_sequence\": [\"email 1\", \"email 2\", \"email 3\"]}.\n\n"
            f"Strategy: {strat}\nReturn ONLY the JSON object."
        )
        fallback = {"email_sequence": [
            f"Email 1 — Hook: {msgs[0] if msgs else 'Save time with AI employees.'} Open to a 15-min look?",
            "Email 2 — Value: here's how teams cut hiring and reporting time with us. Worth a short demo?",
            "Email 3 — Break-up: last note from me; happy to send a 2-min overview instead.",
        ]}
        seq = _ask_json(prompt, fallback).get("email_sequence", fallback["email_sequence"])
        return {"email_sequence": [str(s) for s in seq]}

    # t5
    def _generate_call_scripts(self, task: Task, state: AgentState) -> dict:
        strat = self.get_output(state, "t3")["outreach_strategy"]
        prompt = (
            "Write 1-2 short sales call scripts based on this strategy. Return JSON: "
            "{\"call_scripts\": [\"script text\"]}.\n\n"
            f"Strategy: {strat}\nReturn ONLY the JSON object."
        )
        fallback = {"call_scripts": [
            "Opening: Hi, this is WorkforceAI — got 30 seconds? "
            "Discovery: how much of your week goes to repetitive ops work? "
            "Pitch: we run those workflows with AI employees, with approval on anything sensitive. "
            "Close: can I grab 20 minutes this week to show a live run?",
        ]}
        scripts = _ask_json(prompt, fallback).get("call_scripts", fallback["call_scripts"])
        return {"call_scripts": [str(s) for s in scripts]}

    # ===================== performance_report =====================

    # t2  (mock metrics for MVP — no sales datastore yet; flag to team)
    def _collect_sales_metrics(self, task: Task, state: AgentState) -> dict:
        p = state.params  # PerformanceReportParams
        period = getattr(p, "report_period", "")
        wanted = getattr(p, "metrics_to_include", []) or ["revenue", "deals_won", "pipeline"]
        defaults = {
            "revenue": "₹1.2Cr",
            "deals_won": 28,
            "pipeline": "₹3.5Cr",
            "win_rate": "22%",
            "outreach_sent": 1200,
        }
        metrics = {m: defaults.get(m, "n/a") for m in wanted}
        metrics["report_period"] = period
        return {"sales_metrics": SalesMetrics(metrics=metrics).model_dump()}
