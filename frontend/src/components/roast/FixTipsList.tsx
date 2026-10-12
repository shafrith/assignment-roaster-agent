import { Circle, HStack, Heading, List, ListItem, Text, VStack } from '@chakra-ui/react';

export interface FixTipsListProps {
  tips: string[];
}

export function FixTipsList({ tips }: FixTipsListProps) {
  return (
    <VStack align="stretch" spacing={3}>
      <Heading as="h3" size="md">
        Fix pannu machan 💡
      </Heading>
      {tips.length === 0 ? (
        <Text color="text.muted">Fix panna onnum illa. Semma! 🎉</Text>
      ) : (
        <List as="ol" spacing={3}>
          {tips.map((tip, index) => (
            <ListItem key={`${index}-${tip}`}>
              <HStack align="start" spacing={3}>
                <Circle size={7} bg="fire.500" color="white" fontSize="sm" fontWeight="bold" flexShrink={0}>
                  {index + 1}
                </Circle>
                <Text pt={0.5}>
                  <Text as="span" aria-hidden="true">
                    💡{' '}
                  </Text>
                  {tip}
                </Text>
              </HStack>
            </ListItem>
          ))}
        </List>
      )}
    </VStack>
  );
}

export default FixTipsList;
