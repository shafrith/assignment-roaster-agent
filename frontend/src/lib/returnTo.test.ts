import { describe, expect, it, vi } from 'vitest';
import { consumeReturnTo, saveReturnTo } from './returnTo';

const KEY = 'ar_return_to';

describe('returnTo', () => {
  it('round-trips a safe relative path and clears it after reading', () => {
    saveReturnTo('/roasts/12?tab=x#y');
    expect(consumeReturnTo()).toBe('/roasts/12?tab=x#y');
    expect(window.sessionStorage.getItem(KEY)).toBeNull();
    expect(consumeReturnTo()).toBe('/dashboard');
  });

  it('uses the provided fallback when nothing is stored', () => {
    expect(consumeReturnTo('/home')).toBe('/home');
  });

  it.each(['//evil.com', '//evil.com/path', 'https://evil.com', 'evil.com', '/login', '/login?error=x', '/auth/callback', ''])(
    'refuses to save unsafe path %j',
    (path) => {
      saveReturnTo(path);
      expect(window.sessionStorage.getItem(KEY)).toBeNull();
    },
  );

  it('ignores a tampered stored value', () => {
    window.sessionStorage.setItem(KEY, '//evil.com');
    expect(consumeReturnTo()).toBe('/dashboard');
    window.sessionStorage.setItem(KEY, 'https://evil.com');
    expect(consumeReturnTo()).toBe('/dashboard');
  });

  it('tolerates storage failures', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('denied');
    });
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('denied');
    });
    expect(() => saveReturnTo('/dashboard')).not.toThrow();
    expect(consumeReturnTo('/fallback')).toBe('/fallback');
  });
});
