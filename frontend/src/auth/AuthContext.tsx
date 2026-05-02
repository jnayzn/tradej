import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import {
  TOKEN_STORAGE_KEY,
  fetchMe,
  login as loginApi,
  register as registerApi,
  regenerateToken as regenerateTokenApi,
  setUnauthorizedHandler,
} from '../api/client';
import type { AuthPayload, User } from '../types';

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (input: { username: string; password: string }) => Promise<AuthPayload>;
  register: (input: { username: string; email?: string; password: string }) => Promise<AuthPayload>;
  logout: () => void;
  regenerateToken: () => Promise<AuthPayload>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function readStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

function persistToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token);
    else localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // best-effort
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => readStoredToken());
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(() => readStoredToken() !== null);

  const logout = useCallback(() => {
    persistToken(null);
    setToken(null);
    setUser(null);
  }, []);

  // Wire the axios 401 handler to log out automatically.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      logout();
    });
    return () => setUnauthorizedHandler(null);
  }, [logout]);

  // On mount with a stored token, validate it via /auth/me/.
  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const payload = await fetchMe();
        if (cancelled) return;
        setUser(payload.user);
        setToken(payload.token);
        persistToken(payload.token);
      } catch {
        if (!cancelled) {
          logout();
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // We intentionally only run this once on mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleAuth = useCallback((payload: AuthPayload) => {
    persistToken(payload.token);
    setToken(payload.token);
    setUser(payload.user);
    return payload;
  }, []);

  const login = useCallback(
    async (input: { username: string; password: string }) =>
      handleAuth(await loginApi(input)),
    [handleAuth],
  );

  const register = useCallback(
    async (input: { username: string; email?: string; password: string }) =>
      handleAuth(await registerApi(input)),
    [handleAuth],
  );

  const regenerateToken = useCallback(
    async () => handleAuth(await regenerateTokenApi()),
    [handleAuth],
  );

  const value = useMemo<AuthContextValue>(
    () => ({ user, token, loading, login, register, logout, regenerateToken }),
    [user, token, loading, login, register, logout, regenerateToken],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}
