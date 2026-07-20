import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ReportModal } from './ReportModal';
import * as moderationApi from '@/api/moderation';

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
