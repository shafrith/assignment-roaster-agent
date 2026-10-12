import { createContext } from 'react';
import type { UserResponse } from '../types';

export interface AuthContextValue {
  user: UserResponse | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  /** Full-page redirect to the backend GitHub OAuth login. */
  login: () => void;
  /** Revoke refresh token (best effort), clear tokens + query cache, go to "/". */
  logout: () => Promise<void>;
  /** Store tokens from the OAuth callback and load the current user. */
  completeLogin: (accessToken: string, refreshToken: string) => Promise<UserResponse>;
  /** Replace the cached user (e.g. after PATCH /auth/me). */
  setUser: (user: UserResponse | null) => void;
  /** Re-fetch GET /auth/me. */
  refreshUser: () => Promise<UserResponse | null>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
