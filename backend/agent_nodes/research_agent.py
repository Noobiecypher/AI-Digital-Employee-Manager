"""
backend/agent_nodes/research_agent.py
=====================================
Research Agent (Person 3).

Per workflow_definitions.py, the "research" agent owns these actions:

  sales_outreach:
    t1 gather_market_data          -> {"market_data": MarketData}
    t2 analyze_competitors         -> {"competitor_analysis": CompetitorAnalysis}
  market_research:
    t1 gather_research_data        -> {"research_data": ResearchData}
    t2 perform_competitor_analysis -> {"competitor_analysis": CompetitorAnalysis}
    t3 synthesize_findings         -> {"findings": list[str]}
    t4 generate_recommendations    -> {"recommendations": list[str]}
    t5 generate_structured_report  -> {"structured_report": StructuredReport}

(The final executive_summary in both workflows belongs to the reporting agent.)

Inherits BaseAgent. The executor calls run(task, state); we return the plain
output dict per task_contracts.md and never mutate AgentState.
"""

import json
import re

from backend.agent_nodes.base_agent import BaseAgent
from backend.agent_nodes.llm import llm
from backend.models import (
    AgentState, Task,
    MarketData, CompetitorAnalysis, ResearchData, StructuredReport,
)

# Grounding tools (mock-data backed; simulate web/market research). Import
# defensively so the agent still runs if the tools module is absent.
try:
    from backend.tools.search_tools import get_market_context, get_competitors
except Exception:  # pragma: no cover
    def get_market_context(query):
        return {"market_overview": "", "trends": [], "data_points": []}

    def get_competitors(query):
        return []


def _competitor_fallback(comps: list[dict], topic_competitors: list | None = None) -> dict:
    """Turn grounded competitor records into a flat list[str] CompetitorAnalysis
    fallback, preserving the source detail as readable text."""
    if comps:
        return {
            "competitors": [c.get("name", "Competitor") for c in comps],
            "strengths": [f"{c.get('name','')}: {s}" for c in comps for s in c.get("strengths", [])] or ["Established incumbents"],
            "weaknesses": [f"{c.get('name','')}: {w}" for c in comps for w in c.get("weaknesses", [])] or ["Limited AI-native automation"],
        }
    tc = topic_competitors or []
    return {
        "competitors": tc or ["Incumbent suite vendors", "Point-solution tools"],
        "strengths": [f"{c} has established market presence" for c in tc] or ["Established brand", "Broad feature coverage"],
        "weaknesses": [f"{c} offers limited AI-native automation" for c in tc] or ["Limited AI-native automation", "Slower time-to-value"],
    }


# ---------------------------------------------------------------------------
# LLM helpers — use the shared `llm`, but degrade safely if the model errors
# (no server / bad JSON) so a model hiccup never fails the whole workflow.
# ---------------------------------------------------------------------------
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


def _coerce(model_cls, data: dict, fallback: dict) -> dict:
    try:
        return model_cls(**data).model_dump()
    except Exception:
        return model_cls(**fallback).model_dump()


