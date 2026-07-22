import { api } from './client';

export async function previewMarkdown(body: string): Promise<string> {
  const res = await api.post<{ html: string }>('/markdown/preview/', { body });
  return res.data.html;
}
