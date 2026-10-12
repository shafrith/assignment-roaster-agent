/**
 * Client-side GitHub repo URL validation — mirrors backend `services/github_url.py`.
 * For instant feedback only; the backend is the source of truth.
 */
export const GITHUB_REPO_URL_REGEX =
  /^https?:\/\/(www\.)?github\.com\/([A-Za-z0-9-]{1,39})\/([A-Za-z0-9._-]{1,100})(\.git)?(\/.*)?\/?$/;

export const INVALID_GITHUB_URL_MESSAGE = 'Dei, idhu GitHub repo URL-ae illa da! 😅';

export interface ParsedRepoUrl {
  owner: string;
  repo: string;
  normalizedUrl: string;
}

export function isValidGithubRepoUrl(value: string): boolean {
  return GITHUB_REPO_URL_REGEX.test(value.trim());
}

export function parseGithubRepoUrl(value: string): ParsedRepoUrl | null {
  const match = GITHUB_REPO_URL_REGEX.exec(value.trim());
  if (!match) return null;
  const owner = match[2];
  const repo = match[3].replace(/\.git$/, '');
  return { owner, repo, normalizedUrl: `https://github.com/${owner}/${repo}` };
}

/** Returns an error message, or null when the URL looks valid (empty input → null). */
export function validateGithubRepoUrl(value: string): string | null {
  if (value.trim() === '') return null;
  return isValidGithubRepoUrl(value) ? null : INVALID_GITHUB_URL_MESSAGE;
}
