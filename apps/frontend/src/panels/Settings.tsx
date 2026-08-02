import { useState } from 'react'
import { Card } from '../components/ui'

export function Settings() {
  const [sensitivity, setSensitivity] = useState(1.0)
  const [mode, setMode] = useState('Assisted')
  const [device, setDevice] = useState('gpu')
  const [model, setModel] = useState('qwen2.5:7b-q4')

  return (
    <div className="grid settings">
      <Card title="Input Profile">
        <label className="field">
          Mouse sensitivity
          <input type="range" min={0.2} max={2.0} step={0.1} value={sensitivity} onChange={(e) => setSensitivity(Number(e.target.value))} />
          <span className="muted">{sensitivity.toFixed(1)}x</span>
        </label>
        <label className="field">
          Global mode
          <select value={mode} onChange={(e) => setMode(e.target.value)}>
            <option>Manual</option>
            <option>Assisted</option>
            <option>Autonomous</option>
          </select>
        </label>
      </Card>
      <Card title="Model Runtime">
        <label className="field">
          Inference device
          <select value={device} onChange={(e) => setDevice(e.target.value)}>
            <option value="gpu">GPU (TensorRT)</option>
            <option value="gpu-fallback">GPU → DirectML → CPU</option>
            <option value="cpu">CPU only</option>
          </select>
        </label>
        <label className="field">
          Planner model
          <select value={model} onChange={(e) => setModel(e.target.value)}>
            <option>qwen2.5:7b-q4</option>
            <option>phi-4-mini</option>
            <option>llama-3.2-3b</option>
          </select>
        </label>
      </Card>
      <Card title="Device Integration">
        <div className="field">
          <label><input type="checkbox" defaultChecked /> Logitech LGHUB</label>
          <label><input type="checkbox" defaultChecked /> Razer Synapse</label>
          <label><input type="checkbox" /> Corsair iCUE</label>
          <label><input type="checkbox" defaultChecked /> Stream Deck</label>
        </div>
      </Card>
      <Card title="Safety">
        <div className="field">
          <label><input type="checkbox" defaultChecked /> Enable kill-switch (Ctrl+Alt+K)</label>
          <label><input type="checkbox" defaultChecked /> Act only when ARK is foreground</label>
          <label><input type="checkbox" defaultChecked /> Self-improvement auto-tune</label>
        </div>
      </Card>
    </div>
  )
}
