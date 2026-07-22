export interface PostDraft {
  community: string;
  kind: string;
  title: string;
  body: string;
  url: string;
  savedAt: string;
}

const KEY = 'nexus.postDraft';

export function saveDraft(draft: Omit<PostDraft, 'savedAt'>): void {
  if (!draft.title.trim() && !draft.body.trim() && !draft.url.trim()) {
    clearDraft();
    return;
  }
  try {
    localStorage.setItem(KEY, JSON.stringify({ ...draft, savedAt: new Date().toISOString() }));
  } catch {
    // localStorage full or unavailable — drafts are best-effort
  }
}

export function loadDraft(): PostDraft | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<PostDraft>;
    if (typeof parsed.title !== 'string' || typeof parsed.savedAt !== 'string') return null;
    return {
      community: parsed.community ?? '',
      kind: parsed.kind ?? 'text',
      title: parsed.title,
      body: parsed.body ?? '',
      url: parsed.url ?? '',
      savedAt: parsed.savedAt,
    };
  } catch {
    return null;
  }
}

export function clearDraft(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // ignore
  }
}
