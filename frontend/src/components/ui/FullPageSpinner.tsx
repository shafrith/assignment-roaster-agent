import { Center, Spinner, Text, VStack } from '@chakra-ui/react';

export interface FullPageSpinnerProps {
  label?: string;
}

export function FullPageSpinner({ label = 'Load aagudhu machan...' }: FullPageSpinnerProps) {
  return (
    <Center minH="50vh" w="full">
      <VStack spacing={4}>
        <Spinner size="xl" thickness="4px" speed="0.7s" color="brand.500" emptyColor="gray.100" />
        <Text color="text.muted">{label}</Text>
      </VStack>
    </Center>
  );
}

export default FullPageSpinner;
