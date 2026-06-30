# Agent Responsibilities

Developer reference extracted from `workflow_definitions.py` and `task_contracts.md`.
Do not edit manually — update the source files instead.

---

## Shared Agent Contract

All agents implement:

```python
def execute(task: Task, state: AgentState) -> dict
```

- Read inputs from `state.params` and `state.outputs`.
- Return a plain `dict` whose keys match the contract in `task_contracts.md`.
- Never modify `AgentState` directly — the Workflow Executor writes `state.outputs[task.task_id] = result`.

---

## 1. Recruitment Agent

**Workflows:** `hire_employee`

| Task | Action                    | Purpose                                          | Output                                          |
|------|---------------------------|--------------------------------------------------|-------------------------------------------------|
| t1   | generate_job_description  | Generate a job description for the requested role | `{"job_description": str}`                     |
| t2   | identify_required_skills  | Identify role requirements and hiring criteria   | `{"required_skills": list[str]}`                |
| t3   | shortlist_candidates      | Filter candidates against role requirements      | `{"shortlisted_candidates": list[Candidate]}`   |
| t4   | schedule_interviews       | Create interview schedule for shortlisted candidates | `{"interview_schedule": list[InterviewSchedule]}` |
| t6 | prepare_offer | Prepare hiring offer(s) for HR-selected candidate(s). Falls back to highest-scoring candidate if no human selection exists. | {"offer_details": list[OfferDetails]} |

---

## 2. HR Agent

**Workflows:** `onboard_employee`, `performance_report`, `performance_review`

### onboard_employee

| Task | Action                    | Purpose                                 | Output                                    |
|------|---------------------------|-----------------------------------------|-------------------------------------------|
| t1   | retrieve_employee_details | Retrieve employee information           | `{"employee_details": EmployeeDetails}`   |
| t2   | generate_onboarding_plan  | Generate onboarding roadmap             | `{"onboarding_plan": OnboardingPlan}`     |
| t3   | create_welcome_package    | Create welcome package for new employee | `{"welcome_package": WelcomePackage}`     |
| t4   | create_first_week_tasks   | Generate first-week activities          | `{"first_week_tasks": list[str]}`         |

### performance_report

| Task | Action              | Purpose                       | Output                        |
|------|---------------------|-------------------------------|-------------------------------|
| t1   | collect_hr_metrics  | Collect HR metrics for period | `{"hr_metrics": HRMetrics}`   |

### performance_review

| Task | Action                   | Purpose                                      | Output                                              |
|------|--------------------------|----------------------------------------------|-----------------------------------------------------|
| t1   | retrieve_employee_data   | Retrieve employee record for review period   | `{"employee_data": EmployeeDetails}`                |
| t2   | retrieve_goal_data       | Retrieve set and achieved goals              | `{"goal_data": GoalData}`                           |
| t3   | evaluate_performance     | Assess performance against goals and comments | `{"performance_evaluation": PerformanceEvaluation}` |
| t4   | generate_rating          | Produce numeric rating from evaluation       | `{"rating": int}`                                   |
| t5   | generate_improvement_plan | Generate improvement actions from rating    | `{"improvement_plan": list[str]}`                   |

---

## 3. Sales Agent

**Workflows:** `sales_outreach`, `performance_report`

### sales_outreach

| Task | Action                   | Purpose                            | Output                                  |
|------|--------------------------|------------------------------------|-----------------------------------------|
| t3   | create_outreach_strategy | Create campaign strategy           | `{"outreach_strategy": OutreachStrategy}` |
| t4   | generate_email_sequence  | Generate outreach emails           | `{"email_sequence": list[str]}`         |
| t5   | generate_call_scripts    | Generate sales call scripts        | `{"call_scripts": list[str]}`           |
| t7 | send_outreach | Send approved outreach emails | `{"send_statistics": dict}` |

### performance_report

| Task | Action                | Purpose                          | Output                            |
|------|-----------------------|----------------------------------|-----------------------------------|
| t2   | collect_sales_metrics | Collect sales metrics for period | `{"sales_metrics": SalesMetrics}` |

---

## 4. Research Agent

