import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listFeed, type SortOption } from '@/api/posts';
import type { Post } from '@/features/posts/types';
import { useAppSelector } from '@/app/hooks';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { PostCard } from '@/components/posts/PostCard';
import { PostSortTabs } from '@/components/posts/PostSortTabs';

export function HomePage() {
  const user = useAppSelector((s) => s.auth.user);
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');
  const [posts, setPosts] = useState<Post[]>([]);
  const [sort, setSort] = useState<SortOption>('hot');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listFeed({ sort })
      .then((d) => {
        if (!cancelled) setPosts(d.results);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load feed.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sort]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight">
            {user ? `Welcome back, ${user.username}` : 'Welcome to nexus'}
          </h1>
          <p className="text-xs text-[var(--color-text-muted)]">
            {isAuthed ? 'Your home feed' : 'Popular across nexus'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <PostSortTabs value={sort} onChange={setSort} />
          {isAuthed && (
            <Link to="/submit">
              <Button variant="primary" size="sm">
                Create
              </Button>
            </Link>
          )}
        </div>
      </div>

      {error && (
        <Card>
          <p className="text-sm text-[var(--color-danger)]">{error}</p>
        </Card>
      )}

      {loading ? (
        <div className="flex flex-col gap-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <Card key={i} className="h-32 animate-pulse" />
          ))}
        </div>
      ) : posts.length === 0 ? (
        <Card>
          <p className="text-sm text-[var(--color-text-muted)]">
            {isAuthed
              ? 'Your feed is empty. Try joining a community to populate it.'
              : 'No posts yet. Be the first to contribute!'}
          </p>
          <Link to="/c" className="mt-2 inline-block text-sm text-[var(--color-accent)] hover:underline">
            Browse communities →
          </Link>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {posts.map((p) => (
            <PostCard key={p.id} post={p} />
          ))}
        </div>
      )}
    </div>
  );
}
