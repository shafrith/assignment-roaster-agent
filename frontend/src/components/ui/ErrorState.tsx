import { Heading, Icon, Text, VStack } from '@chakra-ui/react';
import { FiAlertCircle } from 'react-icons/fi';
import type { ReactNode } from 'react';
import { Panel } from './Panel';

export interface ErrorStateProps {
  title?: string;
  message: string;
  /** Action area (retry button, links). */
  children?: ReactNode;
}

/** Centered friendly error card. */
export function ErrorState({ title = 'Aiyo! Edho problem', message, children }: ErrorStateProps) {
  return (
    <Panel maxW="xl" mx="auto" textAlign="center" role="alert">
      <VStack spacing={4}>
        <Icon as={FiAlertCircle} boxSize={10} color="brand.600" aria-hidden="true" />
        <Heading size="md">{title}</Heading>
        <Text color="text.muted">{message}</Text>
        {children}
      </VStack>
    </Panel>
  );
}

export default ErrorState;
