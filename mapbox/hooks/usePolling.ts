import { useState, useEffect, useCallback, useRef } from 'react';
import { UiError } from '../types';

/**
 * Custom hook to handle background polling and stale-state management.
 * Fulfills MCD Feature 18: "Background operational freshness and stale-state handling"
 * 
 * @param fetchFn The async function to fetch data
 * @param intervalMs Polling interval in milliseconds (default 30s)
 * @param enabled Whether polling is currently active
 */
export function usePolling<T>(
  fetchFn: () => Promise<T>,
  intervalMs: number = 30000,
  enabled: boolean = true
) {
  const [data, setData] = useState<T | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isPolling, setIsPolling] = useState<boolean>(false);
  const [error, setError] = useState<UiError | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  
  // Use a ref to keep track of the latest fetchFn without triggering re-renders
  const fetchFnRef = useRef(fetchFn);
  useEffect(() => {
    fetchFnRef.current = fetchFn;
  }, [fetchFn]);

  const executeFetch = useCallback(async (isBackground: boolean = false) => {
    if (!isBackground) {
      setIsLoading(true);
    } else {
      setIsPolling(true);
    }
    
    try {
      const result = await fetchFnRef.current();
      setData(result);
      setError(null);
      setLastUpdated(new Date());
    } catch (err: any) {
      // MCD Rule: "IF polling fails THEN preserve the last known display with stale timestamp ELSE update the cache."
      // We do not clear `data` here, preserving the stale view.
      setError(err.uiError || { code: 'FETCH_FAILED', message: 'Live updates are temporarily paused. Refresh to check for new activity.' });
    } finally {
      setIsLoading(false);
      setIsPolling(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    if (enabled) {
      executeFetch(false);
    }
  }, [executeFetch, enabled]);

  // Polling interval
  useEffect(() => {
    if (!enabled || intervalMs <= 0) return;

    const intervalId = setInterval(() => {
      executeFetch(true);
    }, intervalMs);

    return () => clearInterval(intervalId);
  }, [executeFetch, intervalMs, enabled]);

  // Manual refetch function
  const refetch = useCallback(() => {
    return executeFetch(false);
  }, [executeFetch]);

  // Optimistic update function (for immediate UI updates after mutations)
  const mutateData = useCallback((updater: (prev: T | null) => T | null) => {
    setData(prev => updater(prev));
  }, []);

  return { 
    data, 
    isLoading, 
    isPolling, 
    error, 
    lastUpdated, 
    refetch,
    mutateData
  };
}
