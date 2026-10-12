import { useQuery } from '@tanstack/react-query';
import { isNotFoundError } from '../lib/httpErrors';
import { publicKeys, publicService } from '../services/publicService';

/** Public (no-auth) roast by share slug. 404 when private or missing — not retried. */
export function usePublicRoast(shareSlug: string | undefined) {
  return useQuery({
    queryKey: publicKeys.roast(shareSlug ?? ''),
    queryFn: () => publicService.getRoast(shareSlug as string),
    enabled: Boolean(shareSlug),
    retry: (failureCount, error) => !isNotFoundError(error) && failureCount < 1,
  });
}
