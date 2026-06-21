import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAdminStore } from './store'
import { Sidebar } from './components/Sidebar'

const LoginPage = lazy(() => import('./pages/LoginPage'))
const GenerationPage = lazy(() => import('./pages/GenerationPage'))
const ProblemsPage = lazy(() => import('./pages/ProblemsPage'))
const UsersPage = lazy(() => import('./pages/UsersPage'))
const MonitoringPage = lazy(() => import('./pages/MonitoringPage'))

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAdminStore((s) => s.isAuthenticated)
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <Sidebar />
      <main style={{ flex: 1, padding: '32px 40px', overflowY: 'auto', minWidth: 0 }}>
        {children}
      </main>
    </div>
  )
}

const Spinner = () => (
  <div style={{ display: 'flex', height: '100vh', alignItems: 'center', justifyContent: 'center', color: 'var(--text-secondary)' }}>
    Loading…
  </div>
)

export function App() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/generation" element={<ProtectedLayout><GenerationPage /></ProtectedLayout>} />
        <Route path="/problems" element={<ProtectedLayout><ProblemsPage /></ProtectedLayout>} />
        <Route path="/users" element={<ProtectedLayout><UsersPage /></ProtectedLayout>} />
        <Route path="/monitoring" element={<ProtectedLayout><MonitoringPage /></ProtectedLayout>} />
        <Route path="*" element={<Navigate to="/generation" replace />} />
      </Routes>
    </Suspense>
  )
}
