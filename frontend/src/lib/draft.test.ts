import { describe, it, expect, beforeEach } from 'vitest';
import { clearDraft, loadDraft, saveDraft } from './draft';

const base = { community: 'py', kind: 'text', title: 'Hello', body: 'World', url: '' };

describe('post draft persistence', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('round-trips a draft through localStorage', () => {
    saveDraft(base);
    const loaded = loadDraft();
    expect(loaded).not.toBeNull();
    expect(loaded).toMatchObject(base);
    expect(typeof loaded!.savedAt).toBe('string');
  });

  it('returns null when nothing is saved', () => {
    expect(loadDraft()).toBeNull();
  });

  it('treats an all-empty draft as a clear', () => {
    saveDraft(base);
    saveDraft({ community: 'py', kind: 'text', title: '', body: '  ', url: '' });
    expect(loadDraft()).toBeNull();
  });

  it('clearDraft removes the stored draft', () => {
    saveDraft(base);
    clearDraft();
    expect(loadDraft()).toBeNull();
  });

  it('ignores corrupt stored data', () => {
    localStorage.setItem('nexus.postDraft', '{not json');
    expect(loadDraft()).toBeNull();
  });
});
