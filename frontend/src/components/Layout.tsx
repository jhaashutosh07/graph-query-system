import type { ReactNode } from 'react'

export function Layout({ left, right }: { left: ReactNode; right: ReactNode }) {
  return (
    <div className="app-root">
      <header>
        <h1>Graph-Based Query System</h1>
        <p>Natural language to graph insights</p>
      </header>
      <main>
        <div className="left-pane">{left}</div>
        <div className="right-pane">{right}</div>
      </main>
    </div>
  )
}
