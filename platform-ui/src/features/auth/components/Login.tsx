import { useCallback, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAppStore } from '../../../store';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, UserCircle2, KeyRound } from 'lucide-react';

const loginSchema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

const CARD: React.CSSProperties = {
  background: 'var(--bg-panel)',
  borderRadius: 16,
  padding: '40px 36px',
  width: '100%',
  maxWidth: 420,
  border: '1px solid var(--border-main)',
};

const INPUT: React.CSSProperties = {
  width: '100%',
  padding: '10px 14px',
  background: 'var(--bg-elevated)',
  border: '1px solid var(--border-main)',
  borderRadius: 8,
  fontSize: 14,
  color: 'var(--text-main)',
  outline: 'none',
  boxSizing: 'border-box',
};

const LABEL: React.CSSProperties = {
  display: 'block',
  marginBottom: 6,
  fontSize: 13,
  fontWeight: 500,
  color: 'var(--text-main)',
};

const OUTLINED_BTN: React.CSSProperties = {
  width: '100%',
  padding: '10px 0',
  background: 'var(--bg-panel)',
  border: '1px solid var(--border-main)',
  borderRadius: 8,
  fontSize: 14,
  fontWeight: 500,
  color: 'var(--text-main)',
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 8,
};

export function Login() {
  const login = useAppStore(state => state.login);
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [showPw, setShowPw] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  const handleDevAutoLogin = useCallback(async () => {
    const devValues = { email: 'test@example.com', password: 'password' };
    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(devValues),
      });
      if (response.ok) {
        const data = await response.json();
        login({ id: data.userId, email: data.email, name: data.email, username: data.email.split('@')[0], token: data.token });
        navigate('/');
      } else {
        login({ id: '550e8400-e29b-41d4-a716-446655440000', email: 'test@example.com', name: 'Dev User', username: 'devuser', token: '' });
        navigate('/');
      }
    } catch {
      login({ id: '550e8400-e29b-41d4-a716-446655440000', email: 'test@example.com', name: 'Dev User', username: 'devuser', token: '' });
      navigate('/');
    }
  }, [login, navigate]);

  const onSubmit = useCallback(async (values: LoginFormValues) => {
    setError(null);
    try {
      const response = await fetch('/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.message || 'Login failed');
      }

      const data = await response.json();
      login({ id: data.userId, email: data.email, name: data.email, username: data.email.split('@')[0], token: data.token });
      navigate('/');
    } catch (err: any) {
      setError(err.message);
    }
  }, [login, navigate]);

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-main)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 24 }}>
      <div style={CARD}>
        {/* Icon */}
        <div style={{ display: 'flex', justifyContent: 'center', marginBottom: 20 }}>
          <div style={{ width: 52, height: 52, background: '#000', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <UserCircle2 size={28} color="#fff" />
          </div>
        </div>

        <h1 style={{ textAlign: 'center', fontSize: 22, fontWeight: 700, margin: '0 0 6px', color: 'var(--text-main)' }}>
          Welcome back
        </h1>
        <p style={{ textAlign: 'center', color: 'var(--text-muted)', margin: '0 0 28px', fontSize: 14 }}>
          Enter your credentials to access your account
        </p>

        {error && (
          <p style={{ color: '#dc2626', fontSize: 13, margin: '0 0 16px', padding: '8px 12px', background: '#fee2e2', borderRadius: 6 }}>
            {error}
          </p>
        )}

        <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'flex', flexDirection: 'column', gap: 16 }} noValidate>
          <div>
            <label style={LABEL}>Email</label>
            <input
              type="email"
              {...register('email')}
              placeholder="Email"
              style={INPUT}
            />
            {errors.email && <p style={{ color: '#dc2626', fontSize: 12, margin: '4px 0 0' }}>{errors.email.message}</p>}
          </div>

          <div>
            <label style={LABEL}>Password</label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPw ? 'text' : 'password'}
                {...register('password')}
                placeholder="Password"
                style={{ ...INPUT, paddingRight: 40 }}
              />
              <button
                type="button"
                onClick={() => setShowPw(!showPw)}
                style={{ position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)', padding: 0, display: 'flex' }}
              >
                {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {errors.password && <p style={{ color: '#dc2626', fontSize: 12, margin: '4px 0 0' }}>{errors.password.message}</p>}
          </div>

          <div style={{ textAlign: 'right', marginTop: -8 }}>
            <a href="#" style={{ fontSize: 13, color: 'var(--accent-color)', textDecoration: 'none' }}>
              Forgot your password?
            </a>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            style={{ width: '100%', padding: '11px 0', background: '#000', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: isSubmitting ? 'not-allowed' : 'pointer', opacity: isSubmitting ? 0.7 : 1, marginTop: 4 }}
          >
            {isSubmitting ? 'Signing in…' : 'Sign In'}
          </button>

          <button type="button" style={OUTLINED_BTN}>
            <svg width="16" height="16" viewBox="0 0 48 48" aria-hidden="true">
              <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
              <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
              <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
              <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.18 1.48-4.93 2.31-8.16 2.31-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
            </svg>
            Continue with Google
          </button>

          <button type="button" style={OUTLINED_BTN}>
            <KeyRound size={16} />
            Continue with SSO
          </button>
        </form>

        {/* OR divider */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '20px 0' }}>
          <div style={{ flex: 1, height: 1, background: 'var(--border-main)' }} />
          <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>OR</span>
          <div style={{ flex: 1, height: 1, background: 'var(--border-main)' }} />
        </div>

        <p style={{ textAlign: 'center', fontSize: 14, color: 'var(--text-muted)', margin: '0 0 8px' }}>
          Don't have an account?{' '}
          <Link to="/signup" style={{ color: 'var(--accent-color)', textDecoration: 'none', fontWeight: 500 }}>
            Sign up
          </Link>
        </p>

        <p style={{ textAlign: 'center', margin: 0 }}>
          <button
            type="button"
            onClick={handleDevAutoLogin}
            style={{ background: 'none', border: 'none', fontSize: 12, color: 'var(--text-muted)', cursor: 'pointer', textDecoration: 'underline' }}
          >
            Dev auto-login
          </button>
        </p>
      </div>
    </div>
  );
}
