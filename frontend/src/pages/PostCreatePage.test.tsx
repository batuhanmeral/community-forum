import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import type { Community } from '@/features/communities/types';
import { PostCreatePage } from './PostCreatePage';
import * as communitiesApi from '@/api/communities';

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
