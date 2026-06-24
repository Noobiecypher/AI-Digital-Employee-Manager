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
        You are an HR reporting expert. Analyze the hiring workflow data below and write a real summary.
        Do not copy placeholders. Do not repeat these instructions. Return only valid JSON.

        Output format:
        {{
            "executive_summary": "<generated summary>",
            "system_actions": ["<recommendation 1>", "<recommendation 2>"]
        }}

        Workflow Data: {json.dumps(state.outputs)}
        """
        return self._invoke(prompt)

    def generate_campaign_summary(self, state: AgentState) -> dict:
        prompt = f"""
        You are a sales reporting expert. Analyze the sales campaign data below and write a real summary.
        Do not copy placeholders. Do not repeat these instructions. Return only valid JSON.

        Output format:
        {{
            "executive_summary": "<generated summary>",
            "system_actions": ["<recommendation 1>", "<recommendation 2>"]
        }}

        Workflow Data: {json.dumps(state.outputs)}
        """
        return self._invoke(prompt)

    def generate_review_summary(self, state: AgentState) -> dict:
        prompt = f"""
        You are a performance review expert. Analyze the review cycle data below and write a real summary.
        Do not copy placeholders. Do not repeat these instructions. Return only valid JSON.

        Output format:
        {{
            "executive_summary": "<generated summary>",
            "system_actions": ["<recommendation 1>", "<recommendation 2>"]
        }}

        Workflow Data: {json.dumps(state.outputs)}
        """
        return self._invoke(prompt)

    def generate_executive_summary(self, state: AgentState) -> dict:
        prompt = f"""
        You are a C-suite reporting expert. Analyze the workflow data below and write a real board-level summary.
        Do not copy placeholders. Do not repeat these instructions. Return only valid JSON.

        Output format:
        {{
            "executive_summary": "<generated summary>",
            "system_actions": ["<recommendation 1>", "<recommendation 2>"]
        }}

        Workflow Data: {json.dumps(state.outputs)}
        """
        return self._invoke(prompt)

    def generate_recommendations(self, state: AgentState) -> dict:
        prompt = f"""
        You are an operations analyst. Analyze the workflow data below and generate real actionable recommendations.
        Do not copy placeholders. Do not repeat these instructions. Return only valid JSON.

        Output format:
        {{
            "executive_summary": "<generated summary>",
            "system_actions": ["<recommendation 1>", "<recommendation 2>", "<recommendation 3>"]
        }}

        Workflow Data: {json.dumps(state.outputs)}
        """
        return self._invoke(prompt)

    def aggregate_results(self, state: AgentState) -> dict:
        prompt = f"""
        You are a data aggregation expert. Analyze the multi-agent workflow results below and write a real consolidated summary.
        Do not copy placeholders. Do not repeat these instructions. Return only valid JSON.

        Output format:
        {{
            "executive_summary": "<generated summary>",
            "system_actions": ["<recommendation 1>", "<recommendation 2>"]
        }}

        Workflow Data: {json.dumps(state.outputs)}
        """
        return self._invoke(prompt)

    def generate_kpi_dashboard(self, state: AgentState) -> dict:
        prompt = f"""
        You are a KPI analyst. Analyze the workflow data below and extract real key performance indicators.
        Do not copy placeholders. Do not repeat these instructions. Return only valid JSON.

        Output format:
        {{
            "executive_summary": "<generated summary>",
            "system_actions": ["<recommendation 1>", "<recommendation 2>"]
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
        You are an expert executive reporting agent. Analyze the workflow data below and write a real summary.
        Do not copy placeholders. Do not repeat these instructions. Return only valid JSON.

        Output format:
        {{
            "executive_summary": "<generated summary>",
            "system_actions": ["<recommendation 1>", "<recommendation 2>"]
        }}

        Workflow Data: {json.dumps(log_data)}
        KPIs: {json.dumps(processed_kpis)}
        """
        return self._invoke(prompt)