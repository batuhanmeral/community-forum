import i18n from '@/i18n';

const UNITS: Array<[Intl.RelativeTimeFormatUnit, number]> = [
  ['year', 60 * 60 * 24 * 365],
  ['month', 60 * 60 * 24 * 30],
  ['week', 60 * 60 * 24 * 7],
  ['day', 60 * 60 * 24],
  ['hour', 60 * 60],
  ['minute', 60],
  ['second', 1],
];

// Building a formatter is costly and timeAgo runs per list row, so keep one per language.
const formatters = new Map<string, Intl.RelativeTimeFormat>();

function formatterFor(language: string): Intl.RelativeTimeFormat {
  let formatter = formatters.get(language);
  if (!formatter) {
    formatter = new Intl.RelativeTimeFormat(language, { numeric: 'auto', style: 'narrow' });
    formatters.set(language, formatter);
  }
  return formatter;
}

export function timeAgo(iso: string): string {
  const formatter = formatterFor(i18n.language);
  const seconds = (new Date(iso).getTime() - Date.now()) / 1000;
  for (const [unit, divisor] of UNITS) {
    if (Math.abs(seconds) >= divisor || unit === 'second') {
      return formatter.format(Math.round(seconds / divisor), unit);
    }
  }
  return '';
}
