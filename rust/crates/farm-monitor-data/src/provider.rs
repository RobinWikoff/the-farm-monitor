use crate::models::{LocationRequest, ProviderForecastResponse, ProviderPoint};
use anyhow::Result;
use chrono::Utc;
use reqwest::Client;
use serde::Deserialize;
use std::env;

pub trait WeatherProvider {
    fn fetch_forecast<'a>(
        &'a self,
        location: &'a LocationRequest,
    ) -> impl std::future::Future<Output = Result<ProviderForecastResponse>> + Send + 'a;
}

#[derive(Clone, Debug)]
pub struct VisualCrossingProvider {
    client: Client,
    api_key: String,
    timezone: String,
}

impl VisualCrossingProvider {
    pub fn from_env() -> Result<Self> {
        let api_key = env::var("VISUAL_CROSSING_API_KEY")?;
        Ok(Self::new(api_key))
    }

    pub fn new(api_key: String) -> Self {
        Self {
            client: Client::new(),
            api_key,
            timezone: "America/Denver".to_string(),
        }
    }
}

#[derive(Debug, Deserialize)]
struct TimelineResponse {
    #[serde(default)]
    days: Vec<TimelineDay>,
}

#[derive(Debug, Deserialize)]
struct TimelineDay {
    #[serde(default)]
    hours: Vec<TimelineHour>,
}

#[derive(Debug, Deserialize)]
struct TimelineHour {
    datetime: String,
    temp: Option<f64>,
    feelslike: Option<f64>,
    windspeed: Option<f64>,
    aqius: Option<f64>,
    aqieur: Option<f64>,
    aqi: Option<f64>,
    uvindex: Option<f64>,
    cloudcover: Option<f64>,
    humidity: Option<f64>,
    precipprob: Option<f64>,
    precip: Option<f64>,
}

impl WeatherProvider for VisualCrossingProvider {
    async fn fetch_forecast(&self, location: &LocationRequest) -> Result<ProviderForecastResponse> {
        let url = format!(
            "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{},{}{}",
            location.lat, location.lon, "/today"
        );

        let payload = self
            .client
            .get(url)
            .query(&[
                ("unitGroup", "us"),
                ("include", "hours,current"),
                (
                    "elements",
                    "datetime,temp,feelslike,windspeed,aqius,aqieur,aqi,uvindex,cloudcover,humidity,precipprob,precip",
                ),
                ("key", self.api_key.as_str()),
                ("contentType", "json"),
                ("timezone", self.timezone.as_str()),
            ])
            .send()
            .await?
            .error_for_status()?
            .json::<TimelineResponse>()
            .await?;

        let hourly = payload
            .days
            .into_iter()
            .flat_map(|day| day.hours.into_iter())
            .filter_map(|hour| {
                let hour_num = hour.datetime.split(':').next()?.parse::<u8>().ok()?;
                Some(ProviderPoint {
                    hour: hour_num,
                    temp_f: hour.temp,
                    feels_like_f: hour.feelslike,
                    wind_mph: hour.windspeed,
                    aqi: hour.aqius.or(hour.aqieur).or(hour.aqi),
                    uv_index: hour.uvindex,
                    cloud_cover_pct: hour.cloudcover,
                    humidity_pct: hour.humidity,
                    precip_prob_pct: hour.precipprob,
                    precip_hr_in: hour.precip,
                })
            })
            .collect();

        Ok(ProviderForecastResponse {
            source: "visual-crossing".to_string(),
            generated_at: Utc::now(),
            hourly,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{ProviderForecastResponse, ProviderPoint};
    use chrono::Utc;

    struct MockProvider;

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
                    humidity_pct: None,
                    precip_prob_pct: None,
                    precip_hr_in: None,
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
