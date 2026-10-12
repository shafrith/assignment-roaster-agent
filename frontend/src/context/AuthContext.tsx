import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { tokenStore } from '../lib/tokenStore';
import { isInactiveError, refreshTokens } from '../services/api';
import { fetchMe, getLoginUrl, logout as logoutRequest } from '../services/authService';
import type { UserResponse } from '../types';
import { AuthContext, type AuthContextValue } from './authContextValue';

export interface AuthProviderProps {
  children: ReactNode;
}

/** Must be rendered inside <BrowserRouter> and <QueryClientProvider>. */
export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Ref guard: StrictMode double-invokes effects, and refresh tokens are single-use
  // (a concurrent second refresh would be treated as token reuse and revoke all sessions).
  // refreshTokens() is also single-flight across the axios interceptor and direct callers.
  const bootstrapped = useRef<boolean>(false);

  useEffect(() => {
    if (bootstrapped.current) return;
    bootstrapped.current = true;

    async function bootstrap(): Promise<void> {
      try {
        if (!tokenStore.getAccessToken()) {
          if (!tokenStore.getRefreshToken()) return;
          await refreshTokens(); // stores the rotated refresh token
        }
        setUser(await fetchMe());
      } catch (err) {
        tokenStore.clear();
        setUser(null);
        if (isInactiveError(err)) {
          navigate('/login?error=inactive', { replace: true });
        }
      } finally {
        setIsLoading(false);
      }
    }

    void bootstrap();
  }, [navigate]);

  const login = useCallback((): void => {
    window.location.assign(getLoginUrl());
  }, []);

  const logout = useCallback(async (): Promise<void> => {
    const refreshToken = tokenStore.getRefreshToken();
    if (refreshToken) {
      try {
        await logoutRequest(refreshToken);
      } catch {
        // Best effort — local session is cleared regardless.
      }
    }
    tokenStore.clear();
    queryClient.clear();
    setUser(null);
    navigate('/', { replace: true });
  }, [navigate, queryClient]);

  const completeLogin = useCallback(async (accessToken: string, refreshToken: string): Promise<UserResponse> => {
    tokenStore.setTokens(accessToken, refreshToken);
    try {
      const me = await fetchMe();
      setUser(me);
      return me;
    } catch (err) {
      tokenStore.clear();
      setUser(null);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, []);

  const refreshUser = useCallback(async (): Promise<UserResponse | null> => {
    try {
      const me = await fetchMe();
      setUser(me);
      return me;
    } catch {
      return null;
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      isLoading,
      isAuthenticated: user !== null,
      login,
      logout,
      completeLogin,
      setUser,
      refreshUser,
    }),
    [user, isLoading, login, logout, completeLogin, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export default AuthProvider;
