import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { RoleProvider } from './context/RoleContext'
import AppLayout from './components/layout/AppLayout'
import ProtectedRoute from './components/layout/ProtectedRoute'
import RequireAuth from './components/layout/RequireAuth'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import EmployeeList from './pages/employees/EmployeeList'
import EmployeeForm from './pages/employees/EmployeeForm'
import CandidateList from './pages/candidates/CandidateList'
import CandidateDetail from './pages/candidates/CandidateDetail'
import CandidateForm from './pages/candidates/CandidateForm'
import ProductList from './pages/products/ProductList'
import ProductForm from './pages/products/ProductForm'
import GoalsDashboard from './pages/goals/GoalsDashboard'
import GoalDetail from './pages/goals/GoalDetail'
import RoleList from './pages/roles/RoleList'
import RoleForm from './pages/roles/RoleForm'
import WorkflowDashboard from './pages/workflows/WorkflowDashboard'
import StartWorkflow from './pages/workflows/StartWorkflow'
import WorkflowDetail from './pages/workflows/WorkflowDetail'
import WorkflowHistory from './pages/workflows/WorkflowHistory'
import ApprovalDashboard from './pages/workflows/ApprovalDashboard'
import ReportingDashboard from './pages/reporting/ReportingDashboard'
import ReportsView from './pages/reporting/ReportsView'
import Notifications from './pages/Notifications'
import Unauthorized from './pages/Unauthorized'
import JobsPage from './pages/jobs/JobsPage'
import ApplyPage from './pages/jobs/ApplyPage'

export default function App() {
  return (
    <RoleProvider>
      <BrowserRouter>
        <Routes>
          {/* Public routes — no auth required */}
          <Route path="/login" element={<Login />} />
          <Route path="/apply/:job_id" element={<ApplyPage />} />

          {/* Protected app routes */}
          <Route path="/" element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard"     element={<Dashboard />} />
            <Route path="notifications" element={<Notifications />} />
            <Route path="unauthorized"  element={<Unauthorized />} />

            {/* Goals — accessible to multiple roles, permission matrix handles fine-grain */}
            <Route path="goals"     element={<ProtectedRoute><GoalsDashboard /></ProtectedRoute>} />
            <Route path="goals/:id" element={<ProtectedRoute><GoalDetail /></ProtectedRoute>} />

            {/* Employees — HR + Admin */}
            <Route path="employees"          element={<ProtectedRoute><EmployeeList /></ProtectedRoute>} />
            <Route path="employees/new"      element={<ProtectedRoute><EmployeeForm /></ProtectedRoute>} />
            <Route path="employees/:id/edit" element={<ProtectedRoute><EmployeeForm /></ProtectedRoute>} />

            {/* Candidates — HR, Manager, Admin */}
            <Route path="candidates"          element={<ProtectedRoute><CandidateList /></ProtectedRoute>} />
            <Route path="candidates/new"      element={<ProtectedRoute><CandidateForm /></ProtectedRoute>} />
            <Route path="candidates/:id"      element={<ProtectedRoute><CandidateDetail /></ProtectedRoute>} />
            <Route path="candidates/:id/edit" element={<ProtectedRoute><CandidateForm /></ProtectedRoute>} />

            {/* Products — Manager, Admin */}
            <Route path="products"          element={<ProtectedRoute><ProductList /></ProtectedRoute>} />
            <Route path="products/new"      element={<ProtectedRoute><ProductForm /></ProtectedRoute>} />
            <Route path="products/:id/edit" element={<ProtectedRoute><ProductForm /></ProtectedRoute>} />

            {/* Roles — Admin only per matrix, enforced via canAccess */}
            <Route path="roles"          element={<ProtectedRoute><RoleList /></ProtectedRoute>} />
            <Route path="roles/new"      element={<ProtectedRoute><RoleForm /></ProtectedRoute>} />
            <Route path="roles/:id/edit" element={<ProtectedRoute><RoleForm /></ProtectedRoute>} />

            {/* Workflows — HR, Manager, Admin */}
            <Route path="workflows"         element={<ProtectedRoute><WorkflowDashboard /></ProtectedRoute>} />
            <Route path="workflows/start"   element={<ProtectedRoute><StartWorkflow /></ProtectedRoute>} />
            <Route path="workflows/history" element={<ProtectedRoute><WorkflowHistory /></ProtectedRoute>} />
            <Route path="workflows/:id"     element={<ProtectedRoute><WorkflowDetail /></ProtectedRoute>} />

            <Route path="approvals" element={<ProtectedRoute><ApprovalDashboard /></ProtectedRoute>} />

            {/* Reporting — Manager, Admin */}
            <Route path="reporting"         element={<ProtectedRoute><ReportingDashboard /></ProtectedRoute>} />
            <Route path="reporting/reports" element={<ProtectedRoute><ReportsView /></ProtectedRoute>} />

            {/* Jobs — HR, Manager, Admin */}
            <Route path="jobs"         element={<ProtectedRoute><JobsPage /></ProtectedRoute>} />
            <Route path="jobs/:job_id" element={<ProtectedRoute><JobsPage /></ProtectedRoute>} />
          </Route>
        </Routes>
      </BrowserRouter>
    </RoleProvider>
  )
}