import { FormControl, FormLabel, HStack, Spinner, Switch, useToast } from '@chakra-ui/react';
import { useToggleVisibility } from '../../hooks/useSubmissions';
import { getErrorMessage } from '../../services/api';

export interface VisibilityToggleProps {
  submissionId: number;
  isPublic: boolean;
}

export function VisibilityToggle({ submissionId, isPublic }: VisibilityToggleProps) {
  const toast = useToast();
  const mutation = useToggleVisibility();
  const switchId = `visibility-${submissionId}`;

  const handleChange = (next: boolean) => {
    mutation.mutate(
      { id: submissionId, isPublic: next },
      {
        onSuccess: () =>
          toast({
            title: next ? 'Ippo public! Share pannu 🌍' : 'Private aayiduchu 🔒',
            status: 'success',
            duration: 2000,
          }),
        onError: (error) => toast({ title: getErrorMessage(error), status: 'error', duration: 4000 }),
      },
    );
  };

  return (
    <FormControl display="flex" alignItems="center" w="auto">
      <HStack spacing={3}>
        <Switch
          id={switchId}
          colorScheme="fire"
          isChecked={isPublic}
          isDisabled={mutation.isPending}
          onChange={(event) => handleChange(event.target.checked)}
        />
        <FormLabel htmlFor={switchId} mb={0} cursor="pointer">
          {isPublic ? '🌍 Public' : '🔒 Private'}
        </FormLabel>
        {mutation.isPending && <Spinner size="xs" aria-label="Updating visibility" />}
      </HStack>
    </FormControl>
  );
}

export default VisibilityToggle;
