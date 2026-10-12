import { Badge, Box, Flex, Heading, HStack, Icon, SimpleGrid, Text, VStack } from '@chakra-ui/react';
import type { Variants } from 'framer-motion';
import type { IconType } from 'react-icons';
import { FiCpu, FiLink, FiZap } from 'react-icons/fi';
import { ExampleRoastCard } from '../components/landing/ExampleRoastCard';
import { RoastForm } from '../components/roast/RoastForm';
import { GlassCard } from '../components/ui/GlassCard';
import { MotionBox } from '../lib/motion';

const container: Variants = {
  hidden: {},
  visible: { transition: { staggerChildren: 0.12, delayChildren: 0.05 } },
};

const rise: Variants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 220, damping: 24 } },
};

interface Step {
  icon: IconType;
  title: string;
  tamil: string;
  body: string;
}

const STEPS: Step[] = [
  {
    icon: FiLink,
    title: 'Paste repo',
    tamil: 'Link-a podu',
    body: 'Drop the public GitHub URL of your GenAI community assignment. No login, no repo permissions.',
  },
  {
    icon: FiCpu,
    title: 'We analyze',
    tamil: 'Naanga paakurom',
    body: 'We scan structure, README, dependencies, tests, leaked secrets, git hygiene and GenAI best practices.',
  },
  {
    icon: FiZap,
    title: 'Get roasted + fix tips',
    tamil: 'Roast vaangiko',
    body: 'A brutally honest Tanglish roast, a score out of 10, and concrete tips to level up before you submit.',
  },
];

export default function LandingPage() {
  return (
    <Box position="relative">
      <MotionBox position="relative" zIndex={1} initial="hidden" animate="visible" variants={container}>
        {/* Hero */}
        <Flex
          direction={{ base: 'column', lg: 'row' }}
          align="center"
          gap={{ base: 10, lg: 14 }}
          pt={{ base: 4, md: 10 }}
          pb={{ base: 14, md: 20 }}
        >
          <VStack align={{ base: 'center', lg: 'start' }} textAlign={{ base: 'center', lg: 'left' }} spacing={6} flex="1">
            <MotionBox variants={rise}>
              <Badge colorScheme="fire" variant="subtle" borderRadius="full" px={3} py={1} fontSize="xs">
                For the GenAI community 🤖
              </Badge>
            </MotionBox>
            <MotionBox variants={rise}>
              <Heading
                as="h1"
                fontSize={{ base: '4xl', md: '5xl', xl: '6xl' }}
                lineHeight={1.1}
                letterSpacing="tight"
              >
                <Text as="span" textStyle="accent">
                  Un assignment-a roast panna ready-a?
                </Text>{' '}
                🔥
              </Heading>
            </MotionBox>
            <MotionBox variants={rise}>
              <Text fontSize={{ base: 'md', md: 'lg' }} color="text.muted" maxW="xl">
                Paste a public GitHub repo from your GenAI community assignment and get an instant AI code review —
                a score, a savage-but-friendly Tanglish roast, and practical fix tips covering docs, tests, secrets,
                structure and prompt hygiene.
              </Text>
            </MotionBox>
            <MotionBox variants={rise} w="full" maxW="xl" textAlign="left">
              <RoastForm />
            </MotionBox>
          </VStack>

          <MotionBox
            flex="1"
            w="full"
            maxW="lg"
            variants={rise}
            whileHover={{ rotate: -0.5, y: -4 }}
          >
            <ExampleRoastCard />
          </MotionBox>
        </Flex>

        {/* How it works */}
        <MotionBox variants={rise} pb={{ base: 6, md: 10 }}>
          <VStack spacing={2} mb={8} textAlign="center">
            <Heading size="lg">How it works</Heading>
            <Text color="text.muted">Moonu step, oru roast. That&apos;s it.</Text>
          </VStack>
          <SimpleGrid columns={{ base: 1, md: 3 }} spacing={6}>
            {STEPS.map((step, index) => (
              <GlassCard key={step.title} h="full">
                <VStack align="start" spacing={3}>
                  <HStack spacing={3}>
                    <Flex
                      boxSize={10}
                      align="center"
                      justify="center"
                      borderRadius="xl"
                      bg="fire.500"
                      color="white"
                    >
                      <Icon as={step.icon} boxSize={5} />
                    </Flex>
                    <Text fontFamily="mono" color="text.muted" fontSize="sm">
                      0{index + 1}
                    </Text>
                  </HStack>
                  <Heading size="md">{step.title}</Heading>
                  <Text color="accent" fontSize="sm" fontWeight="semibold">
                    {step.tamil}
                  </Text>
                  <Text color="text.muted" fontSize="sm">
                    {step.body}
                  </Text>
                </VStack>
              </GlassCard>
            ))}
          </SimpleGrid>
        </MotionBox>
      </MotionBox>
    </Box>
  );
}
