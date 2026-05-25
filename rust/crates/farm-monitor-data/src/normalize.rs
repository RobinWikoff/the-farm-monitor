use crate::models::{ForecastBundle, ForecastPoint, ProviderForecastResponse};

fn round1(value: f64) -> f64 {
    (value * 10.0).round() / 10.0
}

fn clamp(value: f64, low: f64, high: f64) -> f64 {
    value.max(low).min(high)
}

pub fn normalize_provider_response(response: ProviderForecastResponse) -> ForecastBundle {
    let points = response
        .hourly
        .into_iter()
        .filter(|h| h.hour <= 23)
        .map(|hourly| ForecastPoint {
            hour: hourly.hour,
            temp_f: round1(hourly.temp_f.unwrap_or(0.0)),
            feels_like_f: round1(hourly.feels_like_f.unwrap_or(hourly.temp_f.unwrap_or(0.0))),
            wind_mph: round1(hourly.wind_mph.unwrap_or(0.0).max(0.0)),
            aqi: hourly.aqi.map(|v| round1(clamp(v, 0.0, 500.0))),
            uv_index: hourly.uv_index.map(|v| round1(clamp(v, 0.0, 20.0))),
            cloud_cover_pct: hourly.cloud_cover_pct.map(|v| round1(clamp(v, 0.0, 100.0))),
        })
        .collect();

    ForecastBundle {
        source: response.source,
        generated_at: response.generated_at,
        points,
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{ProviderForecastResponse, ProviderPoint};
    use chrono::Utc;

    #[test]
    fn normalize_response_clamps_and_rounds_values() {
        let response = ProviderForecastResponse {
            source: "unit-test".to_string(),
            generated_at: Utc::now(),
            hourly: vec![
                ProviderPoint {
                    hour: 1,
                    temp_f: Some(62.34),
                    feels_like_f: None,
                    wind_mph: Some(-2.4),
                    aqi: Some(580.0),
                    uv_index: Some(24.6),
                    cloud_cover_pct: Some(125.1),
                },
                ProviderPoint {
                    hour: 30,
                    temp_f: Some(70.0),
                    feels_like_f: Some(69.0),
                    wind_mph: Some(6.0),
                    aqi: None,
                    uv_index: None,
                    cloud_cover_pct: None,
                },
            ],
        };

        let normalized = normalize_provider_response(response);
        assert_eq!(normalized.points.len(), 1);

        let p = &normalized.points[0];
        assert_eq!(p.hour, 1);
        assert_eq!(p.temp_f, 62.3);
        assert_eq!(p.feels_like_f, 62.3);
        assert_eq!(p.wind_mph, 0.0);
        assert_eq!(p.aqi, Some(500.0));
        assert_eq!(p.uv_index, Some(20.0));
        assert_eq!(p.cloud_cover_pct, Some(100.0));
    }
}
