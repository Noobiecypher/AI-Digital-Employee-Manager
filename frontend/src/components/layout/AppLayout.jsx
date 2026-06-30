import { Outlet } from 'react-router-dom'
import Sidebar from './Sidebar'
import Navbar from './Navbar'
import { useNotifications } from '../../hooks/useNotifications'
import NotificationToast from '../ui/NotificationToast'
import { createContext, useContext } from 'react'

const ToastContext = createContext(null)
export const useToast = () => useContext(ToastContext)

export default function AppLayout() {
  const notifications = useNotifications()

  return (
    <ToastContext.Provider value={notifications}>
      <div style={{
        display: 'flex',
        minHeight: '100vh',
        width: '100%',
        background: 'var(--color-bg-page)',
      }}>
        <Sidebar />
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          marginLeft: 'var(--sidebar-width)',
          width: 'calc(100% - var(--sidebar-width))',
          minWidth: 0,
          overflow: 'hidden',
        }}>
          <Navbar />
          <main style={{
            flex: 1,
            padding: '24px',
            marginTop: 'var(--navbar-height)',
            overflowY: 'auto',
            width: '100%',
            boxSizing: 'border-box',
          }}>
            <Outlet />
          </main>
        </div>
        <NotificationToast
          toasts={notifications.toasts}
          onRemove={notifications.removeToast}
        />
      </div>
    </ToastContext.Provider>
  )
}