import { useCallback, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAppStore } from '../../../store';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Eye, EyeOff, UserPlus } from 'lucide-react';

const signupSchema = z.object({
  username: z.string().min(3, 'Username must be at least 3 characters'),
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  name: z.string().optional(),
});

type SignupFormValues = z.infer<typeof signupSchema>;

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

export function Signup() {
  const login = useAppStore(state => state.login);
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [showPw, setShowPw] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SignupFormValues>({
    resolver: zodResolver(signupSchema),
  });

  const onSubmit = useCallback(async (values: SignupFormValues) => {
    setError(null);
    try {
      const response = await fetch('/api/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...values,
          name: values.name || values.username,
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.message || 'Signup failed');
      }

      const user = await response.json();
      login(user);
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
            <UserPlus size={26} color="#fff" />
          </div>
        </div>

        <h1 style={{ textAlign: 'center', fontSize: 22, fontWeight: 700, margin: '0 0 6px', color: 'var(--text-main)' }}>
          Create your account
        </h1>
        <p style={{ textAlign: 'center', color: 'var(--text-muted)', margin: '0 0 28px', fontSize: 14 }}>
          Join the platform and start coding today
        </p>

        {error && (
          <p style={{ color: '#dc2626', fontSize: 13, margin: '0 0 16px', padding: '8px 12px', background: '#fee2e2', borderRadius: 6 }}>
            {error}
          </p>
        )}

        <form onSubmit={handleSubmit(onSubmit)} style={{ display: 'flex', flexDirection: 'column', gap: 16 }} noValidate>
          <div>
            <label style={LABEL}>Username</label>
            <input
              type="text"
              {...register('username')}
              placeholder="johndoe"
              style={INPUT}
            />
            {errors.username && <p style={{ color: '#dc2626', fontSize: 12, margin: '4px 0 0' }}>{errors.username.message}</p>}
          </div>

          <div>
            <label style={LABEL}>Email</label>
            <input
              type="email"
              {...register('email')}
              placeholder="you@example.com"
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

          <button
            type="submit"
            disabled={isSubmitting}
            style={{ width: '100%', padding: '11px 0', background: '#000', color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: isSubmitting ? 'not-allowed' : 'pointer', opacity: isSubmitting ? 0.7 : 1, marginTop: 4 }}
          >
            {isSubmitting ? 'Creating account…' : 'Create Account'}
          </button>
        </form>

        <div style={{ display: 'flex', alignItems: 'center', gap: 12, margin: '20px 0 16px' }}>
          <div style={{ flex: 1, height: 1, background: 'var(--border-main)' }} />
          <span style={{ fontSize: 12, color: 'var(--text-muted)', fontWeight: 500 }}>OR</span>
          <div style={{ flex: 1, height: 1, background: 'var(--border-main)' }} />
        </div>

        <p style={{ textAlign: 'center', fontSize: 14, color: 'var(--text-muted)', margin: 0 }}>
          Already have an account?{' '}
          <Link to="/login" style={{ color: 'var(--accent-color)', textDecoration: 'none', fontWeight: 500 }}>
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
}
