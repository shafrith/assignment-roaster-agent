import { Badge } from '@chakra-ui/react';
import { STATUS_COLOR_SCHEME, STATUS_LABEL } from '../../lib/format';
import type { SubmissionStatus } from '../../types/api';

export interface StatusBadgeProps {
  status: SubmissionStatus;
}

export function StatusBadge({ status }: StatusBadgeProps) {
  return (
    <Badge colorScheme={STATUS_COLOR_SCHEME[status]} variant="subtle" borderRadius="full" px={2}>
      {STATUS_LABEL[status]}
    </Badge>
  );
}

export default StatusBadge;
