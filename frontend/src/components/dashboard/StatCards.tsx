import { SimpleGrid, Stat, StatHelpText, StatLabel, StatNumber, Text } from '@chakra-ui/react';
import { formatScore } from '../../lib/format';
import { computeStats } from '../../lib/stats';
import type { SubmissionListItem } from '../../types/api';
import { GlassCard } from '../ui/GlassCard';

export interface StatCardsProps {
  /** Items on the current page (avg/best/worst computed from these). */
  items: SubmissionListItem[];
  /** Overall total from the paginated response. */
  total: number;
}

function display(value: number | null): string {
  return value === null ? '—' : `${formatScore(value)}/10`;
}

export function StatCards({ items, total }: StatCardsProps) {
  const stats = computeStats(items, total);
  const cards = [
    { label: 'Total roasts', value: String(stats.total), help: 'All time', emoji: '🔥' },
    { label: 'Avg score', value: display(stats.average), help: 'This page', emoji: '📊' },
    { label: 'Best', value: display(stats.best), help: 'This page', emoji: '🏆' },
    { label: 'Worst', value: display(stats.worst), help: 'This page', emoji: '💀' },
  ];
  return (
    <SimpleGrid columns={{ base: 2, md: 4 }} spacing={4} data-testid="stat-cards">
      {cards.map((card) => (
        <GlassCard key={card.label} p={4}>
          <Stat>
            <StatLabel color="text.muted">
              <Text as="span" aria-hidden="true">
                {card.emoji}{' '}
              </Text>
              {card.label}
            </StatLabel>
            <StatNumber fontSize={{ base: 'xl', md: '2xl' }}>{card.value}</StatNumber>
            <StatHelpText mb={0} fontSize="xs">
              {card.help}
            </StatHelpText>
          </Stat>
        </GlassCard>
      ))}
    </SimpleGrid>
  );
}

export default StatCards;
