import { HStack, Heading, List, ListItem, Text, VStack } from '@chakra-ui/react';

export interface StrengthsListProps {
  strengths: string[];
}

export function StrengthsList({ strengths }: StrengthsListProps) {
  return (
    <VStack align="stretch" spacing={3}>
      <Heading as="h3" size="md">
        Nalla vishayam 👍
      </Heading>
      {strengths.length === 0 ? (
        <Text color="text.muted">Honestly... onnum kandupidika mudiyala 😬</Text>
      ) : (
        <List spacing={2}>
          {strengths.map((strength, index) => (
            <ListItem key={`${index}-${strength}`}>
              <HStack align="start" spacing={2}>
                <Text as="span" aria-hidden="true">
                  ✅
                </Text>
                <Text>{strength}</Text>
              </HStack>
            </ListItem>
          ))}
        </List>
      )}
    </VStack>
  );
}

export default StrengthsList;
