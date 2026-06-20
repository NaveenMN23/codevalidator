import { lazy, Suspense } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { useAppStore } from './store';
import { Navbar } from './components/ui/Navbar';

const DashboardPage = lazy(() => import('./pages/DashboardPage'));
const LoginPage = lazy(() => import('./pages/LoginPage'));
const SignupPage = lazy(() => import('./pages/SignupPage'));
const WorkspacePage = lazy(() => import('./pages/WorkspacePage'));


function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAppStore((state) => state.isAuthenticated);
  return isAuthenticated ? children : <Navigate to="/login" replace />;
}

function App() {
  const location = useLocation();
  const isWorkspace = location.pathname.startsWith('/workspace');

  return (
    <div className="h-screen bg-background text-text-main flex flex-col font-sans overflow-hidden">
      {!isWorkspace && <Navbar />}
      <main className={`flex-grow flex flex-col min-h-0 ${isWorkspace ? '' : 'pt-[72px]'}`}>
        <Suspense fallback={<div className="flex h-full items-center justify-center bg-background text-text-muted font-medium">Loading...</div>}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/signup" element={<SignupPage />} />
            <Route path="/workspace/:challengeId" element={
              <ProtectedRoute>
                <WorkspacePage />
              </ProtectedRoute>
            } />
            <Route path="/profile" element={<ProtectedRoute><div className="p-8">Profile</div></ProtectedRoute>} />
            <Route path="/leaderboard" element={<ProtectedRoute><div className="p-8">Leaderboard</div></ProtectedRoute>} />
            <Route path="/u/:username" element={<div className="p-8">Public Profile</div>} />
          </Routes>
        </Suspense>
      </main>
    </div>
  );
}

export { App };