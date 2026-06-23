import { Dashboard } from '../features/dashboard/components/Dashboard';

export default function DashboardPage() {
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, overflow: 'hidden' }}>
      <Dashboard />
    </div>
  );
}
