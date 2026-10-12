import { AxiosError, AxiosHeaders, type InternalAxiosRequestConfig } from 'axios';
import type {
  AnalysisSummary,
  Paginated,
  PublicRoastResponse,
  RoastResponse,
  SubmissionListItem,
  SubmissionResponse,
} from '../types/api';

export const analysisFixture: AnalysisSummary = {
  languages: { Python: 8000, Jupyter: 2000 },
  fileCount: 42,
  hasReadme: false,
  hasTests: false,
  hasDependencyFile: true,
  hasEnvFileCommitted: true,
  secretsFoundCount: 2,
  commitCount: 3,
};

export const roastFixture: RoastResponse = {
  score: 3.5,
  verdictTitle: 'Copy-paste Champion 🏆',
  roastText: '## Machan...\n\nUn code paatha **azhugai** varudhu.',
  strengths: ['Code runs at least once', 'Nice repo name'],
  issues: [
    { category: 'security', severity: 'critical', file: '.env', message: 'API key committed' },
    { category: 'testing', severity: 'high', file: null, message: 'No tests at all' },
    { category: 'documentation', severity: 'low', file: 'README.md', message: 'README is empty' },
    { category: 'genai_practices', severity: 'critical', file: 'app.py', message: 'Prompt hardcoded' },
  ],
  fixTips: ['Rotate your keys', 'Add pytest'],
  createdAt: '2026-10-01T10:00:00Z',
};

export function makeSubmission(overrides: Partial<SubmissionResponse> = {}): SubmissionResponse {
  return {
    id: 7,
    repoUrl: 'https://github.com/machan/genai-hw',
    repoOwner: 'machan',
    repoName: 'genai-hw',
    status: 'completed',
    errorMessage: null,
    isPublic: false,
    shareSlug: 'abc123',
    createdAt: '2026-10-01T09:59:00Z',
    completedAt: '2026-10-01T10:00:00Z',
    analysis: analysisFixture,
    roast: roastFixture,
    ...overrides,
  };
}

export function makeListItem(overrides: Partial<SubmissionListItem> = {}): SubmissionListItem {
  return {
    id: 1,
    repoOwner: 'machan',
    repoName: 'repo-1',
    status: 'completed',
    score: 5,
    verdictTitle: 'Average Andhra Meals',
    isPublic: false,
    createdAt: new Date().toISOString(),
    ...overrides,
  };
}

export function makePage(
  items: SubmissionListItem[],
  total: number = items.length,
  page = 1,
  pageSize = 10,
): Paginated<SubmissionListItem> {
  return { items, total, page, pageSize };
}

export const publicRoastFixture: PublicRoastResponse = {
  repoUrl: 'https://github.com/machan/genai-hw',
  repoOwner: 'machan',
  repoName: 'genai-hw',
  author: { githubUsername: 'roastee', avatarUrl: null },
  roast: roastFixture,
  analysis: analysisFixture,
  createdAt: '2026-10-01T10:00:00Z',
};

/** An AxiosError carrying an HTTP response (as axios throws for non-2xx statuses). */
export function makeAxiosError(status: number, data: unknown, config?: InternalAxiosRequestConfig): AxiosError {
  const cfg: InternalAxiosRequestConfig = config ?? { headers: new AxiosHeaders() };
  return new AxiosError(`Request failed with status code ${status}`, 'ERR_BAD_REQUEST', cfg, null, {
    status,
    statusText: String(status),
    data,
    headers: {},
    config: cfg,
  });
}
