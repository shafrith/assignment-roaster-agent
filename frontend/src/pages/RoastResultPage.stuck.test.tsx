import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { UseQueryResult } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import { makeSubmission } from '../test/fixtures';
import { renderWithProviders, testUser } from '../test/utils';
import type { SubmissionResponse } from '../types/api';
import RoastResultPage from './RoastResultPage';

const resumePolling = vi.fn();

vi.mock('../hooks/useSubmission', () => ({
  useSubmission: () => ({
    query: {
      data: makeSubmission({ status: 'analyzing', roast: null }),
      isPending: false,
      isError: false,
      error: null,
      isFetching: false,
      refetch: vi.fn(),
    } as unknown as UseQueryResult<SubmissionResponse>,
    isPollingTimedOut: true,
    resumePolling,
  }),
}));

describe('RoastResultPage (polling cap reached)', () => {
  it('shows the Tanglish "taking too long" state and lets the user re-check', async () => {
    renderWithProviders(<RoastResultPage />, { route: '/roasts/7', path: '/roasts/:id', auth: { user: testUser } });
    expect(screen.getByText('Romba neram aagudhu machan ⏳')).toBeInTheDocument();
    expect(screen.queryByTestId('roast-status-loader')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Status check pannu/ }));
    expect(resumePolling).toHaveBeenCalledTimes(1);
  });
});
