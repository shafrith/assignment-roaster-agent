import { Button, Flex, Heading, Text, VStack } from '@chakra-ui/react';
import { useState } from 'react';
import { DashboardSkeleton } from '../components/dashboard/DashboardSkeleton';
import { EmptyState } from '../components/dashboard/EmptyState';
import { PaginationControls } from '../components/dashboard/PaginationControls';
import { StatCards } from '../components/dashboard/StatCards';
import { SubmissionTable } from '../components/dashboard/SubmissionTable';
import { ErrorState } from '../components/ui/ErrorState';
import { GradientLinkButton } from '../components/ui/GradientLinkButton';
import { PageWrapper } from '../components/ui/PageWrapper';
import { useSubmissions } from '../hooks/useSubmissions';
import { DEFAULT_PAGE_SIZE } from '../services/submissionService';
import { getErrorMessage } from '../services/api';

export default function DashboardPage() {
  const [page, setPage] = useState(1);
  const query = useSubmissions(page, DEFAULT_PAGE_SIZE);

  let body;
  if (query.isPending) {
    body = <DashboardSkeleton />;
  } else if (query.isError) {
    body = (
      <ErrorState message={getErrorMessage(query.error)}>
        <Button onClick={() => void query.refetch()} isLoading={query.isFetching}>
          Try again
        </Button>
      </ErrorState>
    );
  } else if (query.data.total === 0) {
    body = <EmptyState />;
  } else if (query.data.items.length === 0) {
    // Page went out of range (e.g. last item on a page was deleted).
    body = (
      <ErrorState title="Indha page kaali 🫙" message="Inga onnum illa." emoji="📭">
        <Button onClick={() => setPage(1)}>First page-ku po</Button>
      </ErrorState>
    );
  } else {
    const { items, total, pageSize } = query.data;
    body = (
      <VStack align="stretch" spacing={6}>
        <StatCards items={items} total={total} />
        <Text fontSize="xs" color="text.muted" mt={-3}>
          Avg / best / worst are computed from the roasts on this page.
        </Text>
        <SubmissionTable items={items} />
        {total > pageSize && (
          <PaginationControls
            page={page}
            pageSize={pageSize}
            total={total}
            onPageChange={setPage}
            isFetching={query.isFetching}
          />
        )}
      </VStack>
    );
  }

  return (
    <PageWrapper>
      <VStack align="stretch" spacing={6}>
        <Flex justify="space-between" align={{ base: 'start', sm: 'center' }} direction={{ base: 'column', sm: 'row' }} gap={4}>
          <VStack align="start" spacing={1}>
            <Heading as="h1" size="lg">
              Un roast history 📜
            </Heading>
            <Text color="text.muted">Ella roast-um inga irukku. Azhudhutu fix pannu 😅</Text>
          </VStack>
          <GradientLinkButton to="/roast/new" size="md">
            Roast another 🔥
          </GradientLinkButton>
        </Flex>
        {body}
      </VStack>
    </PageWrapper>
  );
}
