import type { AxiosAdapter, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './api';
import { publicService } from './publicService';
import { submissionService } from './submissionService';

const originalAdapter = api.defaults.adapter;

function installAdapter(data: unknown = {}) {
  const adapter = vi.fn<AxiosAdapter>(
    async (config: InternalAxiosRequestConfig): Promise<AxiosResponse> => ({
      data,
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    }),
  );
  api.defaults.adapter = adapter;
  return adapter;
}

function call(adapter: ReturnType<typeof installAdapter>, index = 0) {
  const config = adapter.mock.calls[index][0];
  return { method: config.method, url: config.url, params: config.params as unknown, data: config.data as unknown };
}

describe('submissionService / publicService request shapes', () => {
  afterEach(() => {
    api.defaults.adapter = originalAdapter;
  });

  it('create → POST /submissions with camelCase body', async () => {
    const adapter = installAdapter({ id: 1 });
    await expect(submissionService.create({ repoUrl: 'https://github.com/a/b' })).resolves.toEqual({ id: 1 });
    expect(call(adapter)).toMatchObject({ method: 'post', url: '/submissions' });
    expect(JSON.parse(call(adapter).data as string)).toEqual({ repoUrl: 'https://github.com/a/b' });
  });

  it('list → GET /submissions with page params (default pageSize 10)', async () => {
    const adapter = installAdapter({ items: [], total: 0, page: 2, pageSize: 10 });
    await submissionService.list(2);
    expect(call(adapter)).toMatchObject({ method: 'get', url: '/submissions', params: { page: 2, pageSize: 10 } });
  });

  it('get / retry / updateVisibility / remove hit the right endpoints', async () => {
    const adapter = installAdapter({});
    await submissionService.get(5);
    await submissionService.retry(5);
    await submissionService.updateVisibility(5, { isPublic: true });
    await submissionService.remove(5);
    expect(call(adapter, 0)).toMatchObject({ method: 'get', url: '/submissions/5' });
    expect(call(adapter, 1)).toMatchObject({ method: 'post', url: '/submissions/5/retry' });
    expect(call(adapter, 2)).toMatchObject({ method: 'patch', url: '/submissions/5/visibility' });
    expect(JSON.parse(call(adapter, 2).data as string)).toEqual({ isPublic: true });
    expect(call(adapter, 3)).toMatchObject({ method: 'delete', url: '/submissions/5' });
  });

  it('publicService.getRoast URL-encodes the slug', async () => {
    const adapter = installAdapter({});
    await publicService.getRoast('a/b?c');
    expect(call(adapter)).toMatchObject({ method: 'get', url: '/public/roasts/a%2Fb%3Fc' });
  });
});
