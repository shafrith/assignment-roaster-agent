import { Box, Circle, HStack, Heading, Spinner, Text, VStack } from '@chakra-ui/react';
import { AnimatePresence } from 'framer-motion';
import { Fragment, useEffect, useState } from 'react';
import { FiCheck } from 'react-icons/fi';
import { MotionBox } from '../../lib/motion';
import type { SubmissionStatus } from '../../types/api';
import { Panel } from '../ui/Panel';
import { LOADING_LINES, LOADING_LINE_INTERVAL_MS } from './loadingLines';

const STEPS = ['Analyzing', 'Roasting', 'Done'] as const;

function activeStepIndex(status: SubmissionStatus): number {
  switch (status) {
    case 'pending':
    case 'analyzing':
      return 0;
    case 'roasting':
      return 1;
    default:
      return 2;
  }
}

export interface RoastStatusLoaderProps {
  status: SubmissionStatus;
  /** e.g. "owner/repo" */
  repoLabel?: string;
  /** Rotation interval for loading lines (ms). */
  intervalMs?: number;
  lines?: readonly string[];
}

/** In-progress view: spinner, step indicator, rotating Tanglish lines. */
export function RoastStatusLoader({
  status,
  repoLabel,
  intervalMs = LOADING_LINE_INTERVAL_MS,
  lines = LOADING_LINES,
}: RoastStatusLoaderProps) {
  const [lineIndex, setLineIndex] = useState(0);
  const current = activeStepIndex(status);

  useEffect(() => {
    if (lines.length <= 1) return undefined;
    const timer = window.setInterval(() => {
      setLineIndex((i) => (i + 1) % lines.length);
    }, intervalMs);
    return () => window.clearInterval(timer);
  }, [intervalMs, lines.length]);

  return (
    <Panel maxW="2xl" mx="auto" py={{ base: 8, md: 12 }} data-testid="roast-status-loader">
      <VStack spacing={8} textAlign="center">
        <Spinner size="xl" thickness="4px" speed="0.8s" color="brand.500" emptyColor="gray.100" />

        <VStack spacing={1}>
          <Heading size="lg">Roast cooking aagudhu...</Heading>
          {repoLabel && (
            <Text color="text.muted" fontFamily="mono" fontSize="sm">
              {repoLabel}
            </Text>
          )}
        </VStack>

        <HStack spacing={2} w="full" maxW="md" justify="center" role="list" aria-label="Roast progress">
          {STEPS.map((step, index) => {
            const isDone = index < current;
            const isActive = index === current;
            return (
              <Fragment key={step}>
                {index > 0 && (
                  <Box flex="1" h="2px" bg={index <= current ? 'brand.500' : 'border.subtle'} borderRadius="full" />
                )}
                <VStack spacing={1} role="listitem" aria-current={isActive ? 'step' : undefined}>
                  <Circle
                    size={8}
                    bg={isDone || isActive ? 'brand.600' : 'bg.surface'}
                    borderWidth="1px"
                    borderColor={isDone || isActive ? 'brand.600' : 'border.subtle'}
                    color={isDone || isActive ? 'white' : 'text.muted'}
                    fontSize="sm"
                    fontWeight="bold"
                  >
                    {isDone ? <FiCheck aria-hidden="true" /> : index + 1}
                  </Circle>
                  <Text fontSize="xs" fontWeight={isActive ? 'bold' : 'normal'} color={isActive ? 'accent' : 'text.muted'}>
                    {step}
                  </Text>
                </VStack>
              </Fragment>
            );
          })}
        </HStack>

        <Box minH={12} w="full" aria-live="polite">
          <AnimatePresence mode="wait">
            <MotionBox
              key={lineIndex}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              transition={{ duration: 0.3 }}
            >
              <Text fontSize={{ base: 'md', md: 'lg' }} data-testid="loading-line">
                {lines[lineIndex % lines.length]}
              </Text>
            </MotionBox>
          </AnimatePresence>
        </Box>
      </VStack>
    </Panel>
  );
}

export default RoastStatusLoader;
