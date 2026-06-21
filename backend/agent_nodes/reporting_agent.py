import json
from langchain_ollama import ChatOllama
from backend.agent_nodes.base_agent import BaseAgent
from backend.models import AgentState, Task

class ReportingAgent(BaseAgent):
    def __init__(self, api_key: str = None):
        super().__init__("reporting")
        # Swap out the model name here to your lightweight choice
        self.llm = ChatOllama(
            model="qwen2.5:1.5b", 
            format="json"
        )

    def execute(self, task: Task, state: AgentState) -> dict:
        if task.action == "generate_narrative_insights":
            log_data = state.outputs
            processed_kpis = {}
            return self.generate_narrative_insights(log_data, processed_kpis)
        raise ValueError(f"Unknown reporting action: {task.action}")

    def generate_narrative_insights(self, log_data: dict, processed_kpis: dict) -> dict:
        # 1. HARD PROMPTING: Show it the exact dictionary shape
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
        
        response = self.llm.invoke(prompt)
        
        # --- DEBUGGING: PRINT THE RAW OUTPUT TO THE TERMINAL ---
        print(f"\n--- RAW AI OUTPUT START ---\n{response.content}\n--- RAW AI OUTPUT END ---\n")
        
        try:
            # Strip away any rogue markdown formatting the AI might have added
            clean_text = response.content.replace("```json", "").replace("```", "").strip()
            ai_data = json.loads(clean_text)
            
            # 2. BACKEND NORMALIZATION: Catch any hallucinations and map them to the correct keys
            return {
                "executive_summary": ai_data.get("executive_summary", ai_data.get("summary", "Summary data missing.")),
                "system_actions": ai_data.get("system_actions", ai_data.get("recommendations", ai_data.get("actions", ["Please review system manually."])))
            }
            
        except json.JSONDecodeError:
            # If the AI completely fails to generate JSON, gracefully fail without crashing
            return {
                "executive_summary": "The agent analyzed the data, but formatting failed.",
                "system_actions": ["Review raw LLM output in backend terminal.", f"Raw: {response.content[:50]}..."]
            }
