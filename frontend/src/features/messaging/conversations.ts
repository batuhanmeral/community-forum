import type { Conversation } from './types';

/** A polled first page goes on top; rows loaded from later pages that it lacks stay below it. */
export function mergeFirstPage(fresh: Conversation[], loaded: Conversation[]): Conversation[] {
  const ids = new Set(fresh.map((c) => c.id));
  return [...fresh, ...loaded.filter((c) => !ids.has(c.id))];
}

/** New activity shifts rows down a page, so a later page can repeat rows already shown. */
export function appendPage(loaded: Conversation[], page: Conversation[]): Conversation[] {
  const ids = new Set(loaded.map((c) => c.id));
  return [...loaded, ...page.filter((c) => !ids.has(c.id))];
}
