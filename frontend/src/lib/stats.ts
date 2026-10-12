import type { SubmissionListItem } from '../types/api';

export interface SubmissionStats {
  total: number;
  average: number | null;
  best: number | null;
  worst: number | null;
  scoredCount: number;
}

/** Avg/best/worst over the given items (scored only); `total` passed through from the paginated response. */
export function computeStats(items: SubmissionListItem[], total: number): SubmissionStats {
  const scores = items.map((item) => item.score).filter((score): score is number => score !== null);
  if (scores.length === 0) {
    return { total, average: null, best: null, worst: null, scoredCount: 0 };
  }
  const sum = scores.reduce((acc, score) => acc + score, 0);
  return {
    total,
    average: Math.round((sum / scores.length) * 10) / 10,
    best: Math.max(...scores),
    worst: Math.min(...scores),
    scoredCount: scores.length,
  };
}
