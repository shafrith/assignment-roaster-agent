import {
  Box,
  HStack,
  Icon,
  IconButton,
  Table,
  TableContainer,
  Tbody,
  Td,
  Text,
  Th,
  Thead,
  Tooltip,
  Tr,
  VStack,
  useToast,
} from '@chakra-ui/react';
import { useState, type KeyboardEvent, type MouseEvent } from 'react';
import { FiGlobe, FiLock, FiTrash2 } from 'react-icons/fi';
import { useNavigate } from 'react-router-dom';
import { useDeleteSubmission } from '../../hooks/useSubmissions';
import { formatDateTime, formatRelativeTime, formatScore, scoreColorScheme } from '../../lib/format';
import { getErrorMessage } from '../../services/api';
import type { SubmissionListItem } from '../../types/api';
import { GlassCard } from '../ui/GlassCard';
import { DeleteSubmissionDialog } from './DeleteSubmissionDialog';
import { StatusBadge } from './StatusBadge';

export interface SubmissionTableProps {
  items: SubmissionListItem[];
}

function repoLabel(item: SubmissionListItem): string {
  return `${item.repoOwner}/${item.repoName}`;
}

function ScoreText({ score }: { score: number | null }) {
  if (score === null) {
    return <Text color="text.muted">—</Text>;
  }
  return (
    <Text fontWeight="bold" color={`${scoreColorScheme(score)}.300`}>
      {formatScore(score)}/10
    </Text>
  );
}

function VisibilityIcon({ isPublic }: { isPublic: boolean }) {
  const label = isPublic ? 'Public' : 'Private';
  return (
    <Tooltip label={label} hasArrow>
      <Box as="span" display="inline-flex" aria-label={label} role="img">
        <Icon as={isPublic ? FiGlobe : FiLock} color={isPublic ? 'green.300' : 'text.muted'} />
      </Box>
    </Tooltip>
  );
}

/** Desktop table + mobile cards (both rendered; CSS breakpoints toggle visibility). */
export function SubmissionTable({ items }: SubmissionTableProps) {
  const navigate = useNavigate();
  const toast = useToast();
  const deleteMutation = useDeleteSubmission();
  const [pendingDelete, setPendingDelete] = useState<SubmissionListItem | null>(null);

  const open = (item: SubmissionListItem) => navigate(`/roasts/${item.id}`);

  const handleRowKeyDown = (event: KeyboardEvent<HTMLElement>, item: SubmissionListItem) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      open(item);
    }
  };

  const requestDelete = (event: MouseEvent<HTMLButtonElement>, item: SubmissionListItem) => {
    event.stopPropagation();
    setPendingDelete(item);
  };

  const confirmDelete = () => {
    if (!pendingDelete) return;
    deleteMutation.mutate(pendingDelete.id, {
      onSuccess: () => {
        toast({ title: 'Roast delete aayiduchu 🗑️', status: 'success', duration: 2500 });
        setPendingDelete(null);
      },
      onError: (error) => {
        toast({ title: getErrorMessage(error), status: 'error', duration: 4000 });
        setPendingDelete(null);
      },
    });
  };

  const deleteButton = (item: SubmissionListItem) => (
    <IconButton
      aria-label={`Delete roast for ${repoLabel(item)}`}
      icon={<FiTrash2 />}
      size="sm"
      variant="ghost"
      colorScheme="red"
      onClick={(event) => requestDelete(event, item)}
      onKeyDown={(event) => event.stopPropagation()}
    />
  );

  return (
    <>
      <GlassCard disableHover p={0} display={{ base: 'none', md: 'block' }} data-testid="submission-table">
        <TableContainer>
          <Table variant="simple">
            <Thead>
              <Tr>
                <Th>Repo</Th>
                <Th>Status</Th>
                <Th>Score</Th>
                <Th>Verdict</Th>
                <Th>Visibility</Th>
                <Th>Created</Th>
                <Th>
                  <Box as="span" srOnly>
                    Actions
                  </Box>
                </Th>
              </Tr>
            </Thead>
            <Tbody>
              {items.map((item) => (
                <Tr
                  key={item.id}
                  cursor="pointer"
                  tabIndex={0}
                  _hover={{ bg: 'bg.glass' }}
                  _focusVisible={{ outline: '2px solid', outlineColor: 'fire.400' }}
                  onClick={() => open(item)}
                  onKeyDown={(event) => handleRowKeyDown(event, item)}
                  aria-label={`Open roast for ${repoLabel(item)}`}
                >
                  <Td fontFamily="mono" fontSize="sm">
                    {repoLabel(item)}
                  </Td>
                  <Td>
                    <StatusBadge status={item.status} />
                  </Td>
                  <Td>
                    <ScoreText score={item.score} />
                  </Td>
                  <Td maxW="xs" whiteSpace="normal">
                    <Text noOfLines={2}>{item.verdictTitle ?? '—'}</Text>
                  </Td>
                  <Td>
                    <VisibilityIcon isPublic={item.isPublic} />
                  </Td>
                  <Td>
                    <Text fontSize="sm" color="text.muted" title={formatDateTime(item.createdAt)}>
                      {formatRelativeTime(item.createdAt)}
                    </Text>
                  </Td>
                  <Td textAlign="right">{deleteButton(item)}</Td>
                </Tr>
              ))}
            </Tbody>
          </Table>
        </TableContainer>
      </GlassCard>

      <VStack align="stretch" spacing={3} display={{ base: 'flex', md: 'none' }} data-testid="submission-cards">
        {items.map((item) => (
          <GlassCard
            key={item.id}
            p={4}
            cursor="pointer"
            role="link"
            tabIndex={0}
            onClick={() => open(item)}
            onKeyDown={(event: KeyboardEvent<HTMLDivElement>) => handleRowKeyDown(event, item)}
            aria-label={`Open roast for ${repoLabel(item)}`}
          >
            <HStack justify="space-between" align="start" spacing={3}>
              <VStack align="start" spacing={1} minW={0}>
                <Text fontFamily="mono" fontSize="sm" fontWeight="semibold" wordBreak="break-all">
                  {repoLabel(item)}
                </Text>
                {item.verdictTitle && (
                  <Text fontSize="sm" noOfLines={2}>
                    {item.verdictTitle}
                  </Text>
                )}
                <HStack spacing={2}>
                  <StatusBadge status={item.status} />
                  <VisibilityIcon isPublic={item.isPublic} />
                  <Text fontSize="xs" color="text.muted">
                    {formatRelativeTime(item.createdAt)}
                  </Text>
                </HStack>
              </VStack>
              <VStack spacing={1} align="end">
                <ScoreText score={item.score} />
                {deleteButton(item)}
              </VStack>
            </HStack>
          </GlassCard>
        ))}
      </VStack>

      <DeleteSubmissionDialog
        isOpen={pendingDelete !== null}
        repoLabel={pendingDelete ? repoLabel(pendingDelete) : ''}
        isDeleting={deleteMutation.isPending}
        onCancel={() => setPendingDelete(null)}
        onConfirm={confirmDelete}
      />
    </>
  );
}

export default SubmissionTable;
