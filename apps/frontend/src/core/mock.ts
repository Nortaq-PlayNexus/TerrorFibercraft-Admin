// Mock of the Rust core IPC surface (doc 13). Each function mirrors a real
// Tauri command. Swap this module for the generated IPC client in production.

import type {
  AgentStatus, Job, Macro, PackageInfo, TelemetryMetric, Tuning, VisionState,
} from './types'

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms))

let tick = 0
export const mockStore = {
  mode: 'Assisted' as 'Manual' | 'Assisted' | 'Autonomous',
  agents: [
    { id: 'farmer', kind: 'Farmer', state: 'Acting', ticks: 812, failures: 1, progress: 0.42 },
    { id: 'imprinter', kind: 'Imprinter', state: 'Waiting', ticks: 34, failures: 0, progress: 0.7 },
    { id: 'scout', kind: 'Scout', state: 'Idle', ticks: 120, failures: 0, progress: 1 },
  ] as AgentStatus[],
  jobs: [
    { id: 'imprint-rex-01', name: 'Imprint Rex 01', trigger: 'event: hud.imprint.available', action: 'agent:Imprinter', enabled: true, nextRun: 'in 12m' },
    { id: 'metal-rush', name: 'Metal Rush', trigger: 'cron: */30 * * * *', action: 'macro: farm-metal', enabled: true, nextRun: 'in 18m' },
    { id: 'night-guard', name: 'Night Guard', trigger: 'event: world.night', action: 'script: night_watch.nexus', enabled: false, nextRun: '—' },
  ] as Job[],
}

export const core = {
  async snapshot(): Promise<{ mode: typeof mockStore.mode; agents: AgentStatus[]; jobs: Job[] }> {
    tick += 1
    if (tick % 5 === 0) {
      mockStore.agents[0].progress = Math.min(1, mockStore.agents[0].progress + 0.03)
    }
    return { mode: mockStore.mode, agents: mockStore.agents, jobs: mockStore.jobs }
  },

  async killSwitch(): Promise<void> { await wait(100) },
  async setMode(m: 'Manual' | 'Assisted' | 'Autonomous'): Promise<void> {
    mockStore.mode = m
    await wait(120)
  },

  async vision(): Promise<VisionState> {
    await wait(40)
    const now = Date.now()
    return {
      capturedAtMs: now,
      fps: 30,
      player: { hp: 0.87, weight: 0.62, stamina: 0.55, inventoryOpen: false },
      hud: { tamingPercent: 0.43, maturationPercent: 0.21, imprintPercent: 0.12 },
      objects: [
        { id: 7, class: 'metal_node', conf: 0.94, bbox: [120, 340, 45, 67], lastSeenMs: now - 120 },
        { id: 3, class: 'rex', conf: 0.81, bbox: [540, 210, 90, 80], lastSeenMs: now - 900 },
        { id: 9, class: 'anky', conf: 0.88, bbox: [390, 420, 60, 55], lastSeenMs: now - 300 },
      ],
      warnings: [],
    }
  },

  async macros(): Promise<Macro[]> {
    await wait(50)
    return [
      {
        id: 'farm-metal', name: 'Farm Metal', recordedMs: 42_000,
        nodes: [
          { kind: 'delay', label: 'Delay 500ms', ms: 500 },
          { kind: 'key', label: 'W down' },
          { kind: 'key', label: 'W up' },
          { kind: 'vision', label: 'wait metal_node' },
          { kind: 'key', label: 'Attack (hold 400ms)' },
          { kind: 'delay', label: 'Delay 1.2s', ms: 1200 },
        ],
      },
      {
        id: 'deposit', name: 'Deposit All', recordedMs: 12_000,
        nodes: [
          { kind: 'key', label: 'F open inventory' },
          { kind: 'vision', label: 'wait inventory_open' },
          { kind: 'key', label: 'Ctrl+A (transfer)' },
          { kind: 'key', label: 'Esc' },
        ],
      },
    ]
  },

  async telemetryMetrics(): Promise<TelemetryMetric[]> {
    await wait(40)
    return [
      { name: 'tame.success', count: 46, success: 0.72 },
      { name: 'macro.timing', count: 210, success: 0.94 },
      { name: 'farm.yield', count: 88, success: 0.89 },
      { name: 'vision.detect', count: 1540, success: 0.97 },
    ]
  },

  async tunings(): Promise<Tuning[]> {
    await wait(40)
    return [
      { id: 1, parameter: 'tame_success_threshold', from: '60.0', to: '66.0', reason: 'tame.success 72% below target; raise threshold by 10%', applied: true },
      { id: 2, parameter: 'snap_ms', from: '50.0', to: '45.0', reason: 'macro.timing error p95 8ms; tighten snapping', applied: true },
    ]
  },

  async packages(): Promise<PackageInfo[]> {
    await wait(50)
    return [
      { id: 'com.nexusx.farmer-metal-rush', name: 'Metal Rush Farmer', version: '1.2.0', author: 'someUser', tier: 'curated', capabilities: ['input', 'screen', 'kb:read'], installed: true },
      { id: 'com.nexusx.tame-assist', name: 'Tame Assist', version: '0.9.4', author: 'breeder42', tier: 'community', capabilities: ['input', 'screen'], installed: false },
      { id: 'com.nexusx.boss-prep', name: 'Boss Prep Planner', version: '2.0.1', author: 'nexus', tier: 'official', capabilities: ['kb:read', 'kb:write'], installed: false },
    ]
  },
}
