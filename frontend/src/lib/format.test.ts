import { describe, expect, it } from 'vitest';
import {
  buildPublicRoastUrl,
  buildShareText,
  buildWhatsAppShareUrl,
  buildXShareUrl,
  formatCategory,
  formatDateTime,
  formatRelativeTime,
  formatScore,
  isTerminalStatus,
  SEVERITY_BADGE,
  SEVERITY_ORDER,
} from './format';

describe('SEVERITY_BADGE', () => {
  it('uses only the two UI colors (blue for serious, gray for minor)', () => {
    for (const severity of SEVERITY_ORDER) {
      expect(['brand', 'gray']).toContain(SEVERITY_BADGE[severity].colorScheme);
    }
    expect(SEVERITY_BADGE.critical).toEqual({ colorScheme: 'brand', variant: 'solid' });
    expect(SEVERITY_BADGE.low.colorScheme).toBe('gray');
  });
});

describe('formatScore', () => {
  it('keeps integers bare and rounds decimals to one place', () => {
    expect(formatScore(7)).toBe('7');
    expect(formatScore(3.5)).toBe('3.5');
    expect(formatScore(6.25)).toBe('6.3');
  });
});

describe('formatCategory', () => {
  it('title-cases snake_case and special-cases genai', () => {
    expect(formatCategory('code_quality')).toBe('Code Quality');
    expect(formatCategory('genai_practices')).toBe('GenAI Practices');
    expect(formatCategory('security')).toBe('Security');
  });
});

describe('isTerminalStatus', () => {
  it('is true only for completed/failed', () => {
    expect(isTerminalStatus('completed')).toBe(true);
    expect(isTerminalStatus('failed')).toBe(true);
    expect(isTerminalStatus('pending')).toBe(false);
    expect(isTerminalStatus('analyzing')).toBe(false);
    expect(isTerminalStatus('roasting')).toBe(false);
  });
});

describe('formatRelativeTime', () => {
  const now = new Date('2026-10-10T12:00:00Z');

  it('returns "just now" under 45 seconds', () => {
    expect(formatRelativeTime('2026-10-10T11:59:30Z', now)).toBe('just now');
  });

  it('formats minutes, hours and days', () => {
    expect(formatRelativeTime('2026-10-10T11:55:00Z', now)).toBe('5 minutes ago');
    expect(formatRelativeTime('2026-10-10T09:00:00Z', now)).toBe('3 hours ago');
    expect(formatRelativeTime('2026-10-09T12:00:00Z', now)).toBe('yesterday');
  });

  it('falls back to minutes between 45s and 60s', () => {
    expect(formatRelativeTime('2026-10-10T11:59:10Z', now)).toBe('1 minute ago');
  });

  it('returns empty string for invalid dates', () => {
    expect(formatRelativeTime('nope', now)).toBe('');
    expect(formatDateTime('nope')).toBe('');
  });

  it('formatDateTime renders something for valid dates', () => {
    expect(formatDateTime('2026-10-10T12:00:00Z')).not.toBe('');
  });
});

describe('share helpers', () => {
  it('builds the public URL from the origin', () => {
    expect(buildPublicRoastUrl('slug1', 'https://roast.dev')).toBe('https://roast.dev/r/slug1');
    expect(buildPublicRoastUrl('slug1')).toBe(`${window.location.origin}/r/slug1`);
  });

  it('builds the share text with the formatted score', () => {
    expect(buildShareText(3.5)).toBe('En assignment-ku 3.5/10 kuduthanga 😭🔥');
  });

  it('encodes WhatsApp and X share URLs', () => {
    const wa = buildWhatsAppShareUrl('hi & bye', 'https://x.y/r/1');
    expect(wa).toBe(`https://wa.me/?text=${encodeURIComponent('hi & bye https://x.y/r/1')}`);
    const x = new URL(buildXShareUrl('hi & bye', 'https://x.y/r/1'));
    expect(x.origin).toBe('https://twitter.com');
    expect(x.searchParams.get('text')).toBe('hi & bye');
    expect(x.searchParams.get('url')).toBe('https://x.y/r/1');
  });
});
