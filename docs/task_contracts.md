# Task Input / Output Contract Specification (MVP)

## Design Rules

* Agents receive the full `AgentState`.
* Agents may read from:

  * `state.params`
  * `state.outputs`
  * mock data sources
* Agents return only an output dictionary.
* The Workflow Executor stores outputs in:

```python
state.outputs[task.task_id] = result
```

* Task Inputs define the data a task is expected to consume.
* Task Outputs define the data a task guarantees to produce.
* Tasks should return only the data required by downstream tasks.

---

# HIRE EMPLOYEE

## t1 - generate_job_description

### Purpose

Generate a job description for the requested role.

### Reads

| Field      | Source       |
| ---------- | ------------ |
| role       | state.params |
| department | state.params |
| job_type   | state.params |
| location   | state.params |

### Returns

```python
{
    "job_description": str
}
```

### Consumed By

* t2 identify_required_skills

---

## t2 - identify_required_skills

### Purpose

Identify role requirements and hiring criteria.

### Reads

| Field            | Source        |
| ---------------- | ------------- |
| job_description  | outputs["t1"] |
| skills_required  | state.params  |
| experience_years | state.params  |

### Returns

```python
{
    "required_skills": list[str]
}
```

### Consumed By

* t3 shortlist_candidates

---

## t3 - shortlist_candidates

### Purpose

Filter candidates against role requirements.

### Reads

| Field            | Source          |
| ---------------- | --------------- |
| required_skills  | outputs["t2"]   |
| experience_years | state.params    |
| candidates       | candidates.json |

### Returns

```python
{
    "shortlisted_candidates": list[Candidate]
}
```

### Consumed By

* t4 schedule_interviews
* t5 prepare_offer

---

## t4 - schedule_interviews

### Purpose

Create interview schedule for shortlisted candidates.

### Reads

| Field                  | Source        |
| ---------------------- | ------------- |
| shortlisted_candidates | outputs["t3"] |

### Returns

```python
{
    "interview_schedule": list[InterviewSchedule]
}
```

### Consumed By

* Informational only

---

## t5 - prepare_offer

### Purpose

Prepare hiring offer for selected candidate.

### Reads

| Field                  | Source        |
| ---------------------- | ------------- |
| shortlisted_candidates | outputs["t3"] |
| salary_range           | state.params  |
| location               | state.params  |
| job_type               | state.params  |

### Returns

```python
{
    "offer_details": OfferDetails
}
```

### Consumed By

* t6 manager_approval
* t7 generate_hiring_summary

---

## t6 - manager_approval

### Purpose

Human approval gate.

### Reads

| Field         | Source        |
| ------------- | ------------- |
| offer_details | outputs["t5"] |

### Returns

```python
{
    "approval_status": str
}
```

### Special Rule

* Approved → Continue Workflow
* Rejected → Stop Workflow

### Consumed By

* t7 generate_hiring_summary

---

## t7 - generate_hiring_summary

### Purpose

Generate final hiring summary.

### Reads

| Field           | Source         |
| --------------- | -------------- |
| offer_details   | outputs["t5"]  |
| approval_status | workflow state |

### Returns

```python
{
    "hiring_summary": str
}
```

---

# ONBOARD EMPLOYEE

## t1 - retrieve_employee_details

### Purpose

Retrieve employee information.

### Reads

| Field         | Source       |
| ------------- | ------------ |
| employee_name | state.params |

### Returns

```python
{
    "employee_details": EmployeeDetails
}
```

### Consumed By

* t2 generate_onboarding_plan
* t3 create_welcome_package
* t4 create_first_week_tasks

---

## t2 - generate_onboarding_plan

### Purpose

Generate onboarding roadmap.

### Reads

| Field            | Source        |
| ---------------- | ------------- |
| employee_details | outputs["t1"] |

### Returns

```python
{
    "onboarding_plan": OnboardingPlan
}
```

### Consumed By

* t3 create_welcome_package
* t4 create_first_week_tasks
* t5 generate_summary

---

## t3 - create_welcome_package

### Purpose

Create welcome package for new employee.

### Reads

| Field            | Source        |
| ---------------- | ------------- |
| employee_details | outputs["t1"] |
| onboarding_plan  | outputs["t2"] |

### Returns

```python
{
    "welcome_package": WelcomePackage
}
```

---

## t4 - create_first_week_tasks

### Purpose

Generate first-week activities.

### Reads

| Field            | Source        |
| ---------------- | ------------- |
| employee_details | outputs["t1"] |
| onboarding_plan  | outputs["t2"] |

### Returns

```python
{
    "first_week_tasks": list[str]
}
```

### Consumed By

* t5 generate_summary

---

## t5 - generate_summary

### Purpose

Generate onboarding summary.

### Reads

| Field            | Source        |
| ---------------- | ------------- |
| employee_details | outputs["t1"] |
| onboarding_plan  | outputs["t2"] |
| first_week_tasks | outputs["t4"] |

### Returns

```python
{
    "summary": str
}
```

---

# SALES OUTREACH

## t1 - gather_market_data

### Purpose

Collect market information for campaign planning.

### Reads

| Field          | Source       |
| -------------- | ------------ |
| target_segment | state.params |
| product_name   | state.params |
| pain_points    | state.params |

### Returns

```python
{
    "market_data": MarketData
}
```

### Consumed By

* t2 analyze_competitors

---

## t2 - analyze_competitors

### Purpose

Analyze competitor positioning.

### Reads

