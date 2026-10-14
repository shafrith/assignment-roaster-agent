import {
  Alert,
  AlertDescription,
  AlertIcon,
  FormControl,
  FormErrorMessage,
  FormHelperText,
  FormLabel,
  Input,
  InputGroup,
  InputLeftElement,
  Stack,
  VStack,
  chakra,
} from '@chakra-ui/react';
import { useState, type FormEvent } from 'react';
import { FiGithub } from 'react-icons/fi';
import { useCreateRoast } from '../../hooks/useRoast';
import { isValidGithubRepoUrl, validateGithubRepoUrl } from '../../lib/githubUrl';
import { getErrorMessage } from '../../services/api';
import { PrimaryButton } from '../ui/PrimaryButton';

export const ROAST_FORM_HINT = 'Public repos only · No login needed';

/** Paste a public GitHub repo URL and start a roast (no login); navigates to /r/:shareSlug. */
export function RoastForm() {
  const [repoUrl, setRepoUrl] = useState('');
  const [touched, setTouched] = useState(false);
  const createMutation = useCreateRoast();

  const validationError = touched ? validateGithubRepoUrl(repoUrl) : null;
  const isEmpty = repoUrl.trim() === '';

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setTouched(true);
    if (!isValidGithubRepoUrl(repoUrl)) return;
    createMutation.mutate({ repoUrl: repoUrl.trim() });
  };

  return (
    <chakra.form onSubmit={handleSubmit} noValidate aria-label="New roast form" w="full">
      <VStack spacing={4} align="stretch">
        <Stack direction={{ base: 'column', sm: 'row' }} spacing={3} align={{ base: 'stretch', sm: 'flex-start' }}>
          <FormControl isInvalid={validationError !== null} isDisabled={createMutation.isPending} flex="1">
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
                bg="bg.surface"
                fontFamily="mono"
                fontSize="md"
                focusBorderColor="brand.500"
                errorBorderColor="brand.700"
              />
            </InputGroup>
            {validationError ? (
              <FormErrorMessage>{validationError}</FormErrorMessage>
            ) : (
              <FormHelperText>{ROAST_FORM_HINT}</FormHelperText>
            )}
          </FormControl>
          <PrimaryButton
            type="submit"
            isLoading={createMutation.isPending}
            loadingText="Roast start aagudhu..."
            isDisabled={isEmpty}
          >
            Roast Me
          </PrimaryButton>
        </Stack>

        {createMutation.isError && (
          <Alert status="error" colorScheme="brand" borderRadius="lg" data-testid="create-error">
            <AlertIcon />
            <AlertDescription>{getErrorMessage(createMutation.error)}</AlertDescription>
          </Alert>
        )}
      </VStack>
    </chakra.form>
  );
}

export default RoastForm;
