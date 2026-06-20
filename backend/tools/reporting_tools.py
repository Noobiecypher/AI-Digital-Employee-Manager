def calculate_workflow_metrics(log_data: dict) -> dict:
    """
    Parses execution data to compile hard KPIs and visual data structures 
    tailored specifically for UI Dashboard cards and Graph components.
    """
    logs = log_data.get("agent_logs", [])
    total_tasks = len(logs)
    
    if total_tasks == 0:
        return {"ui_kpi_cards": {}, "ui_chart_series": []}

    # Identify tasks that require attention (Failures or Escalations)
    anomalies = sum(1 for item in logs if item["status"] in ["Failed", "Escalated"])
    success_rate = ((total_tasks - anomalies) / total_tasks) * 100
    
    # Structure data perfectly for UI Chart components (e.g., Recharts)
    chart_series = []
    for index, item in enumerate(logs):
        chart_series.append({
            "id": index + 1,
            "task_name": item["task"][:25] + "...", 
            "assigned_agent": item["agent"],
            "execution_status": item["status"]
        })

    return {
        "ui_kpi_cards": {
            "success_rate": f"{success_rate:.1f}%",
            "runtime": f"{log_data['meta_stats']['execution_time_seconds']}s",
            "resource_cost": f"${log_data['meta_stats']['total_cost_usd']}"
        },
        "ui_chart_series": chart_series
    }