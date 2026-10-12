import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { roastService } from '../services/roastService';
import { makeAxiosError, makeRoastStatus } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';
import RoastPage, { ROAST_NOT_FOUND_MESSAGE } from './RoastPage';

function renderAt(route: string) {
  return renderWithProviders(<RoastPage />, { route, path: '/r/:shareSlug' });
}

const inProgress = { roast: null, analysis: null, completedAt: null };

describe('RoastPage', () => {
  it('shows the skeleton while the first fetch is in flight', () => {
    vi.spyOn(roastService, 'get').mockReturnValue(new Promise(() => undefined));
    renderAt('/r/abc123');
    expect(screen.getByTestId('roast-report-skeleton')).toBeInTheDocument();
  });

  it('pending → status loader with repo label', async () => {
    const get = vi.spyOn(roastService, 'get').mockResolvedValue(makeRoastStatus({ status: 'pending', ...inProgress }));
    renderAt('/r/abc123');
    expect(await screen.findByTestId('roast-status-loader')).toHaveTextContent('machan/genai-hw');
    expect(get).toHaveBeenCalledWith('abc123');
    expect(screen.queryByTestId('roast-report')).not.toBeInTheDocument();
  });

  it('polls while in progress and shows the report once completed', async () => {
    const get = vi
      .spyOn(roastService, 'get')
      .mockResolvedValueOnce(makeRoastStatus({ status: 'analyzing', ...inProgress }))
      .mockResolvedValueOnce(makeRoastStatus({ status: 'roasting', ...inProgress }))
      .mockResolvedValue(makeRoastStatus({ status: 'completed' }));
    renderAt('/r/abc123');

    expect(await screen.findByTestId('roast-status-loader')).toBeInTheDocument();
    expect(await screen.findByTestId('roast-report', {}, { timeout: 6000 })).toBeInTheDocument();
    expect(get.mock.calls.length).toBeGreaterThanOrEqual(3);
    const callsAtCompletion = get.mock.calls.length;

    // Terminal status → polling stops.
    await new Promise((resolve) => setTimeout(resolve, 2300));
    expect(get).toHaveBeenCalledTimes(callsAtCompletion);
  }, 15000);

  it('completed → full report with share bar and GitHub link', async () => {
    vi.spyOn(roastService, 'get').mockResolvedValue(makeRoastStatus({ status: 'completed' }));
    renderAt('/r/abc123');
    expect(await screen.findByTestId('roast-report')).toBeInTheDocument();
    expect(screen.getByLabelText('Score 3.5 out of 10')).toBeInTheDocument();
    expect(screen.getByTestId('share-bar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy public roast link' })).toBeEnabled();
    expect(screen.getByRole('link', { name: 'Open machan/genai-hw on GitHub' })).toHaveAttribute(
      'href',
      'https://github.com/machan/genai-hw',
    );
  });

  it('failed → error message + Retry button that calls retry', async () => {
    vi.spyOn(roastService, 'get').mockResolvedValue(
      makeRoastStatus({ status: 'failed', ...inProgress, errorMessage: 'Claude busy machan 😴' }),
    );
    const retry = vi.spyOn(roastService, 'retry').mockResolvedValue(makeRoastStatus({ status: 'pending', ...inProgress }));
    renderAt('/r/abc123');

    expect(await screen.findByText('Roast fail aayiduchu 😵')).toBeInTheDocument();
    expect(screen.getByText('Claude busy machan 😴')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /Retry pannu/ }));
    expect(retry).toHaveBeenCalledWith('abc123');
    expect(await screen.findByTestId('roast-status-loader')).toBeInTheDocument();
  });

  it('non-retryable failure → no Retry button, offers a new roast instead', async () => {
    vi.spyOn(roastService, 'get').mockResolvedValue(
      makeRoastStatus({ status: 'failed', ...inProgress, errorRetryable: false, errorMessage: 'Repo private-a irukku 🔒' }),
    );
    renderAt('/r/abc123');
    expect(await screen.findByText('Repo private-a irukku 🔒')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Retry pannu/ })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Pudhu roast pannu/ })).toHaveAttribute('href', '/');
  });

  it('failed retry shows the backend detail', async () => {
    vi.spyOn(roastService, 'get').mockResolvedValue(makeRoastStatus({ status: 'failed', ...inProgress }));
    vi.spyOn(roastService, 'retry').mockRejectedValue(makeAxiosError(429, { detail: 'Quota over da' }));
    renderAt('/r/abc123');
    await userEvent.click(await screen.findByRole('button', { name: /Retry pannu/ }));
    expect(await screen.findByText('Quota over da')).toBeInTheDocument();
  });

  it('404 → friendly not-found state (no retries)', async () => {
    const get = vi.spyOn(roastService, 'get').mockRejectedValue(makeAxiosError(404, { detail: 'Not found' }));
    renderAt('/r/missing');
    expect(await screen.findByText(ROAST_NOT_FOUND_MESSAGE)).toBeInTheDocument();
    expect(get).toHaveBeenCalledTimes(1);
  });

  it('other errors show the message with a Try again button', async () => {
    const get = vi
      .spyOn(roastService, 'get')
      .mockRejectedValue(makeAxiosError(500, { detail: 'Server sappittu thoongudhu 😴' }));
    renderAt('/r/abc123');
    expect(await screen.findByText('Server sappittu thoongudhu 😴', {}, { timeout: 4000 })).toBeInTheDocument();
    const calls = get.mock.calls.length;
    get.mockResolvedValue(makeRoastStatus());
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    await waitFor(() => expect(get.mock.calls.length).toBeGreaterThan(calls));
    expect(await screen.findByTestId('roast-report')).toBeInTheDocument();
  }, 10000);
});
