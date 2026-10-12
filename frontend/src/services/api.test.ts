import axios, { AxiosError, AxiosHeaders, type AxiosAdapter, type AxiosResponse, type InternalAxiosRequestConfig } from 'axios';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { tokenStore } from '../lib/tokenStore';
import { makeAxiosError } from '../test/fixtures';
import type { TokenResponse } from '../types';
import { api, getErrorMessage, isInactiveError, REFRESH_LOCK_NAME, refreshTokens, withRefreshLock } from './api';

function tokenResponse(access: string, refresh: string): AxiosResponse<TokenResponse> {
  const config: InternalAxiosRequestConfig = { headers: new AxiosHeaders() };
  return {
    data: { accessToken: access, refreshToken: refresh, tokenType: 'bearer' },
    status: 200,
    statusText: 'OK',
    headers: {},
    config,
  };
}

function ok<T>(config: InternalAxiosRequestConfig, data: T): AxiosResponse<T> {
  return { data, status: 200, statusText: 'OK', headers: {}, config };
}

function deferred<T>(): { promise: Promise<T>; resolve: (value: T) => void; reject: (err: unknown) => void } {
  let resolve!: (value: T) => void;
  let reject!: (err: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

const originalAdapter = api.defaults.adapter;

describe('services/api', () => {
  beforeEach(() => {
    tokenStore.clear();
    // Keep handleAuthFailure from attempting a (jsdom-unsupported) navigation.
    window.history.replaceState(null, '', '/login');
  });

  afterEach(() => {
    api.defaults.adapter = originalAdapter;
    tokenStore.clear();
    window.history.replaceState(null, '', '/');
  });

  describe('refreshTokens', () => {
    it('is single-flight: concurrent callers share one POST /auth/refresh', async () => {
      tokenStore.setRefreshToken('refresh-old');
      const pending = deferred<AxiosResponse<TokenResponse>>();
      const post = vi.spyOn(axios, 'post').mockReturnValue(pending.promise);

      const first = refreshTokens();
      const second = refreshTokens();
      expect(post).toHaveBeenCalledTimes(1);
      expect(post.mock.calls[0][0]).toMatch(/\/api\/v1\/auth\/refresh$/);
      expect(post.mock.calls[0][1]).toEqual({ refreshToken: 'refresh-old' });

      pending.resolve(tokenResponse('access-new', 'refresh-new'));
      await expect(first).resolves.toBe('access-new');
      await expect(second).resolves.toBe('access-new');
      expect(tokenStore.getAccessToken()).toBe('access-new');
      expect(tokenStore.getRefreshToken()).toBe('refresh-new');

      // A later call starts a fresh request.
      post.mockResolvedValueOnce(tokenResponse('access-3', 'refresh-3'));
      await expect(refreshTokens()).resolves.toBe('access-3');
      expect(post).toHaveBeenCalledTimes(2);
    });

    it('rejects without a network call when no refresh token is stored', async () => {
      const post = vi.spyOn(axios, 'post');
      await expect(refreshTokens()).rejects.toThrow('No refresh token');
      expect(post).not.toHaveBeenCalled();
    });

    it('resets the in-flight promise after a failure', async () => {
      tokenStore.setRefreshToken('r');
      const post = vi
        .spyOn(axios, 'post')
        .mockRejectedValueOnce(makeAxiosError(401, { detail: 'nope' }))
        .mockResolvedValueOnce(tokenResponse('a2', 'r2'));
      await expect(refreshTokens()).rejects.toBeInstanceOf(AxiosError);
      await expect(refreshTokens()).resolves.toBe('a2');
      expect(post).toHaveBeenCalledTimes(2);
    });
  });

  describe('cross-tab refresh lock (COR-5)', () => {
    type LockCallback = (lock: Lock | null) => Promise<unknown>;

    function installLocks(request: (name: string, options: LockOptions, cb: LockCallback) => Promise<unknown>): void {
      Object.defineProperty(navigator, 'locks', { configurable: true, value: { request } });
    }

    afterEach(() => {
      Reflect.deleteProperty(navigator, 'locks');
    });

    it('serialises refreshes behind an exclusive Web Lock', async () => {
      tokenStore.setRefreshToken('refresh-old');
      const request = vi.fn((_name: string, _options: LockOptions, cb: LockCallback) => cb(null));
      installLocks(request);
      vi.spyOn(axios, 'post').mockResolvedValue(tokenResponse('access-new', 'refresh-new'));

      await expect(refreshTokens()).resolves.toBe('access-new');
      expect(request).toHaveBeenCalledTimes(1);
      expect(request.mock.calls[0][0]).toBe(REFRESH_LOCK_NAME);
      expect(request.mock.calls[0][1]).toEqual({ mode: 'exclusive' });
      expect(tokenStore.getRefreshToken()).toBe('refresh-new');
    });

    it('re-reads the refresh token after acquiring the lock (another tab rotated it meanwhile)', async () => {
      tokenStore.setRefreshToken('refresh-stale');
      // Simulate tab B holding the lock and rotating the token before tab A gets it.
      installLocks(async (_name, _options, cb) => {
        window.localStorage.setItem('ar_refresh_token', 'refresh-rotated-by-other-tab');
        return cb(null);
      });
      const post = vi.spyOn(axios, 'post').mockResolvedValue(tokenResponse('access-a', 'refresh-a'));

      await refreshTokens();
      expect(post).toHaveBeenCalledTimes(1);
      expect(post.mock.calls[0][1]).toEqual({ refreshToken: 'refresh-rotated-by-other-tab' });
    });

    it('two tabs racing never POST the same refresh token', async () => {
      tokenStore.setRefreshToken('refresh-1');
      // A real exclusive lock: callbacks run strictly one after another.
      let tail: Promise<unknown> = Promise.resolve();
      installLocks((_name, _options, cb) => {
        const run = tail.then(() => cb(null));
        tail = run.catch(() => undefined);
        return run;
      });
      let n = 1;
      const post = vi.spyOn(axios, 'post').mockImplementation(async () => {
        n += 1;
        return tokenResponse(`access-${n}`, `refresh-${n}`);
      });

      // Tab B's refresh goes through the lock directly (a separate module instance in reality).
      const tabB = withRefreshLock(async () => {
        const token = tokenStore.getRefreshToken();
        const { data } = await axios.post<TokenResponse>('/api/v1/auth/refresh', { refreshToken: token });
        tokenStore.setTokens(data.accessToken, data.refreshToken);
        return data.accessToken;
      });
      const tabA = refreshTokens();
      await Promise.all([tabA, tabB]);

      const sent = post.mock.calls.map((call) => (call[1] as { refreshToken: string }).refreshToken);
      expect(sent).toEqual(['refresh-1', 'refresh-2']);
      expect(new Set(sent).size).toBe(sent.length);
    });

    it('falls back to running directly when the Web Locks API is unavailable', async () => {
      Reflect.deleteProperty(navigator, 'locks');
      await expect(withRefreshLock(async () => 'ran')).resolves.toBe('ran');
    });
  });

  describe('interceptors', () => {
    it('attaches the bearer token to requests', async () => {
      tokenStore.setAccessToken('tok');
      const adapter = vi.fn<AxiosAdapter>(async (config) => ok(config, { fine: true }));
      api.defaults.adapter = adapter;

      await api.get('/things');
      expect(adapter.mock.calls[0][0].headers.get('Authorization')).toBe('Bearer tok');
    });

    it('on 401: refreshes once, retries with the new token', async () => {
      tokenStore.setTokens('expired', 'refresh-1');
      const post = vi.spyOn(axios, 'post').mockResolvedValue(tokenResponse('fresh', 'refresh-2'));
      const adapter = vi.fn<AxiosAdapter>(async (config) => {
        if (config.headers.get('Authorization') === 'Bearer expired') {
          throw makeAxiosError(401, { detail: 'expired' }, config);
        }
        return ok(config, { url: config.url });
      });
      api.defaults.adapter = adapter;

      const [a, b] = await Promise.all([api.get('/a'), api.get('/b')]);
      expect(a.data).toEqual({ url: '/a' });
      expect(b.data).toEqual({ url: '/b' });
      expect(post).toHaveBeenCalledTimes(1);
      expect(adapter).toHaveBeenCalledTimes(4);
      const retried = adapter.mock.calls.slice(2).map(([config]) => config.headers.get('Authorization'));
      expect(retried).toEqual(['Bearer fresh', 'Bearer fresh']);
      expect(tokenStore.getRefreshToken()).toBe('refresh-2');
    });

    it('does not retry a request twice (no infinite loop)', async () => {
      tokenStore.setTokens('t', 'r');
      vi.spyOn(axios, 'post').mockResolvedValue(tokenResponse('t2', 'r2'));
      const adapter = vi.fn<AxiosAdapter>(async (config) => {
        throw makeAxiosError(401, { detail: 'still no' }, config);
      });
      api.defaults.adapter = adapter;

      await expect(api.get('/x')).rejects.toMatchObject({ response: { status: 401 } });
      expect(adapter).toHaveBeenCalledTimes(2);
    });

    it('passes through non-401 errors untouched', async () => {
      const post = vi.spyOn(axios, 'post');
      api.defaults.adapter = vi.fn<AxiosAdapter>(async (config) => {
        throw makeAxiosError(429, { detail: 'slow down' }, config);
      });
      await expect(api.get('/x')).rejects.toMatchObject({ response: { status: 429 } });
      expect(post).not.toHaveBeenCalled();
    });

    it('clears tokens when the refresh fails', async () => {
      tokenStore.setTokens('expired', 'refresh-bad');
      vi.spyOn(axios, 'post').mockRejectedValue(makeAxiosError(401, { detail: 'revoked' }));
      api.defaults.adapter = vi.fn<AxiosAdapter>(async (config) => {
        throw makeAxiosError(401, { detail: 'expired' }, config);
      });

      await expect(api.get('/x')).rejects.toMatchObject({ response: { data: { detail: 'revoked' } } });
      expect(tokenStore.getAccessToken()).toBeNull();
      expect(tokenStore.getRefreshToken()).toBeNull();
    });
  });

  describe('getErrorMessage', () => {
    it('returns a string detail', () => {
      expect(getErrorMessage(makeAxiosError(429, { detail: 'Innaikku quota mudinjiduchu' }))).toBe(
        'Innaikku quota mudinjiduchu',
      );
    });

    it('returns the first msg of a 422 validation list', () => {
      const err = makeAxiosError(422, { detail: [{ msg: 'Invalid URL', loc: ['body', 'repoUrl'] }, { msg: 'second' }] });
      expect(getErrorMessage(err)).toBe('Invalid URL');
    });

    it('falls back for unknown payloads, empty lists and network errors', () => {
      expect(getErrorMessage(makeAxiosError(500, '<html>oops</html>'))).toBe(
        'Edho thappa pochu machan, konjam apram try pannu 🙏',
      );
      expect(getErrorMessage(makeAxiosError(422, { detail: [] }))).toBe(
        'Edho thappa pochu machan, konjam apram try pannu 🙏',
      );
      expect(getErrorMessage(new AxiosError('Network Error', 'ERR_NETWORK'))).toBe(
        'Server-a reach panna mudiyala, network check pannu 📡',
      );
    });

    it('uses Error.message for plain errors and falls back for anything else', () => {
      expect(getErrorMessage(new Error('boom'))).toBe('boom');
      expect(getErrorMessage('weird')).toBe('Edho thappa pochu machan, konjam apram try pannu 🙏');
      expect(getErrorMessage(new Error(''))).toBe('Edho thappa pochu machan, konjam apram try pannu 🙏');
    });
  });

  describe('isInactiveError', () => {
    it('is true only for axios 403s', () => {
      expect(isInactiveError(makeAxiosError(403, { detail: 'inactive' }))).toBe(true);
      expect(isInactiveError(makeAxiosError(401, {}))).toBe(false);
      expect(isInactiveError(new Error('403'))).toBe(false);
      expect(isInactiveError(null)).toBe(false);
    });
  });
});
