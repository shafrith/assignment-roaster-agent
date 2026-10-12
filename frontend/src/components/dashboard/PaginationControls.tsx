import { Button, HStack, Text } from '@chakra-ui/react';
import { FiChevronLeft, FiChevronRight } from 'react-icons/fi';

export interface PaginationControlsProps {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
  isFetching?: boolean;
}

export function PaginationControls({ page, pageSize, total, onPageChange, isFetching = false }: PaginationControlsProps) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <HStack justify="space-between" w="full" as="nav" aria-label="Pagination">
      <Button
        size="sm"
        variant="outline"
        leftIcon={<FiChevronLeft aria-hidden="true" />}
        onClick={() => onPageChange(page - 1)}
        isDisabled={page <= 1 || isFetching}
      >
        Prev
      </Button>
      <Text fontSize="sm" color="text.muted">
        Page {page} of {totalPages}
      </Text>
      <Button
        size="sm"
        variant="outline"
        rightIcon={<FiChevronRight aria-hidden="true" />}
        onClick={() => onPageChange(page + 1)}
        isDisabled={page >= totalPages || isFetching}
      >
        Next
      </Button>
    </HStack>
  );
}

export default PaginationControls;
