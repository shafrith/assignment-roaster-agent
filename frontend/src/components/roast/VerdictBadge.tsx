import { Badge } from '@chakra-ui/react';
import { scoreColorScheme } from '../../lib/format';

export interface VerdictBadgeProps {
  verdictTitle: string;
  score?: number;
}

export function VerdictBadge({ verdictTitle, score }: VerdictBadgeProps) {
  return (
    <Badge
      colorScheme={score === undefined ? 'orange' : scoreColorScheme(score)}
      variant="subtle"
      fontSize={{ base: 'md', md: 'lg' }}
      px={4}
      py={1}
      borderRadius="full"
      textTransform="none"
      whiteSpace="normal"
      textAlign="center"
    >
      {verdictTitle}
    </Badge>
  );
}

export default VerdictBadge;
