import { afterEach, describe, expect, it, vi } from 'vitest';
import { render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer from '@/features/auth/authSlice';
import type { Poll } from '@/features/posts/types';
import i18n from '@/i18n';
import { resetLanguage, visibleText } from '@/test/i18nHelpers';
import { PollCard } from './PollCard';

vi.mock('@/api/polls', () => ({ votePoll: vi.fn() }));

const poll: Poll = {
  id: 1,
  options: [{ id: 1, text: 'A', order: 0, vote_count: 1, percent: 100 }],
  total_votes: 1,
  closes_at: '2099-12-01T00:00:00Z',
  is_closed: false,
  user_option: null,
};

function renderPoll(value: Poll) {
  const store = configureStore({ reducer: { auth: authReducer } });
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <PollCard poll={value} />
      </MemoryRouter>
    </Provider>,
  );
}

describe('PollCard', () => {
  afterEach(resetLanguage);

  it('pluralises the vote count', () => {
    renderPoll({ ...poll, total_votes: 2 });
    expect(document.body).toHaveTextContent('2 votes');
  });

  it('renders no English in Turkish, open and closed', async () => {
    const ENGLISH_PROBE = /\b(votes?|closes|Closed|Log in to vote)\b/;
    await i18n.changeLanguage('tr');
    const { unmount } = renderPoll(poll);
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
    unmount();
    renderPoll({ ...poll, is_closed: true });
    expect(visibleText()).not.toMatch(ENGLISH_PROBE);
  });
});
