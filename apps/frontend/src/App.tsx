import { useState } from 'react'
import './App.css'
import { Shell, type PanelId } from './components/Shell'
import { Dashboard } from './panels/Dashboard'
import { MacroStudio } from './panels/MacroStudio'
import { Agents } from './panels/Agents'
import { SchedulerPanel } from './panels/Scheduler'
import { Breeding } from './panels/Breeding'
import { Vision } from './panels/Vision'
import { Scripts } from './panels/Scripts'
import { Devices } from './panels/Devices'
import { Marketplace } from './panels/Marketplace'
import { KnowledgeDb } from './panels/KnowledgeDb'
import { Telemetry } from './panels/Telemetry'
import { Settings } from './panels/Settings'

const PANELS: Record<PanelId, () => React.JSX.Element> = {
  dashboard: Dashboard,
  macro: MacroStudio,
  agents: Agents,
  schedule: SchedulerPanel,
  breeding: Breeding,
  vision: Vision,
  scripts: Scripts,
  devices: Devices,
  market: Marketplace,
  kb: KnowledgeDb,
  telemetry: Telemetry,
  settings: Settings,
}

function App() {
  const [active, setActive] = useState<PanelId>('dashboard')
  const [mode, setMode] = useState('Assisted')
  const [killed, setKilled] = useState(false)

  const Panel = PANELS[active]

  return (
    <Shell
      active={active}
      onNavigate={setActive}
      mode={killed ? 'EMERGENCY STOP' : mode}
      onKillSwitch={() => {
        setKilled(true)
        setTimeout(() => {
          setKilled(false)
          setMode('Manual')
        }, 2000)
      }}
    >
      <Panel />
    </Shell>
  )
}

export default App
