import { ChakraProvider } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderResult } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';
import { HelmetProvider } from 'react-helmet-async';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { vi } from 'vitest';
import { AuthContext, type AuthContextValue } from '../context/authContextValue';
import theme from '../theme';
import type { UserResponse } from '../types';

export const testUser: UserResponse = {
  id: 1,
  githubUsername: 'machan',
  displayName: 'Machan',
  avatarUrl: null,
  defaultRoastPublic: false,
  createdAt: '2026-01-01T00:00:00Z',
};

/** Auth context value with sensible (unauthenticated, loaded) defaults and spy actions. */
export function createMockAuth(overrides: Partial<AuthContextValue> = {}): AuthContextValue {
  const user = overrides.user !== undefined ? overrides.user : null;
  return {
    user,
    isLoading: false,
    isAuthenticated: user !== null,
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
    completeLogin: vi.fn().mockResolvedValue(testUser),
    setUser: vi.fn(),
    refreshUser: vi.fn().mockResolvedValue(user),
    ...overrides,
  };
}

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: Infinity, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{`${location.pathname}${location.search}`}</div>;
}

export interface RenderWithProvidersOptions {
  /** Initial URL for the MemoryRouter. */
  route?: string;
  /** Route pattern for `ui` (enables useParams); defaults to "*". */
  path?: string;
  /** Mocked auth context overrides; `null` renders without any AuthContext provider. */
  auth?: Partial<AuthContextValue> | null;
  /** Use a custom auth provider instead of the mock (e.g. the real AuthProvider). */
  authWrapper?: (children: ReactNode) => ReactElement;
  queryClient?: QueryClient;
}

export interface RenderWithProvidersResult extends RenderResult {
  queryClient: QueryClient;
  auth: AuthContextValue | null;
}

/**
 * Renders `ui` inside Helmet + Chakra (app theme) + QueryClient (no retries) + MemoryRouter + auth.
 * A `data-testid="location"` probe exposes the current pathname + search for navigation assertions.
 */
export function renderWithProviders(ui: ReactElement, options: RenderWithProvidersOptions = {}): RenderWithProvidersResult {
  const { route = '/', path = '*', authWrapper } = options;
  const queryClient = options.queryClient ?? createTestQueryClient();
  const auth = options.auth === null || authWrapper ? null : createMockAuth(options.auth ?? {});

  const routes = (
    <>
      <Routes>
        <Route path={path} element={ui} />
        {path !== '*' && <Route path="*" element={null} />}
      </Routes>
      <LocationProbe />
    </>
  );

  let content: ReactElement = routes;
  if (authWrapper) {
    content = authWrapper(routes);
  } else if (auth) {
    content = <AuthContext.Provider value={auth}>{routes}</AuthContext.Provider>;
  }

  const result = render(
    <HelmetProvider>
      <ChakraProvider theme={theme}>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={[route]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>{content}</MemoryRouter>
        </QueryClientProvider>
      </ChakraProvider>
    </HelmetProvider>,
  );
  return { ...result, queryClient, auth };
}
