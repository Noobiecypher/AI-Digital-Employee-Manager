import { api } from './client'
import { mockAnalytics } from '../mock/mockData'

export const reportsApi = {
  getAnalytics: () => api.get('/workflows/report/analytics').catch(() => mockAnalytics),
  getReports:   () => api.get('/workflows/reports').catch(() => []),
}