import { useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AxiosError } from 'axios';
import { useAuth } from '../auth/AuthContext';

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await register({
        username: username.trim(),
        email: email.trim() || undefined,
        password,
      });
      navigate('/', { replace: true });
    } catch (err) {
      setError(extractError(err) ?? 'Could not create your account. Try again.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg p-4 text-slate-100">
      <div className="card w-full max-w-sm space-y-6 p-6">
        <div className="space-y-1">
          <h1 className="text-xl font-semibold">Create an account</h1>
          <p className="text-sm text-slate-400">
            One account = one private journal. Your trades stay yours.
          </p>
        </div>

        <form className="space-y-4" onSubmit={onSubmit}>
          <Field label="Username">
            <input
              type="text"
              autoComplete="username"
              required
              minLength={3}
              maxLength={150}
              className="input"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </Field>

          <Field label="Email (optional)">
            <input
              type="email"
              autoComplete="email"
              className="input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </Field>

          <Field label="Password">
            <input
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
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
            {submitting ? 'Creating account…' : 'Create account'}
          </button>
        </form>

        <p className="text-sm text-slate-400">
          Already have one?{' '}
          <Link to="/login" className="text-brand hover:underline">
            Sign in
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
