import { Box, Button, Container, Flex, Link, Spacer, Text } from '@chakra-ui/react';
import type { ReactNode } from 'react';
import { FiZap } from 'react-icons/fi';
import { Link as RouterLink } from 'react-router-dom';

function Logo() {
  return (
    <Link as={RouterLink} to="/" _hover={{ opacity: 0.9 }} aria-label="Assignment Roaster home">
      <Text
        as="span"
        fontFamily="heading"
        fontWeight="bold"
        fontSize={{ base: 'md', md: 'xl' }}
        textStyle="accent"
      >
        Assignment Roaster
      </Text>{' '}
      <Text as="span" fontSize={{ base: 'md', md: 'xl' }}>
        🔥
      </Text>
    </Link>
  );
}

export interface AppShellProps {
  children: ReactNode;
}

/** Top-level layout: sticky navbar with the logo and a "new roast" shortcut. No login. */
export function AppShell({ children }: AppShellProps) {
  return (
    <Flex direction="column" minH="100vh" bg="bg.canvas">
      <Box
        as="header"
        position="sticky"
        top={0}
        zIndex="sticky"
        backdropFilter="blur(16px)"
        bg="bg.glass"
        borderBottom="1px solid"
        borderColor="border.glass"
      >
        <Container maxW="6xl" px={4}>
          <Flex h={16} align="center" gap={2}>
            <Logo />
            <Spacer />
            <Button as={RouterLink} to="/" size="sm" variant="ghost" leftIcon={<FiZap aria-hidden="true" />}>
              New roast
            </Button>
          </Flex>
        </Container>
      </Box>

      <Container as="main" maxW="6xl" px={4} py={{ base: 6, md: 10 }} flex="1">
        {children}
      </Container>

      <Box as="footer" borderTop="1px solid" borderColor="border.glass" py={6}>
        <Container maxW="6xl" px={4}>
          <Text textAlign="center" fontSize="sm" color="text.muted">
            Made with ❤️ &amp; 🌶️ for the GenAI community
          </Text>
        </Container>
      </Box>
    </Flex>
  );
}

export default AppShell;
