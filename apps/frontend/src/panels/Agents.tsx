import { useEffect, useState } from 'react'
import { core } from '../core/mock'
import type { AgentStatus } from '../core/types'
import { Bar, Card, Tag } from '../components/ui'

const AGENT_CATALOG = ['Farmer', 'Breeder', 'Tamer', 'Imprinter', 'Scout', 'BossPrep', 'ResourceRunner', 'Builder']

export function Agents() {
  const [agents, setAgents] = useState<AgentStatus[]>([])
  const [spawned, setSpawned] = useState<Record<string, boolean>>({})

  useEffect(() => {
    const id = setInterval(async () => {
      const snap = await core.snapshot()
      setAgents(snap.agents)
    }, 2000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="grid agents">
      <Card title="Running Agents">
        {agents.map((a) => (
          <div key={a.id} className="agent-card">
            <div className="agent-header">
              <strong>{a.kind}</strong>
              <Tag tone={a.state === 'Blocked' ? 'err' : a.state === 'Acting' ? 'ok' : 'muted'}>{a.state}</Tag>
            </div>
            <Bar value={a.progress} />
            <div className="agent-meta muted">
              {a.ticks} ticks · {a.failures} failures
            </div>
          </div>
        ))}
      </Card>
      <Card title="Agent Catalog">
        {AGENT_CATALOG.map((kind) => (
          <div key={kind} className="catalog-row">
            <span>{kind}</span>
            <button
              className="btn small"
              onClick={() => setSpawned((s) => ({ ...s, [kind]: true }))}
              disabled={spawned[kind]}
            >
              {spawned[kind] ? 'Spawned' : 'Spawn'}
            </button>
          </div>
        ))}
      </Card>
    </div>
  )
}
