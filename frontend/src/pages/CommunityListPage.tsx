import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { listCommunities } from '@/api/communities';
import type { Community } from '@/features/communities/types';
import { useAppSelector } from '@/app/hooks';
import { Avatar } from '@/components/ui/Avatar';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';

export function CommunityListPage() {
  const [search, setSearch] = useState('');
  const [debounced, setDebounced] = useState('');
  const [communities, setCommunities] = useState<Community[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const isAuthed = useAppSelector((s) => s.auth.status === 'authenticated');

  useEffect(() => {
    const t = setTimeout(() => setDebounced(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listCommunities({ search: debounced || undefined, ordering: '-member_count' })
      .then((data) => {
        if (!cancelled) setCommunities(data.results);
      })
      .catch(() => {
        if (!cancelled) setError('Could not load communities.');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [debounced]);

  return (
    <div className="flex flex-col gap-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Communities</h1>
          <p className="mt-1 text-sm text-[var(--color-text-muted)]">
            Discover and join communities that match your interests.
          </p>
        </div>
        {isAuthed && (
          <Link to="/c/create">
            <Button variant="primary">Create</Button>
          </Link>
        )}
      </div>

      <div className="max-w-md">
        <Input
          name="search"
          placeholder="Search communities..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {error && <p className="text-sm text-[var(--color-danger)]">{error}</p>}

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} className="animate-pulse">
              <div className="flex items-center gap-3">
                <div className="h-10 w-10 rounded-full bg-[var(--color-surface-hover)]" />
                <div className="flex-1 space-y-2">
                  <div className="h-3 w-1/2 rounded bg-[var(--color-surface-hover)]" />
                  <div className="h-2 w-1/3 rounded bg-[var(--color-surface-hover)]" />
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : communities.length === 0 ? (
        <Card>
          <p className="text-sm text-[var(--color-text-muted)]">
            {debounced ? `No communities match "${debounced}".` : 'No communities yet.'}
          </p>
        </Card>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {communities.map((c) => (
            <Link key={c.id} to={`/c/${c.slug}`}>
              <Card interactive className="h-full">
                <div className="flex items-start gap-3">
                  <Avatar src={c.avatar} alt={c.name} size="md" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <h3 className="truncate text-sm font-semibold">c/{c.slug}</h3>
                      {c.is_nsfw && <Badge tone="danger">NSFW</Badge>}
                      {c.is_member && <Badge tone="accent">Joined</Badge>}
                    </div>
                    <p className="mt-0.5 text-xs text-[var(--color-text-muted)]">
                      {c.member_count.toLocaleString()} member
                      {c.member_count === 1 ? '' : 's'}
                    </p>
                    {c.description && (
                      <p className="mt-2 line-clamp-2 text-sm text-[var(--color-text-muted)]">
                        {c.description}
                      </p>
                    )}
                  </div>
                </div>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
