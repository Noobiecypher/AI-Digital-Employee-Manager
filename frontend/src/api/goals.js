import { api } from './client'

const BASE = '/api/goals'

export const goalsApi = {
  getAll:  () => api.get(BASE),
  getForEmployee: (employeeName) =>
    api.get(BASE).then(res => {
      const arr = Array.isArray(res) ? res : res?.items || res?.goals || []
      return arr.filter(g =>
        g.employee_name?.toLowerCase() === employeeName?.toLowerCase()
      )
    }),
  getOne:  (employeeName, period) =>
    api.get(`${BASE}/${encodeURIComponent(employeeName)}/${encodeURIComponent(period)}`),
  create:  (data) => api.post(BASE, data),
  update:  (employeeName, period, data) =>
    api.put(`${BASE}/${encodeURIComponent(employeeName)}/${encodeURIComponent(period)}`, data),
  delete:  (employeeName, period) =>
    api.delete(`${BASE}/${encodeURIComponent(employeeName)}/${encodeURIComponent(period)}`),

  // Employee: mark goals as achieved and submit for manager review
  requestUpdate: (employeeName, period, goalsAchieved) =>
    api.post(
      `${BASE}/${encodeURIComponent(employeeName)}/${encodeURIComponent(period)}/request-update`,
      { goals_achieved: goalsAchieved }
    ),

  // Manager: approve or reject submitted goals
  review: (employeeName, period, approvalStatus, managerComments = null) =>
    api.post(
      `${BASE}/${encodeURIComponent(employeeName)}/${encodeURIComponent(period)}/review`,
      { approval_status: approvalStatus, manager_comments: managerComments }
    ),
}