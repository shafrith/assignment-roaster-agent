import { QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { submissionService } from '../services/submissionService';
import { makeSubmission } from '../test/fixtures';
import { createTestQueryClient } from '../test/utils';
import { pollIntervalFor, SUBMISSION_POLL_INTERVAL_MS, useSubmission } from './useSubmission';

function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={createTestQueryClient()}>{children}</QueryClientProvider>;
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

describe('pollIntervalFor (backoff)', () => {
  it('starts at 2s, backs off to 3s after 30s and 5s after 2 min', () => {
    expect(pollIntervalFor(0)).toBe(SUBMISSION_POLL_INTERVAL_MS);
    expect(pollIntervalFor(29_999)).toBe(2000);
    expect(pollIntervalFor(30_000)).toBe(3000);
    expect(pollIntervalFor(119_999)).toBe(3000);
    expect(pollIntervalFor(120_000)).toBe(5000);
    expect(pollIntervalFor(9 * 60_000)).toBe(5000);
  });
});

describe('useSubmission polling cap', () => {
  it('stops polling and flags a timeout when the submission never finishes', async () => {
    const get = vi
      .spyOn(submissionService, 'get')
      .mockResolvedValue(makeSubmission({ status: 'analyzing', roast: null }));
    const { result } = renderHook(() => useSubmission(7, { maxPollMs: 2500 }), { wrapper });

    await waitFor(() => expect(result.current.query.data?.status).toBe('analyzing'));
    expect(result.current.isPollingTimedOut).toBe(false);

    await waitFor(() => expect(result.current.isPollingTimedOut).toBe(true), { timeout: 4000 });
    const callsAtTimeout = get.mock.calls.length;
    expect(callsAtTimeout).toBeGreaterThanOrEqual(2); // it did poll before giving up

    await sleep(2300);
    expect(get).toHaveBeenCalledTimes(callsAtTimeout);
  }, 15000);

  it('resumePolling clears the timeout and refetches immediately', async () => {
    const get = vi
      .spyOn(submissionService, 'get')
      .mockResolvedValue(makeSubmission({ status: 'pending', roast: null }));
    const { result } = renderHook(() => useSubmission(7, { maxPollMs: 200 }), { wrapper });

    await waitFor(() => expect(result.current.isPollingTimedOut).toBe(true), { timeout: 3000 });
    const calls = get.mock.calls.length;
    get.mockResolvedValue(makeSubmission({ status: 'failed', roast: null }));

    act(() => result.current.resumePolling());
    expect(result.current.isPollingTimedOut).toBe(false);
    await waitFor(() => expect(result.current.query.data?.status).toBe('failed'));
    expect(get.mock.calls.length).toBeGreaterThan(calls);
    // Terminal status → no timeout flag even after the cap elapses.
    await sleep(300);
    expect(result.current.isPollingTimedOut).toBe(false);
  }, 10000);

  it('never flags a timeout for a completed submission', async () => {
    vi.spyOn(submissionService, 'get').mockResolvedValue(makeSubmission({ status: 'completed' }));
    const { result } = renderHook(() => useSubmission(7, { maxPollMs: 50 }), { wrapper });
    await waitFor(() => expect(result.current.query.data?.status).toBe('completed'));
    await sleep(150);
    expect(result.current.isPollingTimedOut).toBe(false);
  });
});
