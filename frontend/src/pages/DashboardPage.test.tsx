import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { submissionService } from '../services/submissionService';
import { makeAxiosError, makeListItem, makePage } from '../test/fixtures';
import { renderWithProviders, testUser } from '../test/utils';
import DashboardPage from './DashboardPage';

function renderPage() {
  return renderWithProviders(<DashboardPage />, { route: '/dashboard', path: '/dashboard', auth: { user: testUser } });
}

const items = [
  makeListItem({ id: 1, repoName: 'repo-1', score: 3, verdictTitle: 'Disaster da', isPublic: true }),
  makeListItem({ id: 2, repoName: 'repo-2', score: 8, verdictTitle: 'Not bad machan' }),
  makeListItem({ id: 3, repoName: 'repo-3', score: null, status: 'roasting', verdictTitle: null }),
];

describe('DashboardPage', () => {
  it('shows the skeleton while loading', () => {
    vi.spyOn(submissionService, 'list').mockReturnValue(new Promise(() => undefined));
    renderPage();
    expect(screen.getByTestId('dashboard-skeleton')).toBeInTheDocument();
  });

  it('shows the empty state when there are no roasts', async () => {
    vi.spyOn(submissionService, 'list').mockResolvedValue(makePage([], 0));
    renderPage();
    const empty = await screen.findByTestId('empty-state');
    expect(empty).toHaveTextContent('Innum oru roast-um illa! Mudhal repo-va kudu 👇');
    expect(within(empty).getByRole('link', { name: 'Roast Me 🔥' })).toHaveAttribute('href', '/roast/new');
  });

  it('renders stats, table and mobile cards', async () => {
    const list = vi.spyOn(submissionService, 'list').mockResolvedValue(makePage(items, 3));
    renderPage();

    const stats = await screen.findByTestId('stat-cards');
    expect(list).toHaveBeenCalledWith(1, 10);
    expect(stats).toHaveTextContent('Total roasts3');
    expect(stats).toHaveTextContent('Avg score5.5/10');
    expect(stats).toHaveTextContent('Best8/10');
    expect(stats).toHaveTextContent('Worst3/10');

    const table = screen.getByTestId('submission-table');
    const cards = screen.getByTestId('submission-cards');
    for (const container of [table, cards]) {
      expect(within(container).getByText('machan/repo-1')).toBeInTheDocument();
      expect(within(container).getByText('machan/repo-2')).toBeInTheDocument();
      expect(within(container).getByText('machan/repo-3')).toBeInTheDocument();
      expect(within(container).getByText('3/10')).toBeInTheDocument();
    }
    expect(within(table).getByText('Disaster da')).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /Delete roast for/, hidden: true })).toHaveLength(6);
    // Single page → no pagination.
    expect(screen.queryByRole('button', { name: 'Next' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Prev' })).not.toBeInTheDocument();
  });

  it('clicking a row opens the roast', async () => {
    vi.spyOn(submissionService, 'list').mockResolvedValue(makePage(items, 3));
    renderPage();
    const rows = await screen.findAllByLabelText('Open roast for machan/repo-2');
    await userEvent.click(rows[0]);
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/roasts\/2$/);
  });

  it('delete: cancel with "Venaam", confirm with "Delete" calls remove and refetches', async () => {
    const list = vi
      .spyOn(submissionService, 'list')
      .mockResolvedValueOnce(makePage(items, 3))
      .mockResolvedValue(makePage(items.slice(1), 2));
    const remove = vi.spyOn(submissionService, 'remove').mockResolvedValue(undefined);
    renderPage();

    const deleteButtons = await screen.findAllByRole('button', { name: 'Delete roast for machan/repo-1', hidden: true });
    expect(deleteButtons).toHaveLength(2);

    // Cancel
    await userEvent.click(deleteButtons[0]);
    let dialog = await screen.findByRole('alertdialog');
    expect(dialog).toHaveTextContent('machan/repo-1');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Venaam' }));
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
    expect(remove).not.toHaveBeenCalled();
    // Delete click must not also navigate to the row.
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/dashboard$/);

    // Confirm
    await userEvent.click(screen.getAllByRole('button', { name: 'Delete roast for machan/repo-1', hidden: true })[1]);
    dialog = await screen.findByRole('alertdialog');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete' }));

    await waitFor(() => expect(remove).toHaveBeenCalledWith(1));
    await waitFor(() => expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('machan/repo-1')).not.toBeInTheDocument());
    expect(list.mock.calls.length).toBeGreaterThanOrEqual(2);
    expect(await screen.findByText('Roast delete aayiduchu 🗑️')).toBeInTheDocument();
  });

  it('delete failure shows the error toast', async () => {
    vi.spyOn(submissionService, 'list').mockResolvedValue(makePage(items, 3));
    vi.spyOn(submissionService, 'remove').mockRejectedValue(makeAxiosError(404, { detail: 'Already gone da' }));
    renderPage();
    await userEvent.click((await screen.findAllByRole('button', { name: 'Delete roast for machan/repo-2' }))[0]);
    await userEvent.click(within(await screen.findByRole('alertdialog')).getByRole('button', { name: 'Delete' }));
    expect(await screen.findByText('Already gone da')).toBeInTheDocument();
  });

  it('shows pagination only when total > pageSize and navigates pages', async () => {
    const page1 = Array.from({ length: 10 }, (_, i) => makeListItem({ id: i + 1, repoName: `p1-${i + 1}` }));
    const page2 = Array.from({ length: 5 }, (_, i) => makeListItem({ id: i + 11, repoName: `p2-${i + 1}` }));
    const list = vi
      .spyOn(submissionService, 'list')
      .mockImplementation(async (page: number) => (page === 1 ? makePage(page1, 15, 1) : makePage(page2, 15, 2)));
    renderPage();

    const next = await screen.findByRole('button', { name: 'Next' });
    const prev = screen.getByRole('button', { name: 'Prev' });
    expect(prev).toBeDisabled();
    expect(next).toBeEnabled();
    expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();

    await userEvent.click(next);
    await waitFor(() => expect(list).toHaveBeenCalledWith(2, 10));
    expect(await screen.findByText('Page 2 of 2')).toBeInTheDocument();
    expect(within(screen.getByTestId('submission-table')).getByText('machan/p2-1')).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Next' })).toBeDisabled());
    expect(screen.getByRole('button', { name: 'Prev' })).toBeEnabled();
  });

  it('shows an error state with Try again', async () => {
    const list = vi.spyOn(submissionService, 'list').mockRejectedValue(makeAxiosError(500, { detail: 'DB thoongudhu' }));
    renderPage();
    expect(await screen.findByText('DB thoongudhu')).toBeInTheDocument();
    list.mockResolvedValue(makePage([], 0));
    await userEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByTestId('empty-state')).toBeInTheDocument();
  });
});
