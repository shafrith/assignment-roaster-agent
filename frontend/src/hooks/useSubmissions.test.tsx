import { QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { submissionService } from '../services/submissionService';
import { makeListItem, makePage } from '../test/fixtures';
import { createTestQueryClient } from '../test/utils';
import { LIST_POLL_INTERVAL_MS, useSubmissions } from './useSubmissions';

function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={createTestQueryClient()}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

describe('useSubmissions auto-refresh (COR-8)', () => {
  it('refreshes the list while a row is still in progress', async () => {
    const list = vi
      .spyOn(submissionService, 'list')
      .mockResolvedValueOnce(makePage([makeListItem({ id: 1, status: 'roasting', score: null })]))
      .mockResolvedValue(makePage([makeListItem({ id: 1, status: 'completed' })]));
    const { result } = renderHook(() => useSubmissions(1), { wrapper });

    await waitFor(() => expect(result.current.data?.items[0].status).toBe('roasting'));
    await waitFor(() => expect(result.current.data?.items[0].status).toBe('completed'), {
      timeout: LIST_POLL_INTERVAL_MS + 2000,
    });
    const calls = list.mock.calls.length;
    // All rows terminal → no further refreshes.
    await sleep(500);
    expect(list).toHaveBeenCalledTimes(calls);
  }, 15000);

  it('does not poll when every row is terminal', async () => {
    const list = vi.spyOn(submissionService, 'list').mockResolvedValue(makePage([makeListItem()]));
    const { result } = renderHook(() => useSubmissions(1), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(list).toHaveBeenCalledTimes(1);
  });
});
