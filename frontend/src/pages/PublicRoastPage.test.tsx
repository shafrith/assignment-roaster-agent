import { screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { publicService } from '../services/publicService';
import { makeAxiosError, publicRoastFixture } from '../test/fixtures';
import { renderWithProviders } from '../test/utils';
import PublicRoastPage, { PUBLIC_ROAST_NOT_FOUND } from './PublicRoastPage';

function renderAt(slug: string) {
  return renderWithProviders(<PublicRoastPage />, { route: `/r/${slug}`, path: '/r/:shareSlug', auth: null });
}

describe('PublicRoastPage', () => {
  it('renders the read-only report with the author chip (works without auth)', async () => {
    const getRoast = vi.spyOn(publicService, 'getRoast').mockResolvedValue(publicRoastFixture);
    renderAt('abc123');

    expect(await screen.findByTestId('roast-report')).toBeInTheDocument();
    expect(getRoast).toHaveBeenCalledWith('abc123');
    expect(screen.getByLabelText('Score 3.5 out of 10')).toBeInTheDocument();
    expect(screen.getByText('Copy-paste Champion 🏆')).toBeInTheDocument();

    const author = screen.getByRole('link', { name: '@roastee' });
    expect(author).toHaveAttribute('href', 'https://github.com/roastee');

    // Read-only: no visibility toggle; share bar enabled.
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy public roast link' })).toBeEnabled();
    expect(screen.getByRole('link', { name: 'Roast my repo 🔥' })).toHaveAttribute('href', '/');

    await waitFor(() => expect(document.title).toBe('machan/genai-hw got roasted: 3.5/10 🔥'));
  });

  it('404 → friendly not-found message, no retry', async () => {
    const getRoast = vi.spyOn(publicService, 'getRoast').mockRejectedValue(makeAxiosError(404, { detail: 'Not found' }));
    renderAt('gone');
    expect(await screen.findByText(PUBLIC_ROAST_NOT_FOUND)).toBeInTheDocument();
    expect(PUBLIC_ROAST_NOT_FOUND).toBe('Indha roast private-a illa delete aayiduchu 🤷');
    expect(screen.queryByTestId('roast-report')).not.toBeInTheDocument();
    expect(getRoast).toHaveBeenCalledTimes(1);
  });

  it('shows the skeleton while loading', () => {
    vi.spyOn(publicService, 'getRoast').mockReturnValue(new Promise(() => undefined));
    renderAt('abc123');
    expect(screen.getByTestId('roast-report-skeleton')).toBeInTheDocument();
  });
});
