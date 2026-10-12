/**
 * SHARED API CONTRACT — copied verbatim from PRPs/assignment-roaster-prp.md.
 * JSON is camelCase on the wire. Backend schema names win on conflict.
 */

export type SubmissionStatus = "pending" | "analyzing" | "roasting" | "completed" | "failed";
export type Severity = "low" | "medium" | "high" | "critical";
export type IssueCategory = "structure" | "documentation" | "dependencies" | "testing"
  | "security" | "code_quality" | "git_hygiene" | "genai_practices";

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

export interface PublicAuthor { githubUsername: string; avatarUrl: string | null; }

/** GET /roasts/{shareSlug}: a roast in any status. `analysis`/`roast` are set only once completed. */
export interface RoastStatusResponse {
  shareSlug: string; repoUrl: string; repoOwner: string; repoName: string;
  status: SubmissionStatus; errorMessage: string | null; errorRetryable: boolean;
  /** Null for anonymous (no-login) roasts. */
  author: PublicAuthor | null;
  analysis: PublicAnalysisSummary | null; roast: RoastResponse | null;
  createdAt: string; completedAt: string | null;
}

export interface ErrorResponse { detail: string; }  // detail may be a Tanglish user-facing message
