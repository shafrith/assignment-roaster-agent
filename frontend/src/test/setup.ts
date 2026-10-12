import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { MotionGlobalConfig } from 'framer-motion';
import { afterEach } from 'vitest';

// Finish Framer Motion animations instantly so assertions don't race animation frames.
MotionGlobalConfig.skipAnimations = true;

// --- jsdom polyfills used by Chakra UI / Framer Motion ---------------------------------------
if (!window.matchMedia) {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    configurable: true,
    value: (query: string): MediaQueryList => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => undefined,
      removeListener: () => undefined,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      dispatchEvent: () => false,
    }),
  });
}

class NoopObserver {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): [] {
    return [];
  }
}

if (!('ResizeObserver' in window)) {
  Object.defineProperty(window, 'ResizeObserver', { writable: true, configurable: true, value: NoopObserver });
}
if (!('IntersectionObserver' in window)) {
  Object.defineProperty(window, 'IntersectionObserver', { writable: true, configurable: true, value: NoopObserver });
}

Object.defineProperty(window, 'scrollTo', { writable: true, configurable: true, value: () => undefined });
Element.prototype.scrollTo = function scrollTo(): void {};
Element.prototype.scrollIntoView = function scrollIntoView(): void {};

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
  window.localStorage.clear();
});
