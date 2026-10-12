import { screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { saveReturnTo } from '../lib/returnTo';
import { makeAxiosError } from '../test/fixtures';
import { renderWithProviders, testUser } from '../test/utils';
import AuthCallbackPage from './AuthCallbackPage';

function setBrowserUrl(url: string): void {
  window.history.replaceState(null, '', url);
}

describe('AuthCallbackPage', () => {
  afterEach(() => {
    setBrowserUrl('/');
  });

  it('parses tokens from the fragment, strips the hash and redirects to /dashboard', async () => {
    setBrowserUrl('/auth/callback#access=acc%2Etoken&refresh=ref-123');
    const completeLogin = vi.fn().mockResolvedValue(testUser);

    renderWithProviders(<AuthCallbackPage />, { route: '/auth/callback', path: '/auth/callback', auth: { completeLogin } });

    expect(window.location.hash).toBe('');
    expect(window.location.pathname).toBe('/auth/callback');
    expect(completeLogin).toHaveBeenCalledWith('acc.token', 'ref-123');
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(/^\/dashboard$/));
  });

  it('redirects to the saved returnTo path', async () => {
    saveReturnTo('/roasts/9');
    setBrowserUrl('/auth/callback#access=a&refresh=r');

    renderWithProviders(<AuthCallbackPage />, { route: '/auth/callback', path: '/auth/callback' });

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(/^\/roasts\/9$/));
  });

  it('missing tokens → /login?error=invalid_state without calling completeLogin', async () => {
    setBrowserUrl('/auth/callback#access=only-access');
    const completeLogin = vi.fn();

    renderWithProviders(<AuthCallbackPage />, { route: '/auth/callback', path: '/auth/callback', auth: { completeLogin } });

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/login?error=invalid_state'));
    expect(completeLogin).not.toHaveBeenCalled();
    expect(window.location.hash).toBe('');
  });

  it('inactive account (403 from /auth/me) → /login?error=inactive', async () => {
    setBrowserUrl('/auth/callback#access=a&refresh=r');
    const completeLogin = vi.fn().mockRejectedValue(makeAxiosError(403, { detail: 'inactive' }));

    renderWithProviders(<AuthCallbackPage />, { route: '/auth/callback', path: '/auth/callback', auth: { completeLogin } });

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/login?error=inactive'));
  });

  it('other completeLogin failures → /login?error=invalid_state', async () => {
    setBrowserUrl('/auth/callback#access=a&refresh=r');
    const completeLogin = vi.fn().mockRejectedValue(makeAxiosError(401, { detail: 'bad token' }));

    renderWithProviders(<AuthCallbackPage />, { route: '/auth/callback', path: '/auth/callback', auth: { completeLogin } });

    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/login?error=invalid_state'));
  });
});
