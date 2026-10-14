import type { Severity, SubmissionStatus } from '../types/api';

export const SEVERITY_ORDER: Severity[] = ['critical', 'high', 'medium', 'low'];

/** Severity badges use only the two UI colors: blue for serious issues, gray for minor ones. */
export const SEVERITY_BADGE: Record<Severity, { colorScheme: 'brand' | 'gray'; variant: 'solid' | 'subtle' }> = {
  critical: { colorScheme: 'brand', variant: 'solid' },
  high: { colorScheme: 'brand', variant: 'subtle' },
  medium: { colorScheme: 'gray', variant: 'solid' },
  low: { colorScheme: 'gray', variant: 'subtle' },
};

export const STATUS_LABEL: Record<SubmissionStatus, string> = {
  pending: 'Pending',
  analyzing: 'Analyzing',
  roasting: 'Roasting',
  completed: 'Completed',
  failed: 'Failed',
};

export const TERMINAL_STATUSES: ReadonlySet<SubmissionStatus> = new Set<SubmissionStatus>(['completed', 'failed']);

export function isTerminalStatus(status: SubmissionStatus): boolean {
  return TERMINAL_STATUSES.has(status);
}

export function formatScore(score: number): string {
  return Number.isInteger(score) ? String(score) : score.toFixed(1);
}

export function formatCategory(category: string): string {
  return category
    .split('_')
    .map((word) => (word === 'genai' ? 'GenAI' : word.charAt(0).toUpperCase() + word.slice(1)))
    .join(' ');
}

const RELATIVE_UNITS: { unit: Intl.RelativeTimeFormatUnit; seconds: number }[] = [
  { unit: 'year', seconds: 31_536_000 },
  { unit: 'month', seconds: 2_592_000 },
  { unit: 'week', seconds: 604_800 },
  { unit: 'day', seconds: 86_400 },
  { unit: 'hour', seconds: 3_600 },
  { unit: 'minute', seconds: 60 },
];

/** "3 hours ago", "yesterday", "just now". */
export function formatRelativeTime(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const diffSeconds = Math.round((date.getTime() - now.getTime()) / 1000);
  const abs = Math.abs(diffSeconds);
  if (abs < 45) return 'just now';
  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  for (const { unit, seconds } of RELATIVE_UNITS) {
    if (abs >= seconds) {
      return rtf.format(Math.round(diffSeconds / seconds), unit);
    }
  }
  return rtf.format(Math.round(diffSeconds / 60), 'minute');
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString();
}

export function buildPublicRoastUrl(shareSlug: string, origin: string = window.location.origin): string {
  return `${origin}/r/${shareSlug}`;
}

export function buildShareText(score: number): string {
  return `En assignment-ku ${formatScore(score)}/10 kuduthanga 😭🔥`;
}

export function buildWhatsAppShareUrl(text: string, url: string): string {
  return `https://wa.me/?text=${encodeURIComponent(`${text} ${url}`)}`;
}

export function buildXShareUrl(text: string, url: string): string {
  return `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}&url=${encodeURIComponent(url)}`;
}
