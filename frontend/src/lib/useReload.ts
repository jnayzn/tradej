import { useEffect, useState } from 'react';

/** Returns a number that increments every time someone calls trigger() OR a `trades:imported`
 *  custom event is dispatched. Use it as a dep in useEffect to refetch data. */
export function useReload(): [number, () => void] {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const handler = () => setTick((n) => n + 1);
    window.addEventListener('trades:imported', handler);
    return () => window.removeEventListener('trades:imported', handler);
  }, []);
  return [tick, () => setTick((n) => n + 1)];
}
