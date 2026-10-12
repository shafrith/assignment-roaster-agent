import { Heading, Text, VStack } from '@chakra-ui/react';
import { GlassCard } from './GlassCard';
import { PageWrapper } from './PageWrapper';

export interface PlaceholderPageProps {
  title: string;
  description?: string;
}

/** Temporary page body used by Phase 1 route stubs. */
export function PlaceholderPage({ title, description }: PlaceholderPageProps) {
  return (
    <PageWrapper>
      <GlassCard disableHover>
        <VStack align="start" spacing={2}>
          <Heading size="lg">{title}</Heading>
          <Text color="text.muted">{description ?? 'Coming soon 🔥'}</Text>
        </VStack>
      </GlassCard>
    </PageWrapper>
  );
}

export default PlaceholderPage;
