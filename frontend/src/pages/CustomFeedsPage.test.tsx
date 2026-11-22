import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setUser } from '@/features/auth/authSlice';
import { CustomFeedsPage } from './CustomFeedsPage';
import * as feedsApi from '@/api/customFeeds';
import * as communitiesApi from '@/api/communities';

vi.mock('@/api/customFeeds', () => ({
  listMyFeeds: vi.fn(),
  createFeed: vi.fn(),
  updateFeed: vi.fn(),
  deleteFeed: vi.fn(),
}));
vi.mock('@/api/communities', () => ({ listCommunities: vi.fn() }));

const existing: feedsApi.CustomFeed = {
  id: 1,
  name: 'Old',
  slug: 'old',
  description: '',
  is_public: false,
  owner_username: 'alice',
  communities: ['py'],
  created: '2026-10-01T00:00:00Z',
};

function renderPage() {
  const store = configureStore({ reducer: { auth: authReducer } });
  store.dispatch(
    setUser({
      id: 1,
      username: 'alice',
      email: 'a@x.com',
      email_verified: true,
      avatar: null,
      bio: '',
      country: '',
      show_nsfw: false,
      post_karma: 0,
      comment_karma: 0,
    }),
  );
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <CustomFeedsPage />
      </MemoryRouter>
    </Provider>,
  );
}

describe('CustomFeedsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(feedsApi.listMyFeeds).mockResolvedValue({ count: 1, next: null, previous: null, results: [existing] });
    vi.mocked(communitiesApi.listCommunities).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [{ slug: 'py' } as never],
    });
  });

  it('lists the user feeds with links', async () => {
    renderPage();
    expect(await screen.findByRole('link', { name: 'Old' })).toHaveAttribute('href', '/u/alice/feeds/old');
  });

  it('creates a feed with chosen communities', async () => {
    vi.mocked(feedsApi.createFeed).mockResolvedValue({ ...existing, id: 2, name: 'New', slug: 'new', communities: ['js'] });
    renderPage();
    await screen.findByRole('link', { name: 'Old' });
    await userEvent.type(screen.getByLabelText('Name'), 'New');
    await userEvent.type(screen.getByLabelText('Add a community'), 'c/JS{Enter}');
    await userEvent.click(screen.getByLabelText('Public (anyone with the link can read it)'));
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(feedsApi.createFeed).toHaveBeenCalledWith({
      name: 'New',
      description: '',
      is_public: true,
      communities: ['js'],
    });
    expect(await screen.findByRole('link', { name: 'New' })).toBeInTheDocument();
  });

  it('shows the server error when saving fails', async () => {
    vi.mocked(feedsApi.createFeed).mockRejectedValue({
      response: { data: { communities: ['Object with slug=nope does not exist.'] } },
    });
    renderPage();
    await screen.findByRole('link', { name: 'Old' });
    await userEvent.type(screen.getByLabelText('Name'), 'X');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('does not exist');
  });

  it('edits and deletes an existing feed', async () => {
    vi.mocked(feedsApi.updateFeed).mockResolvedValue({ ...existing, name: 'Renamed' });
    vi.mocked(feedsApi.deleteFeed).mockResolvedValue();
    renderPage();
    await userEvent.click(await screen.findByRole('button', { name: 'Edit' }));
    const name = screen.getByLabelText('Name');
    await userEvent.clear(name);
    await userEvent.type(name, 'Renamed');
    await userEvent.click(screen.getByRole('button', { name: 'Remove c/py' }));
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(feedsApi.updateFeed).toHaveBeenCalledWith('alice', 'old', {
      name: 'Renamed',
      description: '',
      is_public: false,
      communities: [],
    });
    expect(await screen.findByRole('link', { name: 'Renamed' })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(feedsApi.deleteFeed).toHaveBeenCalledWith('alice', 'old');
    expect(await screen.findByText('You have no custom feeds yet.')).toBeInTheDocument();
  });
});
