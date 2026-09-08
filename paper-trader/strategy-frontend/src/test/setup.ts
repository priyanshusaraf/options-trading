import '@testing-library/jest-dom/vitest'

if (typeof window !== 'undefined') Object.defineProperty(window, 'scrollTo', {
  configurable: true,
  value: () => undefined,
})

class ResizeObserverMock {
  observe() {}
  unobserve() {}
  disconnect() {}
}

Object.defineProperty(globalThis, 'ResizeObserver', {
  configurable: true,
  value: ResizeObserverMock,
})

// Browser layout/pointer APIs used by Radix are absent from jsdom.
if (typeof HTMLElement !== 'undefined') {
  for (const method of ['scrollIntoView', 'setPointerCapture', 'releasePointerCapture'] as const) {
    if (!(method in HTMLElement.prototype)) Object.defineProperty(HTMLElement.prototype, method, {
      configurable: true, writable: true, value: () => undefined,
    })
  }
  if (!('hasPointerCapture' in HTMLElement.prototype)) Object.defineProperty(HTMLElement.prototype, 'hasPointerCapture', {
    configurable: true, writable: true, value: () => false,
  })
}
