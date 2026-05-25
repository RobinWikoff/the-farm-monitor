use chrono::{DateTime, Duration, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum GuardrailDecision {
    Allowed,
    BlockedBudgetExhausted,
    BlockedCooldown { until: DateTime<Utc> },
}

#[derive(Debug, Default, Clone, Serialize, Deserialize)]
pub struct DevGuardrail {
    usage: HashMap<String, u32>,
    blocked: HashMap<String, u32>,
    cooldown_until: HashMap<String, DateTime<Utc>>,
}

impl DevGuardrail {
    pub fn check_and_record(
        &mut self,
        key: &str,
        budget: u32,
        now: DateTime<Utc>,
    ) -> GuardrailDecision {
        if let Some(until) = self.cooldown_until.get(key) {
            if now < *until {
                *self.blocked.entry(key.to_string()).or_default() += 1;
                return GuardrailDecision::BlockedCooldown { until: *until };
            }
        }

        let used = self.usage.get(key).copied().unwrap_or(0);
        if used >= budget {
            *self.blocked.entry(key.to_string()).or_default() += 1;
            return GuardrailDecision::BlockedBudgetExhausted;
        }

        self.usage.insert(key.to_string(), used + 1);
        GuardrailDecision::Allowed
    }

    pub fn start_cooldown(
        &mut self,
        key: &str,
        now: DateTime<Utc>,
        cooldown_minutes: i64,
    ) -> DateTime<Utc> {
        let until = now + Duration::minutes(cooldown_minutes);
        self.cooldown_until.insert(key.to_string(), until);
        until
    }

    pub fn usage_for(&self, key: &str) -> u32 {
        self.usage.get(key).copied().unwrap_or(0)
    }

    pub fn blocked_for(&self, key: &str) -> u32 {
        self.blocked.get(key).copied().unwrap_or(0)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn guardrail_blocks_after_budget_exhaustion() {
        let mut g = DevGuardrail::default();
        let now = Utc::now();

        assert_eq!(
            g.check_and_record("vc_forecast", 2, now),
            GuardrailDecision::Allowed
        );
        assert_eq!(
            g.check_and_record("vc_forecast", 2, now),
            GuardrailDecision::Allowed
        );
        assert_eq!(
            g.check_and_record("vc_forecast", 2, now),
            GuardrailDecision::BlockedBudgetExhausted
        );
        assert_eq!(g.usage_for("vc_forecast"), 2);
        assert_eq!(g.blocked_for("vc_forecast"), 1);
    }

    #[test]
    fn guardrail_blocks_during_cooldown_window() {
        let mut g = DevGuardrail::default();
        let now = Utc::now();
        let until = g.start_cooldown("open_meteo", now, 30);

        assert_eq!(
            g.check_and_record("open_meteo", 10, now + Duration::minutes(5)),
            GuardrailDecision::BlockedCooldown { until }
        );
        assert_eq!(g.blocked_for("open_meteo"), 1);

        assert_eq!(
            g.check_and_record("open_meteo", 10, now + Duration::minutes(31)),
            GuardrailDecision::Allowed
        );
    }
}
