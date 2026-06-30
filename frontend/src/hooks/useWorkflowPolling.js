import { useState, useEffect, useRef, useCallback } from 'react'
import { workflowsApi } from '../api/workflows'

const TERMINAL_STATUSES = ['completed', 'failed']
const POLL_INTERVAL_MS  = 4000

export function useWorkflowPolling(workflowId, { enabled = true } = {}) {
  const [workflow, setWorkflow]   = useState(null)
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const intervalRef               = useRef(null)

  const fetchWorkflow = useCallback(async () => {
    if (!workflowId) return
    try {
      const data = await workflowsApi.getOne(workflowId)
      setWorkflow(data)
      setError(null)
      const status = data.status || data.state || ''
      if (TERMINAL_STATUSES.includes(status)) {
        clearInterval(intervalRef.current)
      }
    } catch (err) {
      setError(err.message)
      clearInterval(intervalRef.current)
    } finally {
      setLoading(false)
    }
  }, [workflowId])

  useEffect(() => {
    if (!workflowId || !enabled) return
    fetchWorkflow()
    intervalRef.current = setInterval(fetchWorkflow, POLL_INTERVAL_MS)
    return () => clearInterval(intervalRef.current)
  }, [workflowId, enabled, fetchWorkflow])

  return { workflow, loading, error, refetch: fetchWorkflow }
}