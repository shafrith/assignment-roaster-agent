import { Heading, Text, VStack } from '@chakra-ui/react';
import type { ReactNode } from 'react';
import { GlassCard } from './GlassCard';

export interface ErrorStateProps {
  title?: string;
  message: string;
  emoji?: string;
  /** Action area (retry button, links). */
  children?: ReactNode;
}

/** Centered friendly error card. */
export function ErrorState({ title = 'Aiyo! Edho problem 😵', message, emoji = '🫠', children }: ErrorStateProps) {
  return (
    <GlassCard disableHover maxW="xl" mx="auto" textAlign="center" role="alert">
      <VStack spacing={4}>
        <Text fontSize="5xl" aria-hidden="true">
          {emoji}
        </Text>
        <Heading size="md">{title}</Heading>
        <Text color="text.muted">{message}</Text>
        {children}
      </VStack>
    </GlassCard>
  );
}

export default ErrorState;
