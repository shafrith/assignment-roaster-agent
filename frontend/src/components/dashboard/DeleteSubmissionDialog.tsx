import {
  AlertDialog,
  AlertDialogBody,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  Button,
  Code,
} from '@chakra-ui/react';
import { useRef } from 'react';

export interface DeleteSubmissionDialogProps {
  isOpen: boolean;
  repoLabel: string;
  isDeleting: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function DeleteSubmissionDialog({ isOpen, repoLabel, isDeleting, onCancel, onConfirm }: DeleteSubmissionDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  return (
    <AlertDialog isOpen={isOpen} leastDestructiveRef={cancelRef} onClose={onCancel} isCentered>
      <AlertDialogOverlay>
        <AlertDialogContent mx={4}>
          <AlertDialogHeader fontSize="lg" fontWeight="bold">
            Roast-a delete pannanuma? 🗑️
          </AlertDialogHeader>
          <AlertDialogBody>
            <Code>{repoLabel}</Code> roast permanent-a poyidum. Public link-um velai seyyadhu.
          </AlertDialogBody>
          <AlertDialogFooter gap={3}>
            <Button ref={cancelRef} variant="ghost" onClick={onCancel} isDisabled={isDeleting}>
              Venaam
            </Button>
            <Button colorScheme="red" onClick={onConfirm} isLoading={isDeleting}>
              Delete
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialogOverlay>
    </AlertDialog>
  );
}

export default DeleteSubmissionDialog;
