import { describe, expect, it } from 'vitest';
import type { Conversation } from './types';
import { appendPage, mergeFirstPage } from './conversations';

const conv = (id: number, unread = 0) => ({ id, unread_count: unread }) as Conversation;

describe('conversation paging', () => {
  it('puts the fresh first page on top and keeps later pages below it', () => {
    const merged = mergeFirstPage([conv(3, 1), conv(1)], [conv(1), conv(2), conv(9)]);
    expect(merged.map((c) => c.id)).toEqual([3, 1, 2, 9]);
    expect(merged[0].unread_count).toBe(1);
  });

  it('appends a page without duplicating rows that shifted down', () => {
    expect(appendPage([conv(1), conv(2)], [conv(2), conv(3)]).map((c) => c.id)).toEqual([1, 2, 3]);
  });
});
