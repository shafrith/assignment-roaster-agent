import { act, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { renderWithProviders } from '../../test/utils';
import type { SubmissionStatus } from '../../types/api';
import { LOADING_LINES } from './loadingLines';
import { RoastStatusLoader } from './RoastStatusLoader';

function activeStep(): HTMLElement | undefined {
  const list = screen.getByRole('list', { name: 'Roast progress' });
  return within(list)
    .getAllByRole('listitem')
    .find((item) => item.getAttribute('aria-current') === 'step');
}

describe('RoastStatusLoader', () => {
  describe('line rotation', () => {
    beforeEach(() => {
      vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] });
    });
    afterEach(() => {
      vi.useRealTimers();
    });

    it('rotates loading lines every intervalMs and wraps around', async () => {
      const lines = ['first line', 'second line', 'third line'];
      renderWithProviders(<RoastStatusLoader status="analyzing" lines={lines} intervalMs={1000} />);
      expect(screen.getByTestId('loading-line')).toHaveTextContent('first line');

      act(() => {
        vi.advanceTimersByTime(999);
      });
      expect(screen.getByTestId('loading-line')).toHaveTextContent('first line');

      act(() => {
        vi.advanceTimersByTime(1);
      });
      expect(await screen.findByText('second line')).toBeInTheDocument();

      act(() => {
        vi.advanceTimersByTime(2000);
      });
      expect(await screen.findByText('first line')).toBeInTheDocument();
    });

    it('defaults to the built-in Tanglish lines with a 2500ms interval', async () => {
      renderWithProviders(<RoastStatusLoader status="pending" />);
      expect(screen.getByTestId('loading-line')).toHaveTextContent(LOADING_LINES[0]);
      act(() => {
        vi.advanceTimersByTime(2500);
      });
      expect(await screen.findByText(LOADING_LINES[1])).toBeInTheDocument();
    });

    it('does not rotate with a single line', () => {
      renderWithProviders(<RoastStatusLoader status="pending" lines={['only']} intervalMs={10} />);
      act(() => {
        vi.advanceTimersByTime(100);
      });
      expect(screen.getByTestId('loading-line')).toHaveTextContent('only');
    });
  });

  it.each<[SubmissionStatus, string]>([
    ['pending', 'Analyzing'],
    ['analyzing', 'Analyzing'],
    ['roasting', 'Roasting'],
    ['completed', 'Done'],
  ])('status %s marks %s as the current step', (status, label) => {
    renderWithProviders(<RoastStatusLoader status={status} />);
    expect(activeStep()).toHaveTextContent(label);
    const current = screen.getByRole('list', { name: 'Roast progress' }).querySelectorAll('[aria-current="step"]');
    expect(current).toHaveLength(1);
  });

  it('shows the repo label', () => {
    renderWithProviders(<RoastStatusLoader status="roasting" repoLabel="machan/genai-hw" />);
    expect(screen.getByTestId('roast-status-loader')).toHaveTextContent('machan/genai-hw');
  });
});
