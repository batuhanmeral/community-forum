import { useState } from 'react';
import { describe, expect, it } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { Provider } from 'react-redux';
import { configureStore } from '@reduxjs/toolkit';
import authReducer, { setAccessToken, setTokens, syncFromStorage } from '@/features/auth/authSlice';
import { fakeJwt } from '@/test/fakeJwt';
import { ProtectedRoute } from './ProtectedRoute';

/** Stands in for a page with local state, e.g. MessagesPage's open conversation. */
function StatefulPage() {
  const [draft, setDraft] = useState('');
  return (
    <>
      <output data-testid="draft">{draft}</output>
      <button type="button" onClick={() => setDraft('secret')}>
        Type
      </button>
    </>
  );
}

function renderProtected() {
  const store = configureStore({ reducer: { auth: authReducer } });
  store.dispatch(setTokens({ access: fakeJwt({ user_id: 1, n: 1 }), refresh: 'r1' }));
  render(
    <Provider store={store}>
      <MemoryRouter initialEntries={['/messages']}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/messages" element={<StatefulPage />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </Provider>,
  );
  fireEvent.click(screen.getByRole('button', { name: 'Type' }));
  expect(screen.getByTestId('draft')).toHaveTextContent('secret');
  return store;
}

describe('ProtectedRoute', () => {
  it("drops the previous account's page state after an account switch in another tab", () => {
    const store = renderProtected();
    act(() => {
      store.dispatch(syncFromStorage({ access: fakeJwt({ user_id: 2 }), refresh: 'r2' }));
    });
    expect(screen.getByTestId('draft')).toBeEmptyDOMElement();
  });

  it('keeps page state when the same account refreshes its token', () => {
    const store = renderProtected();
    act(() => {
      store.dispatch(setAccessToken(fakeJwt({ user_id: 1, n: 2 })));
    });
    expect(screen.getByTestId('draft')).toHaveTextContent('secret');
  });
});
