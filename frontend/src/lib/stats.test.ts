import { describe, expect, it } from 'vitest';
import { makeListItem } from '../test/fixtures';
import { computeStats } from './stats';

describe('computeStats', () => {
  it('returns nulls when nothing is scored', () => {
    expect(computeStats([], 0)).toEqual({ total: 0, average: null, best: null, worst: null, scoredCount: 0 });
    expect(computeStats([makeListItem({ score: null, status: 'pending' })], 4)).toEqual({
      total: 4,
      average: null,
      best: null,
      worst: null,
      scoredCount: 0,
    });
  });

  it('computes avg (1 decimal), best, worst over scored items only and passes total through', () => {
    const items = [
      makeListItem({ id: 1, score: 3 }),
      makeListItem({ id: 2, score: 8.5 }),
      makeListItem({ id: 3, score: null, status: 'failed' }),
      makeListItem({ id: 4, score: 5 }),
    ];
    expect(computeStats(items, 37)).toEqual({ total: 37, average: 5.5, best: 8.5, worst: 3, scoredCount: 3 });
  });

  it('rounds the average to one decimal place', () => {
    const items = [makeListItem({ score: 1 }), makeListItem({ score: 2 }), makeListItem({ score: 2 })];
    expect(computeStats(items, 3).average).toBe(1.7);
  });
});
