export const APP_NAME = 'Nexus';

// React 19 hoists <title> into <head>, so each page can own its document title.
export function PageTitle({ title }: { title?: string }) {
  return <title>{title ? `${title} · ${APP_NAME}` : APP_NAME}</title>;
}
