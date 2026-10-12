import { Button, HStack, Heading, Link, Text, VStack } from '@chakra-ui/react';
import { Helmet } from 'react-helmet-async';
import { FiArrowLeft, FiGithub, FiRefreshCw } from 'react-icons/fi';
import { Link as RouterLink, useParams } from 'react-router-dom';
import { RetryButton } from '../components/roast/RetryButton';
import { RoastReport } from '../components/roast/RoastReport';
import { RoastReportSkeleton } from '../components/roast/RoastReportSkeleton';
import { RoastStatusLoader } from '../components/roast/RoastStatusLoader';
import { ErrorState } from '../components/ui/ErrorState';
import { GlassCard } from '../components/ui/GlassCard';
import { PageWrapper } from '../components/ui/PageWrapper';
import { PrimaryLinkButton } from '../components/ui/PrimaryLinkButton';
import { useRoast } from '../hooks/useRoast';
import { formatScore } from '../lib/format';
import { isNotFoundError } from '../lib/httpErrors';
import { getErrorMessage } from '../services/api';
import type { RoastStatusResponse } from '../types/api';

export const ROAST_NOT_FOUND_MESSAGE = 'Indha roast illa, illa private-a irukku 🤷';

function BackHome() {
  return (
    <Button as={RouterLink} to="/" variant="ghost" size="sm" leftIcon={<FiArrowLeft aria-hidden="true" />}>
      New roast
    </Button>
  );
}

function RoastYourOwnCta() {
  return (
    <GlassCard disableHover textAlign="center" py={8}>
      <VStack spacing={4}>
        <Heading size="md">Innoru repo-vayum roast pannanuma? 🔥</Heading>
        <PrimaryLinkButton to="/">Roast another repo 🔥</PrimaryLinkButton>
      </VStack>
    </GlassCard>
  );
}

interface RoastBodyProps {
  data: RoastStatusResponse;
  isPollingTimedOut: boolean;
  onResumePolling: () => void;
}

function RoastBody({ data, isPollingTimedOut, onResumePolling }: RoastBodyProps) {
  const repoLabel = `${data.repoOwner}/${data.repoName}`;

  if (data.status === 'failed') {
    return (
      <ErrorState title="Roast fail aayiduchu 😵" message={data.errorMessage ?? 'Edho thappa pochu.'} emoji="💥">
        <Text fontFamily="mono" fontSize="sm" color="text.muted">
          {repoLabel}
        </Text>
        {data.errorRetryable ? (
          <RetryButton shareSlug={data.shareSlug} />
        ) : (
          <PrimaryLinkButton to="/">Pudhu roast pannu 🔥</PrimaryLinkButton>
        )}
      </ErrorState>
    );
  }

  if (data.status === 'completed' && data.roast) {
    const score = formatScore(data.roast.score);
    const title = `${repoLabel} got roasted: ${score}/10 🔥`;
    const description = `${data.roast.verdictTitle} — Assignment Roaster`;
    return (
      <VStack align="stretch" spacing={6}>
        <Helmet>
          <title>{title}</title>
          <meta name="description" content={description} />
          <meta property="og:title" content={title} />
          <meta property="og:description" content={description} />
          <meta property="og:type" content="article" />
          <meta name="twitter:card" content="summary" />
          <meta name="twitter:title" content={title} />
          <meta name="twitter:description" content={description} />
        </Helmet>
        <RoastReport
          roast={data.roast}
          analysis={data.analysis}
          repo={{ owner: data.repoOwner, name: data.repoName, url: data.repoUrl }}
          share={{ shareSlug: data.shareSlug, isPublic: true }}
        />
        <RoastYourOwnCta />
      </VStack>
    );
  }

  if (isPollingTimedOut) {
    return (
      <ErrorState
        title="Romba neram aagudhu machan ⏳"
        message="Indha roast 10 nimishathukku mela cook aagudhu — edho stuck aayirukkalam. Konjam kazhichu status check pannu; fail aanaa Retry button varum."
        emoji="🐢"
      >
        <Text fontFamily="mono" fontSize="sm" color="text.muted">
          {repoLabel}
        </Text>
        <Button onClick={onResumePolling} leftIcon={<FiRefreshCw aria-hidden="true" />}>
          Status check pannu 🔁
        </Button>
      </ErrorState>
    );
  }

  return <RoastStatusLoader status={data.status} repoLabel={repoLabel} />;
}

/** /r/:shareSlug — follows a roast from pending to the finished report. No login needed. */
export default function RoastPage() {
  const { shareSlug } = useParams<{ shareSlug: string }>();
  const { query, isPollingTimedOut, resumePolling } = useRoast(shareSlug || null);

  let body;
  if (!shareSlug || (query.isError && isNotFoundError(query.error))) {
    body = (
      <VStack spacing={6} align="stretch">
        <Helmet>
          <title>Roast not found 🤷 · Assignment Roaster</title>
        </Helmet>
        <ErrorState title="Roast kidaikala 🤷" message={ROAST_NOT_FOUND_MESSAGE} emoji="🔍" />
        <RoastYourOwnCta />
      </VStack>
    );
  } else if (query.isPending) {
    body = <RoastReportSkeleton />;
  } else if (query.isError) {
    body = (
      <ErrorState message={getErrorMessage(query.error)}>
        <Button onClick={() => void query.refetch()} isLoading={query.isFetching}>
          Try again
        </Button>
      </ErrorState>
    );
  } else {
    body = <RoastBody data={query.data} isPollingTimedOut={isPollingTimedOut} onResumePolling={resumePolling} />;
  }

  return (
    <PageWrapper>
      <VStack align="stretch" spacing={4}>
        <HStack justify="space-between">
          <BackHome />
          {query.data && (
            <Link
              href={query.data.repoUrl}
              isExternal
              rel="noopener noreferrer"
              fontSize="sm"
              color="text.muted"
              display="inline-flex"
              alignItems="center"
              gap={1}
              aria-label={`Open ${query.data.repoOwner}/${query.data.repoName} on GitHub`}
            >
              <FiGithub aria-hidden="true" /> View on GitHub
            </Link>
          )}
        </HStack>
        {body}
      </VStack>
    </PageWrapper>
  );
}
