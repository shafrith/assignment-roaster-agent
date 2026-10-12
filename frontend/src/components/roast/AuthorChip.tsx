import { Avatar, HStack, Link, Text } from '@chakra-ui/react';

export interface AuthorChipProps {
  githubUsername: string;
  avatarUrl: string | null;
}

export function AuthorChip({ githubUsername, avatarUrl }: AuthorChipProps) {
  return (
    <HStack spacing={2} layerStyle="glass" px={3} py={1.5} borderRadius="full" w="fit-content">
      <Avatar size="xs" name={githubUsername} src={avatarUrl ?? undefined} />
      <Text fontSize="sm" color="text.muted">
        Roasted repo by{' '}
        <Link
          href={`https://github.com/${encodeURIComponent(githubUsername)}`}
          isExternal
          rel="noopener noreferrer"
          fontWeight="semibold"
          color="accent"
        >
          @{githubUsername}
        </Link>
      </Text>
    </HStack>
  );
}

export default AuthorChip;
