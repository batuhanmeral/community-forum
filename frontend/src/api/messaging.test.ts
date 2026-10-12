import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from './client';
import { listConversations } from './messaging';

vi.mock('./client', () => ({ api: { get: vi.fn() } }));

describe('listConversations', () => {
  beforeEach(() => vi.clearAllMocks());

  it('asks for the requested page at the largest size the backend allows', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { results: [] } });
    await listConversations(3);
    expect(api.get).toHaveBeenCalledWith('/conversations/', { params: { page: 3, page_size: 100 } });
  });
});