def _as_str(item) -> str:
    """Normalize one item to a string. The LLM sometimes returns objects
    (e.g. {'action','rationale'} or {'message','channel'}); fold them into
    readable text so the list[str] contract is never violated."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        if "action" in item and "rationale" in item:
            return f"{item['action']} — {item['rationale']}"
        if "message" in item:
            ch = item.get("channel")
            return f"[{ch}] {item['message']}" if ch else str(item["message"])
        for k in ("finding", "text", "summary", "title"):
            if k in item:
                return str(item[k])
        return " — ".join(str(v) for v in item.values())
    return str(item)


def _to_str_list(items) -> list[str]:
    return [_as_str(x) for x in (items or [])]


def _competitor_analysis(data: dict, fallback: dict) -> dict:
    """Build a CompetitorAnalysis with each list normalized to str + per-field
    fallback, so messy LLM shapes are preserved as text rather than dropped."""
    return CompetitorAnalysis(
        competitors=_to_str_list(data.get("competitors") or fallback["competitors"]),
        strengths=_to_str_list(data.get("strengths") or fallback["strengths"]),
        weaknesses=_to_str_list(data.get("weaknesses") or fallback["weaknesses"]),
    ).model_dump()


class ResearchAgent(BaseAgent):

    def __init__(self) -> None:
        super().__init__("research")

    def execute(self, task: Task, state: AgentState) -> dict:
        handlers = {
            "gather_market_data":          self._gather_market_data,
            "analyze_competitors":         self._analyze_competitors,
            "gather_research_data":        self._gather_research_data,
            "perform_competitor_analysis": self._perform_competitor_analysis,
            "synthesize_findings":         self._synthesize_findings,
            "generate_recommendations":    self._generate_recommendations,
            "generate_structured_report":  self._generate_structured_report,
        }
        handler = handlers.get(task.action)
        if not handler:
            raise NotImplementedError(f"ResearchAgent: unknown action '{task.action}'")
        return handler(task, state)

    # ===================== sales_outreach =====================

    # t1
    def _gather_market_data(self, task: Task, state: AgentState) -> dict:
        p = state.params  # SalesOutreachParams
        ctx = get_market_context(f"{p.product_name} {p.target_segment}")
        grounded = ctx.get("trends") or []
        prompt = (
            "You are a senior B2B market analyst. Using the reference context below, "
            "give 3-5 specific, current market trends relevant to this product and "
            "segment. Be concrete (buyer behaviour, budget, adoption), not generic. "
            "Return JSON: {\"market_trends\": [\"...\"]} — each item a single string.\n\n"
            f"Product: {p.product_name}\nSegment: {p.target_segment}\n"
            f"Known pain points: {list(p.pain_points)}\n"
            f"Market overview: {ctx.get('market_overview','')}\n"
            f"Reference trends: {grounded}\nReturn ONLY the JSON object."
        )
        fb = {"market_trends": grounded or [
            "Buyers are consolidating tools and demanding measurable ROI.",
            "Growing appetite for AI automation in operations.",
            "Preference for fast onboarding and low setup cost.",
        ]}
        trends = _ask_json(prompt, fb).get("market_trends") or fb["market_trends"]
        data = MarketData(
            target_segment=p.target_segment,
            pain_points=_to_str_list(p.pain_points),
            market_trends=_to_str_list(trends),
        )
        return {"market_data": data.model_dump()}

    # t2
    def _analyze_competitors(self, task: Task, state: AgentState) -> dict:
        md = self.get_output(state, "t1")["market_data"]
        p = state.params
        comps = get_competitors(f"{p.product_name} {p.target_segment}")
        prompt = (
            "You are a competitive-intelligence analyst. Using the reference "
            "competitors below, return a competitor analysis as JSON with keys "
            "'competitors', 'strengths', 'weaknesses' (each a list of strings). "
            "Make strengths/weaknesses specific and attributable.\n\n"
            f"Product: {p.product_name}\nSegment: {p.target_segment}\n"
            f"Reference competitors: {comps}\n"
            f"Market data: {md}\nReturn ONLY the JSON object."
        )
        fallback = _competitor_fallback(comps)
        return {"competitor_analysis": _competitor_analysis(_ask_json(prompt, fallback), fallback)}

    # ===================== market_research =====================

    # t1
    def _gather_research_data(self, task: Task, state: AgentState) -> dict:
        p = state.params  # MarketResearchParams
        data = ResearchData(
            topic=p.research_topic,
            competitors=list(p.competitors),
            focus_areas=list(p.focus_areas),
        )
        return {"research_data": data.model_dump()}

    # t2
    def _perform_competitor_analysis(self, task: Task, state: AgentState) -> dict:
        rd = self.get_output(state, "t1")["research_data"]
        competitors = rd.get("competitors", [])
        grounded = get_competitors(rd.get("topic", ""))
        prompt = (
            "You are a market research analyst. Using the reference context, analyse "
            "the competitors for the topic below. Return JSON with keys 'competitors', "
            "'strengths', 'weaknesses' (each a list of strings). Be specific and "
            "attributable, not generic.\n\n"
            f"Topic: {rd.get('topic')}\nManager-listed competitors: {competitors}\n"
            f"Reference competitors: {grounded}\n"
            f"Focus areas: {rd.get('focus_areas')}\nReturn ONLY the JSON object."
        )
        fallback = _competitor_fallback(grounded, topic_competitors=competitors)
        return {"competitor_analysis": _competitor_analysis(_ask_json(prompt, fallback), fallback)}

    # t3
    def _synthesize_findings(self, task: Task, state: AgentState) -> dict:
        ca = self.get_output(state, "t2")["competitor_analysis"]
        prompt = (
            "Synthesize the competitor analysis below into 3-5 concise, concrete "
            "findings. Return JSON: {\"findings\": [\"...\"]}. Each finding MUST be a "
            "single plain string, NOT an object.\n\n"
            f"Competitor analysis: {ca}\nReturn ONLY the JSON object."
        )
        fallback = {"findings": [
            f"Competitors ({', '.join(ca.get('competitors', []) or ['n/a'])}) compete on breadth, not AI-native workflows.",
            "Buyers value fast time-to-value and clear ROI.",
            "There is whitespace for an autonomous, agentic offering.",
        ]}
        return {"findings": _to_str_list(_ask_json(prompt, fallback).get("findings", fallback["findings"]))}

    # t4
    def _generate_recommendations(self, task: Task, state: AgentState) -> dict:
        findings = self.get_output(state, "t3")["findings"]
        prompt = (
            "Based on these findings, produce 3-5 actionable recommendations. "
            "Return JSON: {\"recommendations\": [\"...\"]}. Each recommendation MUST be "
            "a single plain string (you may phrase it as 'action — rationale'), NOT an object.\n\n"
            f"Findings: {findings}\nReturn ONLY the JSON object."
        )
        fallback = {"recommendations": [
            "Position the product around autonomous AI employees, not generic software.",
            "Lead messaging with measurable time savings.",
            "Target segments underserved by incumbents.",
        ]}
        return {"recommendations": _to_str_list(_ask_json(prompt, fallback).get("recommendations", fallback["recommendations"]))}

    # t5
    def _generate_structured_report(self, task: Task, state: AgentState) -> dict:
        findings = self.get_output(state, "t3")["findings"]
        recommendations = self.get_output(state, "t4")["recommendations"]
        topic = (self.get_output(state, "t1").get("research_data") or {}).get("topic", "")
        overview = get_market_context(topic).get("market_overview", "")
        summary = _ask_text(
            "Write a 2-3 sentence executive summary tying together the market context, "
            "findings and recommendations below.\n\n"
            f"Market context: {overview}\nFindings: {findings}\nRecommendations: {recommendations}",
            fallback=overview or "The market favours differentiated, AI-native positioning; the "
                     "recommendations focus on time-to-value and underserved segments.",
        )
        report = StructuredReport(
            findings=_to_str_list(findings),
            recommendations=_to_str_list(recommendations),
            summary=summary,
        )
        return {"structured_report": report.model_dump()}
