import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './shell/precision.css'
import App from './App'

// Vite removes this entire branch and its import graph from production builds.
if (import.meta.env.DEV && (location.pathname === '/prototype' || /^\/d\d+(?:\/|$)/.test(location.pathname))) {
  void import('./prototype-entry')
} else {
  document.title = 'Strategy OS'
  createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
}
