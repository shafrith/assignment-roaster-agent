import { Alert, AlertDescription, AlertIcon, VStack } from '@chakra-ui/react';
import { FiRefreshCw } from 'react-icons/fi';
import { useRetryRoast } from '../../hooks/useRoast';
import { getErrorMessage } from '../../services/api';
import { PrimaryButton } from '../ui/PrimaryButton';

export interface RetryButtonProps {
  shareSlug: string;
}

export function RetryButton({ shareSlug }: RetryButtonProps) {
  const mutation = useRetryRoast();
  return (
    <VStack spacing={3} w="full">
      <PrimaryButton
        leftIcon={<FiRefreshCw aria-hidden="true" />}
        onClick={() => mutation.mutate(shareSlug)}
        isLoading={mutation.isPending}
        loadingText="Retrying..."
      >
        Retry pannu
      </PrimaryButton>
      {mutation.isError && (
        <Alert status="error" colorScheme="brand" borderRadius="md">
          <AlertIcon />
          <AlertDescription>{getErrorMessage(mutation.error)}</AlertDescription>
        </Alert>
      )}
    </VStack>
  );
}

export default RetryButton;
