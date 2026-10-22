import { afterEach, describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReportModal } from './ReportModal';
import * as moderationApi from '@/api/moderation';
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';

vi.mock('@/api/moderation', () => ({
  reportContent: vi.fn(),
}));

const reportContent = vi.mocked(moderationApi.reportContent);

describe('ReportModal', () => {
  beforeEach(() => {
    reportContent.mockReset();
    reportContent.mockResolvedValue({} as never);
  });

  it('keeps submit disabled until a reason is chosen', async () => {
    render(<ReportModal open onClose={() => {}} target="post" objectId={5} />);
    const submit = screen.getByRole('button', { name: /submit report/i });
    expect(submit).toBeDisabled();

    await userEvent.click(screen.getByRole('button', { name: 'Spam' }));
    expect(submit).toBeEnabled();
  });

  it('submits the chosen reason combined with the detail text', async () => {
    render(<ReportModal open onClose={() => {}} target="comment" objectId={9} />);

    await userEvent.click(screen.getByRole('button', { name: 'Spam' }));
    await userEvent.type(
      screen.getByPlaceholderText(/add more context/i),
      'links to a scam',
    );
    await userEvent.click(screen.getByRole('button', { name: /submit report/i }));

    await waitFor(() => expect(reportContent).toHaveBeenCalledTimes(1));
    expect(reportContent).toHaveBeenCalledWith('comment', 9, 'Spam: links to a scam');
    // Success confirmation replaces the form.
    expect(await screen.findByText(/report submitted/i)).toBeInTheDocument();
  });

  it('shows an error message when the report fails', async () => {
    reportContent.mockRejectedValueOnce({
      response: { data: { detail: 'Already reported recently.' } },
    });
    render(<ReportModal open onClose={() => {}} target="user" objectId={3} label="user" />);

    await userEvent.click(screen.getByRole('button', { name: 'Harassment or bullying' }));
    await userEvent.click(screen.getByRole('button', { name: /submit report/i }));

    expect(await screen.findByText(/already reported recently/i)).toBeInTheDocument();
  });
});

describe('ReportModal in Turkish', () => {
  const ENGLISH_PROBE =
    /\b(Report|Why|Harassment|Hate speech|Violence|Misinformation|Other|Cancel|Close|Submit|Thanks|Add more|submitted|Could not)\b/;

  afterEach(resetLanguage);

  it('renders no English in Turkish through the form, a failure and the confirmation', async () => {
    await i18n.changeLanguage('tr');
    reportContent.mockReset();
    reportContent.mockRejectedValueOnce(new Error('down')).mockResolvedValueOnce({} as never);
    render(<ReportModal open onClose={() => {}} target="comment" objectId={9} />);
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);

    await userEvent.click(screen.getByRole('button', { name: i18n.t('report.reason_spam') }));
    await userEvent.click(screen.getByRole('button', { name: i18n.t('report.submit') }));
    await screen.findByText(i18n.t('report.failed'));
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);

    await userEvent.click(screen.getByRole('button', { name: i18n.t('report.submit') }));
    await screen.findByText(i18n.t('report.thanks'));
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('sends the English reason to the backend whatever the interface language', async () => {
    await i18n.changeLanguage('tr');
    reportContent.mockReset();
    reportContent.mockResolvedValue({} as never);
    render(<ReportModal open onClose={() => {}} target="post" objectId={5} />);
    await userEvent.click(screen.getByRole('button', { name: i18n.t('report.reason_harassment') }));
    await userEvent.click(screen.getByRole('button', { name: i18n.t('report.submit') }));
    await waitFor(() => expect(reportContent).toHaveBeenCalledWith('post', 5, 'Harassment or bullying'));
  });
});