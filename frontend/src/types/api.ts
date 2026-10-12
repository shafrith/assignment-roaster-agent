/**
 * SHARED API CONTRACT — copied verbatim from PRPs/assignment-roaster-prp.md.
 * JSON is camelCase on the wire. Backend schema names win on conflict.
 */

export type SubmissionStatus = "pending" | "analyzing" | "roasting" | "completed" | "failed";
export type Severity = "low" | "medium" | "high" | "critical";
export type IssueCategory = "structure" | "documentation" | "dependencies" | "testing"
  | "security" | "code_quality" | "git_hygiene" | "genai_practices";

export interface UserResponse {
  id: number; githubUsername: string; displayName: string | null;
  avatarUrl: string | null; defaultRoastPublic: boolean; createdAt: string;
  /** COR-8: optional until the backend exposes ROAST_DAILY_LIMIT / today's usage on /auth/me. */
  dailyLimit?: number | null; roastsUsedToday?: number | null;
}
export interface TokenResponse { accessToken: string; refreshToken: string; tokenType: "bearer"; }

export interface RoastIssue { category: IssueCategory; severity: Severity; file: string | null; message: string; }

export interface RoastResponse {
  score: number; verdictTitle: string; roastText: string;
  strengths: string[]; issues: RoastIssue[]; fixTips: string[]; createdAt: string;
}

export interface AnalysisSummary {
  languages: Record<string, number>; fileCount: number; hasReadme: boolean;
  hasTests: boolean; hasDependencyFile: boolean; hasEnvFileCommitted: boolean;
  secretsFoundCount: number; commitCount: number;
}

/** Public share pages never expose secret counts or `.env` status (SEC-8). */
export type PublicAnalysisSummary = Omit<AnalysisSummary, 'hasEnvFileCommitted' | 'secretsFoundCount'>;

/** Analysis shape accepted by shared result components: owner view has the secret fields, public view doesn't. */
export type AnalysisView = PublicAnalysisSummary & Partial<Pick<AnalysisSummary, 'hasEnvFileCommitted' | 'secretsFoundCount'>>;

export interface SubmissionResponse {
  id: number; repoUrl: string; repoOwner: string; repoName: string;
  status: SubmissionStatus; errorMessage: string | null; isPublic: boolean;
  shareSlug: string; createdAt: string; completedAt: string | null;
  analysis: AnalysisSummary | null; roast: RoastResponse | null;
}

export interface SubmissionListItem {
  id: number; repoOwner: string; repoName: string; status: SubmissionStatus;
  score: number | null; verdictTitle: string | null; isPublic: boolean; createdAt: string;
}
export interface Paginated<T> { items: T[]; total: number; page: number; pageSize: number; }

export interface PublicRoastResponse {
  repoUrl: string; repoOwner: string; repoName: string;
  author: { githubUsername: string; avatarUrl: string | null };
  roast: RoastResponse; analysis: PublicAnalysisSummary; createdAt: string;
}

export interface ErrorResponse { detail: string; }  // detail may be a Tanglish user-facing message
