import { api } from './client'
import { mockGoals } from '../mock/mockData'

const BASE = '/api/goals'

export const goalsApi = {
  getAll:  ()                         => api.get(BASE).catch(() => mockGoals),
  getOne:  (employeeName, period)     => api.get(`${BASE}/${employeeName}/${period}`).catch(() => mockGoals[0]),
  create:  (data)                     => api.post(BASE, data).catch(() => ({ ...data })),
  update:  (employeeName, period, data) => api.put(`${BASE}/${employeeName}/${period}`, data).catch(() => data),
  delete:  (employeeName, period)     => api.delete(`${BASE}/${employeeName}/${period}`).catch(() => null),
}