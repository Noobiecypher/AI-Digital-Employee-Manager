export const mockEmployees = [
    { _id: '1', employee_id: 'EMP001', employee_name: 'Alex Sharma', role: 'Backend Engineer', department: 'Engineering', joining_date: '2025-01-15', manager_name: 'Ravi Kumar', work_mode: 'hybrid' },
    { _id: '2', employee_id: 'EMP002', employee_name: 'Priya Nair', role: 'Frontend Developer', department: 'Engineering', joining_date: '2025-03-01', manager_name: 'Ravi Kumar', work_mode: 'remote' },
    { _id: '3', employee_id: 'EMP003', employee_name: 'Rahul Mehta', role: 'Product Manager', department: 'Product', joining_date: '2024-11-10', manager_name: 'Sunita Patel', work_mode: 'onsite' },
  ]
  
  export const mockCandidates = [
    { _id: '1', candidate_id: 'CAN001', name: 'Ananya Rao', role_applied: 'Backend Engineer', skills: ['Python', 'FastAPI', 'Docker', 'PostgreSQL'], experience_years: 4, match_score: 82, email: 'ananya@email.com', phone: '+91 98765 43210' },
    { _id: '2', candidate_id: 'CAN002', name: 'Karan Verma', role_applied: 'Frontend Developer', skills: ['React', 'TypeScript', 'Tailwind'], experience_years: 2, match_score: 67, email: 'karan@email.com', phone: '+91 91234 56789' },
    { _id: '3', candidate_id: 'CAN003', name: 'Sneha Iyer', role_applied: 'DevOps Engineer', skills: ['Kubernetes', 'AWS', 'Terraform', 'Docker'], experience_years: 5, match_score: 91, email: 'sneha@email.com', phone: '+91 99887 76655' },
  ]
  
  export const mockProducts = [
    { _id: '1', product_name: 'AI Recruiter Pro', category: 'HR Tech', description: 'End-to-end AI-powered recruitment automation platform.', pain_points: ['Manual screening', 'Slow hiring'], target_industries: ['BFSI', 'Healthcare'], price_range: '₹10,000–₹50,000/mo' },
    { _id: '2', product_name: 'SalesBot 360', category: 'Sales Tech', description: 'Automated outreach and lead nurturing platform.', pain_points: ['Low response rates', 'Manual follow-ups'], target_industries: ['Retail', 'SaaS'], price_range: '₹5,000–₹25,000/mo' },
  ]
  
  export const mockGoals = [
    { _id: '1', employee_name: 'Alex Sharma', review_period: 'Q1 2025', goals: ['Ship v2 API', 'Reduce latency by 30%', 'Mentor 2 junior devs'], manager_feedback: 'Alex has shown exceptional ownership this quarter. Delivered all milestones on time.', overall_rating: 4, rating_scale: 5 },
    { _id: '2', employee_name: 'Priya Nair', review_period: 'Q1 2025', goals: ['Launch new dashboard', 'Improve accessibility score', 'Write component library docs'], manager_feedback: 'Priya delivered the dashboard ahead of schedule with great attention to detail.', overall_rating: 5, rating_scale: 5 },
  ]
  
  export const mockRoles = [
    { _id: '1', role: 'Backend Engineer', department: 'Engineering', experience_years: 3, skills_required: ['Python', 'FastAPI', 'MongoDB'], location: 'Hyderabad / Remote', salary_range: '₹8–15 LPA', rating_scale: 5, onboarding_checklist: ['Setup dev environment', 'Meet the team', 'Review codebase'] },
    { _id: '2', role: 'Frontend Developer', department: 'Engineering', experience_years: 2, skills_required: ['React', 'TypeScript', 'Tailwind'], location: 'Remote', salary_range: '₹6–12 LPA', rating_scale: 5, onboarding_checklist: ['Setup local env', 'Review design system', 'Ship first PR'] },
  ]
  
  export const mockWorkflows = [
    { _id: 'wf001', workflow_type: 'hire_employee', state: 'completed', result: 'Candidate Ananya Rao has been shortlisted. Offer letter prepared for ₹12 LPA.', task_outputs: { t1: 'Job description generated for Backend Engineer role.', t2: 'Required skills identified: Python, FastAPI, Docker, PostgreSQL, Redis.', t3: 'Top 3 candidates shortlisted from pool of 12 applicants.', t4: 'Interviews scheduled for Mon 30 June at 10am, 11am, 12pm.', t5: 'Offer letter prepared: ₹12 LPA, hybrid, joining 1 Aug 2025.' } },
    { _id: 'wf002', workflow_type: 'sales_outreach', state: 'waiting_for_human', result: 'Outreach campaign ready for review. 3 email templates generated targeting BFSI sector.', task_outputs: { t1: 'Lead research completed. 15 prospects identified in BFSI sector.', t2: 'Outreach strategy: LinkedIn + Email, 3-touch sequence over 2 weeks.' } },
    { _id: 'wf003', workflow_type: 'market_research', state: 'running', task_outputs: { t1: 'Market analysis initiated for HR Tech segment.' } },
    { _id: 'wf004', workflow_type: 'onboard_employee', state: 'failed', task_outputs: { t1: 'Onboarding plan generation failed — employee record not found.' } },
  ]
  
  export const mockAnalytics = {
    total_workflows: 4,
    success_rate: 50,
    completed: 1,
    failed: 1,
    running: 1,
    paused: 1,
    objective_distribution: { hire_employee: 1, sales_outreach: 1, market_research: 1, onboard_employee: 1 },
    agent_usage: [
      { assigned_agent: 'recruitment', count: 2 },
      { assigned_agent: 'reporting', count: 1 },
      { assigned_agent: 'sales', count: 1 },
    ],
    workflow_execution_history: [
      { workflow_name: 'hire_employee', status: 'completed', assigned_agent: 'recruitment', date: '2025-06-20' },
      { workflow_name: 'sales_outreach', status: 'waiting_for_human', assigned_agent: 'sales', date: '2025-06-22' },
      { workflow_name: 'market_research', status: 'running', assigned_agent: 'reporting', date: '2025-06-25' },
      { workflow_name: 'onboard_employee', status: 'failed', assigned_agent: 'recruitment', date: '2025-06-26' },
    ],
    narrative: 'Platform has processed 4 workflows with a 50% success rate. Recruitment agent is the most active.',
  }