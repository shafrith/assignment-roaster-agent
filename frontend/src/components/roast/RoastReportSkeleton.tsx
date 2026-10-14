import { Flex, Skeleton, SkeletonCircle, SkeletonText, VStack } from '@chakra-ui/react';
import { Panel } from '../ui/Panel';

export function RoastReportSkeleton() {
  return (
    <VStack align="stretch" spacing={6} data-testid="roast-report-skeleton" aria-busy="true" aria-label="Loading roast">
      <Panel>
        <Flex direction={{ base: 'column', md: 'row' }} align="center" gap={8}>
          <SkeletonCircle size="36" />
          <VStack align="stretch" flex="1" spacing={3} w="full">
            <Skeleton h={8} w="60%" />
            <Skeleton h={6} w="40%" />
            <Skeleton h={8} w="50%" />
          </VStack>
        </Flex>
      </Panel>
      <Panel>
        <SkeletonText noOfLines={8} spacing={4} />
      </Panel>
    </VStack>
  );
}

export default RoastReportSkeleton;
