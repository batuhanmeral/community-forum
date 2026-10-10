import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { usePagedList } from './usePagedList';

type Row = { id: number };

function page(ids: number[], next: string | null = null) {
  return { count: ids.length, next, previous: null, results: ids.map((id) => ({ id })) };
}

describe('usePagedList', () => {
  it('loads page 1 and appends later pages without duplicates', async () => {
    const fetchPage = vi
      .fn<(p: number) => Promise<ReturnType<typeof page>>>()
      .mockResolvedValueOnce(page([1, 2], 'p2'))
      .mockResolvedValueOnce(page([2, 3]));
    const { result } = renderHook(() => usePagedList<Row>(fetchPage));
    await waitFor(() => expect(result.current.items).toHaveLength(2));
    expect(result.current.nextPage).toBe(2);

    await act(() => result.current.loadMore());
    expect(result.current.items.map((r) => r.id)).toEqual([1, 2, 3]);
    expect(result.current.nextPage).toBeNull();
    expect(fetchPage).toHaveBeenLastCalledWith(2);
  });

  it('reloads the first page once the visible rows run out', async () => {
    const fetchPage = vi
      .fn<(p: number) => Promise<ReturnType<typeof page>>>()
      .mockResolvedValueOnce(page([1], 'p2'))
      .mockResolvedValueOnce(page([2]));
    const { result } = renderHook(() => usePagedList<Row>(fetchPage));
    await waitFor(() => expect(result.current.items).toHaveLength(1));

    act(() => result.current.remove(1));
    await waitFor(() => expect(result.current.items.map((r) => r.id)).toEqual([2]));
    expect(fetchPage).toHaveBeenNthCalledWith(2, 1);
  });

  it('reports a failed first load', async () => {
    const fetchPage = vi.fn().mockRejectedValue(new Error('down'));
    const { result } = renderHook(() => usePagedList<Row>(fetchPage));
    await waitFor(() => expect(result.current.loadFailed).toBe(true));
    expect(result.current.items).toEqual([]);
  });
});
