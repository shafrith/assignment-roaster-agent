import { Heading, Text, VStack } from '@chakra-ui/react';
import { MotionBox } from '../../lib/motion';
import { GlassCard } from '../ui/GlassCard';
import { GradientLinkButton } from '../ui/GradientLinkButton';

export function EmptyState() {
  return (
    <GlassCard disableHover textAlign="center" py={12} data-testid="empty-state">
      <VStack spacing={5}>
        <MotionBox
          fontSize="6xl"
          animate={{ y: [0, -8, 0] }}
          transition={{ duration: 1.6, repeat: Infinity, ease: 'easeInOut' }}
          aria-hidden="true"
        >
          🍳
        </MotionBox>
        <Heading size="md">Innum oru roast-um illa! Mudhal repo-va kudu 👇</Heading>
        <Text color="text.muted">Public GitHub repo URL paste pannu, naanga paathukrom.</Text>
        <GradientLinkButton to="/roast/new">
          Roast Me 🔥
        </GradientLinkButton>
      </VStack>
    </GlassCard>
  );
}

export default EmptyState;
