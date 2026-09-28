import { useState } from 'react'
import { Card, Tag } from '../components/ui'

const DEFAULT_SCRIPT = `# Farmer.nexus — gather metal at the mountain node
import ark.*
import vision.*

config {
  max_runs: 5,
  timeout_s: 3600,
  require: ["pick", "metal_location"],
}

run(mount, location) {
  mount_ride(mount)
  navigate_to(location)
  repeat max_runs {
    let node = vision.find_nearest("metal_node")
    break unless node
    approach(node, dist: 2.0)
    attack(hold_ms: 400)
    wait_for_hud("weight", < 80%)
    harvest_ground()
    wait(500ms)
  }
  return_to_base()
  deposit_all("storage")
  log("done: runs=", max_runs)
}`

const MARKERS: Record<string, string> = {
  import: '#5ac8fa',
  config: '#ffd60a',
  run: '#ff9f0a',
  repeat: '#ff9f0a',
  let: '#bf5af2',
  break: '#ff9f0a',
  unless: '#ff9f0a',
  log: '#30d158',
}

function highlight(code: string): React.ReactNode {
  const lines = code.split('\n')
  return lines.map((line, i) => {
    const first = line.match(/^(\w+)/)?.[1]
    const color = first ? MARKERS[first] : undefined
    return (
      <div key={i} className="code-line" style={color ? { color } : undefined}>
        <span className="code-no">{i + 1}</span>
        <span>{line}</span>
      </div>
    )
  })
}

export function Scripts() {
  const [src, setSrc] = useState(DEFAULT_SCRIPT)
  const [checked, setChecked] = useState<null | { ok: boolean; msg: string }>(null)

  const runCheck = () => {
    const hasRun = /run\s*\(/.test(src)
    const hasRepeat = /\brepeat\b/.test(src)
    const hasCap = /require:\s*\[/.test(src)
    setChecked({
      ok: hasRun && hasRepeat && hasCap,
      msg: hasRun && hasRepeat && hasCap
        ? 'nexus check: OK — capabilities declared, liveness confirmed'
        : 'nexus check: 3 issues (missing run(), repeat, or require: [...])',
    })
  }

  return (
    <div className="grid scripts">
      <Card title="NexusScript Editor">
        <pre className="code-editor">{highlight(src)}</pre>
        <textarea
          className="hidden-src"
          value={src}
          onChange={(e) => setSrc(e.target.value)}
          spellCheck={false}
        />
        <div className="btn-row">
          <button className="btn" onClick={runCheck}>nexus check</button>
          <button className="btn" onClick={() => setChecked(null)}>fmt</button>
          <button className="btn accent">Run</button>
        </div>
      </Card>
      <Card title="Capabilities">
        <Tag tone="ok">input</Tag> <Tag tone="ok">screen</Tag>
        <Tag tone="ok">kb:read</Tag> <Tag tone="warn">kb:write</Tag>
        <div className="muted" style={{ marginTop: 8 }}>
          {checked ? checked.msg : 'Run nexus check to validate.'}
        </div>
      </Card>
    </div>
  )
}
