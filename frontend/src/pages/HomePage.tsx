import { Card } from '@/components/ui/Card';
import { useAppSelector } from '@/app/hooks';

export function HomePage() {
  const user = useAppSelector((s) => s.auth.user);

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <h1 className="text-xl font-bold">
          {user ? `Welcome back, ${user.username}` : 'Welcome to nexus'}
        </h1>
        <p className="mt-1 text-sm text-[var(--color-text-muted)]">
          Your feed will appear here once the post UI is wired up.
        </p>
      </Card>

      {[1, 2, 3].map((i) => (
        <Card key={i} interactive>
          <div className="flex items-start gap-3">
            <div className="flex flex-col items-center gap-1 text-[var(--color-text-muted)]">
              <button className="hover:text-[var(--color-accent)]">▲</button>
              <span className="text-xs font-semibold">0</span>
              <button className="hover:text-[var(--color-danger)]">▼</button>
            </div>
            <div className="flex-1">
              <div className="text-xs text-[var(--color-text-dim)]">
                c/placeholder · posted by u/anonymous
              </div>
              <h3 className="mt-1 text-base font-semibold">Placeholder post #{i}</h3>
              <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                This is a UI placeholder. Real posts arrive in a later phase.
              </p>
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
}
