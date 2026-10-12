import {
  Avatar,
  Box,
  Button,
  Container,
  Drawer,
  DrawerBody,
  DrawerCloseButton,
  DrawerContent,
  DrawerHeader,
  DrawerOverlay,
  Flex,
  HStack,
  IconButton,
  Link,
  Menu,
  MenuButton,
  MenuDivider,
  MenuGroup,
  MenuItem,
  MenuList,
  Skeleton,
  Spacer,
  Text,
  VStack,
  useDisclosure,
} from '@chakra-ui/react';
import type { ReactNode } from 'react';
import { FaGithub } from 'react-icons/fa';
import { FiLogOut, FiMenu, FiSettings, FiUser } from 'react-icons/fi';
import { NavLink as RouterNavLink, Link as RouterLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../hooks/useAuth';
import { MotionBox } from '../../lib/motion';

interface NavItem {
  label: string;
  to: string;
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', to: '/dashboard' },
  { label: 'New Roast', to: '/roast/new' },
];

interface NavItemLinkProps {
  item: NavItem;
  onNavigate?: () => void;
}

function NavItemLink({ item, onNavigate }: NavItemLinkProps) {
  return (
    <MotionBox whileHover={{ y: -2 }} whileTap={{ scale: 0.97 }}>
      <Link
        as={RouterNavLink}
        to={item.to}
        onClick={onNavigate}
        display="block"
        px={3}
        py={2}
        borderRadius="full"
        fontWeight="medium"
        color="text.muted"
        _hover={{ color: 'accent', bg: 'bg.glass' }}
        _activeLink={{ color: 'accent', bg: 'bg.glass' }}
      >
        {item.label}
      </Link>
    </MotionBox>
  );
}

function Logo() {
  return (
    <Link as={RouterLink} to="/" _hover={{ opacity: 0.9 }} aria-label="Assignment Roaster home">
      <Text
        as="span"
        fontFamily="heading"
        fontWeight="bold"
        fontSize={{ base: 'md', md: 'xl' }}
        textStyle="fireGradient"
      >
        Assignment Roaster
      </Text>{' '}
      <Text as="span" fontSize={{ base: 'md', md: 'xl' }}>
        🔥
      </Text>
    </Link>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  if (!user) return null;

  const name = user.displayName ?? user.githubUsername;

  return (
    <Menu placement="bottom-end" isLazy>
      <MenuButton
        as={IconButton}
        aria-label="Open user menu"
        variant="ghost"
        borderRadius="full"
        icon={<Avatar size="sm" name={name} src={user.avatarUrl ?? undefined} bg="fire.500" />}
      />
      <MenuList bg="bg.surface" borderColor="border.glass">
        <MenuGroup title={`@${user.githubUsername}`}>
          <MenuItem icon={<FiUser />} onClick={() => navigate('/profile')}>
            Profile
          </MenuItem>
          <MenuItem icon={<FiSettings />} onClick={() => navigate('/settings')}>
            Settings
          </MenuItem>
        </MenuGroup>
        <MenuDivider />
        <MenuItem icon={<FiLogOut />} color="red.300" onClick={() => void logout()}>
          Logout
        </MenuItem>
      </MenuList>
    </Menu>
  );
}

function LoginNavButton() {
  const { login } = useAuth();
  return (
    <Button size="sm" leftIcon={<FaGithub />} onClick={login}>
      Login
    </Button>
  );
}

export interface AppShellProps {
  children: ReactNode;
}

/** Top-level layout: sticky glass navbar, avatar menu, mobile drawer. */
export function AppShell({ children }: AppShellProps) {
  const { isAuthenticated, isLoading } = useAuth();
  const drawer = useDisclosure();

  let rightSide: ReactNode;
  if (isLoading) {
    rightSide = <Skeleton boxSize={8} borderRadius="full" />;
  } else if (isAuthenticated) {
    rightSide = <UserMenu />;
  } else {
    rightSide = <LoginNavButton />;
  }

  return (
    <Flex direction="column" minH="100vh" bg="bg.canvas">
      <Box
        as="header"
        position="sticky"
        top={0}
        zIndex="sticky"
        backdropFilter="blur(16px)"
        bg="bg.glass"
        borderBottom="1px solid"
        borderColor="border.glass"
      >
        <Container maxW="6xl" px={4}>
          <Flex h={16} align="center" gap={2}>
            {isAuthenticated && (
              <IconButton
                aria-label="Open navigation"
                icon={<FiMenu />}
                variant="ghost"
                display={{ base: 'inline-flex', md: 'none' }}
                onClick={drawer.onOpen}
              />
            )}
            <Logo />
            <Spacer />
            {isAuthenticated && (
              <HStack
                as="nav"
                spacing={2}
                aria-label="Main navigation"
                display={{ base: 'none', md: 'flex' }}
              >
                {NAV_ITEMS.map((item) => (
                  <NavItemLink key={item.to} item={item} />
                ))}
              </HStack>
            )}
            <Box data-testid="avatar-area" ml={2}>
              {rightSide}
            </Box>
          </Flex>
        </Container>
      </Box>

      <Drawer isOpen={drawer.isOpen} placement="left" onClose={drawer.onClose}>
        <DrawerOverlay backdropFilter="blur(4px)" />
        <DrawerContent bg="bg.surface">
          <DrawerCloseButton />
          <DrawerHeader>
            <Logo />
          </DrawerHeader>
          <DrawerBody>
            <VStack as="nav" align="stretch" spacing={1} aria-label="Mobile navigation">
              {NAV_ITEMS.map((item) => (
                <NavItemLink key={item.to} item={item} onNavigate={drawer.onClose} />
              ))}
              <NavItemLink item={{ label: 'Profile', to: '/profile' }} onNavigate={drawer.onClose} />
              <NavItemLink item={{ label: 'Settings', to: '/settings' }} onNavigate={drawer.onClose} />
            </VStack>
          </DrawerBody>
        </DrawerContent>
      </Drawer>

      <Container as="main" maxW="6xl" px={4} py={{ base: 6, md: 10 }} flex="1">
        {children}
      </Container>

      <Box as="footer" borderTop="1px solid" borderColor="border.glass" py={6}>
        <Container maxW="6xl" px={4}>
          <Text textAlign="center" fontSize="sm" color="text.muted">
            Made with ❤️ &amp; 🌶️ for the GenAI community
          </Text>
        </Container>
      </Box>
    </Flex>
  );
}

export default AppShell;
