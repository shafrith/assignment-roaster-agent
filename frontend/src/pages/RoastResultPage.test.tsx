import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { submissionService } from '../services/submissionService';
import { makeAxiosError, makeSubmission } from '../test/fixtures';
import { renderWithProviders, testUser } from '../test/utils';
import RoastResultPage from './RoastResultPage';

function renderAt(route: string) {
  return renderWithProviders(<RoastResultPage />, { route, path: '/roasts/:id', auth: { user: testUser } });
}

describe('RoastResultPage', () => {
  it('shows the skeleton while the first fetch is in flight', () => {
    vi.spyOn(submissionService, 'get').mockReturnValue(new Promise(() => undefined));
    renderAt('/roasts/7');
    expect(screen.getByTestId('roast-report-skeleton')).toBeInTheDocument();
  });

  it('pending → status loader with repo label', async () => {
    const get = vi
      .spyOn(submissionService, 'get')
      .mockResolvedValue(makeSubmission({ status: 'pending', roast: null, analysis: null, completedAt: null }));
    renderAt('/roasts/7');
    expect(await screen.findByTestId('roast-status-loader')).toHaveTextContent('machan/genai-hw');
    expect(get).toHaveBeenCalledWith(7);
    expect(screen.queryByTestId('roast-report')).not.toBeInTheDocument();
  });

  it('polls while in progress and shows the report once completed', async () => {
    const get = vi
      .spyOn(submissionService, 'get')
      .mockResolvedValueOnce(makeSubmission({ status: 'analyzing', roast: null, analysis: null }))
      .mockResolvedValueOnce(makeSubmission({ status: 'roasting', roast: null }))
      .mockResolvedValue(makeSubmission({ status: 'completed' }));
    renderAt('/roasts/7');

    expect(await screen.findByTestId('roast-status-loader')).toBeInTheDocument();
    expect(await screen.findByTestId('roast-report', {}, { timeout: 6000 })).toBeInTheDocument();
    expect(get.mock.calls.length).toBeGreaterThanOrEqual(3);
    const callsAtCompletion = get.mock.calls.length;

    // Terminal status → polling stops.
    await new Promise((resolve) => setTimeout(resolve, 2300));
    expect(get).toHaveBeenCalledTimes(callsAtCompletion);
  }, 15000);

  it('completed → full report with owner controls and GitHub link', async () => {
    vi.spyOn(submissionService, 'get').mockResolvedValue(makeSubmission({ status: 'completed', isPublic: true }));
    renderAt('/roasts/7');
    expect(await screen.findByTestId('roast-report')).toBeInTheDocument();
    expect(screen.getByLabelText('Score 3.5 out of 10')).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: '🌍 Public' })).toBeChecked();
    expect(screen.getByTestId('share-bar')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Open machan/genai-hw on GitHub' })).toHaveAttribute(
      'href',
      'https://github.com/machan/genai-hw',
    );
  });

  it('failed → error message + Retry button that calls retry', async () => {
    vi.spyOn(submissionService, 'get').mockResolvedValue(
      makeSubmission({ status: 'failed', roast: null, errorMessage: 'Repo romba perusu machan 🐘' }),
    );
    const retry = vi
      .spyOn(submissionService, 'retry')
      .mockResolvedValue(makeSubmission({ status: 'pending', roast: null, errorMessage: null }));
    renderAt('/roasts/7');

    expect(await screen.findByText('Roast fail aayiduchu 😵')).toBeInTheDocument();
    expect(screen.getByText('Repo romba perusu machan 🐘')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Retry pannu/ }));
    expect(retry).toHaveBeenCalledWith(7);
    expect(await screen.findByTestId('roast-status-loader')).toBeInTheDocument();
  });

  it('failed retry shows the backend detail', async () => {
    vi.spyOn(submissionService, 'get').mockResolvedValue(makeSubmission({ status: 'failed', roast: null }));
    vi.spyOn(submissionService, 'retry').mockRejectedValue(makeAxiosError(429, { detail: 'Quota over da' }));
    renderAt('/roasts/7');
    await userEvent.click(await screen.findByRole('button', { name: /Retry pannu/ }));
    expect(await screen.findByText('Quota over da')).toBeInTheDocument();
  });

  it('404 → friendly not-found state (no retries)', async () => {
    const get = vi.spyOn(submissionService, 'get').mockRejectedValue(makeAxiosError(404, { detail: 'Not found' }));
    renderAt('/roasts/999');
    expect(await screen.findByText('Roast kidaikala 🤷')).toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(1);
  });

  it('non-numeric id → not-found without fetching', () => {
    const get = vi.spyOn(submissionService, 'get');
    renderAt('/roasts/abc');
    expect(screen.getByText('Roast kidaikala 🤷')).toBeInTheDocument();
    expect(get).not.toHaveBeenCalled();
  });

  it('other errors show the message with a Try again button', async () => {
    const get = vi
      .spyOn(submissionService, 'get')
      .mockRejectedValue(makeAxiosError(500, { detail: 'Server sappittu thoongudhu 😴' }));
    renderAt('/roasts/7');
    expect(await screen.findByText('Server sappittu thoongudhu 😴', {}, { timeout: 4000 })).toBeInTheDocument();
    const calls = get.mock.calls.length;
    get.mockResolvedValue(makeSubmission());
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(get.mock.calls.length).toBeGreaterThan(calls));
    expect(await screen.findByTestId('roast-report')).toBeInTheDocument();
  }, 10000);
});
