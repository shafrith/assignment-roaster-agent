import { Alert, AlertDescription, AlertIcon, Center, Heading, Text, VStack } from '@chakra-ui/react';
import { Navigate, useSearchParams } from 'react-router-dom';
import { GitHubLoginButton } from '../components/auth/GitHubLoginButton';
import { FullPageSpinner } from '../components/ui/FullPageSpinner';
import { GlassCard } from '../components/ui/GlassCard';
import { PageWrapper } from '../components/ui/PageWrapper';
import { useAuth } from '../hooks/useAuth';

const ERROR_MESSAGES: Record<string, string> = {
  oauth_denied: 'GitHub permission kudukkala pola machan. Roast venumna allow pannu 😅',
  invalid_state: 'Login session expire aayiduchu. Innoru vaati try pannu 🔁',
  github_error: 'GitHub konjam mood-out-la irukku. Konjam apram try pannu 🐙',
  inactive: 'Un account disable pannirukku machan. Admin-a contact pannu 🚫',
};

const FALLBACK_ERROR = 'Login-la edho problem machan. Thirumba try pannu 🙏';

export default function LoginPage() {
  const { isAuthenticated, isLoading } = useAuth();
  const [params] = useSearchParams();
  const errorCode = params.get('error');
  const errorMessage = errorCode ? (ERROR_MESSAGES[errorCode] ?? FALLBACK_ERROR) : null;

  if (isLoading) return <FullPageSpinner />;
  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  return (
    <PageWrapper>
      <Center minH={{ base: '60vh', md: '65vh' }}>
        <GlassCard disableHover w="full" maxW="md" p={{ base: 6, md: 10 }}>
          <VStack spacing={6} textAlign="center">
            <Text fontSize="5xl" lineHeight={1} aria-hidden>
              🔥
            </Text>
            <Heading size="xl" textStyle="fireGradient">
              Login pannu machan, roast ready-a irukku 🔥
            </Heading>
            <Text color="text.muted">
              Sign in with GitHub to roast your GenAI assignment repos. We only read your public profile — no repo access.
            </Text>
            {errorMessage && (
              <Alert status="error" borderRadius="lg" variant="subtle" textAlign="left">
                <AlertIcon />
                <AlertDescription>{errorMessage}</AlertDescription>
              </Alert>
            )}
            <GitHubLoginButton w="full" />
          </VStack>
        </GlassCard>
      </Center>
    </PageWrapper>
  );
}
