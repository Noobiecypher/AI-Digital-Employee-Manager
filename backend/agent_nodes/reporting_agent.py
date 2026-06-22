import json
from langchain_ollama import ChatOllama
from backend.agent_nodes.base_agent import BaseAgent
from backend.models import AgentState, Task


class ReportingAgent(BaseAgent):
    def __init__(self, api_key: str = None):
        super().__init__("reporting")
        self.llm = ChatOllama(
            model="qwen2.5:1.5b",
            format="json"
        )

    # ------------------------------------------------------------------
    # BaseAgent contract
    # ------------------------------------------------------------------

    def execute(self, task: Task, state: AgentState) -> dict:
        action_map = {
            "generate_narrative_insights": self.generate_narrative_insights_action,
            "generate_summary":            self.generate_narrative_insights_action,
            "generate_hiring_summary":     self.generate_hiring_summary,
            "generate_campaign_summary":   self.generate_campaign_summary,
            "generate_review_summary":     self.generate_review_summary,
            "generate_executive_summary":  self.generate_executive_summary,
            "generate_recommendations":    self.generate_recommendations,
            "aggregate_results":           self.aggregate_results,
            "generate_kpi_dashboard":      self.generate_kpi_dashboard,
        }

        handler = action_map.get(task.action)
        if handler is None:
            raise ValueError(f"Unknown reporting action: {task.action}")

        return handler(state)

    # ------------------------------------------------------------------
    # Action handlers — each builds a tailored prompt then calls _invoke
    # ------------------------------------------------------------------

    def generate_narrative_insights_action(self, state: AgentState) -> dict:
        return self.generate_narrative_insights(state.outputs, {})

    def generate_hiring_summary(self, state: AgentState) -> dict:
        prompt = f"""
        You are an HR reporting expert. Summarize the hiring workflow results below.
        Return ONLY a raw JSON object — no markdown, no extra keys.

        Output format:
        {{
            "executive_summary": "2-sentence summary of hiring outcomes and candidate pipeline.",
            "system_actions": ["Hiring recommendation 1", "Hiring recommendation 2"]
        }}

        Workflow Data: {json.dumps(state.outputs)}
        """
        return self._invoke(prompt)

    def generate_campaign_summary(self, state: AgentState) -> dict:
        prompt = f"""
        You are a sales reporting expert. Summarize the sales campaign results below.
        Return ONLY a raw JSON object — no markdown, no extra keys.

        Output format:
        {{
            "executive_summary": "2-sentence summary of campaign performance and ROI.",
            "system_actions": ["Campaign recommendation 1", "Campaign recommendation 2"]
        }}

        Workflow Data: {json.dumps(state.outputs)}
        """
        return self._invoke(prompt)

    def generate_review_summary(self, state: AgentState) -> dict:
        prompt = f"""
        You are a performance review reporting expert. Summarize the review cycle results below.
        Return ONLY a raw JSON object — no markdown, no extra keys.

        Output format:
        {{
            "executive_summary": "2-sentence summary of employee performance trends.",
            "system_actions": ["Performance recommendation 1", "Performance recommendation 2"]
        }}

        Workflow Data: {json.dumps(state.outputs)}
        """
        return self._invoke(prompt)

    def generate_executive_summary(self, state: AgentState) -> dict:
        prompt = f"""
        You are a C-suite reporting expert. Produce a high-level executive summary of the workflow below.
        Return ONLY a raw JSON object — no markdown, no extra keys.

        Output format:
        {{
            "executive_summary": "2-sentence board-level summary of outcomes and business impact.",
            "system_actions": ["Strategic recommendation 1", "Strategic recommendation 2"]
        }}

        Workflow Data: {json.dumps(state.outputs)}
        """
        return self._invoke(prompt)

    def generate_recommendations(self, state: AgentState) -> dict:
        prompt = f"""
        You are an operations analyst. Based on the workflow data below, generate actionable recommendations.
        Return ONLY a raw JSON object — no markdown, no extra keys.

        Output format:
        {{
            "executive_summary": "2-sentence overview of the key areas needing improvement.",
            "system_actions": ["Recommendation 1", "Recommendation 2", "Recommendation 3"]
        }}

        Workflow Data: {json.dumps(state.outputs)}
        """
        return self._invoke(prompt)

    def aggregate_results(self, state: AgentState) -> dict:
        prompt = f"""
        You are a data aggregation expert. Consolidate the multi-agent workflow results below into a unified summary.
        Return ONLY a raw JSON object — no markdown, no extra keys.

        Output format:
        {{
            "executive_summary": "2-sentence summary of the aggregated results across all agents.",
            "system_actions": ["Aggregated insight 1", "Aggregated insight 2"]
        }}

        Workflow Data: {json.dumps(state.outputs)}
        """
        return self._invoke(prompt)

    def generate_kpi_dashboard(self, state: AgentState) -> dict:
        prompt = f"""
        You are a KPI analyst. Extract and summarize the key performance indicators from the workflow data below.
        Return ONLY a raw JSON object — no markdown, no extra keys.

        Output format:
        {{
            "executive_summary": "2-sentence summary of KPI performance against targets.",
            "system_actions": ["KPI action 1", "KPI action 2"]
        }}

        Workflow Data: {json.dumps(state.outputs)}
        """
        return self._invoke(prompt)

    # ------------------------------------------------------------------
    # Core LLM call (shared by all handlers)
    # ------------------------------------------------------------------

    def _invoke(self, prompt: str) -> dict:
        response = self.llm.invoke(prompt)

        print(f"\n--- RAW AI OUTPUT START ---\n{response.content}\n--- RAW AI OUTPUT END ---\n")

        try:
            clean_text = response.content.replace("```json", "").replace("```", "").strip()
            ai_data = json.loads(clean_text)

            return {
                "executive_summary": ai_data.get("executive_summary", ai_data.get("summary", "Summary data missing.")),
                "system_actions": ai_data.get("system_actions", ai_data.get("recommendations", ai_data.get("actions", ["Please review system manually."])))
            }

        except json.JSONDecodeError:
            return {
                "executive_summary": "The agent analyzed the data, but formatting failed.",
                "system_actions": ["Review raw LLM output in backend terminal.", f"Raw: {response.content[:50]}..."]
            }

    # ------------------------------------------------------------------
    # Legacy public method (kept for main.py direct calls)
    # ------------------------------------------------------------------

    def generate_narrative_insights(self, log_data: dict, processed_kpis: dict) -> dict:
        prompt = f"""
        You are an expert executive reporting agent. Analyze the workflow data below.
        You must return ONLY a raw JSON object. Do NOT include markdown blocks like ```json.

        Your output MUST exactly match this format:
        {{
            "executive_summary": "A 2-sentence executive summary of the runtime and success rate.",
            "system_actions": ["Technical recommendation 1", "Technical recommendation 2"]
        }}

        Workflow Data: {json.dumps(log_data)}
        KPIs: {json.dumps(processed_kpis)}
        """
        return self._invoke(prompt)