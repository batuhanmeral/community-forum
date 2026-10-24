import { describe, expect, it } from 'vitest';
import { COUNTRY_CODES, countriesByName, countryFlag, countryName } from './countries';

describe('countries', () => {
  it('lists every ISO 3166-1 alpha-2 code once', () => {
    expect(COUNTRY_CODES).toHaveLength(249);
    expect(new Set(COUNTRY_CODES).size).toBe(249);
  });

  it('builds the flag emoji from the code', () => {
    expect(countryFlag('TR')).toBe('🇹🇷');
    expect(countryFlag('US')).toBe('🇺🇸');
  });

  it('names countries in the given language', () => {
    expect(countryName('DE', 'en')).toBe('Germany');
    expect(countryName('DE', 'tr')).toBe('Almanya');
  });

  it('sorts by the localised name', () => {
    const names = countriesByName('tr').map((c) => c.name);
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b, 'tr')));
  });
});
