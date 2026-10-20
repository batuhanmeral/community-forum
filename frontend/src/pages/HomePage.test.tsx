import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import type { Community } from '@/features/communities/types';
import { HomePage } from './HomePage';
import * as communitiesApi from '@/api/communities';
import * as postsApi from '@/api/posts';

vi.mock('@/api/communities', () => ({ listCommunities: vi.fn() }));
vi.mock('@/api/posts', () => ({ listFeed: vi.fn(), listFollowingFeed: vi.fn() }));
vi.mock('@/api/users', () => ({ updatePreferences: vi.fn() }));

const communities = vi.mocked(communitiesApi);
const posts = vi.mocked(postsApi);

const joined: Community = {
  id: 1,
  slug: 'py',
  name: 'Py',
  description: '',
  avatar: null,
  is_nsfw: false,
  requires_approval: false,
  creator: 9,
  created_at: '2026-10-01T00:00:00Z',
  member_count: 1,
  is_member: true,
  is_banned: false,
  my_role: 'member',
  my_notify_level: 'all',
};

function renderAuthed() {
  const store = configureStore({ reducer: { auth: authReducer } });
  store.dispatch(
    setUser({
      id: 1,
      username: 'alice',
      email: 'a@x.com',
      email_verified: true,
      avatar: null,
      bio: '',
      show_nsfw: false,
      post_karma: 0,
      comment_karma: 0,
    }),
  );
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    </Provider>,
  );
}

describe('HomePage joined communities subtitle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    posts.listFeed.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  });

  it('shows the joined total reported by the API', async () => {
    communities.listCommunities.mockResolvedValue({
      count: 37,
      next: 'p2',
      previous: null,
      results: [joined],
    });
    renderAuthed();
    expect(await screen.findByText(/· 37 communities/)).toBeInTheDocument();
    expect(communities.listCommunities).toHaveBeenCalledWith(
      expect.objectContaining({ joined: true }),
    );
  });
});

describe('HomePage compose box', () => {
  it('has no nested anchors and keeps the tool links', async () => {
    posts.listFeed.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    communities.listCommunities.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    const { container } = renderAuthed();
    await screen.findByText(/Your feed is empty/);
    expect(container.querySelectorAll('a a')).toHaveLength(0);
    for (const kind of ['image', 'link', 'poll']) {
      expect(container.querySelector(`a[href="/submit?kind=${kind}"]`)).not.toBeNull();
    }
  });
});
