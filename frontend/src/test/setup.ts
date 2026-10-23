import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Node 26 exposes an experimental global `localStorage` that is undefined unless
// a backing file is configured, which shadows jsdom's. Provide a simple in-memory
// implementation so modules that read localStorage at import time (e.g. the auth
// slice) work under tests.
if (!globalThis.localStorage) {
  const store = new Map<string, string>();
  const mock: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (key) => (store.has(key) ? store.get(key)! : null),
    key: (index) => Array.from(store.keys())[index] ?? null,
    removeItem: (key) => void store.delete(key),
    setItem: (key, value) => void store.set(key, String(value)),
  };
  Object.defineProperty(globalThis, 'localStorage', { value: mock, configurable: true });
}

// jsdom has no modal <dialog> API; emulate the open attribute and the close event.
// Skipped under the node environment (lint-rule tests have no DOM).
const hasDom = typeof HTMLDialogElement !== 'undefined';
if (hasDom && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function (this: HTMLDialogElement) {
    this.open = true;
  };
}
if (hasDom && !HTMLDialogElement.prototype.close) {
  HTMLDialogElement.prototype.close = function (this: HTMLDialogElement) {
    if (!this.open) return;
    this.open = false;
    this.dispatchEvent(new Event('close'));
  };
}

afterEach(() => {
  cleanup();
});

// Initialize the i18n singleton (English default) for components using useTranslation.
// It sets <html lang> on import, so the DOM-less lint-rule tests skip it.
if (hasDom) await import('@/i18n');
