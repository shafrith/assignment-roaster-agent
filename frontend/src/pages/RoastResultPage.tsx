import { Button, HStack, Link, Text, VStack } from '@chakra-ui/react';
import { FiArrowLeft, FiGithub, FiRefreshCw } from 'react-icons/fi';
import { Link as RouterLink, useParams } from 'react-router-dom';
import { RetryButton } from '../components/roast/RetryButton';
import { RoastReport } from '../components/roast/RoastReport';
import { RoastReportSkeleton } from '../components/roast/RoastReportSkeleton';
import { RoastStatusLoader } from '../components/roast/RoastStatusLoader';
import { ErrorState } from '../components/ui/ErrorState';
import { GradientLinkButton } from '../components/ui/GradientLinkButton';
import { PageWrapper } from '../components/ui/PageWrapper';
import { useSubmission } from '../hooks/useSubmission';
import { isNotFoundError } from '../lib/httpErrors';
import { getErrorMessage } from '../services/api';
import type { SubmissionResponse } from '../types/api';

function parseId(raw: string | undefined): number | null {
  if (!raw || !/^\d+$/.test(raw)) return null;
  const id = Number(raw);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
}

function BackToDashboard() {
  return (
    <Button as={RouterLink} to="/dashboard" variant="ghost" size="sm" leftIcon={<FiArrowLeft aria-hidden="true" />}>
      Dashboard
    </Button>
  );
}

interface SubmissionBodyProps {
  submission: SubmissionResponse;
  isPollingTimedOut: boolean;
  onResumePolling: () => void;
}

function SubmissionBody({ submission, isPollingTimedOut, onResumePolling }: SubmissionBodyProps) {
  const repoLabel = `${submission.repoOwner}/${submission.repoName}`;

  if (submission.status === 'failed') {
    return (
      <ErrorState title="Roast fail aayiduchu 😵" message={submission.errorMessage ?? 'Edho thappa pochu.'} emoji="💥">
        <Text fontFamily="mono" fontSize="sm" color="text.muted">
          {repoLabel}
        </Text>
        <RetryButton submissionId={submission.id} />
      </ErrorState>
    );
  }

  if (submission.status === 'completed' && submission.roast) {
    return (
      <RoastReport
        roast={submission.roast}
        analysis={submission.analysis}
        repo={{ owner: submission.repoOwner, name: submission.repoName, url: submission.repoUrl }}
        share={{ shareSlug: submission.shareSlug, isPublic: submission.isPublic }}
        submissionId={submission.id}
      />
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

  return <RoastStatusLoader status={submission.status} repoLabel={repoLabel} />;
}

export default function RoastResultPage() {
  const { id: rawId } = useParams<{ id: string }>();
  const id = parseId(rawId);
  const { query, isPollingTimedOut, resumePolling } = useSubmission(id);

  let body;
  if (id === null || (query.isError && isNotFoundError(query.error))) {
    body = (
      <ErrorState title="Roast kidaikala 🤷" message="Indha roast illa, illa unakku access illa." emoji="🔍">
        <GradientLinkButton to="/roast/new">
          Pudhu roast pannu 🔥
        </GradientLinkButton>
      </ErrorState>
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
    body = (
      <SubmissionBody submission={query.data} isPollingTimedOut={isPollingTimedOut} onResumePolling={resumePolling} />
    );
  }

  return (
    <PageWrapper>
      <VStack align="stretch" spacing={4}>
        <HStack justify="space-between">
          <BackToDashboard />
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
