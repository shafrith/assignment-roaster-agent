import {
  Box,
  Code,
  Divider,
  Heading,
  ListItem,
  OrderedList,
  Text,
  UnorderedList,
} from '@chakra-ui/react';
import Markdown, { type Components } from 'react-markdown';

/**
 * Markdown → Chakra mapping for UNTRUSTED LLM output (the model reads attacker-controlled repos).
 *
 * - No rehype-raw + `skipHtml`: raw HTML never renders (XSS-safe).
 * - Links and images are dropped and unwrapped to plain text (SEC-6). Roasts never need links —
 *   file references are code spans — and an allowlist (e.g. github.com only) would still let a
 *   prompt-injected repo point visitors at an attacker-owned GitHub page/gist from our domain.
 *   Plain-text URLs stay non-clickable (no remark-gfm autolinks).
 * - `urlTransform` blanks every URL as defence in depth in case a link/image slips through.
 */
const DISALLOWED_ELEMENTS: readonly string[] = ['a', 'img', 'iframe', 'script', 'style'];

const blockAllUrls = (): string => '';
const components: Components = {
  h1: ({ children }) => (
    <Heading as="h3" size="lg" mt={6} mb={3}>
      {children}
    </Heading>
  ),
  h2: ({ children }) => (
    <Heading as="h3" size="md" mt={5} mb={2}>
      {children}
    </Heading>
  ),
  h3: ({ children }) => (
    <Heading as="h4" size="sm" mt={4} mb={2}>
      {children}
    </Heading>
  ),
  h4: ({ children }) => (
    <Heading as="h5" size="xs" mt={3} mb={1}>
      {children}
    </Heading>
  ),
  p: ({ children }) => (
    <Text mb={3} lineHeight="tall">
      {children}
    </Text>
  ),
  ul: ({ children }) => (
    <UnorderedList mb={3} spacing={1} pl={2}>
      {children}
    </UnorderedList>
  ),
  ol: ({ children }) => (
    <OrderedList mb={3} spacing={1} pl={2}>
      {children}
    </OrderedList>
  ),
  li: ({ children }) => <ListItem>{children}</ListItem>,
  blockquote: ({ children }) => (
    <Box as="blockquote" borderLeftWidth="4px" borderColor="fire.400" pl={4} py={1} my={3} color="text.muted">
      {children}
    </Box>
  ),
  pre: ({ children }) => (
    <Box
      as="pre"
      bg="blackAlpha.500"
      p={4}
      my={3}
      borderRadius="md"
      overflowX="auto"
      fontFamily="mono"
      fontSize="sm"
      sx={{ '& code': { bg: 'transparent', p: 0, whiteSpace: 'pre' } }}
    >
      {children}
    </Box>
  ),
  code: ({ children }) => (
    <Code fontFamily="mono" fontSize="0.9em" px={1} colorScheme="orange">
      {children}
    </Code>
  ),
  hr: () => <Divider my={4} borderColor="border.glass" />,
  strong: ({ children }) => (
    <Text as="strong" fontWeight="bold">
      {children}
    </Text>
  ),
  em: ({ children }) => (
    <Text as="em" fontStyle="italic">
      {children}
    </Text>
  ),
};

export interface RoastMarkdownProps {
  markdown: string;
}

export function RoastMarkdown({ markdown }: RoastMarkdownProps) {
  return (
    <Box data-testid="roast-markdown">
      <Markdown
        components={components}
        skipHtml
        disallowedElements={[...DISALLOWED_ELEMENTS]}
        unwrapDisallowed
        urlTransform={blockAllUrls}
      >
        {markdown}
      </Markdown>
    </Box>
  );
}

export default RoastMarkdown;
