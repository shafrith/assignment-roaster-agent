import { describe, expect, it } from 'vitest';
import {
  INVALID_GITHUB_URL_MESSAGE,
  isValidGithubRepoUrl,
  parseGithubRepoUrl,
  validateGithubRepoUrl,
} from './githubUrl';

describe('isValidGithubRepoUrl', () => {
  it.each([
    'https://github.com/owner/repo',
    'http://github.com/owner/repo',
    'https://www.github.com/owner/repo',
    'https://github.com/owner/repo/',
    'https://github.com/owner/repo.git',
    'https://github.com/owner/repo/tree/main/src',
    'https://github.com/my-org/repo_name.v2',
    '  https://github.com/owner/repo  ',
  ])('accepts %s', (url) => {
    expect(isValidGithubRepoUrl(url)).toBe(true);
  });

  it.each([
    '',
    'github.com/owner/repo',
    'https://github.com/owner',
    'https://github.com/',
    'https://gitlab.com/owner/repo',
    'https://github.com.evil.com/owner/repo',
    'https://gist.github.com/owner/repo',
    'ftp://github.com/owner/repo',
    'https://github.com/own_er/repo',
    `https://github.com/${'a'.repeat(40)}/repo`,
    'javascript:alert(1)',
    'not a url',
  ])('rejects %s', (url) => {
    expect(isValidGithubRepoUrl(url)).toBe(false);
  });
});

describe('parseGithubRepoUrl', () => {
  it('extracts owner/repo and normalizes the URL', () => {
    expect(parseGithubRepoUrl('http://www.github.com/Owner/Repo.git')).toEqual({
      owner: 'Owner',
      repo: 'Repo',
      normalizedUrl: 'https://github.com/Owner/Repo',
    });
  });

  it('ignores trailing path segments', () => {
    expect(parseGithubRepoUrl('https://github.com/a/b/blob/main/x.py')?.normalizedUrl).toBe('https://github.com/a/b');
  });

  it('returns null for invalid input', () => {
    expect(parseGithubRepoUrl('https://example.com/a/b')).toBeNull();
  });
});

describe('validateGithubRepoUrl', () => {
  it('returns null for empty / whitespace input', () => {
    expect(validateGithubRepoUrl('')).toBeNull();
    expect(validateGithubRepoUrl('   ')).toBeNull();
  });

  it('returns null for a valid URL', () => {
    expect(validateGithubRepoUrl('https://github.com/a/b')).toBeNull();
  });

  it('returns the Tanglish message for an invalid URL', () => {
    expect(validateGithubRepoUrl('https://gitlab.com/a/b')).toBe(INVALID_GITHUB_URL_MESSAGE);
    expect(INVALID_GITHUB_URL_MESSAGE).toBe('Dei, idhu GitHub repo URL-ae illa da! 😅');
  });
});
