import {
  Badge,
  Box,
  CircularProgress,
  CircularProgressLabel,
  Divider,
  HStack,
  Heading,
  Icon,
  List,
  ListIcon,
  ListItem,
  Text,
  VStack,
} from '@chakra-ui/react';
import { FaGithub } from 'react-icons/fa';
import { FiCheckCircle } from 'react-icons/fi';
import { GlassCard } from '../ui/GlassCard';

const SAMPLE_SCORE = 3.5;

const ROAST_LINES: string[] = [
  'README illa, setup steps illa — repo-va open panna treasure hunt maari irukku machan 🗺️',
  '.env file-a commit pannitta... API key-um public-a, un confidence-um public-a 🔑',
  'Prompt ellam main.py-la hardcode — idhu assignment-a illa hostage situation-a? 😬',
  'Tests folder kooda illa. "Works on my machine" dhaan un CI pipeline 💀',
];

const FIX_TIPS: string[] = [
  'Add a README with setup, usage and a sample output screenshot.',
  'Remove .env from git history, rotate the key, and ship a .env.example.',
  'Move prompts into a prompts/ module and load config from env vars.',
  'Add at least one pytest for the core chain with a mocked LLM.',
];

/** Static sample roast for the landing page — no API calls. */
export function ExampleRoastCard() {
  return (
    <GlassCard p={{ base: 5, md: 7 }} w="full" disableHover>
      <HStack justify="space-between" align="start" spacing={4} mb={5}>
        <VStack align="start" spacing={2}>
          <HStack color="text.muted" fontSize="sm" spacing={2}>
            <Icon as={FaGithub} />
            <Text fontFamily="mono">someone/genai-week3-rag-bot</Text>
          </HStack>
          <Badge colorScheme="red" variant="subtle" borderRadius="full" px={3} py={1}>
            Sample roast
          </Badge>
          <Heading size="md" textStyle="fireGradient">
            README Illaadha Rajini 🕶️
          </Heading>
        </VStack>
        <CircularProgress
          value={SAMPLE_SCORE * 10}
          size="88px"
          thickness="10px"
          color="red.400"
          trackColor="whiteAlpha.200"
          capIsRound
          flexShrink={0}
          aria-label={`Sample score ${SAMPLE_SCORE} out of 10`}
        >
          <CircularProgressLabel fontWeight="bold" fontSize="lg">
            {SAMPLE_SCORE}
            <Text as="span" fontSize="xs" color="text.muted">
              /10
            </Text>
          </CircularProgressLabel>
        </CircularProgress>
      </HStack>

      <VStack align="stretch" spacing={3}>
        {ROAST_LINES.map((line) => (
          <Box key={line} borderLeft="3px solid" borderColor="fire.500" pl={3}>
            <Text fontSize="sm">{line}</Text>
          </Box>
        ))}
      </VStack>

      <Divider my={5} borderColor="border.glass" />

      <Text fontWeight="semibold" fontSize="sm" mb={3} color="accent">
        Fix tips 🛠️
      </Text>
      <List spacing={2}>
        {FIX_TIPS.map((tip) => (
          <ListItem key={tip} fontSize="sm" color="text.muted" display="flex" alignItems="start">
            <ListIcon as={FiCheckCircle} color="green.400" mt={1} />
            {tip}
          </ListItem>
        ))}
      </List>
    </GlassCard>
  );
}

export default ExampleRoastCard;
