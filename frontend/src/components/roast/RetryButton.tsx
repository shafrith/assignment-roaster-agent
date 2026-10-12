import { Alert, AlertDescription, AlertIcon, VStack } from '@chakra-ui/react';
import { FiRefreshCw } from 'react-icons/fi';
import { useRetry } from '../../hooks/useSubmissions';
import { getErrorMessage } from '../../services/api';
import { GradientButton } from '../ui/GradientButton';

export interface RetryButtonProps {
  submissionId: number;
}

export function RetryButton({ submissionId }: RetryButtonProps) {
  const mutation = useRetry();
  return (
    <VStack spacing={3} w="full">
      <GradientButton
        leftIcon={<FiRefreshCw aria-hidden="true" />}
        onClick={() => mutation.mutate(submissionId)}
        isLoading={mutation.isPending}
        loadingText="Retrying..."
      >
        Retry pannu 🔁
      </GradientButton>
      {mutation.isError && (
        <Alert status="error" borderRadius="md">
          <AlertIcon />
          <AlertDescription>{getErrorMessage(mutation.error)}</AlertDescription>
        </Alert>
      )}
    </VStack>
  );
}

export default RetryButton;
