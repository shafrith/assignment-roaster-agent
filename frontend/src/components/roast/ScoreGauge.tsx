import { CircularProgress, CircularProgressLabel, Text, VStack } from '@chakra-ui/react';
import { animate } from 'framer-motion';
import { useEffect, useState } from 'react';
import { formatScore } from '../../lib/format';

export interface ScoreGaugeProps {
  /** 0–10 */
  score: number;
  size?: string;
  /** Count-up duration in seconds (0 disables the animation). */
  duration?: number;
}

/** Circular score gauge with a count-up number. */
export function ScoreGauge({ score, size = '140px', duration = 0 }: ScoreGaugeProps) {
  const clamped = Math.min(10, Math.max(0, score));
  const [display, setDisplay] = useState(duration > 0 ? 0 : clamped);

  useEffect(() => {
    if (duration <= 0) {
      setDisplay(clamped);
      return undefined;
    }
    const controls = animate(0, clamped, {
      duration,
      ease: 'easeOut',
      onUpdate: (latest) => setDisplay(latest),
    });
    return () => controls.stop();
  }, [clamped, duration]);

  const shown = display === clamped ? formatScore(clamped) : display.toFixed(Number.isInteger(clamped) ? 0 : 1);

  return (
    <VStack spacing={1} data-testid="score-gauge">
      <CircularProgress
        value={display * 10}
        size={size}
        thickness="10px"
        color="brand.500"
        trackColor="gray.100"
        capIsRound
        aria-label={`Score ${formatScore(clamped)} out of 10`}
      >
        <CircularProgressLabel>
          <Text as="span" fontSize="3xl" fontWeight="bold" color="gray.800">
            {shown}
          </Text>
          <Text as="span" fontSize="md" color="text.muted">
            /10
          </Text>
        </CircularProgressLabel>
      </CircularProgress>
    </VStack>
  );
}

export default ScoreGauge;
