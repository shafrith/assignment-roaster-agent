import { Button, Center, Heading, Text, VStack } from '@chakra-ui/react';
import { Link as RouterLink } from 'react-router-dom';
import { Panel } from '../components/ui/Panel';
import { PageWrapper } from '../components/ui/PageWrapper';

export default function NotFoundPage() {
  return (
    <PageWrapper>
      <Center minH="60vh">
        <Panel maxW="lg" w="full" p={{ base: 6, md: 10 }}>
          <VStack spacing={5} textAlign="center">
            <Heading size="2xl" textStyle="accent">
              404
            </Heading>
            <Heading size="md">Indha page-a kaanom da!</Heading>
            <Text color="text.muted">
              The page you&apos;re looking for doesn&apos;t exist — maybe it got roasted a little too hard.
            </Text>
            <Button as={RouterLink} to="/">
              Veetuku po (Go home)
            </Button>
          </VStack>
        </Panel>
      </Center>
    </PageWrapper>
  );
}
