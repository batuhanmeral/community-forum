import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { CrosspostButton } from './CrosspostButton';
import * as postsApi from '@/api/posts';
import * as communitiesApi from '@/api/communities';
import i18n from '@/i18n';

vi.mock('@/api/posts', () => ({ crosspostPost: vi.fn() }));
vi.mock('@/api/communities', () => ({ listCommunities: vi.fn() }));

function renderButton() {
  return render(
    <MemoryRouter initialEntries={['/posts/1']}>
      <Routes>
        <Route path="/posts/:id" element={<CrosspostButton postId={1} title="Hello" />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('CrosspostButton', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(communitiesApi.listCommunities).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [{ slug: 'dst' } as never],
    });
  });

  it('requires a community before sending', async () => {
    renderButton();
    await userEvent.click(screen.getByRole('button', { name: 'Crosspost' }));
    await userEvent.click(screen.getAllByRole('button', { name: 'Crosspost' })[1]);
    expect(await screen.findByRole('alert')).toHaveTextContent('Please pick a community.');
    expect(postsApi.crosspostPost).not.toHaveBeenCalled();
  });

  it('crossposts to the chosen community and opens the new post', async () => {
    vi.mocked(postsApi.crosspostPost).mockResolvedValue({ id: 9 } as never);
    renderButton();
    await userEvent.click(screen.getByRole('button', { name: 'Crosspost' }));
    await userEvent.selectOptions(await screen.findByRole('combobox'), 'dst');
    await userEvent.click(screen.getAllByRole('button', { name: 'Crosspost' })[1]);
    await waitFor(() => expect(postsApi.crosspostPost).toHaveBeenCalledWith(1, 'dst', 'Hello'));
  });

  async function submitWith(rejection: unknown, label = 'Crosspost') {
    vi.mocked(postsApi.crosspostPost).mockRejectedValue(rejection);
    renderButton();
    await userEvent.click(screen.getByRole('button', { name: label }));
    await userEvent.selectOptions(await screen.findByRole('combobox'), 'dst');
    await userEvent.click(screen.getAllByRole('button', { name: label })[1]);
    return screen.findByRole('alert');
  }

  it('translates the known server errors', async () => {
    const alert = await submitWith({
      response: { status: 400, data: ['You already crossposted this post to that community.'] },
    });
    expect(alert).toHaveTextContent('You already crossposted this post there.');
  });

  it('explains a same-community refusal', async () => {
    const alert = await submitWith({
      response: {
        status: 400,
        data: { community: ['The original post is already in this community.'] },
      },
    });
    expect(alert).toHaveTextContent('The original post is already in that community.');
  });

  it('shows a translated refusal for 403s', async () => {
    const alert = await submitWith({
      response: { status: 403, data: { detail: "You cannot crosspost this user's post." } },
    });
    expect(alert).toHaveTextContent('You cannot crosspost this post there.');
  });

  it('never shows raw server English in Turkish', async () => {
    await i18n.changeLanguage('tr');
    try {
      const alert = await submitWith({
        response: { status: 400, data: ['Some new server message.'] },
      }, 'Çapraz paylaş');
      expect(alert).toHaveTextContent('Çapraz paylaşım yapılamadı.');
      expect(alert.textContent).not.toMatch(/server message/);
    } finally {
      await i18n.changeLanguage('en');
    }
  });
});
