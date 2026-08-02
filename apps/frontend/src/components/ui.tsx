import type { ReactNode } from 'react'

export function Card({ title, children, accent }: { title?: string; children: ReactNode; accent?: string }) {
  return (
    <div className="card" style={accent ? { borderLeft: `4px solid ${accent}` } : undefined}>
      {title && <div className="card-title">{title}</div>}
      <div className="card-body">{children}</div>
    </div>
  )
}

export function Bar({ value, max = 1, label }: { value: number; max?: number; label?: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  return (
    <div className="bar">
      {label && <div className="bar-label">{label}</div>}
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  )
}

export function Tag({ children, tone }: { children: ReactNode; tone?: 'ok' | 'warn' | 'err' | 'muted' }) {
  return <span className={`tag tag-${tone ?? 'muted'}`}>{children}</span>
}
