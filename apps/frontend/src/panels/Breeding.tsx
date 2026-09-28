import { Card, Bar, Tag } from '../components/ui'

const TAMES = [
  { id: 'rex-01', species: 'Rex', maturity: 0.65, imprint: 0.5, mutations: 4, nextImprint: '12m' },
  { id: 'rex-02', species: 'Rex', maturity: 0.21, imprint: 0.12, mutations: 7, nextImprint: '2h' },
  { id: 'argy-01', species: 'Argentavis', maturity: 0.9, imprint: 0.88, mutations: 2, nextImprint: '34m' },
]

export function Breeding() {
  return (
    <div className="grid breeding">
      <Card title="Active Babies">
        {TAMES.map((t) => (
          <div key={t.id} className="baby-card">
            <div className="agent-header">
              <strong>{t.species} <span className="muted">({t.id})</span></strong>
              <Tag tone="warn">{t.mutations} mutations</Tag>
            </div>
            <Bar value={t.maturity} label={`Maturation ${Math.round(t.maturity * 100)}%`} />
            <Bar value={t.imprint} label={`Imprint ${Math.round(t.imprint * 100)}%`} />
            <div className="agent-meta muted">Next imprint: {t.nextImprint}</div>
          </div>
        ))}
      </Card>
      <Card title="Mutation Tracker">
        <table className="table">
          <thead>
            <tr><th>Pair</th><th>Predicted</th><th>Observed</th><th>Stat</th></tr>
          </thead>
          <tbody>
            <tr><td>A×B</td><td>+2</td><td>+2</td><td>Health</td></tr>
            <tr><td>A×C</td><td>+1</td><td>+0</td><td>Speed</td></tr>
            <tr><td>D×E</td><td>+2</td><td>+2</td><td>Damage</td></tr>
          </tbody>
        </table>
      </Card>
    </div>
  )
}
