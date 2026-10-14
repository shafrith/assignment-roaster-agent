import { HStack, Heading, Icon, List, ListItem, Text, VStack } from '@chakra-ui/react';
import { FiCheck } from 'react-icons/fi';

export interface StrengthsListProps {
  strengths: string[];
}

export function StrengthsList({ strengths }: StrengthsListProps) {
  return (
    <VStack align="stretch" spacing={3}>
      <Heading as="h3" size="md">
        Nalla vishayam
      </Heading>
      {strengths.length === 0 ? (
        <Text color="text.muted">Honestly... onnum kandupidika mudiyala</Text>
      ) : (
        <List spacing={2}>
          {strengths.map((strength, index) => (
            <ListItem key={`${index}-${strength}`}>
              <HStack align="start" spacing={2}>
                <Icon as={FiCheck} color="brand.600" mt={1} flexShrink={0} aria-hidden="true" />
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
