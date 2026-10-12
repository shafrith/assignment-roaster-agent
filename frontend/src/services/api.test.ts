import { AxiosError } from 'axios';
import { describe, expect, it } from 'vitest';
import { makeAxiosError } from '../test/fixtures';
import { api, getErrorMessage } from './api';

describe('services/api', () => {
  it('never sends an Authorization header (no login)', () => {
    expect(api.defaults.headers.common.Authorization).toBeUndefined();
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
});
