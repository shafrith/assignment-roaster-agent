import axios, { AxiosError, type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios';
import { tokenStore } from '../lib/tokenStore';
import type { ErrorResponse, TokenResponse } from '../types';

export const API_BASE_URL = `${import.meta.env.VITE_API_URL ?? ''}/api/v1`;

const REFRESH_PATH = '/auth/refresh';
const LOGIN_PATH = '/login';

interface RetryableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = tokenStore.getAccessToken();
  if (token) {
    config.headers.set('Authorization', `Bearer ${token}`);
  }
  return config;
});

/** Single in-flight refresh shared by all concurrent 401s (per tab). */
let refreshPromise: Promise<string> | null = null;

/** Web Locks name shared by every tab of this origin. */
export const REFRESH_LOCK_NAME = 'ar-refresh-token';

/**
 * Run `fn` while holding a cross-tab exclusive lock (COR-5).
 *
 * Refresh tokens are single-use and the backend treats a replayed one as theft (revoking every
 * session), so two tabs must never POST the same refresh token concurrently. The Web Locks API
 * serialises refreshes across tabs. Browsers without it (pre-2022) fall back to running directly:
 * the per-tab single-flight still applies, only the cross-tab race remains there.
 */
export async function withRefreshLock<T>(fn: () => Promise<T>): Promise<T> {
  const locks: LockManager | undefined =
    typeof navigator !== 'undefined' && 'locks' in navigator ? navigator.locks : undefined;
  if (!locks || typeof locks.request !== 'function') {
    return fn();
  }
  return locks.request(REFRESH_LOCK_NAME, { mode: 'exclusive' }, () => fn());
}

async function refreshAccessToken(): Promise<string> {
  return withRefreshLock(async () => {
    // Read the token only once we hold the lock: if another tab rotated it while we waited,
    // localStorage already holds the new (unused) token, so we never replay a revoked one.
    const refreshToken = tokenStore.getRefreshToken();
    if (!refreshToken) {
      throw new Error('No refresh token');
    }
    // Use a bare axios call so this request bypasses the interceptors.
    const { data } = await axios.post<TokenResponse>(`${API_BASE_URL}${REFRESH_PATH}`, { refreshToken });
    tokenStore.setTokens(data.accessToken, data.refreshToken);
    return data.accessToken;
  });
}

/** Shared refresh used by the interceptor and by AuthContext on boot. */
export function refreshTokens(): Promise<string> {
  if (!refreshPromise) {
    refreshPromise = refreshAccessToken().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

function handleAuthFailure(): void {
  tokenStore.clear();
  if (typeof window !== 'undefined' && window.location.pathname !== LOGIN_PATH) {
    window.location.assign(LOGIN_PATH);
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as RetryableConfig | undefined;
    const status = error.response?.status;
    const isRefreshCall = original?.url?.includes(REFRESH_PATH) ?? false;

    if (status !== 401 || !original || original._retry || isRefreshCall) {
      return Promise.reject(error);
    }

    original._retry = true;
    try {
      const newToken = await refreshTokens();
      original.headers.set('Authorization', `Bearer ${newToken}`);
      return api(original as AxiosRequestConfig);
    } catch (refreshError) {
      handleAuthFailure();
      return Promise.reject(refreshError);
    }
  },
);

const FALLBACK_MESSAGE = 'Edho thappa pochu machan, konjam apram try pannu 🙏';

function isErrorResponse(value: unknown): value is ErrorResponse {
  return (
    typeof value === 'object' &&
    value !== null &&
    'detail' in value &&
    typeof (value as { detail: unknown }).detail === 'string'
  );
}

interface ValidationErrorResponse {
  detail: { msg: string }[];
}

function isValidationErrorResponse(value: unknown): value is ValidationErrorResponse {
  if (typeof value !== 'object' || value === null || !('detail' in value)) return false;
  const detail: unknown = (value as { detail: unknown }).detail;
  return (
    Array.isArray(detail) &&
    detail.every((d: unknown) => typeof d === 'object' && d !== null && typeof (d as { msg?: unknown }).msg === 'string')
  );
}

/** 403 from an authenticated endpoint (e.g. GET /auth/me) means the account is inactive. */
export function isInactiveError(err: unknown): boolean {
  return axios.isAxiosError(err) && err.response?.status === 403;
}

/** Extract a user-facing message (backend `detail`) from any thrown value. */
export function getErrorMessage(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const data: unknown = err.response?.data;
    if (isErrorResponse(data)) {
      return data.detail;
    }
    if (isValidationErrorResponse(data) && data.detail.length > 0) {
      return data.detail[0].msg;
    }
    if (!err.response) {
      return 'Server-a reach panna mudiyala, network check pannu 📡';
    }
    return FALLBACK_MESSAGE;
  }
  if (err instanceof Error && err.message) {
    return err.message;
  }
  return FALLBACK_MESSAGE;
}

export default api;
