/**
 * Passwordless single-user-per-instance auth context.
 *
 * On mount we fetch ``/api/bridge/info/`` (public endpoint) to discover the
 * owner's API token, cache it in ``localStorage``, and attach it to every
 * subsequent API request via the axios interceptor. There is no login flow —
 * anyone who can reach the deployed URL is treated as the owner. This is
 * intentional for the "share with friends, one instance per friend" model.
 *
 * The provider exposes a refresh + regenerate API so the MT5 Bridge page
 * can rotate the token and re-poll the sync timestamp.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import {
  TOKEN_STORAGE_KEY,
  fetchBridgeInfo,
  regenerateBridgeToken,
  setUnauthorizedHandler,
} from '../api/client';
import type { BridgeInfo } from '../types';

interface BridgeContextValue {
  info: BridgeInfo | null;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<BridgeInfo>;
  regenerate: () => Promise<BridgeInfo>;
}

const BridgeContext = createContext<BridgeContextValue | undefined>(undefined);

function persistToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_STORAGE_KEY, token);
    else localStorage.removeItem(TOKEN_STORAGE_KEY);
  } catch {
    // best-effort
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [info, setInfo] = useState<BridgeInfo | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Stale-token recovery: if a previously cached token gets rejected by the
  // server (e.g. someone rotated it on another tab), force a refetch.
  const refresh = useCallback(async (): Promise<BridgeInfo> => {
    const next = await fetchBridgeInfo();
    persistToken(next.token);
    setInfo(next);
    setError(null);
    return next;
  }, []);

  const regenerate = useCallback(async (): Promise<BridgeInfo> => {
    const next = await regenerateBridgeToken();
    persistToken(next.token);
    setInfo(next);
    setError(null);
    return next;
  }, []);

  // Keep a ref to refresh so the 401 handler effect doesn't churn.
  const refreshRef = useRef(refresh);
  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      // Owner token is stale — refetch silently.
      refreshRef.current().catch(() => {
        /* surface via error state on next manual refresh */
      });
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const next = await fetchBridgeInfo();
        if (cancelled) return;
        persistToken(next.token);
        setInfo(next);
      } catch (err) {
        if (cancelled) return;
        setError(
          err instanceof Error
            ? err.message
            : 'Could not reach the API. Check that the backend is running.',
        );
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const value = useMemo<BridgeContextValue>(
    () => ({ info, loading, error, refresh, regenerate }),
    [info, loading, error, refresh, regenerate],
  );

  return <BridgeContext.Provider value={value}>{children}</BridgeContext.Provider>;
}

export function useBridge(): BridgeContextValue {
  const ctx = useContext(BridgeContext);
  if (!ctx) {
    throw new Error('useBridge must be used within an AuthProvider');
  }
  return ctx;
}
