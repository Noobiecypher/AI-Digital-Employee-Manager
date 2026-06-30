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
import os
import re

from backend.agent_nodes.base_agent import BaseAgent
from backend.agent_nodes.llm import llm
from backend.models import (
    AgentState, Task, OutreachStrategy, SalesMetrics,
)

# Sales-domain data tools (mock-data backed). Import defensively so the agent
# still runs if the tools module is absent.
try:
    from backend.tools.sales_tools import get_product_profile, get_sales_metrics
except Exception:  # pragma: no cover
    def get_product_profile(name):
        return {}

    def get_sales_metrics(report_period, departments=None):
        return {}

# Outreach sender (SMTP). Defensive import; dry-run safe by default.
try:
    from backend.tools.outreach_tools import send_approved_outreach
except Exception:  # pragma: no cover
    def send_approved_outreach(email_sequence, recipients):
        return [{"status": "unavailable", "sent": False}]


def _inr(n):
    if not isinstance(n, (int, float)):
        return None
    if n >= 1e7:
        return f"₹{n / 1e7:.1f}Cr"
    if n >= 1e5:
        return f"₹{n / 1e5:.1f}L"
    return f"₹{n:,.0f}"


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


def _as_str(item) -> str:
    """Normalize one item to a string. The LLM sometimes returns objects
    (e.g. {'message','channel'} or {'subject','body'}); fold them into
    readable text so the list[str] contract is never violated."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        if "message" in item:
            ch = item.get("channel")
            return f"[{ch}] {item['message']}" if ch else str(item["message"])
        if "subject" in item and "body" in item:
            return f"Subject: {item['subject']}\n{item['body']}"
        for k in ("text", "script", "body", "content"):
            if k in item:
                return str(item[k])
        return " — ".join(str(v) for v in item.values())
    return str(item)


def _to_str_list(items) -> list[str]:
    return [_as_str(x) for x in (items or [])]


class SalesAgent(BaseAgent):

    def __init__(self) -> None:
        super().__init__("sales")

    def execute(self, task: Task, state: AgentState) -> dict:
        handlers = {
            "create_outreach_strategy": self._create_outreach_strategy,
            "generate_email_sequence":  self._generate_email_sequence,
            "generate_call_scripts":    self._generate_call_scripts,
            "collect_sales_metrics":    self._collect_sales_metrics,
            "send_outreach":            self._send_outreach,
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
        prod = get_product_profile(p.product_name)
        prompt = (
            "You are a senior B2B sales strategist. Using the product profile and "
            "competitor analysis, craft an outreach strategy. Return JSON with "
            "'key_messages' (3-5 sharp, pain-led positioning statements). Each item "
            "MUST be a single plain string, NOT an object. Lead with buyer value, not "
            "features.\n\n"
            f"Campaign goal: {p.campaign_goal}\nChannels: {list(p.outreach_channels)}\n"
            f"Segment: {p.target_segment}\nProduct: {p.product_name}\n"
            f"Pain points: {list(p.pain_points)}\n"
            f"Value props: {prod.get('value_props', [])}\n"
            f"Differentiators: {prod.get('differentiators', [])}\n"
            f"Competitor analysis: {ca}\nReturn ONLY the JSON object."
        )
        fb = {"key_messages": (prod.get("value_props") or [
            f"Cut manual work for {p.target_segment} with AI employees.",
            "Faster time-to-value than incumbent suites.",
            "Human stays in control on sensitive actions.",
        ])}
        messages = _ask_json(prompt, fb).get("key_messages") or fb["key_messages"]
        strategy = OutreachStrategy(
            campaign_goal=p.campaign_goal,
            channels=list(p.outreach_channels),
            key_messages=_to_str_list(messages),
        )
        return {"outreach_strategy": strategy.model_dump()}

    # t4
    def _generate_email_sequence(self, task: Task, state: AgentState) -> dict:
        strat = self.get_output(state, "t3")["outreach_strategy"]
        p = state.params
        prod = get_product_profile(p.product_name)
        msgs = strat.get("key_messages", [])
        pain = list(p.pain_points)[0] if getattr(p, "pain_points", None) else "manual, repetitive work"
        prompt = (
            "You are a top B2B SDR. Write a 3-email cold outreach sequence for the "
            "segment below: (1) pain-led hook, (2) value + light proof, (3) short "
            "break-up. Personalised, concise, no buzzword soup. Return JSON: "
            "{\"email_sequence\": [\"email 1\", \"email 2\", \"email 3\"]} — each a single string.\n\n"
            f"Segment: {p.target_segment}\nProduct: {p.product_name}\n"
            f"Lead pain point: {pain}\nKey messages: {msgs}\n"
            f"Differentiators: {prod.get('differentiators', [])}\nReturn ONLY the JSON object."
        )
        fallback = {"email_sequence": [
            f"Email 1 — Subject: {p.target_segment}, still stuck on {pain}? "
            f"Most {p.target_segment.lower()} lose hours to it. {p.product_name} automates that end-to-end. Open to a 15-min look?",
            f"Email 2 — Subject: how teams cut that time. {msgs[0] if msgs else 'We remove the manual grind'} — "
            "with human approval on anything sensitive. Worth a short demo this week?",
            "Email 3 — Subject: should I close the loop? Last note from me — happy to send a 2-minute overview instead if that's easier.",
        ]}
        seq = _ask_json(prompt, fallback).get("email_sequence", fallback["email_sequence"])
        return {"email_sequence": _to_str_list(seq)}

    # t5
    def _generate_call_scripts(self, task: Task, state: AgentState) -> dict:
        strat = self.get_output(state, "t3")["outreach_strategy"]
        p = state.params
        prod = get_product_profile(p.product_name)
        prompt = (
            "You are a sales enablement specialist. Write a discovery-call script with "
            "an opening hook, 3-4 qualification questions, a value pitch, and a clear "
            "next-step close. Return JSON: {\"call_scripts\": [\"script text\"]}.\n\n"
            f"Segment: {p.target_segment}\nProduct: {p.product_name}\n"
            f"Pain points: {list(p.pain_points)}\nValue props: {prod.get('value_props', [])}\n"
            f"Strategy: {strat}\nReturn ONLY the JSON object."
        )
        vp = (prod.get("value_props") or ["we run those workflows with AI employees"])[0]
        fallback = {"call_scripts": [
            f"Opening: Hi, this is {p.product_name} — caught you at a bad time, or got 30 seconds? "
            f"Discovery: How much of your team's week goes to {(list(p.pain_points)[:1] or ['repetitive ops work'])[0]}? "
            "How are you handling it today? What would freeing that time up be worth? "
            f"Pitch: {vp} — with human approval on anything sensitive, so you get speed without losing control. "
            "Close: Can I put 20 minutes on the calendar this week to show a live run?",
        ]}
        scripts = _ask_json(prompt, fallback).get("call_scripts", fallback["call_scripts"])
        return {"call_scripts": _to_str_list(scripts)}

    # ===================== performance_report =====================

    # t2  Sales metrics for the performance report.
    # MVP approach: sourced from a structured mock dataset (sales_metrics.json) via
    # sales_tools.get_sales_metrics — deterministic and clearly labelled as mock.
    # Swap the tool body for a CRM/DB query later; this method does not change.
    def _collect_sales_metrics(self, task: Task, state: AgentState) -> dict:
        p = state.params  # PerformanceReportParams
        period = getattr(p, "report_period", "")
        departments = list(getattr(p, "departments", []) or [])
        raw = get_sales_metrics(period, departments) or {}

        metrics: dict = {}
        if _inr(raw.get("revenue_inr")) is not None:
            metrics["revenue"] = _inr(raw["revenue_inr"])
        if raw.get("deals_won") is not None:
            metrics["deals_won"] = raw["deals_won"]
        if _inr(raw.get("pipeline_inr")) is not None:
            metrics["pipeline"] = _inr(raw["pipeline_inr"])
        if raw.get("win_rate_pct") is not None:
            metrics["win_rate"] = f"{raw['win_rate_pct']}%"
        if raw.get("outreach_sent") is not None:
            metrics["outreach_sent"] = raw["outreach_sent"]
        if raw.get("demos_booked") is not None:
            metrics["demos_booked"] = raw["demos_booked"]

        if not metrics:  # last-resort fallback
            metrics = {"revenue": "₹1.0Cr", "deals_won": 24, "pipeline": "₹3.0Cr", "win_rate": "21%"}

        metrics["report_period"] = period or "current"
        metrics["source"] = "mock_data (sales_metrics.json)"
        return {"sales_metrics": SalesMetrics(metrics=metrics).model_dump()}

    # POST-APPROVAL send. This action should only appear in the workflow AFTER a
    # human approval gate — reaching it means the drafts were approved. It reads
    # the approved email_sequence from state.outputs and sends via SMTP.
    # Safe by default: with no SMTP config it dry-runs (sends nothing).
    def _send_outreach(self, task: Task, state: AgentState) -> dict:
        # find the approved email sequence anywhere in upstream outputs
        emails = []
        for out in state.outputs.values():
            if isinstance(out, dict) and "email_sequence" in out:
                emails = out["email_sequence"]
                break
        # recipients: from params if present, else from an env test list
        recipients = list(getattr(state.params, "recipients", []) or [])
        if not recipients:
            env = os.environ.get("OUTREACH_TEST_RECIPIENTS", "")
            recipients = [r.strip() for r in env.split(",") if r.strip()]

        results = send_approved_outreach(emails, recipients) if recipients else []
        return {"send_result": {
            "requested": len(emails),
            "recipients": recipients,
            "sent": sum(1 for r in results if r.get("sent")),
            "results": results,
        }}
