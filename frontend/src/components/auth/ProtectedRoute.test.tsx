import { screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { consumeReturnTo } from '../../lib/returnTo';
import { renderWithProviders, testUser } from '../../test/utils';
import { ProtectedRoute } from './ProtectedRoute';

const secret = <div>secret dashboard</div>;

describe('ProtectedRoute', () => {
  it('redirects unauthenticated users to /login and remembers where they were going', () => {
    renderWithProviders(<ProtectedRoute>{secret}</ProtectedRoute>, { route: '/roasts/5?x=1', path: '/roasts/:id' });
    expect(screen.queryByText('secret dashboard')).not.toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/login$/);
    expect(consumeReturnTo()).toBe('/roasts/5?x=1');
  });

  it('shows a spinner while auth is loading', () => {
    renderWithProviders(<ProtectedRoute>{secret}</ProtectedRoute>, {
      route: '/dashboard',
      path: '/dashboard',
      auth: { isLoading: true },
    });
    expect(screen.queryByText('secret dashboard')).not.toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/dashboard$/);
  });

  it('renders children when authenticated', () => {
    renderWithProviders(<ProtectedRoute>{secret}</ProtectedRoute>, {
      route: '/dashboard',
      path: '/dashboard',
      auth: { user: testUser },
    });
    expect(screen.getByText('secret dashboard')).toBeInTheDocument();
  });
});
