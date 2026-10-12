import type { PublicRoastResponse } from '../types/api';
import { api } from './api';

export const publicKeys = {
  roast: (shareSlug: string) => ['public', 'roast', shareSlug] as const,
};

export const publicService = {
  async getRoast(shareSlug: string): Promise<PublicRoastResponse> {
    const { data } = await api.get<PublicRoastResponse>(`/public/roasts/${encodeURIComponent(shareSlug)}`);
    return data;
  },
};

export default publicService;
