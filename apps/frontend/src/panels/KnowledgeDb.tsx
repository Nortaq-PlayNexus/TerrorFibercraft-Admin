import { Card } from '../components/ui'

const CREATURES = [
  { class: 'Rex', taming: 'Knockout', food: 'Kibble (Megalosaurus)', gather: '—', weight: 540 },
  { class: 'Ankylosaurus', taming: 'Knockout', food: 'Kibble (Dilo)', gather: 'Metal ★★★', weight: 420 },
  { class: 'Doedicurus', taming: 'Knockout', food: 'Mejoberries', gather: 'Stone ★★★', weight: 400 },
  { class: 'Argentavis', taming: 'Knockout', food: 'Raw Mutton', gather: 'Carry ★★★', weight: 460 },
  { class: 'Therizinosaurus', taming: 'Knockout', food: 'Kibble (Oviraptor)', gather: 'Multi ★★★', weight: 520 },
]

export function KnowledgeDb() {
  return (
    <div className="grid kb">
      <Card title="Creatures (curated)">
        <table className="table">
          <thead>
            <tr><th>Creature</th><th>Taming</th><th>Preferred Food</th><th>Gather</th><th>Weight</th></tr>
          </thead>
          <tbody>
            {CREATURES.map((c) => (
              <tr key={c.class}>
                <td><strong>{c.class}</strong></td>
                <td>{c.taming}</td>
                <td>{c.food}</td>
                <td>{c.gather}</td>
                <td>{c.weight}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Node Locations — The Island">
        <table className="table">
          <thead><tr><th>Resource</th><th>Best Dino</th><th>Hotspot</th></tr></thead>
          <tbody>
            <tr><td>Metal</td><td>Ankylosaurus</td><td>Mountains N 85° W 40°</td></tr>
            <tr><td>Obsidian</td><td>Ankylosaurus</td><td>Volcano S 50° E 60°</td></tr>
            <tr><td>Crystal</td><td>Ankylosaurus</td><td>Cave NE 30° E 70°</td></tr>
            <tr><td>Thatch</td><td>Mammoth</td><td>Forest W 20° N 30°</td></tr>
          </tbody>
        </table>
      </Card>
    </div>
  )
}
