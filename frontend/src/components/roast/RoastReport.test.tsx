import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { analysisFixture, roastFixture } from '../../test/fixtures';
import { renderWithProviders } from '../../test/utils';
import type { RoastResponse } from '../../types/api';
import { RoastMarkdown } from './RoastMarkdown';
import { RoastReport, type RoastReportProps } from './RoastReport';

const repo = { owner: 'machan', name: 'genai-hw', url: 'https://github.com/machan/genai-hw' };

function renderReport(props: Partial<RoastReportProps> = {}) {
  return renderWithProviders(<RoastReport roast={roastFixture} analysis={analysisFixture} repo={repo} {...props} />);
}

describe('RoastReport', () => {
  it('renders score, verdict, repo, strengths, fix tips and analysis chips', () => {
    renderReport();
    expect(screen.getByTestId('roast-report')).toBeInTheDocument();
    expect(screen.getByLabelText('Score 3.5 out of 10')).toBeInTheDocument();
    expect(screen.getByText('Copy-paste Champion 🏆')).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('machan/genai-hw');
    expect(screen.getByRole('link', { name: /machan\/genai-hw/ })).toHaveAttribute('href', repo.url);
    expect(screen.getByText('Code runs at least once')).toBeInTheDocument();
    expect(screen.getByText('Nice repo name')).toBeInTheDocument();
    expect(screen.getByText('Rotate your keys')).toBeInTheDocument();
    expect(screen.getByText('Add pytest')).toBeInTheDocument();

    const chips = screen.getByTestId('analysis-chips');
    expect(chips).toHaveTextContent('Python 80%');
    expect(chips).toHaveTextContent('42 files');
    expect(chips).toHaveTextContent('.env committed');
    expect(chips).toHaveTextContent('2 secrets found');
  });

  it('groups issues by severity (critical → low) and omits empty groups', () => {
    renderReport();
    const critical = screen.getByTestId('issues-critical');
    expect(within(critical).getByText('2 issues')).toBeInTheDocument();
    expect(critical).toHaveTextContent('API key committed');
    expect(critical).toHaveTextContent('Prompt hardcoded');
    expect(critical).toHaveTextContent('GenAI Practices');
    expect(critical).toHaveTextContent('.env');
    expect(screen.getByTestId('issues-high')).toHaveTextContent('No tests at all');
    expect(screen.getByTestId('issues-low')).toHaveTextContent('README is empty');
    expect(screen.queryByTestId('issues-medium')).not.toBeInTheDocument();

    const order = ['critical', 'high', 'low'].map((s) => screen.getByTestId(`issues-${s}`));
    expect(order[0].compareDocumentPosition(order[1]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(order[1].compareDocumentPosition(order[2]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('shows friendly empty states', () => {
    const empty: RoastResponse = { ...roastFixture, strengths: [], issues: [], fixTips: [] };
    renderReport({ roast: empty, analysis: null });
    expect(screen.getByText('Honestly... onnum kandupidika mudiyala')).toBeInTheDocument();
    expect(screen.getByText('Fix panna onnum illa. Semma!')).toBeInTheDocument();
    expect(screen.getByText('Issues onnum illa! Nambave mudiyala')).toBeInTheDocument();
    expect(screen.queryByTestId('analysis-chips')).not.toBeInTheDocument();
  });

  it('hides the share bar when no share info is given', () => {
    renderReport();
    expect(screen.queryByTestId('share-bar')).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });

  it('renders the share bar when share info is given', () => {
    renderReport({ share: { shareSlug: 'abc123', isPublic: true } });
    expect(screen.getByTestId('share-bar')).toBeInTheDocument();
  });

  it('private roast: share buttons disabled with a lock hint', () => {
    renderReport({ share: { shareSlug: 'abc123', isPublic: false } });
    expect(screen.getByRole('button', { name: 'Copy public roast link' })).toBeDisabled();
    const wa = screen.getByLabelText('Share on WhatsApp');
    const x = screen.getByLabelText('Share on X');
    expect(wa).toHaveAttribute('aria-disabled', 'true');
    expect(wa).not.toHaveAttribute('href');
    expect(x).toHaveAttribute('aria-disabled', 'true');
    expect(x).not.toHaveAttribute('href');
    expect(screen.getByTestId('share-bar')).toHaveTextContent('Private roast');
  });

  it('public roast: share links point at the public URL', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
    renderReport({ share: { shareSlug: 'abc123', isPublic: true } });

    const publicUrl = `${window.location.origin}/r/abc123`;
    const wa = screen.getByLabelText('Share on WhatsApp');
    expect(wa.getAttribute('href')).toContain(encodeURIComponent(publicUrl));
    expect(screen.getByLabelText('Share on X').getAttribute('href')).toContain(encodeURIComponent(publicUrl));
    expect(screen.queryByText(/Private roast/)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Copy public roast link' }));
    expect(writeText).toHaveBeenCalledWith(publicUrl);
    expect(await screen.findByText('Link copy aayiduchu!')).toBeInTheDocument();
  });
});

describe('RoastMarkdown (XSS safety)', () => {
  it('renders markdown formatting', () => {
    renderWithProviders(<RoastMarkdown markdown={'## Title\n\nSome **bold** and `code`.\n\n- item one'} />);
    const md = screen.getByTestId('roast-markdown');
    expect(within(md).getByRole('heading', { name: 'Title' })).toBeInTheDocument();
    expect(within(md).getByText('bold').tagName).toBe('STRONG');
    expect(within(md).getByText('item one')).toBeInTheDocument();
  });

  it('does not render raw HTML elements', () => {
    const evil = [
      '<script>window.__pwned = true</script>',
      '',
      'Hello <img src="x" onerror="window.__pwned = true"> world',
      '',
      '<iframe src="https://evil.com"></iframe>',
      '',
      '<a href="javascript:alert(1)">raw link</a>',
      '',
      '![tracker](https://evil.com/pixel.png)',
    ].join('\n');
    renderWithProviders(<RoastMarkdown markdown={evil} />);
    const md = screen.getByTestId('roast-markdown');

    expect(md.querySelector('script')).toBeNull();
    expect(md.querySelector('img')).toBeNull();
    expect(md.querySelector('iframe')).toBeNull();
    expect(md.querySelector('[onerror]')).toBeNull();
    expect(md.querySelector('a')).toBeNull();
    expect(md).toHaveTextContent('Hello');
    expect((window as Window & { __pwned?: boolean }).__pwned).toBeUndefined();
  });

  it('unwraps every markdown link to plain text (no phishing links from LLM output)', () => {
    renderWithProviders(
      <RoastMarkdown
        markdown={
          '[claim your certificate](https://evil.example/login), [click me](javascript:alert(1)), ' +
          '[even github](https://github.com/attacker/gist) and <https://evil.example/autolink>'
        }
      />,
    );
    const md = screen.getByTestId('roast-markdown');
    expect(md.querySelector('a')).toBeNull();
    expect(md.querySelector('[href]')).toBeNull();
    expect(md).toHaveTextContent('claim your certificate');
    expect(md).toHaveTextContent('click me');
    expect(md).toHaveTextContent('even github');
    expect(md.innerHTML).not.toMatch(/javascript:/i);
  });

  it('drops images entirely, including reference-style ones', () => {
    renderWithProviders(<RoastMarkdown markdown={'Look ![alt text][pix]\n\n[pix]: https://evil.example/p.png'} />);
    const md = screen.getByTestId('roast-markdown');
    expect(md.querySelector('img')).toBeNull();
    expect(md.innerHTML).not.toContain('evil.example');
  });
});
