import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAdminStore } from '../store'
import { login } from '../lib/api'
import { Eye, EyeOff, UserCircle2 } from 'lucide-react'

export default function LoginPage() {
  const navigate = useNavigate()
  const loginStore = useAdminStore((s) => s.login)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await login(email, password)
      loginStore({ id: data.userId, email: data.email }, data.token)
      navigate('/generation')
    } catch {
      setError('Invalid credentials or not an admin account.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-page)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <div style={{ background: 'var(--bg-surface)', borderRadius: 16, padding: '40px 36px', width: '100%', maxWidth: 420, border: '1px solid var(--border-color)' }}>
        {/* Icon */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
          <div style={{ width: 52, height: 52, background: '#000', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <UserCircle2 size={28} color="#fff" />
          </div>
        </div>

        <h1 style={{ textAlign: 'center', fontSize: 22, fontWeight: 700, margin: '0 0 6px', color: 'var(--text-primary)' }}>
          Welcome back
        </h1>
        <p style={{ textAlign: 'center', color: 'var(--text-secondary)', margin: '0 0 28px', fontSize: 14 }}>
          Enter your admin credentials to continue
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="admin@company.com"
              required
              style={{ width: '100%', padding: '10px 14px', background: 'var(--bg-elevated)', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: 14, color: 'var(--text-primary)', outline: 'none', boxSizing: 'border-box' }}
            />
          </div>

          <div>
            <label style={{ display: 'block', marginBottom: 6, fontSize: 13, fontWeight: 500, color: 'var(--text-primary)' }}>Password</label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPw ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                required
                style={{ width: '100%', padding: '10px 40px 10px 14px', background: 'var(--bg-elevated)', border: '1px solid var(--border-color)', borderRadius: 8, fontSize: 14, color: 'var(--text-primary)', outline: 'none', boxSizing: 'border-box' }}
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-secondary)', padding: 0, display: 'flex' }}
              >
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          {error && (
            <p style={{ color: '#dc2626', fontSize: 13, margin: 0, padding: '8px 12px', background: '#fee2e2', borderRadius: 6 }}>
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            style={{ width: '100%', padding: '11px 0', background: '#000', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer', opacity: loading ? 0.7 : 1, marginTop: 4 }}
          >
            {loading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}
