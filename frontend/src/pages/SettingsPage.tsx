import { FormControl, FormHelperText, FormLabel, Heading, HStack, Switch, Text, VStack, useToast } from '@chakra-ui/react';
import { useMutation } from '@tanstack/react-query';
import { useState } from 'react';
import { GlassCard } from '../components/ui/GlassCard';
import { PageWrapper } from '../components/ui/PageWrapper';
import { useAuth } from '../hooks/useAuth';
import { getErrorMessage } from '../services/api';
import { updateSettings } from '../services/authService';
import type { UserResponse } from '../types';

export default function SettingsPage() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  // Optimistic value shown while the PATCH is in flight.
  const [pendingValue, setPendingValue] = useState<boolean | null>(null);

  const mutation = useMutation<UserResponse, Error, boolean>({
    mutationFn: updateSettings,
    onMutate: (next) => setPendingValue(next),
    onSuccess: (updated) => {
      setUser(updated);
      toast({
        status: 'success',
        title: updated.defaultRoastPublic ? 'New roasts public-a irukkum 🌍' : 'New roasts private-a irukkum 🔒',
        duration: 3000,
        isClosable: true,
      });
    },
    onError: (err) => {
      toast({
        status: 'error',
        title: 'Save aagala machan',
        description: getErrorMessage(err),
        duration: 5000,
        isClosable: true,
      });
    },
    onSettled: () => setPendingValue(null),
  });

  if (!user) return null;

  const checked = pendingValue ?? user.defaultRoastPublic;

  return (
    <PageWrapper>
      <VStack align="stretch" spacing={6} maxW="2xl" mx="auto">
        <VStack align="start" spacing={1}>
          <Heading size="lg">Settings</Heading>
          <Text color="text.muted">Un roast, un rules ⚙️</Text>
        </VStack>
        <GlassCard disableHover>
          <FormControl>
            <HStack justify="space-between" align="start" spacing={6}>
              <VStack align="start" spacing={1}>
                <FormLabel htmlFor="default-roast-public" mb={0} fontWeight="semibold">
                  Make new roasts public by default
                </FormLabel>
                <FormHelperText mt={0}>
                  Public roasts get a shareable link anyone can open. You can still change each roast individually.
                </FormHelperText>
              </VStack>
              <Switch
                id="default-roast-public"
                size="lg"
                colorScheme="fire"
                isChecked={checked}
                isDisabled={mutation.isPending}
                onChange={(e) => mutation.mutate(e.target.checked)}
              />
            </HStack>
          </FormControl>
        </GlassCard>
      </VStack>
    </PageWrapper>
  );
}
