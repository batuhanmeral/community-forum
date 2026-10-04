import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from './client';
import { listConversations } from './messaging';

vi.mock('./client', () => ({ api: { get: vi.fn() } }));

describe('listConversations', () => {
  beforeEach(() => vi.clearAllMocks());

  it('asks for the largest page the backend allows', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { results: [] } });
    await listConversations();
    expect(api.get).toHaveBeenCalledWith('/conversations/', { params: { page_size: 100 } });
  });
});
