import {
  Alert,
  AlertDescription,
  AlertIcon,
  FormControl,
  FormErrorMessage,
  FormHelperText,
  FormLabel,
  Heading,
  Input,
  InputGroup,
  InputLeftElement,
  Text,
  VStack,
} from '@chakra-ui/react';
import { useState, type FormEvent } from 'react';
import { FiGithub } from 'react-icons/fi';
import { GlassCard } from '../components/ui/GlassCard';
import { GradientButton } from '../components/ui/GradientButton';
import { PageWrapper } from '../components/ui/PageWrapper';
import { useAuth } from '../hooks/useAuth';
import { quotaHint } from '../lib/quota';
import { useCreateSubmission } from '../hooks/useSubmissions';
import { isValidGithubRepoUrl, validateGithubRepoUrl } from '../lib/githubUrl';
import { getErrorMessage } from '../services/api';

export default function NewRoastPage() {
  const [repoUrl, setRepoUrl] = useState('');
  const [touched, setTouched] = useState(false);
  const createMutation = useCreateSubmission();
  const { user } = useAuth();

  const validationError = touched ? validateGithubRepoUrl(repoUrl) : null;
  const isEmpty = repoUrl.trim() === '';

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setTouched(true);
    if (!isValidGithubRepoUrl(repoUrl)) return;
    createMutation.mutate({ repoUrl: repoUrl.trim() });
  };

  return (
    <PageWrapper>
      <VStack minH={{ base: 'auto', md: '60vh' }} justify="center">
        <GlassCard disableHover w="full" maxW="2xl" p={{ base: 6, md: 10 }}>
          <form onSubmit={handleSubmit} noValidate aria-label="New roast form">
            <VStack spacing={6}>
              <VStack spacing={2} textAlign="center">
                <Heading as="h1" size={{ base: 'lg', md: 'xl' }}>
                  Un repo-va kudu, roast pannrom 🔥
                </Heading>
                <Text color="text.muted">GitHub repo URL paste pannu. Brutal honesty guaranteed.</Text>
              </VStack>
  
              <FormControl isInvalid={validationError !== null} isDisabled={createMutation.isPending}>
                <FormLabel htmlFor="repo-url" srOnly>
                  GitHub repo URL
                </FormLabel>
                <InputGroup size="lg">
                  <InputLeftElement pointerEvents="none" color="text.muted">
                    <FiGithub aria-hidden="true" />
                  </InputLeftElement>
                  <Input
                    id="repo-url"
                    name="repoUrl"
                    type="url"
                    inputMode="url"
                    autoComplete="off"
                    spellCheck={false}
                    placeholder="https://github.com/username/repo"
                    value={repoUrl}
                    onChange={(event) => {
                      setRepoUrl(event.target.value);
                      if (createMutation.isError) createMutation.reset();
                    }}
                    onBlur={() => setTouched(true)}
                    borderRadius="full"
                    bg="bg.glass"
                    fontFamily="mono"
                    fontSize="md"
                    focusBorderColor="fire.400"
                  />
                </InputGroup>
                {validationError ? (
                  <FormErrorMessage>{validationError}</FormErrorMessage>
                ) : (
                  <FormHelperText textAlign="center">{quotaHint(user)}</FormHelperText>
                )}
              </FormControl>
  
              {createMutation.isError && (
                <Alert status="error" borderRadius="lg" data-testid="create-error">
                  <AlertIcon />
                  <AlertDescription>{getErrorMessage(createMutation.error)}</AlertDescription>
                </Alert>
              )}
  
              <GradientButton
                type="submit"
                w={{ base: 'full', sm: 'auto' }}
                isLoading={createMutation.isPending}
                loadingText="Roast start aagudhu..."
                isDisabled={isEmpty}
              >
                Roast Me 🔥
              </GradientButton>
            </VStack>
          </form>
        </GlassCard>
      </VStack>
    </PageWrapper>
  );
}