| Field       | Source        |
| ----------- | ------------- |
| market_data | outputs["t1"] |

### Returns

```python
{
    "competitor_analysis": CompetitorAnalysis
}
```

### Consumed By

* t3 create_outreach_strategy

---

## t3 - create_outreach_strategy

### Purpose

Create campaign strategy.

### Reads

| Field               | Source        |
| ------------------- | ------------- |
| competitor_analysis | outputs["t2"] |
| campaign_goal       | state.params  |
| outreach_channels   | state.params  |

### Returns

```python
{
    "outreach_strategy": OutreachStrategy
}
```

### Consumed By

* t4 generate_email_sequence
* t5 generate_call_scripts
* t6 generate_campaign_summary

---

## t4 - generate_email_sequence

### Purpose

Generate outreach emails.

### Reads

| Field             | Source        |
| ----------------- | ------------- |
| outreach_strategy | outputs["t3"] |

### Returns

```python
{
    "email_sequence": list[str]
}
```

### Consumed By

* t6 generate_campaign_summary

---

## t5 - generate_call_scripts

### Purpose

Generate sales call scripts.

### Reads

| Field             | Source        |
| ----------------- | ------------- |
| outreach_strategy | outputs["t3"] |

### Returns

```python
{
    "call_scripts": list[str]
}
```

### Consumed By

* t6 generate_campaign_summary

---

## t6 - generate_campaign_summary

### Purpose

Generate outreach campaign summary.

### Reads

| Field             | Source        |
| ----------------- | ------------- |
| outreach_strategy | outputs["t3"] |
| email_sequence    | outputs["t4"] |
| call_scripts      | outputs["t5"] |

### Returns

```python
{
    "campaign_summary": str
}
```

---

# PERFORMANCE REPORT

## t1 - collect_hr_metrics

### Reads

* report_period
* departments
* metrics_to_include

### Returns

```python
{
    "hr_metrics": HRMetrics
}
```

### Consumed By

* t3 aggregate_results

---

## t2 - collect_sales_metrics

### Reads

* report_period
* metrics_to_include

### Returns

```python
{
    "sales_metrics": SalesMetrics
}
```

### Consumed By

* t3 aggregate_results

---

## t3 - aggregate_results

### Reads

* hr_metrics
* sales_metrics

### Returns

```python
{
    "aggregated_metrics": AggregatedMetrics
}
```

### Consumed By

* t4 generate_kpi_dashboard

---

## t4 - generate_kpi_dashboard

### Reads

* aggregated_metrics

### Returns

```python
{
    "kpi_dashboard": KPIDashboard
}
```

### Consumed By

* t5 generate_executive_summary

---

## t5 - generate_executive_summary

### Reads

* kpi_dashboard

### Returns

```python
{
    "executive_summary": str
}
```

### Consumed By

* t6 generate_recommendations

---

## t6 - generate_recommendations

### Reads

* executive_summary
* aggregated_metrics

### Returns

```python
{
    "recommendations": list[str]
}
```

---

# PERFORMANCE REVIEW

## t1 - retrieve_employee_data

### Reads

* employee_name
* review_period

### Returns

```python
{
    "employee_data": EmployeeDetails
}
```

### Consumed By

* t2 retrieve_goal_data
* t3 evaluate_performance

---

## t2 - retrieve_goal_data

### Reads

* employee_data
* goals_set
* goals_achieved

### Returns

```python
{
    "goal_data": GoalData
}
```

### Consumed By

* t3 evaluate_performance

---

## t3 - evaluate_performance

### Reads

* employee_data
* goal_data
* manager_comments

### Returns

```python
{
    "performance_evaluation": PerformanceEvaluation
}
```

### Consumed By

* t4 generate_rating
* t5 generate_improvement_plan

---

## t4 - generate_rating

### Reads

* performance_evaluation
* rating_scale

### Returns

```python
{
    "rating": int
}
```

### Consumed By

* t5 generate_improvement_plan
* t6 generate_review_summary

---

## t5 - generate_improvement_plan

### Reads

* rating
* performance_evaluation

### Returns

```python
{
    "improvement_plan": list[str]
}
```

### Consumed By

* t6 generate_review_summary

---

## t6 - generate_review_summary

### Reads

* rating
* improvement_plan

### Returns

```python
{
    "review_summary": str
}
```

---

# MARKET RESEARCH

## t1 - gather_research_data

### Reads

* research_topic
* competitors
* focus_areas

### Returns

```python
{
    "research_data": ResearchData
}
```

### Consumed By

* t2 perform_competitor_analysis

---

## t2 - perform_competitor_analysis

### Reads

* research_data

### Returns

```python
{
    "competitor_analysis": CompetitorAnalysis
}
```

### Consumed By

* t3 synthesize_findings

---

## t3 - synthesize_findings

### Reads

* competitor_analysis

### Returns

```python
{
    "findings": list[str]
}
```

### Consumed By

* t4 generate_recommendations
* t5 generate_structured_report

---

## t4 - generate_recommendations

### Reads

* findings

### Returns

```python
{
    "recommendations": list[str]
}
```

### Consumed By

* t5 generate_structured_report

---

## t5 - generate_structured_report

### Reads

* findings
* recommendations

### Returns

```python
{
    "structured_report": StructuredReport
}
```

### Consumed By

* t6 generate_executive_summary

---

## t6 - generate_executive_summary

### Reads

* structured_report

### Returns

```python
{
    "executive_summary": str
}
```
