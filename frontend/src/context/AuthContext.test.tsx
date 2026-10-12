import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { ReactNode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAuth } from '../hooks/useAuth';
import { tokenStore } from '../lib/tokenStore';
import { refreshTokens } from '../services/api';
import { fetchMe, logout as logoutRequest } from '../services/authService';
import { makeAxiosError } from '../test/fixtures';
import { renderWithProviders, testUser } from '../test/utils';
import { AuthProvider } from './AuthContext';

vi.mock('../services/authService', () => ({
  getLoginUrl: () => '/api/v1/auth/github/login',
  fetchMe: vi.fn(),
  logout: vi.fn(),
}));

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('../services/api')>();
  return { ...actual, refreshTokens: vi.fn() };
});

const fetchMeMock = vi.mocked(fetchMe);
const refreshMock = vi.mocked(refreshTokens);
const logoutMock = vi.mocked(logoutRequest);

function Probe() {
  const { user, isLoading, isAuthenticated, logout } = useAuth();
  return (
    <div>
      <span data-testid="state">{isLoading ? 'loading' : isAuthenticated ? `user:${user?.githubUsername}` : 'anon'}</span>
      <button type="button" onClick={() => void logout()}>
        logout
      </button>
    </div>
  );
}

function renderWithAuth(route = '/dashboard') {
  return renderWithProviders(<Probe />, {
    route,
    authWrapper: (children: ReactNode) => <AuthProvider>{children}</AuthProvider>,
  });
}

describe('AuthProvider', () => {
  beforeEach(() => {
    tokenStore.clear();
    fetchMeMock.mockReset();
    refreshMock.mockReset();
    logoutMock.mockReset();
  });
  afterEach(() => {
    tokenStore.clear();
  });

  it('without tokens → anonymous, no network calls', async () => {
    renderWithAuth();
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('anon'));
    expect(refreshMock).not.toHaveBeenCalled();
    expect(fetchMeMock).not.toHaveBeenCalled();
  });

  it('with a stored refresh token → refreshes once then loads the user', async () => {
    tokenStore.setRefreshToken('r1');
    refreshMock.mockResolvedValue('a1');
    fetchMeMock.mockResolvedValue(testUser);
    renderWithAuth();
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('user:machan'));
    expect(refreshMock).toHaveBeenCalledTimes(1);
  });

  it('refresh failure clears tokens and stays anonymous', async () => {
    tokenStore.setRefreshToken('bad');
    refreshMock.mockRejectedValue(makeAxiosError(401, { detail: 'revoked' }));
    renderWithAuth();
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('anon'));
    expect(tokenStore.getRefreshToken()).toBeNull();
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/dashboard$/);
  });

  it('inactive account (403 on /auth/me) → /login?error=inactive', async () => {
    tokenStore.setAccessToken('a');
    fetchMeMock.mockRejectedValue(makeAxiosError(403, { detail: 'inactive' }));
    renderWithAuth();
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent('/login?error=inactive'));
    expect(screen.getByTestId('state')).toHaveTextContent('anon');
  });

  it('logout revokes the refresh token (best effort), clears state and goes home', async () => {
    tokenStore.setTokens('a', 'r');
    fetchMeMock.mockResolvedValue(testUser);
    logoutMock.mockRejectedValue(new Error('network'));
    renderWithAuth();
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('user:machan'));

    await userEvent.click(screen.getByRole('button', { name: 'logout' }));
    await waitFor(() => expect(screen.getByTestId('state')).toHaveTextContent('anon'));
    expect(logoutMock).toHaveBeenCalledWith('r');
    expect(tokenStore.getAccessToken()).toBeNull();
    expect(tokenStore.getRefreshToken()).toBeNull();
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/$/);
  });
});