**Workflows:** `sales_outreach`, `market_research`

### sales_outreach

| Task | Action              | Purpose                                    | Output                                      |
|------|---------------------|--------------------------------------------|---------------------------------------------|
| t1   | gather_market_data  | Collect market information for campaign planning | `{"market_data": MarketData}`         |
| t2   | analyze_competitors | Analyze competitor positioning             | `{"competitor_analysis": CompetitorAnalysis}` |

### market_research

| Task | Action                      | Purpose                                   | Output                                        |
|------|-----------------------------|-------------------------------------------|-----------------------------------------------|
| t1   | gather_research_data        | Collect research data for topic           | `{"research_data": ResearchData}`             |
| t2   | perform_competitor_analysis | Analyze competitor positioning            | `{"competitor_analysis": CompetitorAnalysis}` |
| t3   | synthesize_findings         | Synthesize findings from competitor data  | `{"findings": list[str]}`                     |
| t4   | generate_recommendations    | Generate recommendations from findings   | `{"recommendations": list[str]}`              |
| t5   | generate_structured_report  | Compile findings and recommendations into a report | `{"structured_report": StructuredReport}` |

---

## 5. Reporting Agent

**Workflows:** `hire_employee`, `onboard_employee`, `sales_outreach`, `performance_report`, `performance_review`, `market_research`

| Workflow           | Task | Action                    | Purpose                                         | Output                                      |
|--------------------|------|---------------------------|-------------------------------------------------|---------------------------------------------|
| hire_employee      | t9   | generate_hiring_summary   | Generate final hiring summary                   | `{"hiring_summary": str}`                   |
| onboard_employee   | t5   | generate_summary          | Generate onboarding summary                     | `{"summary": str}`                          |
| sales_outreach     | t8   | generate_campaign_summary | Generate outreach campaign summary              | `{"campaign_summary": str}`                 |
| performance_report | t3   | aggregate_results         | Aggregate HR and sales metrics                  | `{"aggregated_metrics": AggregatedMetrics}` |
| performance_report | t4   | generate_kpi_dashboard    | Build KPI dashboard from aggregated metrics     | `{"kpi_dashboard": KPIDashboard}`           |
| performance_report | t5   | generate_executive_summary | Summarise KPI dashboard for leadership         | `{"executive_summary": str}`                |
| performance_report | t6   | generate_recommendations  | Generate recommendations from metrics          | `{"recommendations": list[str]}`            |
| performance_review | t6   | generate_review_summary   | Generate final review summary                   | `{"review_summary": str}`                   |
| market_research    | t6   | generate_executive_summary | Summarise structured report for leadership     | `{"executive_summary": str}`                |

---

## 6. Human Approval Gate

The human approval gate is **not an agent**. It is a Workflow Executor checkpoint that pauses execution and awaits an external decision.

Workflows : hire_employee, sales_outreach

Human approval gates are Executor checkpoints that pause execution and await an external decision.

Supported gates:

| Task | Action | Approver Role |
|-------|--------|---------------|
| t5 | hr_select_candidates | HR |
| t7 | hr_offer_approval | HR |
| t8 | manager_approval | MANAGER |
| t6 | approve_outreach_campaign | MANAGER |

### Output stored

Each human task stores:

```python
state.outputs[task_id] = {
    "approval_status": str,
    "human_feedback": str | None,
    "human_input_data": dict
}
```

### Behaviour

| State field             | Value set by Executor          |
|-------------------------|--------------------------------|
| `state.awaiting_human_input` | `True` while pending      |
| `state.approval_status` | `"approved"` or `"rejected"`  |
| `state.status`          | `"failed"` if rejected         |
| `state.human_feedback` | Human approver comments for the most recently resolved approval gate |

### Decision rules

```
approval_status == "approved"  →  continue workflow execution
approval_status == "rejected"  →  set state.status = "failed", stop execution
```

### Output stored

The Executor copies:

```python
state.outputs[task_id]["approval_status"]
```

to:

```python
state.approval_status
```

before deciding whether workflow execution should continue.

The authoritative workflow approval state is:

```python
state.approval_status
```