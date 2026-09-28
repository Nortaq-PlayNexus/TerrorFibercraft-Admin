import { Card, Tag } from '../components/ui'

const DEVICES = [
  { vendor: 'Logitech', status: 'detected', sdk: 'LGHUB', bindings: ['mouse.g7 → run macro farm-metal'] },
  { vendor: 'Razer', status: 'detected', sdk: 'Synapse Chroma', bindings: ['fx: farmer → pulse_blue'] },
  { vendor: 'Corsair', status: 'not detected', sdk: 'iCUE', bindings: [] },
  { vendor: 'Stream Deck', status: 'detected', sdk: 'Elgato WS', bindings: ['key:0,0 → toggle farmer', 'key:0,1 → kill switch'] },
]

export function Devices() {
  return (
    <div className="grid devices">
      <Card title="Device Providers">
        {DEVICES.map((d) => (
          <div key={d.vendor} className="device-card">
            <div className="agent-header">
              <strong>{d.vendor}</strong>
              <Tag tone={d.status === 'detected' ? 'ok' : 'err'}>{d.status}</Tag>
            </div>
            <div className="muted">{d.sdk}</div>
            <ul>
              {d.bindings.map((b, i) => (
                <li key={i} className="muted">{b}</li>
              ))}
            </ul>
          </div>
        ))}
      </Card>
      <Card title="Action Map">
        <table className="table">
          <thead><tr><th>Device</th><th>Trigger</th><th>Action</th></tr></thead>
          <tbody>
            <tr><td>Stream Deck</td><td>key:0,0</td><td>toggle_agent(farmer)</td></tr>
            <tr><td>Stream Deck</td><td>key:0,1</td><td>kill_switch</td></tr>
            <tr><td>Logitech</td><td>mouse.g7</td><td>run_macro(farm-metal)</td></tr>
            <tr><td>Razer</td><td>agent.farmer</td><td>fx pulse_blue</td></tr>
          </tbody>
        </table>
      </Card>
    </div>
  )
}
