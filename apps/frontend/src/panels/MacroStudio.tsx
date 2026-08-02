import { useEffect, useState } from 'react'
import { core } from '../core/mock'
import type { Macro } from '../core/types'
import { Card, Tag } from '../components/ui'

export function MacroStudio() {
  const [macros, setMacros] = useState<Macro[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [recording, setRecording] = useState(false)

  useEffect(() => {
    core.macros().then((m) => {
      setMacros(m)
      setSelected(m[0]?.id ?? null)
    })
  }, [])

  const active = macros.find((m) => m.id === selected)

  return (
    <div className="grid macro-studio">
      <Card title="Library">
        {macros.map((m) => (
          <button
            key={m.id}
            className={`row-btn ${active?.id === m.id ? 'active' : ''}`}
            onClick={() => setSelected(m.id)}
          >
            <span>{m.name}</span>
            <span className="muted">{(m.recordedMs / 1000).toFixed(1)}s</span>
          </button>
        ))}
        <button className="row-btn accent" onClick={() => setRecording(!recording)}>
          {recording ? '■ Stop Recording' : '● Record'}
        </button>
      </Card>
      <Card title={active?.name ?? 'Timeline'}>
        {active?.nodes.map((n, i) => (
          <div key={i} className="timeline-node">
            <Tag tone={n.kind === 'vision' ? 'warn' : n.kind === 'delay' ? 'muted' : 'ok'}>{n.kind}</Tag>
            <span>{n.label}</span>
            {n.ms != null && <span className="muted">{n.ms}ms</span>}
          </div>
        ))}
        <div className="btn-row">
          <button className="btn" disabled={!active}>Play</button>
          <button className="btn" disabled={!active}>Clean</button>
          <button className="btn" disabled={!active}>Save</button>
        </div>
      </Card>
    </div>
  )
}
