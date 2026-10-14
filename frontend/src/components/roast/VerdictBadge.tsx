import { Badge } from '@chakra-ui/react';

export interface VerdictBadgeProps {
  verdictTitle: string;
  score?: number;
}

export function VerdictBadge({ verdictTitle }: VerdictBadgeProps) {
  return (
    <Badge
      colorScheme="brand"
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
