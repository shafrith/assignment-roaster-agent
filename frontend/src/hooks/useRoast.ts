import { useMutation, useQuery, useQueryClient, type UseQueryResult } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { isNotFoundError } from '../lib/httpErrors';
import { isTerminalStatus } from '../lib/format';
import { roastKeys, roastService, type CreateRoastRequest } from '../services/roastService';
import type { RoastStatusResponse } from '../types/api';

/** Initial poll interval while a roast is in progress. */
export const ROAST_POLL_INTERVAL_MS = 2000;
/** Stop polling after this long without reaching a terminal status (COR-2 / PERF-5). */
export const ROAST_POLL_MAX_MS = 10 * 60 * 1000;

/**
 * Backoff schedule: 2s for the first 30s (most roasts finish here), 3s up to 2 min, then 5s.
 *
 * Args:
 *   elapsedMs: time since polling (re)started for this roast.
 */
export function pollIntervalFor(elapsedMs: number): number {
  if (elapsedMs < 30_000) return ROAST_POLL_INTERVAL_MS;
  if (elapsedMs < 120_000) return 3000;
  return 5000;
}

export interface UseRoastOptions {
  /** Override the polling cap (tests). */
  maxPollMs?: number;
}

export interface UseRoastResult {
  query: UseQueryResult<RoastStatusResponse>;
  /** True when the roast is still non-terminal after `maxPollMs`; polling has stopped. */
  isPollingTimedOut: boolean;
  /** Restart polling (with a fresh cap) and refetch immediately. */
  resumePolling: () => void;
}

/**
 * One roast by share slug; polls with backoff while status is not completed/failed and gives up
 * after `maxPollMs` (a roast orphaned by a server restart would otherwise poll forever).
 */
export function useRoast(id: string | null, { maxPollMs = ROAST_POLL_MAX_MS }: UseRoastOptions = {}): UseRoastResult {
  // Keyed by slug so navigating to another roast never inherits a timed-out state.
  const [timedOutId, setTimedOutId] = useState<string | null>(null);
  const isPollingTimedOut = id !== null && timedOutId === id;
  const pollStartedAt = useRef<number>(Date.now());

  const query = useQuery({
    queryKey: roastKeys.detail(id ?? ''),
    queryFn: () => roastService.get(id as string),
    enabled: id !== null,
    retry: (failureCount, error) => !isNotFoundError(error) && failureCount < 1,
    refetchInterval: (q) => {
      if (isPollingTimedOut) return false;
      if (q.state.status === 'error') return false;
      const status = q.state.data?.status;
      if (status && isTerminalStatus(status)) return false;
      return pollIntervalFor(Date.now() - pollStartedAt.current);
    },
  });

  const status = query.data?.status;
  const inProgress = status !== undefined && !isTerminalStatus(status);

  // Start the cap timer whenever a roast enters (or re-enters, after retry) a non-terminal
  // state; reset the timed-out flag once it reaches a terminal state.
  useEffect(() => {
    if (id === null) return undefined;
    if (!inProgress) {
      setTimedOutId((current) => (current === id ? null : current));
      return undefined;
    }
    if (isPollingTimedOut) return undefined;
    pollStartedAt.current = Date.now();
    const timer = window.setTimeout(() => setTimedOutId(id), maxPollMs);
    return () => window.clearTimeout(timer);
  }, [id, inProgress, isPollingTimedOut, maxPollMs]);

  const { refetch } = query;
  const resumePolling = useCallback((): void => {
    setTimedOutId(null);
    void refetch();
  }, [refetch]);

  return { query, isPollingTimedOut, resumePolling };
}

/** POST /roasts (no login) → navigates to the roast page /r/:shareSlug on success. */
export function useCreateRoast() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  return useMutation({
    mutationFn: (payload: CreateRoastRequest) => roastService.create(payload),
    onSuccess: (roast: RoastStatusResponse) => {
      queryClient.setQueryData(roastKeys.detail(roast.shareSlug), roast);
      navigate(`/r/${roast.shareSlug}`);
    },
  });
}

/** POST /roasts/:shareSlug/retry (only valid when failed). Polling resumes via useRoast. */
export function useRetryRoast() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (shareSlug: string) => roastService.retry(shareSlug),
    onSuccess: (roast: RoastStatusResponse) => {
      queryClient.setQueryData(roastKeys.detail(roast.shareSlug), roast);
    },
  });
}
