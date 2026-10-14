import { Tag, TagLabel, Tooltip, Wrap, WrapItem } from '@chakra-ui/react';
import type { AnalysisView } from '../../types/api';

export interface AnalysisChipsProps {
  analysis: AnalysisView;
  /** Max languages to show. */
  maxLanguages?: number;
}

function topLanguages(languages: Record<string, number>, max: number): { name: string; percent: number }[] {
  const entries = Object.entries(languages);
  const total = entries.reduce((sum, [, bytes]) => sum + bytes, 0);
  return entries
    .sort(([, a], [, b]) => b - a)
    .slice(0, max)
    .map(([name, bytes]) => ({ name, percent: total > 0 ? Math.round((bytes / total) * 100) : 0 }));
}

function check(value: boolean): string {
  return value ? '✓' : '✗';
}

export function AnalysisChips({ analysis, maxLanguages = 5 }: AnalysisChipsProps) {
  const languages = topLanguages(analysis.languages, maxLanguages);
  return (
    <Wrap spacing={2} data-testid="analysis-chips">
      {languages.map((lang) => (
        <WrapItem key={lang.name}>
          <Tag colorScheme="brand" variant="subtle" borderRadius="full">
            <TagLabel>
              {lang.name} {lang.percent}%
            </TagLabel>
          </Tag>
        </WrapItem>
      ))}
      <WrapItem>
        <Tag colorScheme="gray" variant="subtle" borderRadius="full">
          <TagLabel> {analysis.fileCount} files</TagLabel>
        </Tag>
      </WrapItem>
      <WrapItem>
        <Tag colorScheme="gray" variant="subtle" borderRadius="full">
          <TagLabel> {analysis.commitCount} commits</TagLabel>
        </Tag>
      </WrapItem>
      <WrapItem>
        <Tag colorScheme={analysis.hasReadme ? 'brand' : 'gray'} variant={analysis.hasReadme ? 'subtle' : 'outline'} borderRadius="full">
          <TagLabel>README {check(analysis.hasReadme)}</TagLabel>
        </Tag>
      </WrapItem>
      <WrapItem>
        <Tag colorScheme={analysis.hasTests ? 'brand' : 'gray'} variant={analysis.hasTests ? 'subtle' : 'outline'} borderRadius="full">
          <TagLabel>Tests {check(analysis.hasTests)}</TagLabel>
        </Tag>
      </WrapItem>
      <WrapItem>
        <Tag colorScheme={analysis.hasDependencyFile ? 'brand' : 'gray'} variant={analysis.hasDependencyFile ? 'subtle' : 'outline'} borderRadius="full">
          <TagLabel>Deps {check(analysis.hasDependencyFile)}</TagLabel>
        </Tag>
      </WrapItem>
      {analysis.hasEnvFileCommitted && (
        <WrapItem>
          <Tooltip label="Un .env file repo-la commit aayirukku. Udane remove pannu, keys rotate pannu!" hasArrow>
            <Tag colorScheme="brand" variant="solid" borderRadius="full">
              <TagLabel> .env committed</TagLabel>
            </Tag>
          </Tooltip>
        </WrapItem>
      )}
      {analysis.secretsFoundCount !== undefined && analysis.secretsFoundCount > 0 && (
        <WrapItem>
          <Tooltip label="Possible secrets kandupidichom. Rotate pannu machan!" hasArrow>
            <Tag colorScheme="brand" variant="solid" borderRadius="full">
              <TagLabel>
                {analysis.secretsFoundCount} secret{analysis.secretsFoundCount === 1 ? '' : 's'} found
              </TagLabel>
            </Tag>
          </Tooltip>
        </WrapItem>
      )}
    </Wrap>
  );
}

export default AnalysisChips;
