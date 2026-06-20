import { useCallback, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAppStore } from '../../../store';
import { motion } from 'framer-motion';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';

const signupSchema = z.object({
  username: z.string().min(3, 'Username must be at least 3 characters'),
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  name: z.string().optional(),
});

type SignupFormValues = z.infer<typeof signupSchema>;

export function Signup() {
  const login = useAppStore(state => state.login);
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

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
          name: values.name || values.username
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
    <div className="flex flex-col items-center justify-center min-h-[80vh]">
      <motion.div
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        className="glass-panel p-8 w-full max-w-md"
      >
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold text-text-main mb-2">Create Account</h2>
          <p className="text-text-muted text-sm">Join the platform to start coding</p>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-500 p-3 rounded-lg text-sm mb-6">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <div>
            <label htmlFor="username" className="block text-sm font-medium text-text-muted mb-1">Username</label>
            <input
              id="username"
              type="text"
              {...register('username')}
              className="w-full bg-panel border border-border-main rounded-lg px-4 py-2.5 text-text-main focus:outline-none focus:border-primary transition-colors"
              placeholder="johndoe"
            />
            {errors.username && <p className="text-red-500 text-xs mt-1" role="alert">{errors.username.message}</p>}
          </div>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-text-muted mb-1">Email</label>
            <input
              id="email"
              type="email"
              {...register('email')}
              className="w-full bg-panel border border-border-main rounded-lg px-4 py-2.5 text-text-main focus:outline-none focus:border-primary transition-colors"
              placeholder="you@example.com"
            />
            {errors.email && <p className="text-red-500 text-xs mt-1" role="alert">{errors.email.message}</p>}
          </div>
          <div>
            <label htmlFor="password" className="block text-sm font-medium text-text-muted mb-1">Password</label>
            <input
              id="password"
              type="password"
              {...register('password')}
              className="w-full bg-panel border border-border-main rounded-lg px-4 py-2.5 text-text-main focus:outline-none focus:border-primary transition-colors"
              placeholder="••••••••"
            />
            {errors.password && <p className="text-red-500 text-xs mt-1" role="alert">{errors.password.message}</p>}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full bg-primary hover:bg-primary/90 text-white font-medium py-2.5 rounded-lg transition-colors mt-4 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Creating Account...' : 'Create Account'}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-text-muted">
          Already have an account? <Link to="/login" className="text-primary hover:text-primary/80">Log in</Link>
        </div>
      </motion.div>
    </div>
  );
}
