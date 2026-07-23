import { Link } from 'react-router-dom';
import { useAppStore } from '../../store';
import { LogOut, User as UserIcon, Trophy, Code2, Sun, Moon } from 'lucide-react';

export function Navbar() {
  const { isAuthenticated, user, logout, theme, setTheme } = useAppStore();

  const toggleTheme = () => {
    setTheme(theme === 'light' ? 'dark' : 'light');
  };

  return (
    <nav style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      height: 60,
      zIndex: 50,
      background: 'var(--bg-panel)',
      borderBottom: '1px solid var(--border-main)',
      padding: '0 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 24 }}>
        <Link to="/problems" style={{ display: 'flex', alignItems: 'center', gap: 8, textDecoration: 'none' }}>
          <div style={{ width: 32, height: 32, borderRadius: 6, background: 'var(--accent-color)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Code2 size={18} className="text-[var(--on-accent)]" />
          </div>
          <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-main)' }}>
            Code<span style={{ color: 'var(--accent-color)' }}>Forge</span>
          </span>
        </Link>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginLeft: 8 }}>
          {isAuthenticated && (
            <>
              <Link to="/problems" style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-muted)', textDecoration: 'none' }}>
                Problems
              </Link>
              <Link to="/leaderboard" style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-muted)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: 6 }}>
                <Trophy size={14} color="#eab308" /> Leaderboard
              </Link>
            </>
          )}
          <Link to="/pricing" style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-muted)', textDecoration: 'none' }}>
            Pricing
          </Link>
          <Link to="/refer" style={{ fontSize: 14, fontWeight: 500, color: 'var(--text-muted)', textDecoration: 'none' }}>
            Refer
          </Link>
        </div>
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <button
          onClick={toggleTheme}
          title={theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode'}
          style={{ padding: 8, borderRadius: 8, border: 'none', background: 'none', cursor: 'pointer', color: 'var(--text-muted)', display: 'flex', alignItems: 'center' }}
        >
          {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
        </button>

        {isAuthenticated ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 12px', borderRadius: 999, background: 'var(--bg-elevated)', border: '1px solid var(--border-main)' }}>
              <UserIcon size={14} color="var(--text-muted)" />
              <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-main)' }}>{user?.username || 'User'}</span>
            </div>
            <button
              onClick={logout}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: 13, fontWeight: 500, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <LogOut size={15} /> Logout
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <Link to="/login" style={{ fontSize: 13, fontWeight: 500, color: 'var(--text-muted)', textDecoration: 'none', padding: '6px 14px' }}>
              Log in
            </Link>
            <Link to="/signup" style={{ fontSize: 13, fontWeight: 600, background: 'var(--accent-strong)', color: 'var(--on-accent)', textDecoration: 'none', padding: '6px 14px', borderRadius: 8 }}>
              Sign up
            </Link>
          </div>
        )}
      </div>
    </nav>
  );
}
