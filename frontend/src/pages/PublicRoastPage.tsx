import { Heading, Text, VStack } from '@chakra-ui/react';
import { Helmet } from 'react-helmet-async';
import { useParams } from 'react-router-dom';
import { AuthorChip } from '../components/roast/AuthorChip';
import { RoastReport } from '../components/roast/RoastReport';
import { RoastReportSkeleton } from '../components/roast/RoastReportSkeleton';
import { ErrorState } from '../components/ui/ErrorState';
import { GlassCard } from '../components/ui/GlassCard';
import { GradientLinkButton } from '../components/ui/GradientLinkButton';
import { PageWrapper } from '../components/ui/PageWrapper';
import { usePublicRoast } from '../hooks/usePublicRoast';
import { formatScore } from '../lib/format';
import { isNotFoundError } from '../lib/httpErrors';
import { getErrorMessage } from '../services/api';

export const PUBLIC_ROAST_NOT_FOUND = 'Indha roast private-a illa delete aayiduchu 🤷';

function RoastYourOwnCta() {
  return (
    <GlassCard disableHover textAlign="center" py={8}>
      <VStack spacing={4}>
        <Heading size="md">Un repo-vayum roast pannanuma? Try pannu 🔥</Heading>
        <GradientLinkButton to="/">
          Roast my repo 🔥
        </GradientLinkButton>
      </VStack>
    </GlassCard>
  );
}

export default function PublicRoastPage() {
  const { shareSlug } = useParams<{ shareSlug: string }>();
  const query = usePublicRoast(shareSlug);

  if (!shareSlug || (query.isError && isNotFoundError(query.error))) {
    return (
      <PageWrapper>
        <Helmet>
          <title>Roast not found 🤷 · Assignment Roaster</title>
        </Helmet>
        <VStack spacing={6} align="stretch">
          <ErrorState title="Roast kidaikala" message={PUBLIC_ROAST_NOT_FOUND} emoji="🙈" />
          <RoastYourOwnCta />
        </VStack>
      </PageWrapper>
    );
  }

  if (query.isPending) {
    return (
      <PageWrapper>
        <RoastReportSkeleton />
      </PageWrapper>
    );
  }

  if (query.isError) {
    return (
      <PageWrapper>
        <ErrorState message={getErrorMessage(query.error)} />
      </PageWrapper>
    );
  }

  const data = query.data;
  const repoLabel = `${data.repoOwner}/${data.repoName}`;
  const score = formatScore(data.roast.score);
  const title = `${repoLabel} got roasted: ${score}/10 🔥`;
  const description = `${data.roast.verdictTitle} — Assignment Roaster`;

  return (
    <PageWrapper>
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
      <VStack align="stretch" spacing={6}>
        <RoastReport
          readOnly
          roast={data.roast}
          analysis={data.analysis}
          repo={{ owner: data.repoOwner, name: data.repoName, url: data.repoUrl }}
          share={shareSlug ? { shareSlug, isPublic: true } : undefined}
          headerExtra={<AuthorChip githubUsername={data.author.githubUsername} avatarUrl={data.author.avatarUrl} />}
        />
        <RoastYourOwnCta />
        <Text fontSize="xs" color="text.muted" textAlign="center">
          Roasted on {new Date(data.createdAt).toLocaleDateString()}
        </Text>
      </VStack>
    </PageWrapper>
  );
}
