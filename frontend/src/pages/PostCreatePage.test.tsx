import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import type { Community } from '@/features/communities/types';
import { PostCreatePage } from './PostCreatePage';
import * as communitiesApi from '@/api/communities';
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';

vi.mock('@/api/communities', () => ({
  getCommunity: vi.fn(),
  listCommunities: vi.fn(),
  listFlairs: vi.fn(),
}));

vi.mock('@/api/posts', () => ({ createPost: vi.fn() }));

const api = vi.mocked(communitiesApi);

const joined: Community = {
  id: 1,
  slug: 'small-club',
  name: 'Small club',
  description: '',
  avatar: null,
  is_nsfw: false,
  requires_approval: false,
  creator: 9,
  created_at: '2026-10-01T00:00:00Z',
  member_count: 3,
  is_member: true,
  is_banned: false,
  my_role: 'member',
  my_notify_level: 'all',
};

function renderPage() {
  const store = configureStore({ reducer: { auth: authReducer } });
  return render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/submit']}>
        <Routes>
          <Route path="/submit" element={<PostCreatePage />} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  );
}

describe('PostCreatePage community picker', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    api.listFlairs.mockResolvedValue([]);
  });

  it('offers only communities the user has joined', async () => {
    api.listCommunities.mockResolvedValue({ count: 1, next: null, previous: null, results: [joined] });
    renderPage();
    expect(await screen.findByRole('option', { name: 'c/small-club' })).toBeInTheDocument();
    expect(api.listCommunities).toHaveBeenCalledWith(
      expect.objectContaining({ joined: true, page_size: 100 }),
    );
  });

  it('explains what to do when the user has not joined any community', async () => {
    api.listCommunities.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    renderPage();
    await waitFor(() =>
      expect(screen.getByText('Join a community to start posting.')).toBeInTheDocument(),
    );
  });
});

describe('PostCreatePage in Turkish', () => {
  const ENGLISH_PROBE =
    /\b(Create a post|Community|Choose a community|Text|Image|Link|Poll|Title|URL|Options?|Add option|Remove option|Closes at|Flair|optional|Mark this post|Discard draft|Draft restored|Cancel|Post)\b/;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    api.listFlairs.mockResolvedValue([{ id: 1, name: 'Help', color: '#ffffff' }] as never);
    api.listCommunities.mockResolvedValue({ count: 1, next: null, previous: null, results: [joined] });
  });
  afterEach(resetLanguage);

  it.each(['text', 'link', 'image', 'poll'] as const)('renders no English in Turkish for the %s form', async (kind) => {
    await i18n.changeLanguage('tr');
    renderPage();
    await screen.findByRole('option', { name: 'c/small-club' });
    await userEvent.click(screen.getByRole('button', { name: new RegExp(`^${{ text: 'Metin', link: 'Bağlantı', image: 'Görsel', poll: 'Anket' }[kind]}`) }));
    await userEvent.selectOptions(screen.getByRole('combobox'), 'small-club');
    await screen.findByRole('button', { name: 'Help' });
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('renders no English in Turkish with a restored draft and no joined community', async () => {
    localStorage.setItem(
      'nexus.postDraft',
      JSON.stringify({ community: '', kind: 'text', title: 'x', body: '', url: '', savedAt: new Date().toISOString() }),
    );
    api.listCommunities.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    await i18n.changeLanguage('tr');
    renderPage();
    expect(await screen.findByText(/Taslak geri yüklendi/)).toBeInTheDocument();
    await screen.findByText(/Gönderi paylaşmak için önce/);
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });

  it('asks for a community in Turkish', async () => {
    await i18n.changeLanguage('tr');
    renderPage();
    await screen.findByRole('option', { name: 'c/small-club' });
    await userEvent.type(screen.getByLabelText('Başlık'), 'Merhaba');
    await userEvent.click(screen.getByRole('button', { name: 'Paylaş' }));
    expect(await screen.findByText('Lütfen bir topluluk seç.')).toBeInTheDocument();
  });
});

describe('PostCreatePage title', () => {
  it('sets the page title', async () => {
    localStorage.clear();
    api.listFlairs.mockResolvedValue([]);
    api.listCommunities.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    renderPage();
    await waitFor(() => expect(document.title).toBe('Create a post · Nexus'));
  });
});
