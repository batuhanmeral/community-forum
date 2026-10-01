import { renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { usePolling } from './usePolling';

describe('usePolling', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('calls the callback on every interval while enabled', () => {
    const fn = vi.fn();
    renderHook(() => usePolling(fn, 1000));
    vi.advanceTimersByTime(3000);
    expect(fn).toHaveBeenCalledTimes(3);
  });

  it('skips ticks while the tab is hidden', () => {
    const fn = vi.fn();
    const hidden = vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
    renderHook(() => usePolling(fn, 1000));
    vi.advanceTimersByTime(3000);
    expect(fn).not.toHaveBeenCalled();
    hidden.mockRestore();
  });

  it('does nothing when disabled', () => {
    const fn = vi.fn();
    renderHook(() => usePolling(fn, 1000, false));
    vi.advanceTimersByTime(3000);
    expect(fn).not.toHaveBeenCalled();
  });

  it('always calls the latest callback', () => {
    const first = vi.fn();
    const second = vi.fn();
    const { rerender } = renderHook(({ fn }) => usePolling(fn, 1000), {
      initialProps: { fn: first },
    });
    rerender({ fn: second });
    vi.advanceTimersByTime(1000);
    expect(first).not.toHaveBeenCalled();
    expect(second).toHaveBeenCalledTimes(1);
  });
});
