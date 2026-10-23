import { afterEach, describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MarkdownEditor } from './MarkdownEditor';
import * as markdownApi from '@/api/markdown';
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';

vi.mock('@/api/markdown', () => ({
  previewMarkdown: vi.fn(),
}));

const previewMarkdown = vi.mocked(markdownApi.previewMarkdown);

describe('MarkdownEditor', () => {
  beforeEach(() => {
    previewMarkdown.mockReset();
    previewMarkdown.mockResolvedValue('<p><strong>bold</strong></p>');
  });

  it('renders the textarea in write mode and forwards edits', async () => {
    const onChange = vi.fn();
    render(<MarkdownEditor value="" onChange={onChange} />);
    await userEvent.type(screen.getByRole('textbox'), 'a');
    expect(onChange).toHaveBeenCalledWith('a');
  });

  it('fetches server-rendered HTML when switching to preview', async () => {
    render(<MarkdownEditor value="**bold**" onChange={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /preview/i }));
    expect(await screen.findByText('bold')).toBeInTheDocument();
    expect(previewMarkdown).toHaveBeenCalledWith('**bold**');
  });

  it('does not re-fetch when the content has not changed', async () => {
    render(<MarkdownEditor value="**bold**" onChange={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /preview/i }));
    await screen.findByText('bold');
    await userEvent.click(screen.getByRole('button', { name: /write/i }));
    await userEvent.click(screen.getByRole('button', { name: /preview/i }));
    expect(previewMarkdown).toHaveBeenCalledTimes(1);
  });

  it('shows an empty state instead of calling the API for blank content', async () => {
    render(<MarkdownEditor value="   " onChange={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: /preview/i }));
    expect(await screen.findByText(/nothing to preview/i)).toBeInTheDocument();
  });
});

describe('MarkdownEditor in Turkish', () => {
  const ENGLISH_PROBE = /\b(Body|Write|Preview|Rendering|Nothing to preview)\b/;

  afterEach(resetLanguage);

  it('renders no English in Turkish in write, loading and empty preview states', async () => {
    await i18n.changeLanguage('tr');
    previewMarkdown.mockReset();
    previewMarkdown.mockReturnValue(new Promise(() => undefined));
    const { rerender } = render(<MarkdownEditor value="x" onChange={() => {}} />);
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);

    await userEvent.click(screen.getByRole('button', { name: i18n.t('editor.preview') }));
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);

    rerender(<MarkdownEditor value=" " onChange={() => {}} />);
    await userEvent.click(screen.getByRole('button', { name: i18n.t('editor.write') }));
    await userEvent.click(screen.getByRole('button', { name: i18n.t('editor.preview') }));
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });
});