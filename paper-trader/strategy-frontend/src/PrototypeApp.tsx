import { Component, useEffect, type ReactNode } from 'react'
import { Routes, Route, useLocation } from 'react-router-dom'
import Launcher from './pages/Launcher'
import DirectionD1 from './directions/d1'
import DirectionD2 from './directions/d2'
import DirectionD3 from './directions/d3'
import DirectionD4 from './directions/d4'
import DirectionD5 from './directions/d5'
import DirectionD6 from './directions/d6'
import DirectionD7 from './directions/d7'
import DirectionD8 from './directions/d8'
import DirectionD9 from './directions/d9'
import DirectionD10 from './directions/d10'
import DirectionD11 from './directions/d11'

class DirectionBoundary extends Component<{ children: ReactNode }, { err: string | null }> {
  state = { err: null as string | null }
  static getDerivedStateFromError(e: unknown) {
    return { err: e instanceof Error ? e.message : String(e) }
  }
  render() {
    if (this.state.err) {
      return (
        <div className="min-h-screen bg-base flex items-center justify-center p-10">
          <div className="max-w-lg border border-edge bg-surface rounded-lg p-6">
            <div className="text-2xs uppercase tracking-widest text-bad mb-2">Direction crashed</div>
            <div className="text-muted text-sm font-mono break-all">{this.state.err}</div>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}

function ScrollTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

export default function App() {
  return (
    <>
      <ScrollTop />
      <Routes>
        <Route path="/prototype" element={<Launcher />} />
        <Route
          path="/d1/*"
          element={
            <DirectionBoundary>
              <DirectionD1 />
            </DirectionBoundary>
          }
        />
        <Route
          path="/d2/*"
          element={
            <DirectionBoundary>
              <DirectionD2 />
            </DirectionBoundary>
          }
        />
        <Route
          path="/d3/*"
          element={
            <DirectionBoundary>
              <DirectionD3 />
            </DirectionBoundary>
          }
        />
        <Route
          path="/d4/*"
          element={
            <DirectionBoundary>
              <DirectionD4 />
            </DirectionBoundary>
          }
        />
        <Route
          path="/d5/*"
          element={
            <DirectionBoundary>
              <DirectionD5 />
            </DirectionBoundary>
          }
        />
        <Route
          path="/d6/*"
          element={
            <DirectionBoundary>
              <DirectionD6 />
            </DirectionBoundary>
          }
        />
        <Route
          path="/d7/*"
          element={<DirectionBoundary><DirectionD7 /></DirectionBoundary>}
        />
        <Route
          path="/d8/*"
          element={<DirectionBoundary><DirectionD8 /></DirectionBoundary>}
        />
        <Route
          path="/d9/*"
          element={<DirectionBoundary><DirectionD9 /></DirectionBoundary>}
        />
        <Route
          path="/d10/*"
          element={<DirectionBoundary><DirectionD10 /></DirectionBoundary>}
        />
        <Route
          path="/d11/*"
          element={<DirectionBoundary><DirectionD11 /></DirectionBoundary>}
        />
      </Routes>
    </>
  )
}
