import { useCallback, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAppStore } from '../../../store';
import { motion } from 'framer-motion';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const loginSchema = z.object({
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function Login() {
  const login = useAppStore(state => state.login);
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

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
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(devValues),
      });
      if (response.ok) {
        const user = await response.json();
        login(user);
        navigate('/');
      } else {
        // Fallback for when DB isn't running yet but user wants to see UI
        login({ id: '550e8400-e29b-41d4-a716-446655440000', email: 'test@example.com', name: 'Dev User', username: 'devuser' });
        navigate('/');
      }
    } catch (e) {
      login({ id: '550e8400-e29b-41d4-a716-446655440000', email: 'test@example.com', name: 'Dev User', username: 'devuser' });
      navigate('/');
    }
  }, [login, navigate]);

  const onSubmit = useCallback(async (values: LoginFormValues) => {
    setError(null);
    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(values),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.message || 'Login failed');
      }

      const user = await response.json();
      login(user);
      navigate('/');
    } catch (err: any) {
      setError(err.message);
    }
  }, [login, navigate]);

  return (
    <div className="flex flex-col items-center justify-center min-h-[80vh]">
      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="glass-panel p-8 w-full max-w-md"
      >
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-white mb-2">Welcome Back</h2>
          <p className="text-slate-400 text-sm">Sign in to continue your progress</p>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 p-3 rounded-lg text-sm mb-6">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-400 mb-1">Email</label>
            <input 
              id="email"
              type="email" 
              {...register('email')}
              className="w-full bg-background/50 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-primary transition-colors"
              placeholder="you@example.com"
            />
            {errors.email && <p className="text-red-400 text-xs mt-1" role="alert">{errors.email.message}</p>}
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-400 mb-1">Password</label>
            <input 
              id="password"
              type="password" 
              {...register('password')}
              className="w-full bg-background/50 border border-white/10 rounded-lg px-4 py-2.5 text-white focus:outline-none focus:border-primary transition-colors"
              placeholder="••••••••"
            />
            {errors.password && <p className="text-red-400 text-xs mt-1" role="alert">{errors.password.message}</p>}
          </div>
          
          <button 
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-primary hover:bg-primary/90 text-white font-medium py-2.5 rounded-lg transition-colors mt-4 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Signing in...' : 'Sign In'}
          </button>

          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-white/10"></span>
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-[#0b0c10] px-2 text-slate-500">Dev Only</span>
            </div>
          </div>

          <button 
            type="button"
            onClick={handleDevAutoLogin}
            className="w-full bg-white/5 hover:bg-white/10 text-slate-300 font-medium py-2 rounded-lg border border-white/10 transition-colors"
          >
            Dev Auto-Login
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-slate-400">
          Don't have an account? <Link to="/signup" className="text-primary hover:text-primary/80">Sign up</Link>
        </div>
      </motion.div>
    </div>
  );
}
