import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { INVALID_GITHUB_URL_MESSAGE } from '../../lib/githubUrl';
import { roastService } from '../../services/roastService';
import { makeAxiosError, makeRoastStatus } from '../../test/fixtures';
import { renderWithProviders } from '../../test/utils';
import { ROAST_FORM_HINT, RoastForm } from './RoastForm';

function renderForm() {
  return renderWithProviders(<RoastForm />, { route: '/', path: '/' });
}

describe('RoastForm', () => {
  it('shows the no-login hint and disables submit while empty', () => {
    renderForm();
    expect(screen.getByText(ROAST_FORM_HINT)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Roast Me' })).toBeDisabled();
  });

  it('shows the validation error on blur for an invalid URL', async () => {
    const create = vi.spyOn(roastService, 'create');
    renderForm();
    const input = screen.getByLabelText('GitHub repo URL');
    await userEvent.type(input, 'https://gitlab.com/a/b');
    expect(screen.queryByText(INVALID_GITHUB_URL_MESSAGE)).not.toBeInTheDocument();
    await userEvent.tab();
    expect(screen.getByText(INVALID_GITHUB_URL_MESSAGE)).toBeInTheDocument();
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(screen.queryByText(ROAST_FORM_HINT)).not.toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
  });

  it('shows the validation error on submit and does not call the API', async () => {
    const create = vi.spyOn(roastService, 'create');
    renderForm();
    await userEvent.type(screen.getByLabelText('GitHub repo URL'), 'not a url{Enter}');
    expect(screen.getByText(INVALID_GITHUB_URL_MESSAGE)).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
  });

  it('valid submit creates the roast (trimmed) and navigates to /r/:shareSlug', async () => {
    const create = vi
      .spyOn(roastService, 'create')
      .mockResolvedValue(makeRoastStatus({ shareSlug: 'xYz_42', status: 'pending', roast: null, analysis: null }));
    renderForm();
    await userEvent.type(screen.getByLabelText('GitHub repo URL'), '  https://github.com/machan/genai-hw  ');
    await userEvent.click(screen.getByRole('button', { name: 'Roast Me' }));

    expect(create).toHaveBeenCalledWith({ repoUrl: 'https://github.com/machan/genai-hw' });
    await waitFor(() => expect(screen.getByTestId('location')).toHaveTextContent(/^\/r\/xYz_42$/));
  });

  it('shows the backend detail on 429 and clears it when the user edits the URL', async () => {
    vi.spyOn(roastService, 'create').mockRejectedValue(
      makeAxiosError(429, { detail: 'Innaikku 5 roast aachu machan, naalaikku vaa 😴' }),
    );
    renderForm();
    const input = screen.getByLabelText('GitHub repo URL');
    await userEvent.type(input, 'https://github.com/a/b');
    await userEvent.click(screen.getByRole('button', { name: 'Roast Me' }));

    const alert = await screen.findByTestId('create-error');
    expect(alert).toHaveTextContent('Innaikku 5 roast aachu machan, naalaikku vaa 😴');
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/$/);

    await userEvent.type(input, 'c');
    await waitFor(() => expect(screen.queryByTestId('create-error')).not.toBeInTheDocument());
  });

  it('shows the backend detail on 400', async () => {
    vi.spyOn(roastService, 'create').mockRejectedValue(makeAxiosError(400, { detail: 'Repo private-a irukku 🔒' }));
    renderForm();
    await userEvent.type(screen.getByLabelText('GitHub repo URL'), 'https://github.com/a/b{Enter}');
    expect(await screen.findByTestId('create-error')).toHaveTextContent('Repo private-a irukku 🔒');
  });
});
