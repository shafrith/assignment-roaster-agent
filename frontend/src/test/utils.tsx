import { ChakraProvider } from '@chakra-ui/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderResult } from '@testing-library/react';
import type { ReactElement } from 'react';
import { HelmetProvider } from 'react-helmet-async';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import theme from '../theme';

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
  queryClient?: QueryClient;
}

export interface RenderWithProvidersResult extends RenderResult {
  queryClient: QueryClient;
}

/**
 * Renders `ui` inside Helmet + Chakra (app theme) + QueryClient (no retries) + MemoryRouter.
 * A `data-testid="location"` probe exposes the current pathname + search for navigation assertions.
 */
export function renderWithProviders(ui: ReactElement, options: RenderWithProvidersOptions = {}): RenderWithProvidersResult {
  const { route = '/', path = '*' } = options;
  const queryClient = options.queryClient ?? createTestQueryClient();

  const result = render(
    <HelmetProvider>
      <ChakraProvider theme={theme}>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={[route]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
            <Routes>
              <Route path={path} element={ui} />
              {path !== '*' && <Route path="*" element={null} />}
            </Routes>
            <LocationProbe />
          </MemoryRouter>
        </QueryClientProvider>
      </ChakraProvider>
    </HelmetProvider>,
  );
  return { ...result, queryClient };
}
