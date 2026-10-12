import { api, API_BASE_URL } from './api';
import type { UserResponse } from '../types';

/** Full-page URL that starts the GitHub OAuth flow (navigate, never XHR). */
export function getLoginUrl(): string {
  return `${API_BASE_URL}/auth/github/login`;
}

export async function fetchMe(): Promise<UserResponse> {
  const { data } = await api.get<UserResponse>('/auth/me');
  return data;
}

export async function updateSettings(defaultRoastPublic: boolean): Promise<UserResponse> {
  const { data } = await api.patch<UserResponse>('/auth/me', { defaultRoastPublic });
  return data;
}

export async function logout(refreshToken: string): Promise<void> {
  await api.post('/auth/logout', { refreshToken });
}

export const authService = { getLoginUrl, fetchMe, updateSettings, logout };

export default authService;
