import type { RoastStatusResponse } from '../types/api';
import { api } from './api';

export interface CreateRoastRequest {
  repoUrl: string;
}

export const roastKeys = {
  all: ['roasts'] as const,
  detail: (shareSlug: string) => [...roastKeys.all, shareSlug] as const,
};

/** No-login roast API: create by URL, then follow progress by the returned share slug. */
export const roastService = {
  async create(payload: CreateRoastRequest): Promise<RoastStatusResponse> {
    const { data } = await api.post<RoastStatusResponse>('/roasts', payload);
    return data;
  },

  async get(shareSlug: string): Promise<RoastStatusResponse> {
    const { data } = await api.get<RoastStatusResponse>(`/roasts/${encodeURIComponent(shareSlug)}`);
    return data;
  },

  async retry(shareSlug: string): Promise<RoastStatusResponse> {
    const { data } = await api.post<RoastStatusResponse>(`/roasts/${encodeURIComponent(shareSlug)}/retry`);
    return data;
  },
};

export default roastService;
