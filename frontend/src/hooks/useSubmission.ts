import { useQuery, type UseQueryResult } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';
import { isNotFoundError } from '../lib/httpErrors';
import { isTerminalStatus } from '../lib/format';
import { submissionKeys, submissionService } from '../services/submissionService';
import type { SubmissionResponse } from '../types/api';

/** Initial poll interval while a submission is in progress. */
export const SUBMISSION_POLL_INTERVAL_MS = 2000;
/** Stop polling after this long without reaching a terminal status (COR-2 / PERF-5). */
export const SUBMISSION_POLL_MAX_MS = 10 * 60 * 1000;

/**
 * Backoff schedule: 2s for the first 30s (most roasts finish here), 3s up to 2 min, then 5s.
 *
 * Args:
 *   elapsedMs: time since polling (re)started for this submission.
 */
export function pollIntervalFor(elapsedMs: number): number {
  if (elapsedMs < 30_000) return SUBMISSION_POLL_INTERVAL_MS;
  if (elapsedMs < 120_000) return 3000;
  return 5000;
}

export interface UseSubmissionOptions {
  /** Override the polling cap (tests). */
  maxPollMs?: number;
}

export interface UseSubmissionResult {
  query: UseQueryResult<SubmissionResponse>;
  /** True when the submission is still non-terminal after `maxPollMs`; polling has stopped. */
  isPollingTimedOut: boolean;
  /** Restart polling (with a fresh cap) and refetch immediately. */
  resumePolling: () => void;
}

/**
 * Single submission; polls with backoff while status is not completed/failed and gives up
 * after `maxPollMs` (a submission orphaned by a server restart would otherwise poll forever).
 */
export function useSubmission(id: number | null, { maxPollMs = SUBMISSION_POLL_MAX_MS }: UseSubmissionOptions = {}): UseSubmissionResult {
  // Keyed by id so navigating to another submission never inherits a timed-out state.
  const [timedOutId, setTimedOutId] = useState<number | null>(null);
  const isPollingTimedOut = id !== null && timedOutId === id;
  const pollStartedAt = useRef<number>(Date.now());

  const query = useQuery({
    queryKey: submissionKeys.detail(id ?? -1),
    queryFn: () => submissionService.get(id as number),
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

  // Start the cap timer whenever a submission enters (or re-enters, after retry) a non-terminal
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
