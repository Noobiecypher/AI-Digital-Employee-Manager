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
        prompt = (
            "You are a B2B market analyst. List 3-5 current market trends for the "
            "product/segment below. Return JSON: {\"market_trends\": [\"...\"]}.\n\n"
            f"Product: {p.product_name}\nSegment: {p.target_segment}\n"
            f"Known pain points: {list(p.pain_points)}\nReturn ONLY the JSON object."
        )
        trends = _ask_json(prompt, {"market_trends": [
            "Buyers are consolidating tools and demanding measurable ROI.",
            "Growing appetite for AI automation in operations.",
            "Preference for fast onboarding and low setup cost.",
        ]}).get("market_trends", [])
        data = MarketData(
            target_segment=p.target_segment,
            pain_points=list(p.pain_points),
            market_trends=list(trends),
        )
        return {"market_data": data.model_dump()}

    # t2
    def _analyze_competitors(self, task: Task, state: AgentState) -> dict:
        md = self.get_output(state, "t1")["market_data"]
        p = state.params
        prompt = (
            "Infer the main competitors for this product/segment and analyse them. "
            "Return JSON with keys 'competitors', 'strengths', 'weaknesses' "
            "(each a list of strings).\n\n"
            f"Product: {p.product_name}\nSegment: {p.target_segment}\n"
            f"Market data: {md}\nReturn ONLY the JSON object."
        )
        fallback = {
            "competitors": ["Incumbent suite vendors", "Point-solution tools"],
            "strengths": ["Established brand", "Broad feature coverage"],
            "weaknesses": ["Limited AI-native automation", "Slower time-to-value"],
        }
        return {"competitor_analysis": _coerce(CompetitorAnalysis, _ask_json(prompt, fallback), fallback)}

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
        prompt = (
            "You are a market research analyst. Analyse the competitors for the topic "
            "below. Return JSON with keys 'competitors', 'strengths', 'weaknesses' "
            "(each a list of strings).\n\n"
            f"Topic: {rd.get('topic')}\nCompetitors: {competitors}\n"
            f"Focus areas: {rd.get('focus_areas')}\nReturn ONLY the JSON object."
        )
        fallback = {
            "competitors": competitors,
            "strengths": [f"{c} has established market presence" for c in competitors] or ["Established incumbents"],
            "weaknesses": [f"{c} offers limited AI-native automation" for c in competitors] or ["Limited automation"],
        }
        return {"competitor_analysis": _coerce(CompetitorAnalysis, _ask_json(prompt, fallback), fallback)}

    # t3
    def _synthesize_findings(self, task: Task, state: AgentState) -> dict:
        ca = self.get_output(state, "t2")["competitor_analysis"]
        prompt = (
            "Synthesize the competitor analysis below into 3-5 concise, concrete "
            "findings. Return JSON: {\"findings\": [\"...\"]}.\n\n"
            f"Competitor analysis: {ca}\nReturn ONLY the JSON object."
        )
        fallback = {"findings": [
            f"Competitors ({', '.join(ca.get('competitors', []) or ['n/a'])}) compete on breadth, not AI-native workflows.",
            "Buyers value fast time-to-value and clear ROI.",
            "There is whitespace for an autonomous, agentic offering.",
        ]}
        return {"findings": list(_ask_json(prompt, fallback).get("findings", fallback["findings"]))}

    # t4
    def _generate_recommendations(self, task: Task, state: AgentState) -> dict:
        findings = self.get_output(state, "t3")["findings"]
        prompt = (
            "Based on these findings, produce 3-5 actionable recommendations. "
            "Return JSON: {\"recommendations\": [\"...\"]}.\n\n"
            f"Findings: {findings}\nReturn ONLY the JSON object."
        )
        fallback = {"recommendations": [
            "Position the product around autonomous AI employees, not generic software.",
            "Lead messaging with measurable time savings.",
            "Target segments underserved by incumbents.",
        ]}
        return {"recommendations": list(_ask_json(prompt, fallback).get("recommendations", fallback["recommendations"]))}

    # t5
    def _generate_structured_report(self, task: Task, state: AgentState) -> dict:
        findings = self.get_output(state, "t3")["findings"]
        recommendations = self.get_output(state, "t4")["recommendations"]
        summary = _ask_text(
            "Write a 2-3 sentence summary tying together the findings and recommendations below.\n\n"
            f"Findings: {findings}\nRecommendations: {recommendations}",
            fallback="The market favours differentiated, AI-native positioning; the recommendations "
                     "focus on time-to-value and underserved segments.",
        )
        report = StructuredReport(
            findings=list(findings),
            recommendations=list(recommendations),
            summary=summary,
        )
        return {"structured_report": report.model_dump()}
