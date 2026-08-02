import { useEffect, useState } from 'react'
import { core } from '../core/mock'
import type { TelemetryMetric, Tuning } from '../core/types'
import { Bar, Card, Tag } from '../components/ui'

export function Telemetry() {
  const [metrics, setMetrics] = useState<TelemetryMetric[]>([])
  const [tunings, setTunings] = useState<Tuning[]>([])

  useEffect(() => {
    core.telemetryMetrics().then(setMetrics)
    core.tunings().then(setTunings)
  }, [])

  return (
    <div className="grid telemetry">
      <Card title="Metrics">
        {metrics.map((m) => (
          <div key={m.name} className="metric-row">
            <div className="agent-header">
              <span>{m.name}</span>
              <Tag tone={m.success > 0.8 ? 'ok' : 'warn'}>{Math.round(m.success * 100)}%</Tag>
            </div>
            <Bar value={m.success} />
            <div className="agent-meta muted">{m.count} samples</div>
          </div>
        ))}
      </Card>
      <Card title="Applied Tunings (Self-Improvement)">
        {tunings.map((t) => (
          <div key={t.id} className="tuning-card">
            <div className="agent-header">
              <strong>{t.parameter}</strong>
              <Tag tone={t.applied ? 'ok' : 'muted'}>{t.applied ? 'applied' : 'rolled back'}</Tag>
            </div>
            <div className="muted">
              {t.from} → {t.to}
            </div>
            <div className="muted">{t.reason}</div>
          </div>
        ))}
      </Card>
    </div>
  )
}
