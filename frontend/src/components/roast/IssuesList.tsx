import { Badge, Box, Code, HStack, Heading, Text, VStack, Wrap } from '@chakra-ui/react';
import { SEVERITY_BADGE, SEVERITY_ORDER, formatCategory } from '../../lib/format';
import type { RoastIssue, Severity } from '../../types/api';

export interface IssuesListProps {
  issues: RoastIssue[];
}

function groupBySeverity(issues: RoastIssue[]): [Severity, RoastIssue[]][] {
  return SEVERITY_ORDER.map((severity): [Severity, RoastIssue[]] => [
    severity,
    issues.filter((issue) => issue.severity === severity),
  ]).filter(([, group]) => group.length > 0);
}

/** Issues grouped by severity (critical → low). */
export function IssuesList({ issues }: IssuesListProps) {
  const groups = groupBySeverity(issues);
  return (
    <VStack align="stretch" spacing={4}>
      <Heading as="h3" size="md">
        Problems list
      </Heading>
      {groups.length === 0 && <Text color="text.muted">Issues onnum illa! Nambave mudiyala</Text>}
      {groups.map(([severity, group]) => (
        <VStack key={severity} align="stretch" spacing={2} data-testid={`issues-${severity}`}>
          <HStack>
            <Badge {...SEVERITY_BADGE[severity]} textTransform="uppercase">
              {severity}
            </Badge>
            <Text fontSize="sm" color="text.muted">
              {group.length} issue{group.length === 1 ? '' : 's'}
            </Text>
          </HStack>
          {group.map((issue, index) => (
            <Box
              key={`${severity}-${index}`}
              p={3}
              borderRadius="lg"
              borderWidth="1px"
              borderColor="border.subtle"
              borderLeftWidth="3px"
              borderLeftColor={SEVERITY_BADGE[severity].colorScheme === 'brand' ? 'brand.500' : 'gray.300'}
              bg="bg.surface"
            >
              <Wrap spacing={2} mb={1} align="center">
                <Badge {...SEVERITY_BADGE[severity]}>
                  {severity}
                </Badge>
                <Badge variant="outline" colorScheme="gray" textTransform="none">
                  {formatCategory(issue.category)}
                </Badge>
                {issue.file && (
                  <Code fontFamily="mono" fontSize="xs" wordBreak="break-all">
                    {issue.file}
                  </Code>
                )}
              </Wrap>
              <Text>{issue.message}</Text>
            </Box>
          ))}
        </VStack>
      ))}
    </VStack>
  );
}

export default IssuesList;
