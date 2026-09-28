use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Copy, Serialize, Deserialize, PartialEq, Eq, Hash)]
pub enum Stat {
    Health,
    Stamina,
    Oxygen,
    Food,
    Weight,
    Damage,
    Speed,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Mutation {
    pub id: String,
    pub stat: Stat,
    pub bonus: f64,
    pub from_parent: Option<String>, // "sire" | "dam"
    pub generation: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Lineage {
    pub sire: Option<String>,
    pub dam: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Tame {
    pub id: String,
    pub species: String,
    pub stats: HashMap<Stat, f64>,
    pub lineage: Lineage,
    pub generation: u32,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct Offspring {
    pub expected_stats: HashMap<Stat, f64>,
    pub predicted_mutations: Vec<Mutation>,
}

/// The classic ARK rule: each mutation adds 2 points to a stat (or 1 if the
/// stat is movement speed) and increments a counter in the parent's line.
pub fn apply_mutation(stat: Stat, parent_stat: f64) -> f64 {
    if stat == Stat::Speed {
        parent_stat + 1.0
    } else {
        parent_stat + 2.0
    }
}

/// Track mutations across generations.
#[derive(Default)]
pub struct MutationTracker {
    pub tames: Vec<Tame>,
}

impl MutationTracker {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn register(&mut self, t: Tame) {
        if let Some(existing) = self.tames.iter_mut().find(|x| x.id == t.id) {
            *existing = t;
        } else {
            self.tames.push(t);
        }
    }

    pub fn get(&self, id: &str) -> Option<&Tame> {
        self.tames.iter().find(|t| t.id == id)
    }

    /// Simulate offspring by averaging parent stats, then applying the
    /// mutation bonus where a mutation is claimed.
    pub fn breed(&self, sire_id: &str, dam_id: &str, mutations: &[Stat]) -> Result<Offspring, String> {
        let sire = self.get(sire_id).ok_or(format!("unknown sire {sire_id}"))?;
        let dam = self.get(dam_id).ok_or(format!("unknown dam {dam_id}"))?;
        if sire.species != dam.species {
            return Err(format!(
                "species mismatch: {} vs {}",
                sire.species, dam.species
            ));
        }

        let mut expected = HashMap::new();
        let mut predicted = Vec::new();
        for stat in [Stat::Health, Stat::Stamina, Stat::Oxygen, Stat::Food, Stat::Weight, Stat::Damage, Stat::Speed] {
            let sire_v = sire.stats.get(&stat).copied().unwrap_or(0.0);
            let dam_v = dam.stats.get(&stat).copied().unwrap_or(0.0);
            let base = (sire_v + dam_v) / 2.0;
            if mutations.contains(&stat) {
                let mutated = apply_mutation(stat, base);
                predicted.push(Mutation {
                    id: format!("{}-{}", sire_id, stat as usize),
                    stat,
                    bonus: mutated - base,
                    from_parent: None,
                    generation: sire.generation.max(dam.generation) + 1,
                });
                expected.insert(stat, mutated);
            } else {
                expected.insert(stat, base);
            }
        }
        Ok(Offspring {
            expected_stats: expected,
            predicted_mutations: predicted,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn rex(id: &str, hp: f64) -> Tame {
        let mut stats = HashMap::new();
        stats.insert(Stat::Health, hp);
        stats.insert(Stat::Weight, 100.0);
        stats.insert(Stat::Speed, 20.0);
        Tame {
            id: id.into(),
            species: "Rex".into(),
            stats,
            lineage: Lineage { sire: None, dam: None },
            generation: 0,
        }
    }

    #[test]
    fn mutation_adds_two_points_to_health() {
        assert_eq!(apply_mutation(Stat::Health, 100.0), 102.0);
    }

    #[test]
    fn speed_mutation_adds_one() {
        assert_eq!(apply_mutation(Stat::Speed, 20.0), 21.0);
    }

    #[test]
    fn breed_averages_and_applies_mutation() {
        let mut t = MutationTracker::new();
        t.register(rex("A", 100.0));
        t.register(rex("B", 120.0));
        let off = t.breed("A", "B", &[Stat::Health]).unwrap();
        // (100 + 120)/2 + 2
        assert_eq!(off.expected_stats.get(&Stat::Health), Some(&112.0));
        assert_eq!(off.expected_stats.get(&Stat::Weight), Some(&100.0));
        assert_eq!(off.predicted_mutations.len(), 1);
        assert_eq!(off.predicted_mutations[0].stat, Stat::Health);
    }

    #[test]
    fn breed_rejects_species_mismatch() {
        let mut t = MutationTracker::new();
        t.register(rex("A", 100.0));
        let mut giga = rex("G", 500.0);
        giga.species = "Giga".into();
        t.register(giga);
        assert!(t.breed("A", "G", &[]).is_err());
    }

    #[test]
    fn unknown_parent_errors() {
        let mut t = MutationTracker::new();
        t.register(rex("A", 100.0));
        assert!(t.breed("A", "Nope", &[]).is_err());
    }

    #[test]
    fn offspring_generation_increments() {
        let mut t = MutationTracker::new();
        t.register(rex("A", 100.0));
        t.register(rex("B", 120.0));
        let off = t.breed("A", "B", &[Stat::Health]).unwrap();
        assert_eq!(off.predicted_mutations[0].generation, 1);
    }
}
