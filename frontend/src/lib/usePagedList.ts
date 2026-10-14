import { useCallback, useEffect, useRef, useState } from 'react';
import type { Paginated } from '@/features/communities/types';

export function usePagedList<T extends { id: number }>(
  fetchPage: (page: number) => Promise<Paginated<T>>,
) {
  const [items, setItems] = useState<T[]>([]);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [loadMoreFailed, setLoadMoreFailed] = useState(false);
  // Bumped on every reload and unmount so late responses are dropped.
  const version = useRef(0);
  // Server page size, learned from a full first page.
  const pageSize = useRef(0);

  const reload = useCallback(() => {
    version.current += 1;
    const v = version.current;
    setLoading(true);
    setLoadFailed(false);
    setLoadMoreFailed(false);
    fetchPage(1)
      .then((d) => {
        if (v !== version.current) return;
        setItems(d.results);
        if (d.next) pageSize.current = d.results.length;
        setNextPage(d.next ? 2 : null);
      })
      .catch(() => {
        if (v !== version.current) return;
        setItems([]);
        setNextPage(null);
        setLoadFailed(true);
      })
      .finally(() => {
        if (v === version.current) setLoading(false);
      });
  }, [fetchPage]);

  useEffect(() => {
    reload();
    return () => {
      version.current += 1;
    };
  }, [reload]);

  // Acting on rows shifts later pages down; once the visible rows are gone, start over at page 1.
  useEffect(() => {
    if (!loading && items.length === 0 && nextPage !== null) reload();
  }, [loading, items.length, nextPage, reload]);

  async function loadMore() {
    if (nextPage === null) return;
    const v = version.current;
    setLoadMoreFailed(false);
    // Rows removed locally also left the server, so the next unseen row sits at items.length.
    const target = pageSize.current ? Math.floor(items.length / pageSize.current) + 1 : nextPage;
    try {
      const d = await fetchPage(target);
      if (v !== version.current) return;
      setItems((prev) => {
        const seen = new Set(prev.map((i) => i.id));
        return [...prev, ...d.results.filter((i) => !seen.has(i.id))];
      });
      setNextPage(d.next ? target + 1 : null);
    } catch {
      if (v === version.current) setLoadMoreFailed(true);
    }
  }

  function remove(id: number) {
    setItems((prev) => prev.filter((i) => i.id !== id));
  }

  return { items, loading, loadFailed, nextPage, loadMore, loadMoreFailed, remove, reload };
}
