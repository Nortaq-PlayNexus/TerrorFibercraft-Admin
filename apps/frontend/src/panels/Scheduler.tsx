import { useEffect, useState } from 'react'
import { core } from '../core/mock'
import type { Job } from '../core/types'
import { Card, Tag } from '../components/ui'

const PRESETS = [
  { name: 'Imprint Rex', trigger: 'event: hud.imprint.available' },
  { name: 'Metal Rush', trigger: 'cron: */30 * * * *' },
  { name: 'Night Guard', trigger: 'event: world.night' },
  { name: 'Fertilize', trigger: 'interval: 45m' },
]

export function SchedulerPanel() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [added, setAdded] = useState<string[]>([])

  useEffect(() => {
    core.snapshot().then((s) => setJobs(s.jobs))
  }, [])

  const addJob = (name: string, trigger: string) => {
    const j: Job = {
      id: `${name.toLowerCase().replace(/\s/g, '-')}-${Date.now()}`,
      name,
      trigger,
      action: 'macro',
      enabled: true,
      nextRun: 'pending',
    }
    setJobs((j2) => [...j2, j])
    setAdded((a) => [...a, name])
  }

  return (
    <div className="grid scheduler">
      <Card title="Jobs">
        {jobs.map((j) => (
          <div key={j.id} className="job-row">
            <span><strong>{j.name}</strong></span>
            <Tag tone={j.enabled ? 'ok' : 'muted'}>{j.enabled ? 'on' : 'off'}</Tag>
            <span className="muted">{j.trigger}</span>
          </div>
        ))}
      </Card>
      <Card title="Create Job">
        {PRESETS.map((p) => (
          <div key={p.name} className="catalog-row">
            <span>{p.name}</span>
            <span className="muted">{p.trigger}</span>
            <button className="btn small" onClick={() => addJob(p.name, p.trigger)} disabled={added.includes(p.name)}>
              {added.includes(p.name) ? 'Added' : 'Add'}
            </button>
          </div>
        ))}
      </Card>
    </div>
  )
}
