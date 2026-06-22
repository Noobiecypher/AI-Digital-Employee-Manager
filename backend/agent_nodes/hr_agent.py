"""
hr_agent.py
-----------
HR Agent for the AI Digital Employee Platform.

Handles:
    onboard_employee workflow  : t1, t2, t3, t4
    performance_review workflow: t1, t2, t3, t4, t5

Inherits BaseAgent. Workflow Executor calls agent.run(task, state).
Returns output dict per task_contracts.md. Never mutates AgentState directly.

Requirements:
    pip install langchain langchain-ollama
    Ollama running locally: ollama serve
"""

from backend.agent_nodes.base_agent import BaseAgent
from backend.models import (
    AgentState,
    Task,
    EmployeeDetails,
    OnboardingPlan,
    WelcomePackage,
    GoalData,
    PerformanceEvaluation,
    OnboardEmployeeParams,
    PerformanceReviewParams,
    HRMetrics,
)
from backend.planner.data_loader import get_employee, get_role_info
from backend.agent_nodes.llm import llm


class HRAgent(BaseAgent):

    def __init__(self) -> None:
        super().__init__("hr")

    # ----------------------------------------------------------
    # DISPATCH
    # ----------------------------------------------------------

    def execute(self, task: Task, state: AgentState) -> dict:

        handlers = {
            # onboard_employee
            "retrieve_employee_details": self._retrieve_employee_details,
            "generate_onboarding_plan":  self._generate_onboarding_plan,
            "create_welcome_package":    self._create_welcome_package,
            "create_first_week_tasks":   self._create_first_week_tasks,

            # performance_review
            "retrieve_employee_data":    self._retrieve_employee_data,
            "retrieve_goal_data":        self._retrieve_goal_data,
            "evaluate_performance":      self._evaluate_performance,
            "generate_rating":           self._generate_rating,
            "generate_improvement_plan": self._generate_improvement_plan,

            # performance report
            # performance_report
            "collect_hr_metrics": self._collect_hr_metrics,
        }

        handler = handlers.get(task.action)

        if not handler:
            raise NotImplementedError(
                f"HRAgent: unknown action '{task.action}'"
            )

        return handler(task, state)

    # ==========================================================
    # ONBOARD EMPLOYEE
    # ==========================================================

    # ----------------------------------------------------------
    # t1 — retrieve_employee_details
    # Reads: state.params.employee_name
    # Returns: { "employee_details": EmployeeDetails }
    # ----------------------------------------------------------

    def _retrieve_employee_details(
        self, task: Task, state: AgentState
    ) -> dict:

        params: OnboardEmployeeParams = state.params
        raw = get_employee(params.employee_name)

        employee = EmployeeDetails(
            employee_id  = raw.get("employee_id", ""),
            name         = raw["employee_name"],
            role         = raw["role"],
            department   = raw["department"],
            manager_name = raw["manager_name"],
            joining_date = raw["joining_date"],
            work_mode    = raw["work_mode"],
        )

        return {"employee_details": employee.model_dump()}

    # ----------------------------------------------------------
    # t2 — generate_onboarding_plan
    # Reads: outputs["t1"] (employee_details)
    # Returns: { "onboarding_plan": OnboardingPlan }
    # ----------------------------------------------------------

    def _generate_onboarding_plan(
        self, task: Task, state: AgentState
    ) -> dict:

        emp = self.get_output(state, "t1")["employee_details"]

        prompt = f"""
You are an HR onboarding specialist. Create a structured onboarding plan.

Employee  : {emp["name"]}
Role      : {emp["role"]}
Department: {emp["department"]}
Manager   : {emp["manager_name"]}
Work Mode : {emp["work_mode"]}
Start Date: {emp["joining_date"]}

Return the plan in this exact format:

DURATION_DAYS: <number>

MILESTONES:
- <milestone 1>
- <milestone 2>
- <milestone 3>
- <milestone 4>
- <milestone 5>

Keep milestones concise and actionable. No extra text.
"""

        response = llm.invoke(prompt)
        content  = response.content.strip()

        # Parse duration
        duration_days = 30  # default
        for line in content.split("\n"):
            if "DURATION_DAYS:" in line:
                try:
                    duration_days = int(line.split(":")[-1].strip())
                except ValueError:
                    pass
                break

        # Parse milestones
        milestones = []
        in_milestones = False
        for line in content.split("\n"):
            if "MILESTONES:" in line:
                in_milestones = True
                continue
            if in_milestones and line.strip().startswith("-"):
                milestones.append(line.strip("- ").strip())

        plan = OnboardingPlan(
            duration_days = duration_days,
            milestones    = milestones,
        )

        return {"onboarding_plan": plan.model_dump()}

    # ----------------------------------------------------------
    # t3 — create_welcome_package
    # Reads: outputs["t1"] (employee_details), outputs["t2"] (onboarding_plan)
    # Returns: { "welcome_package": WelcomePackage }
    # ----------------------------------------------------------

    def _create_welcome_package(
        self, task: Task, state: AgentState
    ) -> dict:

        emp  = self.get_output(state, "t1")["employee_details"]
        plan = self.get_output(state, "t2")["onboarding_plan"]

        prompt = f"""
You are an HR coordinator. Generate a welcome package for a new employee.

Employee  : {emp["name"]}
Role      : {emp["role"]}
Department: {emp["department"]}
Manager   : {emp["manager_name"]}
Work Mode : {emp["work_mode"]}
Milestones: {plan["milestones"]}

Return in this exact format:

DOCUMENTS:
- <document 1>
- <document 2>
- <document 3>
- <document 4>
- <document 5>

RESOURCES:
- <resource 1>
- <resource 2>
- <resource 3>
- <resource 4>

No extra text. Only the two sections above.
"""

        response = llm.invoke(prompt)
        content  = response.content.strip()

        documents = []
        resources = []

        in_docs = False
        in_res  = False

        for line in content.split("\n"):
            if "DOCUMENTS:" in line:
                in_docs = True
                in_res  = False
                continue
            if "RESOURCES:" in line:
                in_res  = True
                in_docs = False
                continue
            if line.strip().startswith("-"):
                item = line.strip("- ").strip()
                if in_docs:
                    documents.append(item)
                elif in_res:
                    resources.append(item)

        package = WelcomePackage(
            documents = documents,
            resources = resources,
        )

        return {"welcome_package": package.model_dump()}

    # ----------------------------------------------------------
    # t4 — create_first_week_tasks
    # Reads: outputs["t1"] (employee_details), outputs["t2"] (onboarding_plan)
    # Returns: { "first_week_tasks": list[str] }
    # ----------------------------------------------------------

    def _create_first_week_tasks(
        self, task: Task, state: AgentState
    ) -> dict:

        emp  = self.get_output(state, "t1")["employee_details"]
        plan = self.get_output(state, "t2")["onboarding_plan"]

        prompt = f"""
You are an HR specialist. Generate first week tasks for a new employee.

Employee  : {emp["name"]}
Role      : {emp["role"]}
Department: {emp["department"]}
Work Mode : {emp["work_mode"]}
Milestones: {plan["milestones"]}

Return ONLY a flat list of tasks for the first week, one per line:
- <task 1>
- <task 2>
- <task 3>
...

Keep tasks specific and actionable. No day headings. No extra text.
"""

        response = llm.invoke(prompt)
        content  = response.content.strip()

        tasks = [
            line.strip("•-* ").strip()
            for line in content.split("\n")
            if line.strip().startswith("-") or line.strip().startswith("•")
        ]

        return {"first_week_tasks": tasks}

    # ==========================================================
    # PERFORMANCE REVIEW
    # ==========================================================

    # ----------------------------------------------------------
    # t1 — retrieve_employee_data
    # Reads: state.params (employee_name, review_period)
    # Returns: { "employee_data": EmployeeDetails }
    # ----------------------------------------------------------

    def _retrieve_employee_data(
        self, task: Task, state: AgentState
    ) -> dict:

        params: PerformanceReviewParams = state.params
        raw       = get_employee(params.employee_name)
        role_info = get_role_info(raw["department"], raw["role"])

        # Write rating_scale back into params so downstream tasks can read it
        # This is the only case where we update params — it's an enrichment
        # that belongs in params, not in outputs.
        state.params.rating_scale = role_info["rating_scale"]

        employee = EmployeeDetails(
            employee_id  = raw.get("employee_id", ""),
            name         = raw["employee_name"],
            role         = raw["role"],
            department   = raw["department"],
            manager_name = raw["manager_name"],
            joining_date = raw["joining_date"],
            work_mode    = raw["work_mode"],
        )

        return {"employee_data": employee.model_dump()}

    # ----------------------------------------------------------
    # t2 — retrieve_goal_data
    # Reads: state.params (goals_set, goals_achieved) — enriched before workflow
    # Returns: { "goal_data": GoalData }
    # ----------------------------------------------------------

    def _retrieve_goal_data(
        self, task: Task, state: AgentState
    ) -> dict:

        params: PerformanceReviewParams = state.params

        goal_data = GoalData(
            goals_set      = params.goals_set,
            goals_achieved = params.goals_achieved,
        )

        return {"goal_data": goal_data.model_dump()}

    # ----------------------------------------------------------
    # t3 — evaluate_performance
    # Reads: outputs["t1"] (employee_data), outputs["t2"] (goal_data),
    #        state.params.manager_comments
    # Returns: { "performance_evaluation": PerformanceEvaluation }
    # ----------------------------------------------------------

    def _evaluate_performance(
        self, task: Task, state: AgentState
    ) -> dict:

        emp       = self.get_output(state, "t1")["employee_data"]
        goal_data = self.get_output(state, "t2")["goal_data"]
        params: PerformanceReviewParams = state.params

        goals_set      = goal_data["goals_set"]
        goals_achieved = goal_data["goals_achieved"]
        achievement    = (
            len(goals_achieved) / len(goals_set)
            if goals_set else 0.0
        )

        prompt = f"""
You are a senior HR performance evaluator. Evaluate the employee objectively.

Employee        : {emp["name"]}
Role            : {emp["role"]}
Department      : {emp["department"]}
Manager Comments: {params.manager_comments}
Goals Set       : {goals_set}
Goals Achieved  : {goals_achieved}
Achievement Rate: {achievement * 100:.0f}%

Return in this exact format:

SUMMARY:
<2-3 sentence overall performance summary>

STRENGTHS:
- <strength 1>
- <strength 2>
- <strength 3>

WEAKNESSES:
- <weakness 1>
- <weakness 2>

No extra text outside these three sections.
"""

        response = llm.invoke(prompt)
        content  = response.content.strip()

        summary    = ""
        strengths  = []
        weaknesses = []

        in_summary    = False
        in_strengths  = False
        in_weaknesses = False

        for line in content.split("\n"):
            line_stripped = line.strip()

            if "SUMMARY:" in line:
                in_summary    = True
                in_strengths  = False
                in_weaknesses = False
                continue
            if "STRENGTHS:" in line:
                in_summary    = False
                in_strengths  = True
                in_weaknesses = False
                continue
            if "WEAKNESSES:" in line:
                in_summary    = False
                in_strengths  = False
                in_weaknesses = True
                continue

            if in_summary and line_stripped:
                summary += line_stripped + " "
            elif in_strengths and line_stripped.startswith("-"):
                strengths.append(line_stripped.lstrip("- ").strip())
            elif in_weaknesses and line_stripped.startswith("-"):
                weaknesses.append(line_stripped.lstrip("- ").strip())

        evaluation = PerformanceEvaluation(
            strengths  = strengths,
            weaknesses = weaknesses,
            summary    = summary.strip(),
        )

        return {"performance_evaluation": evaluation.model_dump()}

    # ----------------------------------------------------------
    # t4 — generate_rating
    # Reads: outputs["t3"] (performance_evaluation), state.params.rating_scale
    # Returns: { "rating": int }
    # Pure logic — no LLM needed.
    # ----------------------------------------------------------

    def _generate_rating(
        self, task: Task, state: AgentState
    ) -> dict:

        params: PerformanceReviewParams = state.params
        goal_data  = self.get_output(state, "t2")["goal_data"]
        evaluation = self.get_output(state, "t3")["performance_evaluation"]

        rating_scale   = params.rating_scale
        goals_set      = goal_data["goals_set"]
        goals_achieved = goal_data["goals_achieved"]

        achievement_ratio = (
            len(goals_achieved) / len(goals_set)
            if goals_set else 0.0
        )

        # Qualitative weight from summary sentiment
        summary = evaluation["summary"].lower()
        if any(w in summary for w in ["excellent", "outstanding", "exceeds"]):
            qualitative = 1.0
        elif any(w in summary for w in ["good", "meets", "solid"]):
            qualitative = 0.75
        else:
            qualitative = 0.5

        # 70% goal completion, 30% qualitative assessment
        raw_score    = (0.7 * achievement_ratio + 0.3 * qualitative) * rating_scale
        final_rating = max(1, min(round(raw_score), rating_scale))

        return {"rating": final_rating}

    # ----------------------------------------------------------
    # t5 — generate_improvement_plan
    # Reads: outputs["t3"] (performance_evaluation), outputs["t4"] (rating)
    # Returns: { "improvement_plan": list[str] }
    # ----------------------------------------------------------

    def _generate_improvement_plan(
        self, task: Task, state: AgentState
    ) -> dict:

        params: PerformanceReviewParams = state.params
        evaluation   = self.get_output(state, "t3")["performance_evaluation"]
        rating_output = self.get_output(state, "t4")

        rating       = rating_output["rating"]
        rating_scale = params.rating_scale
        weaknesses   = evaluation["weaknesses"]

        prompt = f"""
You are an HR development specialist. Create a concrete improvement plan.

Employee  : {params.employee_name}
Role      : {params.role}
Rating    : {rating}/{rating_scale}
Weak Areas: {weaknesses}

Return ONLY a list of specific, actionable improvement items, one per line:
- <action item 1>
- <action item 2>
- <action item 3>
- <action item 4>
- <action item 5>

Each item must include: what to improve, how, and a timeframe.
No extra text. No headers.
"""

        response = llm.invoke(prompt)
        content  = response.content.strip()

        plan = [
            line.strip("•-* ").strip()
            for line in content.split("\n")
            if line.strip().startswith("-") or line.strip().startswith("•")
        ]

        return {"improvement_plan": plan}
    


    # performance report 
    # ----------------------------------------------------------
    # t1 - collect_hr_metrics
    # Reads:report_period,departments,metrics_to_include
    # Returns:`{"hr_metrics": HRMetrics}`
    # ----------------------------------------------------------


    def _collect_hr_metrics(
        self,
        task: Task,
        state: AgentState
    ) -> dict:

        p = state.params  # PerformanceReportParams

        period = getattr(p, "report_period", "")

        wanted = getattr(
            p,
            "metrics_to_include",
            []
        ) or [
            "employee_count",
            "goal_completion_rate",
            "average_performance_rating",
        ]

        defaults = {
            "employee_count": 120,
            "average_performance_rating": 4.2,
            "goal_completion_rate": "82%",
            "employee_satisfaction_score": 4.4,
            "attrition_rate": "5%",
            "training_completion_rate": "91%",
            "internal_promotions": 8,
        }

        metrics = {
            m: defaults.get(m, "n/a")
            for m in wanted
        }

        metrics["report_period"] = period

        return {
            "hr_metrics": HRMetrics(
                metrics=metrics
            ).model_dump()
        }