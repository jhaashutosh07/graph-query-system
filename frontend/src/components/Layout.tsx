import type { ReactNode } from 'react'

export function Layout({ left, right }: { left: ReactNode; right: ReactNode }) {
  return (
    <div className="app-root">
      <header className="topbar">
        <div className="topbar-left">
          <div className="menu-icon" role="button" aria-label="Menu">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <div className="breadcrumb">
            <span className="crumb">Mapping</span>
            <span className="crumb-sep">/</span>
            <span className="crumb-active">Order to Cash</span>
          </div>
        </div>
        <div className="topbar-right" />
      </header>
      <main>
        <div className="left-pane">{left}</div>
        <div className="right-pane">{right}</div>
      </main>
    </div>
  )
}