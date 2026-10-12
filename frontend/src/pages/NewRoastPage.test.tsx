import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { INVALID_GITHUB_URL_MESSAGE } from '../lib/githubUrl';
import { submissionService } from '../services/submissionService';
import { makeAxiosError, makeSubmission } from '../test/fixtures';
import { renderWithProviders, testUser } from '../test/utils';
import { quotaHint } from '../lib/quota';
import NewRoastPage from './NewRoastPage';

describe('quotaHint', () => {
  it('never hardcodes the limit and shows what is left when known', () => {
    expect(quotaHint(null)).toBe('Public repos only');
    expect(quotaHint(testUser)).toBe('Public repos only');
    expect(quotaHint({ ...testUser, dailyLimit: 7 })).toBe('Public repos only · 7 roasts/day');
    expect(quotaHint({ ...testUser, dailyLimit: 7, roastsUsedToday: 2 })).toBe('Public repos only · innaikku 5/7 roasts baakki');
    expect(quotaHint({ ...testUser, dailyLimit: 3, roastsUsedToday: 9 })).toBe('Public repos only · innaikku 0/3 roasts baakki');
  });
});

function renderPage() {
  return renderWithProviders(<NewRoastPage />, { route: '/roast/new', path: '/roast/new', auth: { user: testUser } });
}

describe('NewRoastPage', () => {
  it('shows the hint and disables submit while empty', () => {
    renderPage();
    expect(screen.getByText('Public repos only')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Roast Me 🔥' })).toBeDisabled();
  });

  it('shows the validation error on blur for an invalid URL', async () => {
    const create = vi.spyOn(submissionService, 'create');
    renderPage();
    const input = screen.getByLabelText('GitHub repo URL');
    await userEvent.type(input, 'https://gitlab.com/a/b');
    expect(screen.queryByText(INVALID_GITHUB_URL_MESSAGE)).not.toBeInTheDocument();
    await userEvent.tab();
    expect(screen.getByText(INVALID_GITHUB_URL_MESSAGE)).toBeInTheDocument();
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(screen.queryByText('Public repos only')).not.toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
  });

  it('shows the validation error on submit and does not call the API', async () => {
    const create = vi.spyOn(submissionService, 'create');
    renderPage();
    await userEvent.type(screen.getByLabelText('GitHub repo URL'), 'not a url{Enter}');
    expect(screen.getByText(INVALID_GITHUB_URL_MESSAGE)).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
  });

  it('valid submit creates the submission (trimmed) and navigates to /roasts/:id', async () => {
    const create = vi.spyOn(submissionService, 'create').mockResolvedValue(makeSubmission({ id: 42, status: 'pending' }));
    renderPage();
    await userEvent.type(screen.getByLabelText('GitHub repo URL'), '  https://github.com/machan/genai-hw  ');
    await userEvent.click(screen.getByRole('button', { name: 'Roast Me 🔥' }));

    expect(create).toHaveBeenCalledWith({ repoUrl: 'https://github.com/machan/genai-hw' });
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(/^\/roasts\/42$/));
  });

  it('shows the backend detail on 429 and clears it when the user edits the URL', async () => {
    vi.spyOn(submissionService, 'create').mockRejectedValue(
      makeAxiosError(429, { detail: 'Innaikku 5 roast aachu machan, naalaikku vaa 😴' }),
    );
    renderPage();
    const input = screen.getByLabelText('GitHub repo URL');
    await userEvent.type(input, 'https://github.com/a/b');
    await userEvent.click(screen.getByRole('button', { name: 'Roast Me 🔥' }));

    const alert = await screen.findByTestId('create-error');
    expect(alert).toHaveTextContent('Innaikku 5 roast aachu machan, naalaikku vaa 😴');
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/roast\/new$/);

    await userEvent.type(input, 'c');
    await waitFor(() => expect(screen.queryByTestId('create-error')).not.toBeInTheDocument());
  });

  it('shows the backend detail on 400', async () => {
    vi.spyOn(submissionService, 'create').mockRejectedValue(makeAxiosError(400, { detail: 'Repo private-a irukku 🔒' }));
    renderPage();
    await userEvent.type(screen.getByLabelText('GitHub repo URL'), 'https://github.com/a/b{Enter}');
    expect(await screen.findByTestId('create-error')).toHaveTextContent('Repo private-a irukku 🔒');
  });
});
