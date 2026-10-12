import { afterEach, describe, expect, it, vi } from 'vitest';
import { makeRoastStatus } from '../test/fixtures';
import { api } from './api';
import { roastKeys, roastService } from './roastService';

describe('roastService', () => {
  afterEach(() => vi.restoreAllMocks());

  it('create POSTs the repo URL to /roasts', async () => {
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: makeRoastStatus({ status: 'pending' }) });
    const result = await roastService.create({ repoUrl: 'https://github.com/a/b' });
    expect(post).toHaveBeenCalledWith('/roasts', { repoUrl: 'https://github.com/a/b' });
    expect(result.status).toBe('pending');
  });

  it('get and retry address the roast by its encoded share slug', async () => {
    const get = vi.spyOn(api, 'get').mockResolvedValue({ data: makeRoastStatus() });
    const post = vi.spyOn(api, 'post').mockResolvedValue({ data: makeRoastStatus({ status: 'pending' }) });
    await roastService.get('a/b');
    await roastService.retry('abc_-1');
    expect(get).toHaveBeenCalledWith('/roasts/a%2Fb');
    expect(post).toHaveBeenCalledWith('/roasts/abc_-1/retry');
  });

  it('query keys are per slug', () => {
    expect(roastKeys.detail('x')).toEqual(['roasts', 'x']);
  });
});
