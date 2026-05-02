import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate, type Location } from 'react-router-dom';
import { AxiosError } from 'axios';
import { useAuth } from '../auth/AuthContext';

interface LocationState {
  from?: { pathname: string };
}

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation() as Location & { state: LocationState | null };
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await login({ username: username.trim(), password });
      const dest = location.state?.from?.pathname ?? '/';
      navigate(dest, { replace: true });
    } catch (err) {
      setError(extractError(err) ?? 'Could not sign in. Check your username and password.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg p-4 text-slate-100">
      <div className="card w-full max-w-sm space-y-6 p-6">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold">Sign in</h1>
          <p className="text-sm text-slate-400">Welcome back to your Trading Journal.</p>
        </div>

        <form className="space-y-4" onSubmit={onSubmit}>
          <Field label="Username">
            <input
              type="text"
              autoComplete="username"
              required
              className="input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </Field>

          <Field label="Password">
            <input
              type="password"
              autoComplete="current-password"
              required
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>

          {error && (
            <p role="alert" className="text-sm text-rose-400">
              {error}
            </p>
          )}

          <button type="submit" className="btn btn-primary w-full" disabled={submitting}>
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        <p className="text-sm text-slate-400">
          No account?{' '}
          <Link to="/register" className="text-brand hover:underline">
            Create one
          </Link>
          .
        </p>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-xs uppercase tracking-wide text-slate-400">{label}</span>
      {children}
    </label>
  );
}

function extractError(err: unknown): string | null {
  if (err instanceof AxiosError && err.response?.data) {
    const body = err.response.data;
    if (typeof body === 'string') return body;
    if (typeof body === 'object' && body !== null) {
      const data = body as Record<string, unknown>;
      if (typeof data.detail === 'string') return data.detail;
      const first = Object.values(data)[0];
      if (Array.isArray(first) && typeof first[0] === 'string') return first[0];
      if (typeof first === 'string') return first;
    }
  }
  return null;
}
