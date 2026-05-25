use crate::models::{LocationRequest, ProviderForecastResponse};
use anyhow::Result;
use async_trait::async_trait;

#[async_trait]
pub trait WeatherProvider {
    async fn fetch_forecast(&self, location: &LocationRequest) -> Result<ProviderForecastResponse>;
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{ProviderForecastResponse, ProviderPoint};
    use chrono::Utc;

    struct MockProvider;

    #[async_trait]
    impl WeatherProvider for MockProvider {
        async fn fetch_forecast(
            &self,
            _location: &LocationRequest,
        ) -> Result<ProviderForecastResponse> {
            Ok(ProviderForecastResponse {
                source: "mock".to_string(),
                generated_at: Utc::now(),
                hourly: vec![ProviderPoint {
                    hour: 12,
                    temp_f: Some(71.4),
                    feels_like_f: Some(70.9),
                    wind_mph: Some(8.2),
                    aqi: Some(56.0),
                    uv_index: Some(7.5),
                    cloud_cover_pct: Some(28.0),
                }],
            })
        }
    }

    #[tokio::test]
    async fn weather_provider_trait_can_be_mocked() {
        let provider = MockProvider;
        let location = LocationRequest {
            lat: 40.39,
            lon: -105.07,
        };

        let response = provider
            .fetch_forecast(&location)
            .await
            .expect("mock response");

        assert_eq!(response.source, "mock");
        assert_eq!(response.hourly.len(), 1);
        assert_eq!(response.hourly[0].hour, 12);
    }
}
