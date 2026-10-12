/**
 * Token storage.
 * - Access token: in memory only (never persisted).
 * - Refresh token: persisted in localStorage (wrapped in try/catch — storage may be unavailable).
 */

const REFRESH_TOKEN_KEY = 'ar_refresh_token';

let accessToken: string | null = null;

function readStorage(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStorage(key: string, value: string | null): void {
  try {
    if (value === null) {
      window.localStorage.removeItem(key);
    } else {
      window.localStorage.setItem(key, value);
    }
  } catch {
    // Storage unavailable (private mode, blocked cookies) — keep working in memory.
  }
}

export const tokenStore = {
  getAccessToken(): string | null {
    return accessToken;
  },
  setAccessToken(token: string | null): void {
    accessToken = token;
  },
  getRefreshToken(): string | null {
    return readStorage(REFRESH_TOKEN_KEY);
  },
  setRefreshToken(token: string | null): void {
    writeStorage(REFRESH_TOKEN_KEY, token);
  },
  setTokens(access: string, refresh: string): void {
    accessToken = access;
    writeStorage(REFRESH_TOKEN_KEY, refresh);
  },
  clear(): void {
    accessToken = null;
    writeStorage(REFRESH_TOKEN_KEY, null);
  },
};

export type TokenStore = typeof tokenStore;
