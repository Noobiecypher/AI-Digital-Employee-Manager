export const WORKFLOW_STATES = {
  PENDING:            'pending',
  RUNNING:            'running',
  WAITING_FOR_HUMAN:  'waiting_for_human',
  COMPLETED:          'completed',
  FAILED:             'failed',
}

export const WORKFLOW_TYPES = [
  { value: 'hire_employee',      label: 'Hire Employee' },
  { value: 'onboard_employee',   label: 'Onboard Employee' },
  { value: 'sales_outreach',     label: 'Sales Outreach' },
  { value: 'market_research',    label: 'Market Research' },
  { value: 'performance_review', label: 'Performance Review' },
  { value: 'performance_report', label: 'Performance Report' },
]

export const STATE_META = {
  pending:           { label: 'Pending',        color: 'warning' },
  running:           { label: 'Running',        color: 'info'    },
  waiting_for_human: { label: 'Needs Approval', color: 'warning' },
  completed:         { label: 'Completed',      color: 'success' },
  failed:            { label: 'Failed',         color: 'danger'  },
  // real API values
  paused:            { label: 'Needs Approval', color: 'warning' },
}