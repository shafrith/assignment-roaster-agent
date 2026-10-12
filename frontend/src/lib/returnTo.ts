/** Post-login redirect target, set by ProtectedRoute and consumed by AuthCallbackPage. */
const RETURN_TO_KEY = 'ar_return_to';

function isSafePath(path: string): boolean {
  return path.startsWith('/') && !path.startsWith('//') && !path.startsWith('/login') && !path.startsWith('/auth/');
}

export function saveReturnTo(path: string): void {
  if (!isSafePath(path)) return;
  try {
    window.sessionStorage.setItem(RETURN_TO_KEY, path);
  } catch {
    // Storage unavailable — fall back to the default redirect.
  }
}

/** Read and clear the stored target. */
export function consumeReturnTo(fallback = '/dashboard'): string {
  try {
    const value = window.sessionStorage.getItem(RETURN_TO_KEY);
    window.sessionStorage.removeItem(RETURN_TO_KEY);
    return value && isSafePath(value) ? value : fallback;
  } catch {
    return fallback;
  }
}
