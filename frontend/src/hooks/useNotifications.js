import { useState, useCallback } from 'react'

let _id = 0

export function useNotifications() {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback(({ type = 'info', title, message, duration = 4000 }) => {
    const id = ++_id
    setToasts(prev => [...prev, { id, type, title, message }])
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id))
    }, duration)
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return {
    toasts,
    success: (title, message) => addToast({ type: 'success', title, message }),
    error:   (title, message) => addToast({ type: 'danger',  title, message }),
    info:    (title, message) => addToast({ type: 'info',    title, message }),
    warning: (title, message) => addToast({ type: 'warning', title, message }),
    removeToast,
  }
}