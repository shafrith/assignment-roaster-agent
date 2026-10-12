import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { renderWithProviders, testUser } from '../test/utils';
import LoginPage from './LoginPage';

describe('LoginPage', () => {
  it.each([
    ['oauth_denied', 'GitHub permission kudukkala pola machan. Roast venumna allow pannu 😅'],
    ['invalid_state', 'Login session expire aayiduchu. Innoru vaati try pannu 🔁'],
    ['github_error', 'GitHub konjam mood-out-la irukku. Konjam apram try pannu 🐙'],
    ['inactive', 'Un account disable pannirukku machan. Admin-a contact pannu 🚫'],
    ['something_else', 'Login-la edho problem machan. Thirumba try pannu 🙏'],
  ])('shows the alert for ?error=%s', (code, message) => {
    renderWithProviders(<LoginPage />, { route: `/login?error=${code}`, path: '/login' });
    expect(screen.getByRole('alert')).toHaveTextContent(message);
  });

  it('shows no alert without an error code, and the button starts the GitHub login', async () => {
    const login = vi.fn();
    renderWithProviders(<LoginPage />, { route: '/login', path: '/login', auth: { login } });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /login with github/i }));
    expect(login).toHaveBeenCalledTimes(1);
  });

  it('redirects authenticated users to /dashboard', () => {
    renderWithProviders(<LoginPage />, { route: '/login', path: '/login', auth: { user: testUser } });
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/dashboard$/);
  });

  it('shows a spinner while auth is loading', () => {
    renderWithProviders(<LoginPage />, { route: '/login', path: '/login', auth: { isLoading: true } });
    expect(screen.getByText('Load aagudhu machan... 🔥')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /login with github/i })).not.toBeInTheDocument();
  });
});
