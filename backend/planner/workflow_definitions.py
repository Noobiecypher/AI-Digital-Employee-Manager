from models import Task


WORKFLOWS = {

    "hire_employee": [

        Task(
            task_id="t1",
            agent="recruitment",
            action="generate_job_description",
            depends_on=[]
        ),

        Task(
            task_id="t2",
            agent="recruitment",
            action="identify_required_skills",
            depends_on=["t1"]
        ),

        Task(
            task_id="t3",
            agent="recruitment",
            action="shortlist_candidates",
            depends_on=["t2"]
        ),

        Task(
            task_id="t4",
            agent="recruitment",
            action="schedule_interviews",
            depends_on=["t3"]
        ),

        Task(
            task_id="t5",
            agent="recruitment",
            action="prepare_offer",
            depends_on=["t4"]
        ),

        # Human-in-the-Loop Approval Gate
        # Approved -> continue workflow
        # Rejected -> fail workflow

        Task(
            task_id="t6",
            agent="human",
            action="manager_approval",
            depends_on=["t5"]
        ),

        Task(
            task_id="t7",
            agent="reporting",
            action="generate_hiring_summary",
            depends_on=["t6"]
        ),
    ],

    "onboard_employee": [

        Task(
            task_id="t1",
            agent="hr",
            action="retrieve_employee_details",
            depends_on=[]
        ),

        Task(
            task_id="t2",
            agent="hr",
            action="generate_onboarding_plan",
            depends_on=["t1"]
        ),

        Task(
            task_id="t3",
            agent="hr",
            action="create_welcome_package",
            depends_on=["t2"]
        ),

        Task(
            task_id="t4",
            agent="hr",
            action="create_first_week_tasks",
            depends_on=["t3"]
        ),

        Task(
            task_id="t5",
            agent="reporting",
            action="generate_summary",
            depends_on=["t4"]
        ),
    ],

    "sales_outreach": [

        Task(
            task_id="t1",
            agent="research",
            action="gather_market_data",
            depends_on=[]
        ),

        Task(
            task_id="t2",
            agent="research",
            action="analyze_competitors",
            depends_on=["t1"]
        ),

        Task(
            task_id="t3",
            agent="sales",
            action="create_outreach_strategy",
            depends_on=["t2"]
        ),

        Task(
            task_id="t4",
            agent="sales",
            action="generate_email_sequence",
            depends_on=["t3"]
        ),

        Task(
            task_id="t5",
            agent="sales",
            action="generate_call_scripts",
            depends_on=["t4"]
        ),

        Task(
            task_id="t6",
            agent="reporting",
            action="generate_campaign_summary",
            depends_on=["t5"]
        ),
    ],

    "performance_report": [

        Task(
            task_id="t1",
            agent="hr",
            action="collect_hr_metrics",
            depends_on=[]
        ),

        Task(
            task_id="t2",
            agent="sales",
            action="collect_sales_metrics",
            depends_on=[]
        ),

        Task(
            task_id="t3",
            agent="reporting",
            action="aggregate_results",
            depends_on=["t1", "t2"]
        ),

        Task(
            task_id="t4",
            agent="reporting",
            action="generate_kpi_dashboard",
            depends_on=["t3"]
        ),

        Task(
            task_id="t5",
            agent="reporting",
            action="generate_executive_summary",
            depends_on=["t4"]
        ),

        Task(
            task_id="t6",
            agent="reporting",
            action="generate_recommendations",
            depends_on=["t3","t5"]
        ),
    ],

    "performance_review": [

        Task(
            task_id="t1",
            agent="hr",
            action="retrieve_employee_data",
            depends_on=[]
        ),

        Task(
            task_id="t2",
            agent="hr",
            action="retrieve_goal_data",
            depends_on=["t1"]
        ),

        Task(
            task_id="t3",
            agent="hr",
            action="evaluate_performance",
            depends_on=["t2"]
        ),

        Task(
            task_id="t4",
            agent="hr",
            action="generate_rating",
            depends_on=["t3"]
        ),

        Task(
            task_id="t5",
            agent="hr",
            action="generate_improvement_plan",
            depends_on=["t4"]
        ),

        Task(
            task_id="t6",
            agent="reporting",
            action="generate_review_summary",
            depends_on=["t3","t4","t5"]
        ),
    ],

    "market_research": [

        Task(
            task_id="t1",
            agent="research",
            action="gather_research_data",
            depends_on=[]
        ),

        Task(
            task_id="t2",
            agent="research",
            action="perform_competitor_analysis",
            depends_on=["t1"]
        ),

        Task(
            task_id="t3",
            agent="research",
            action="synthesize_findings",
            depends_on=["t2"]
        ),

        Task(
            task_id="t4",
            agent="research",
            action="generate_recommendations",
            depends_on=["t3"]
        ),

        Task(
            task_id="t5",
            agent="research",
            action="generate_structured_report",
            depends_on=["t4"]
        ),

        Task(
            task_id="t6",
            agent="reporting",
            action="generate_executive_summary",
            depends_on=["t5"]
        ),
    ],
}