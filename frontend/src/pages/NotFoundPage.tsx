import { Button, Center, Heading, Text, VStack } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';
import { GlassCard } from '../components/ui/GlassCard';
import { PageWrapper } from '../components/ui/PageWrapper';
import { MotionBox } from '../lib/motion';

export default function NotFoundPage() {
  return (
    <PageWrapper>
      <Center minH="60vh">
        <GlassCard disableHover maxW="lg" w="full" p={{ base: 6, md: 10 }}>
          <VStack spacing={5} textAlign="center">
            <MotionBox
              fontSize="6xl"
              lineHeight={1}
              animate={{ rotate: [0, -12, 12, -6, 0] }}
              transition={{ duration: 1.6, repeat: Infinity, repeatDelay: 1.2 }}
              aria-hidden
            >
              🔍
            </MotionBox>
            <Heading size="2xl" textStyle="accent">
              404
            </Heading>
            <Heading size="md">Indha page-a kaanom da! 🔍</Heading>
            <Text color="text.muted">
              The page you&apos;re looking for doesn&apos;t exist — maybe it got roasted a little too hard.
            </Text>
            <Button as={RouterLink} to="/">
              Veetuku po (Go home)
            </Button>
          </VStack>
        </GlassCard>
      </Center>
    </PageWrapper>
  );
}
