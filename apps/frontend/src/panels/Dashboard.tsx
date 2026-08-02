import { useEffect, useState } from 'react'
import { core } from '../core/mock'
import type { AgentStatus, Job } from '../core/types'
import { Bar, Card, Stat, Tag } from '../components/ui'

export function Dashboard() {
  const [agents, setAgents] = useState<AgentStatus[]>([])
  const [jobs, setJobs] = useState<Job[]>([])
  const [mode, setMode] = useState('Assisted')

  useEffect(() => {
    const id = setInterval(async () => {
      const snap = await core.snapshot()
      setAgents(snap.agents)
      setJobs(snap.jobs)
      setMode(snap.mode)
    }, 2000)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="grid dashboard">
      <Card title="Autopilot">
        <Stat label="Mode" value={mode} />
        <Stat label="Vision" value="30 fps" />
        <Stat label="Latency" value="5 ms" />
      </Card>
      <Card title="Agents">
        {agents.map((a) => (
          <div key={a.id} className="agent-row">
            <div>
              <strong>{a.kind}</strong>
              <Tag tone={a.state === 'Blocked' ? 'err' : a.state === 'Acting' ? 'ok' : 'muted'}>{a.state}</Tag>
            </div>
            <Bar value={a.progress} label={`${Math.round(a.progress * 100)}%`} />
          </div>
        ))}
      </Card>
      <Card title="Upcoming Jobs">
        {jobs.map((j) => (
          <div key={j.id} className="job-row">
            <span>{j.name}</span>
            <span className="muted">{j.nextRun}</span>
          </div>
        ))}
      </Card>
      <Card title="World Snapshot">
        <Stat label="HP" value="87%" />
        <Stat label="Weight" value="62%" />
        <Stat label="Taming" value="43%" />
        <Stat label="Maturation" value="21%" />
      </Card>
    </div>
  )
}
