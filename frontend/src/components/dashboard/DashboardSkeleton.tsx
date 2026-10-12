import { SimpleGrid, Skeleton, VStack } from '@chakra-ui/react';

export function DashboardSkeleton() {
  return (
    <VStack align="stretch" spacing={6} data-testid="dashboard-skeleton" aria-busy="true" aria-label="Loading dashboard">
      <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4}>
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} h={24} borderRadius="2xl" />
        ))}
      </SimpleGrid>
      <VStack align="stretch" spacing={3}>
        {[0, 1, 2, 3, 4].map((i) => (
          <Skeleton key={i} h={14} borderRadius="lg" />
        ))}
      </VStack>
    </VStack>
  );
}

export default DashboardSkeleton;
