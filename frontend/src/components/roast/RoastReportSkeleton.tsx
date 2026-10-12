import { Flex, Skeleton, SkeletonCircle, SkeletonText, VStack } from '@chakra-ui/react';
import { GlassCard } from '../ui/GlassCard';

export function RoastReportSkeleton() {
  return (
    <VStack align="stretch" spacing={6} data-testid="roast-report-skeleton" aria-busy="true" aria-label="Loading roast">
      <GlassCard disableHover>
        <Flex direction={{ base: 'column', md: 'row' }} align="center" gap={8}>
          <SkeletonCircle size="36" />
          <VStack align="stretch" flex="1" spacing={3} w="full">
            <Skeleton h={8} w="60%" />
            <Skeleton h={6} w="40%" />
            <Skeleton h={8} w="50%" />
          </VStack>
        </Flex>
      </GlassCard>
      <GlassCard disableHover>
        <SkeletonText noOfLines={8} spacing={4} />
      </GlassCard>
    </VStack>
  );
}

export default RoastReportSkeleton;
