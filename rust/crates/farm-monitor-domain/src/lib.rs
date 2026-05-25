use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct HealthStatus {
    pub status: String,
    pub service: String,
}

impl HealthStatus {
    pub fn ok(service: &str) -> Self {
        Self {
            status: "ok".to_string(),
            service: service.to_string(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn health_status_ok_constructor_sets_expected_values() {
        let health = HealthStatus::ok("farm-monitor-api");
        assert_eq!(health.status, "ok");
        assert_eq!(health.service, "farm-monitor-api");
    }
}
