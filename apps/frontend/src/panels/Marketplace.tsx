import { useEffect, useState } from 'react'
import { core } from '../core/mock'
import type { PackageInfo } from '../core/types'
import { Card, Tag } from '../components/ui'

const TIER_TONE = { official: 'ok', curated: 'ok', community: 'warn', local: 'muted' } as const

export function Marketplace() {
  const [pkgs, setPkgs] = useState<PackageInfo[]>([])

  useEffect(() => {
    core.packages().then(setPkgs)
  }, [])

  const toggle = (id: string) => {
    setPkgs((ps) => ps.map((p) => (p.id === id ? { ...p, installed: !p.installed } : p)))
  }

  return (
    <div className="grid market">
      <Card title="Packages">
        {pkgs.map((p) => (
          <div key={p.id} className="pkg-card">
            <div className="agent-header">
              <strong>{p.name}</strong>
              <Tag tone={TIER_TONE[p.tier]}>{p.tier}</Tag>
            </div>
            <div className="muted">
              {p.id} · v{p.version} · by {p.author}
            </div>
            <div className="pkg-caps">
              {p.capabilities.map((c) => (
                <Tag key={c} tone={c === 'network' || c === 'kb:write' ? 'err' : 'muted'}>{c}</Tag>
              ))}
            </div>
            <div className="btn-row">
              <button className="btn small" onClick={() => toggle(p.id)}>
                {p.installed ? 'Uninstall' : 'Install'}
              </button>
              <button className="btn small" disabled={!p.installed}>Update</button>
            </div>
          </div>
        ))}
      </Card>
      <Card title="Trust Tiers">
        <div className="muted">
          <Tag tone="ok">official</Tag> — Nexus-signed, CI-tested.
          <br />
          <Tag tone="ok">curated</Tag> — community, reviewed, hash-pinned.
          <br />
          <Tag tone="warn">community</Tag> — author-signed, high-risk caps default off.
          <br />
          <Tag tone="muted">local</Tag> — user-authored, full trust.
        </div>
      </Card>
    </div>
  )
}
