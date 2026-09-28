import type { ReactNode } from 'react'
import { useState } from 'react'

const NAV = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'macro', label: 'Macro Studio' },
  { id: 'agents', label: 'Agents' },
  { id: 'schedule', label: 'Scheduler' },
  { id: 'breeding', label: 'Breeding' },
  { id: 'vision', label: 'Vision' },
  { id: 'scripts', label: 'NexusScript' },
  { id: 'devices', label: 'Devices' },
  { id: 'market', label: 'Marketplace' },
  { id: 'kb', label: 'Knowledge DB' },
  { id: 'telemetry', label: 'Telemetry' },
  { id: 'settings', label: 'Settings' },
] as const

export type PanelId = (typeof NAV)[number]['id']

export function Shell({
  active,
  onNavigate,
  mode,
  onKillSwitch,
  children,
}: {
  active: PanelId
  onNavigate: (id: PanelId) => void
  mode: string
  onKillSwitch: () => void
  children: ReactNode
}) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="shell">
      <aside className={`sidebar ${collapsed ? 'collapsed' : ''}`}>
        <div className="brand" onClick={() => setCollapsed(!collapsed)}>
          <span className="brand-mark">N</span>
          {!collapsed && <span className="brand-text">ARK NEXUS X</span>}
        </div>
        <nav>
          {NAV.map((n) => (
            <button
              key={n.id}
              className={`nav-item ${active === n.id ? 'active' : ''}`}
              onClick={() => onNavigate(n.id)}
              title={n.label}
            >
              <span className="nav-dot" />
              {!collapsed && <span>{n.label}</span>}
            </button>
          ))}
        </nav>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="mode-pill">{mode}</div>
          <button className="kill-switch" onClick={onKillSwitch}>
            KILL SWITCH
          </button>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  )
}
