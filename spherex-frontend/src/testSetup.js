import '@testing-library/jest-dom/vitest'

globalThis.IntersectionObserver = class IntersectionObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

window.scrollTo = () => {}
