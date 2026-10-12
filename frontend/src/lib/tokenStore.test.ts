import { afterEach, describe, expect, it, vi } from 'vitest';
import { tokenStore } from './tokenStore';

const REFRESH_KEY = 'ar_refresh_token';

describe('tokenStore', () => {
  afterEach(() => {
    tokenStore.clear();
  });

  it('keeps the access token in memory only and persists the refresh token', () => {
    tokenStore.setTokens('access-1', 'refresh-1');
    expect(tokenStore.getAccessToken()).toBe('access-1');
    expect(tokenStore.getRefreshToken()).toBe('refresh-1');
    expect(window.localStorage.getItem(REFRESH_KEY)).toBe('refresh-1');
    expect(JSON.stringify({ ...window.localStorage })).not.toContain('access-1');
  });

  it('setAccessToken / setRefreshToken work individually', () => {
    tokenStore.setAccessToken('a');
    tokenStore.setRefreshToken('r');
    expect(tokenStore.getAccessToken()).toBe('a');
    expect(tokenStore.getRefreshToken()).toBe('r');
    tokenStore.setRefreshToken(null);
    expect(tokenStore.getRefreshToken()).toBeNull();
  });

  it('clear() wipes both tokens', () => {
    tokenStore.setTokens('a', 'r');
    tokenStore.clear();
    expect(tokenStore.getAccessToken()).toBeNull();
    expect(tokenStore.getRefreshToken()).toBeNull();
    expect(window.localStorage.getItem(REFRESH_KEY)).toBeNull();
  });

  it('tolerates localStorage failures (private mode)', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('QuotaExceeded');
    });
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });

    expect(() => tokenStore.setTokens('a', 'r')).not.toThrow();
    expect(tokenStore.getAccessToken()).toBe('a');
    expect(tokenStore.getRefreshToken()).toBeNull();
    expect(() => tokenStore.clear()).not.toThrow();
    expect(tokenStore.getAccessToken()).toBeNull();
  });
});
