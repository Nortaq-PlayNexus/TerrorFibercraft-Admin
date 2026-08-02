export type Mode = 'Manual' | 'Assisted' | 'Autonomous' | 'Scheduled'

export type AgentState = 'Idle' | 'Planning' | 'Acting' | 'Verifying' | 'Waiting' | 'Blocked' | 'Paused' | 'Killed'

export interface AgentStatus {
  id: string
  kind: string
  state: AgentState
  ticks: number
  failures: number
  progress: number
}

export interface Job {
  id: string
  name: string
  trigger: string
  action: string
  enabled: boolean
  nextRun: string
}

export interface DetectedObject {
  id: number
  class: string
  conf: number
  bbox: [number, number, number, number]
  lastSeenMs: number
}

export interface VisionState {
  capturedAtMs: number
  fps: number
  player: { hp: number; weight: number; stamina: number; inventoryOpen: boolean }
  hud: { tamingPercent: number | null; maturationPercent: number | null; imprintPercent: number | null }
  objects: DetectedObject[]
  warnings: string[]
}

export interface MacroNode {
  kind: 'delay' | 'key' | 'vision' | 'call'
  label: string
  ms?: number
}

export interface Macro {
  id: string
  name: string
  nodes: MacroNode[]
  recordedMs: number
}

export interface Taming {
  id: string
  species: string
  percent: number
  effectiveness: number
  food: string
}

export interface TelemetryMetric {
  name: string
  count: number
  success: number
}

export interface Tuning {
  id: number
  parameter: string
  from: string
  to: string
  reason: string
  applied: boolean
}

export interface PackageInfo {
  id: string
  name: string
  version: string
  author: string
  tier: 'official' | 'curated' | 'community' | 'local'
  capabilities: string[]
  installed: boolean
}
