import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { FullPageSpinner } from '../components/ui/FullPageSpinner';
import { PageWrapper } from '../components/ui/PageWrapper';
import { useAuth } from '../hooks/useAuth';
import { consumeReturnTo } from '../lib/returnTo';
import { isInactiveError } from '../services/api';

interface CallbackTokens {
  access: string;
  refresh: string;
}

function parseTokens(hash: string): CallbackTokens | null {
  // Fragment is `#access=<jwt>&refresh=<token>` (URL-encoded); URLSearchParams decodes it.
  const params = new URLSearchParams(hash.startsWith('#') ? hash.slice(1) : hash);
  const access = params.get('access');
  const refresh = params.get('refresh');
  if (!access || !refresh) return null;
  return { access, refresh };
}

/** Receives tokens in the URL fragment from the backend OAuth callback. */
export default function AuthCallbackPage() {
  const { completeLogin } = useAuth();
  const navigate = useNavigate();
  const handled = useRef<boolean>(false);

  useEffect(() => {
    // StrictMode runs effects twice; the hash is stripped on the first run.
    if (handled.current) return;
    handled.current = true;

    const tokens = parseTokens(window.location.hash);
    // Strip tokens from the address bar/history immediately.
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);

    if (!tokens) {
      navigate('/login?error=invalid_state', { replace: true });
      return;
    }

    completeLogin(tokens.access, tokens.refresh)
      .then(() => navigate(consumeReturnTo('/dashboard'), { replace: true }))
      .catch((err: unknown) =>
        navigate(`/login?error=${isInactiveError(err) ? 'inactive' : 'invalid_state'}`, { replace: true }),
      );
  }, [completeLogin, navigate]);

  return (
    <PageWrapper>
      <FullPageSpinner label="GitHub-la irundhu varra... konjam wait pannu machan 🔥" />
    </PageWrapper>
  );
}
