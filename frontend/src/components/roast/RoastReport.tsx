import { Box, Divider, Flex, HStack, Heading, Link, SimpleGrid, Text, VStack } from '@chakra-ui/react';
import { FiGithub } from 'react-icons/fi';
import type { AnalysisView, RoastResponse } from '../../types/api';
import { Panel } from '../ui/Panel';
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
}

/** Completed roast view, rendered by RoastPage. */
export function RoastReport({ roast, analysis, repo, share }: RoastReportProps) {
  return (
    <VStack align="stretch" spacing={6} data-testid="roast-report">
      <Panel>
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
            {share && (
              <VStack align={{ base: 'center', md: 'start' }} spacing={3} pt={2}>
                <ShareBar shareSlug={share.shareSlug} score={roast.score} isPublic={share.isPublic} />
              </VStack>
            )}
          </VStack>
        </Flex>
        {analysis && (
          <>
            <Divider my={5} borderColor="border.subtle" />
            <AnalysisChips analysis={analysis} />
          </>
        )}
      </Panel>

      <Panel>
        <Heading as="h2" size="md" mb={4}>
          The Roast
        </Heading>
        <RoastMarkdown markdown={roast.roastText} />
      </Panel>

      <SimpleGrid columns={{ base: 1, lg: 2 }} spacing={6}>
        <Panel>
          <StrengthsList strengths={roast.strengths} />
        </Panel>
        <Panel>
          <FixTipsList tips={roast.fixTips} />
        </Panel>
      </SimpleGrid>

      <Panel>
        <IssuesList issues={roast.issues} />
      </Panel>

      <Box>
        <Text fontSize="xs" color="text.muted" textAlign="center">
          Roast is for fun — fix tips are for real.
        </Text>
      </Box>
    </VStack>
  );
}

export default RoastReport;
