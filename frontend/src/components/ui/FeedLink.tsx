import { api } from '@/api/client';

/** Advertises an Atom feed to browsers and feed readers (React hoists <link> into <head>). */
export function FeedLink({ path, title }: { path: string; title: string }) {
  const href = new URL(`${api.defaults.baseURL ?? ''}${path}`, window.location.origin).toString();
  return <link rel="alternate" type="application/atom+xml" title={title} href={href} />;
}
