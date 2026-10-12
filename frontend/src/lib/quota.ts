import type { UserResponse } from '../types';

/** Helper text under the URL input; never hardcodes the (configurable) daily limit. */
export function quotaHint(user: UserResponse | null): string {
  const limit = user?.dailyLimit;
  if (typeof limit !== 'number') return 'Public repos only';
  const used = user?.roastsUsedToday;
  if (typeof used === 'number') {
    return `Public repos only · innaikku ${Math.max(limit - used, 0)}/${limit} roasts baakki`;
  }
  return `Public repos only · ${limit} roasts/day`;
}
