import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { Zap, BookOpen, Users, BarChart2, Moon, Sun, LogOut, ChevronRight, ChevronLeft } from 'lucide-react'
import { useAdminStore } from '../store'

const NAV = [
  { to: '/generation', icon: Zap, label: 'Generation' },
  { to: '/problems', icon: BookOpen, label: 'Problems' },
  { to: '/users', icon: Users, label: 'Users' },
  { to: '/monitoring', icon: BarChart2, label: 'Monitoring' },
]

export function Sidebar() {
  const [expanded, setExpanded] = useState(true)
  const { theme, setTheme, logout } = useAdminStore()

  return (
    <aside
      style={{
        width: expanded ? 220 : 56,
        background: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-color)',
        transition: 'width 0.2s ease',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        height: '100vh',
        position: 'sticky',
        top: 0,
      }}
    >
      {/* Logo + toggle */}
      <div style={{ padding: '16px 12px', display: 'flex', alignItems: 'center', gap: 8, borderBottom: '1px solid var(--border-color)' }}>
        <div style={{ width: 28, height: 28, background: '#000', borderRadius: 6, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
          <span style={{ color: '#fff', fontSize: 12, fontWeight: 700 }}>A</span>
        </div>
        {expanded && <span style={{ fontWeight: 700, fontSize: 14, color: 'var(--text-primary)', flex: 1 }}>Admin</span>}
        <button
          onClick={() => setExpanded(!expanded)}
          style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', padding: 2, display: 'flex' }}
        >
          {expanded ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </button>
      </div>

      {/* Nav items */}
      <nav style={{ flex: 1, padding: '8px 6px', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {NAV.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '8px 10px',
              borderRadius: 6,
              textDecoration: 'none',
              color: isActive ? 'var(--accent-color)' : 'var(--text-secondary)',
              background: isActive ? 'color-mix(in srgb, var(--accent-color) 10%, transparent)' : 'transparent',
              fontWeight: isActive ? 500 : 400,
              fontSize: 13,
              borderLeft: isActive ? '3px solid var(--accent-color)' : '3px solid transparent',
              transition: 'all 0.15s',
            })}
          >
            <Icon size={16} style={{ flexShrink: 0 }} />
            {expanded && <span>{label}</span>}
          </NavLink>
        ))}
      </nav>

      {/* Bottom controls */}
      <div style={{ padding: '8px 6px', borderTop: '1px solid var(--border-color)', display: 'flex', flexDirection: 'column', gap: 2 }}>
        <button
          onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
          style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', borderRadius: 6, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', fontSize: 13, width: '100%' }}
        >
          {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
          {expanded && <span>{theme === 'light' ? 'Dark mode' : 'Light mode'}</span>}
        </button>
        <button
          onClick={logout}
          style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', borderRadius: 6, background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', fontSize: 13, width: '100%' }}
        >
          <LogOut size={16} />
          {expanded && <span>Sign out</span>}
        </button>
      </div>
    </aside>
  )
}
