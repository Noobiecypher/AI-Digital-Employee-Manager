import { api } from './client'
import { mockWorkflows } from '../mock/mockData'

export const workflowsApi = {
  getAll:     ()         => api.get('/workflows?limit=100').then(res => Array.isArray(res) ? res : res?.items || []).catch(() => mockWorkflows),
  getOne:     (id)       => api.get(`/workflows/${id}`).catch(() => mockWorkflows.find(w => w.workflow_id === id) || mockWorkflows[0]),
  start:      (data)     => api.post('/workflows/start', data),
  approve:    (id)       => api.post(`/workflows/${id}/resume`, { approval_status: 'approved', human_feedback: null }),
  reject:     (id)       => api.post(`/workflows/${id}/resume`, { approval_status: 'rejected', human_feedback: null }),
  getPending: ()         => api.get('/workflows?limit=100').then(res => {
    const all = Array.isArray(res) ? res : res?.items || []
    return all.filter(w => w.awaiting_human_input === true)
  }).catch(() => []),
  getHistory: ()         => api.get('/workflows?limit=100').then(res => Array.isArray(res) ? res : res?.items || []).catch(() => mockWorkflows),
}