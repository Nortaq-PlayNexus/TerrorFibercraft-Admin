import { useEffect, useState } from 'react'
import { core } from '../core/mock'
import type { VisionState } from '../core/types'
import { Bar, Card, Tag } from '../components/ui'

export function Vision() {
  const [vs, setVs] = useState<VisionState | null>(null)

  useEffect(() => {
    const id = setInterval(async () => {
      setVs(await core.vision())
    }, 2000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="grid vision">
      <Card title="Live Feed (masked)">
        <div className="feed">
          <div className="feed-grid" />
          {vs?.objects.map((o) => (
            <div
              key={o.id}
              className="det-box"
              style={{ left: o.bbox[0], top: o.bbox[1], width: o.bbox[2], height: o.bbox[3] }}
            >
              <span>{o.class} {Math.round(o.conf * 100)}%</span>
            </div>
          ))}
          <div className="feed-overlay muted">frame @ {vs?.fps ?? 0} fps</div>
        </div>
      </Card>
      <Card title="HUD Read">
        {vs && (
          <>
            <Bar value={vs.player.hp} label={`HP ${Math.round(vs.player.hp * 100)}%`} />
            <Bar value={vs.player.weight} label={`Weight ${Math.round(vs.player.weight * 100)}%`} />
            {vs.hud.tamingPercent != null && (
              <Bar value={vs.hud.tamingPercent} label={`Taming ${Math.round(vs.hud.tamingPercent * 100)}%`} />
            )}
            {vs.hud.maturationPercent != null && (
              <Bar value={vs.hud.maturationPercent} label={`Maturation ${Math.round(vs.hud.maturationPercent * 100)}%`} />
            )}
          </>
        )}
      </Card>
      <Card title="Detections">
        {vs?.objects.map((o) => (
          <div key={o.id} className="job-row">
            <span>#{o.id} {o.class}</span>
            <Tag tone={o.conf > 0.85 ? 'ok' : 'warn'}>{Math.round(o.conf * 100)}%</Tag>
            <span className="muted">{o.lastSeenMs ? 'fresh' : 'stale'}</span>
          </div>
        ))}
      </Card>
    </div>
  )
}
