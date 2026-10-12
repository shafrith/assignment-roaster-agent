import { Avatar, Button, Divider, HStack, Heading, Icon, Stack, Text, VStack } from '@chakra-ui/react';
import { FaGithub } from 'react-icons/fa';
import { FiCalendar, FiSettings } from 'react-icons/fi';
import { Link as RouterLink } from 'react-router-dom';
import { LogoutButton } from '../components/auth/LogoutButton';
import { GlassCard } from '../components/ui/GlassCard';
import { PageWrapper } from '../components/ui/PageWrapper';
import { useAuth } from '../hooks/useAuth';

function formatMemberSince(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
}

export default function ProfilePage() {
  const { user } = useAuth();
  if (!user) return null;

  const name = user.displayName ?? user.githubUsername;
  const githubUrl = `https://github.com/${encodeURIComponent(user.githubUsername)}`;

  return (
    <PageWrapper>
      <GlassCard disableHover maxW="2xl" mx="auto" p={{ base: 6, md: 10 }}>
        <Stack direction={{ base: 'column', sm: 'row' }} spacing={6} align="center">
          <Avatar
            size="2xl"
            name={name}
            src={user.avatarUrl ?? undefined}
            bg="fire.500"
            borderWidth="3px"
            borderColor="fire.400"
          />
          <VStack align={{ base: 'center', sm: 'start' }} spacing={1} textAlign={{ base: 'center', sm: 'left' }}>
            <Heading size="lg">{name}</Heading>
            <Text color="accent" fontWeight="semibold">
              @{user.githubUsername}
            </Text>
            <HStack color="text.muted" fontSize="sm" pt={1}>
              <Icon as={FiCalendar} />
              <Text>Member since {formatMemberSince(user.createdAt)}</Text>
            </HStack>
          </VStack>
        </Stack>

        <Divider my={6} borderColor="border.glass" />

        <Stack direction={{ base: 'column', sm: 'row' }} spacing={3}>
          <Button
            as="a"
            href={githubUrl}
            target="_blank"
            rel="noopener noreferrer"
            leftIcon={<FaGithub />}
            variant="outline"
          >
            GitHub profile
          </Button>
          <Button as={RouterLink} to="/settings" leftIcon={<FiSettings />} variant="ghost">
            Settings
          </Button>
          <LogoutButton colorScheme="red" />
        </Stack>
      </GlassCard>
    </PageWrapper>
  );
}
