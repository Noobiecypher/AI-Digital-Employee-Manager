import { api } from './client'
import { mockWorkflows } from '../mock/mockData'

export const workflowsApi = {
  getAll:     ()         => api.get('/workflows').catch(() => ({ items: mockWorkflows })),
  getOne:     (id)       => api.get(`/workflows/${id}`).catch(() => mockWorkflows.find(w => w._id === id) || mockWorkflows[0]),
  start:      (data)     => api.post('/workflows/start', data),
  approve:    (id, data) => api.post(`/workflows/${id}/resume`, { approved: true, ...data }),
  reject:     (id, data) => api.post(`/workflows/${id}/resume`, { approved: false, ...data }),
  getPending: ()         => api.get('/workflows').then(res => {
    const all = Array.isArray(res) ? res : res?.items || []
    return all.filter(w => w.awaiting_human_input === true)
  }).catch(() => []),
  getHistory: ()         => api.get('/workflows').catch(() => ({ items: mockWorkflows })),
}