import { Box, Divider, Flex, HStack, Heading, Link, SimpleGrid, Text, VStack } from '@chakra-ui/react';
import type { ReactNode } from 'react';
import { FiGithub } from 'react-icons/fi';
import type { AnalysisView, RoastResponse } from '../../types/api';
import { GlassCard } from '../ui/GlassCard';
import { AnalysisChips } from './AnalysisChips';
import { FixTipsList } from './FixTipsList';
import { IssuesList } from './IssuesList';
import { RoastMarkdown } from './RoastMarkdown';
import { ScoreGauge } from './ScoreGauge';
import { ShareBar } from './ShareBar';
import { StrengthsList } from './StrengthsList';
import { VerdictBadge } from './VerdictBadge';

export interface RoastRepoInfo {
  owner: string;
  name: string;
  url: string;
}

export interface RoastShareInfo {
  shareSlug: string;
  isPublic: boolean;
}

export interface RoastReportProps {
  roast: RoastResponse;
  analysis: AnalysisView | null;
  repo: RoastRepoInfo;
  /** When provided, renders the ShareBar. */
  share?: RoastShareInfo;
  /** Extra content under the header (e.g. AuthorChip). */
  headerExtra?: ReactNode;
}

/** Completed roast view, rendered by RoastPage. */
export function RoastReport({ roast, analysis, repo, share, headerExtra }: RoastReportProps) {
  return (
    <VStack align="stretch" spacing={6} data-testid="roast-report">
      <GlassCard disableHover>
        <Flex direction={{ base: 'column', md: 'row' }} align="center" gap={{ base: 6, md: 10 }}>
          <ScoreGauge score={roast.score} />
          <VStack align={{ base: 'center', md: 'start' }} spacing={3} flex="1" textAlign={{ base: 'center', md: 'left' }}>
            <Link href={repo.url} isExternal rel="noopener noreferrer" _hover={{ color: 'accent' }}>
              <HStack spacing={2}>
                <FiGithub aria-hidden="true" />
                <Heading as="h1" size="lg" wordBreak="break-word">
                  {repo.owner}/{repo.name}
                </Heading>
              </HStack>
            </Link>
            <VerdictBadge verdictTitle={roast.verdictTitle} score={roast.score} />
            {headerExtra}
            {share && (
              <VStack align={{ base: 'center', md: 'start' }} spacing={3} pt={2}>
                <ShareBar shareSlug={share.shareSlug} score={roast.score} isPublic={share.isPublic} />
              </VStack>
            )}
          </VStack>
        </Flex>
        {analysis && (
          <>
            <Divider my={5} borderColor="border.glass" />
            <AnalysisChips analysis={analysis} />
          </>
        )}
      </GlassCard>

      <GlassCard disableHover>
        <Heading as="h2" size="md" mb={4}>
          The Roast 🔥
        </Heading>
        <RoastMarkdown markdown={roast.roastText} />
      </GlassCard>

      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        <GlassCard disableHover>
          <StrengthsList strengths={roast.strengths} />
        </GlassCard>
        <GlassCard disableHover>
          <FixTipsList tips={roast.fixTips} />
        </GlassCard>
      </SimpleGrid>

      <GlassCard disableHover>
        <IssuesList issues={roast.issues} />
      </GlassCard>

      <Box>
        <Text fontSize="xs" color="text.muted" textAlign="center">
          Roast is for fun 😄 — fix tips are for real.
        </Text>
      </Box>
    </VStack>
  );
}

export default RoastReport;
