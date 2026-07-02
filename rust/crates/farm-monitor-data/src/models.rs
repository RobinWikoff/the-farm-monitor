use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct LocationRequest {
    pub lat: f64,
    pub lon: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ProviderPoint {
    pub hour: u8,
    pub temp_f: Option<f64>,
    pub feels_like_f: Option<f64>,
    pub wind_mph: Option<f64>,
    pub aqi: Option<f64>,
    pub uv_index: Option<f64>,
    pub cloud_cover_pct: Option<f64>,
    pub humidity_pct: Option<f64>,
    pub precip_prob_pct: Option<f64>,
    pub precip_hr_in: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ProviderForecastResponse {
    pub source: String,
    pub generated_at: DateTime<Utc>,
    pub hourly: Vec<ProviderPoint>,
    /// "HH:MM:SS" from Visual Crossing day-level field
    pub sunrise: Option<String>,
    pub sunset: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ForecastPoint {
    pub hour: u8,
    pub temp_f: f64,
    pub feels_like_f: f64,
    pub wind_mph: f64,
    pub aqi: Option<f64>,
    pub uv_index: Option<f64>,
    pub cloud_cover_pct: Option<f64>,
    pub humidity_pct: Option<f64>,
    pub precip_prob_pct: Option<f64>,
    pub precip_hr_in: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct ForecastBundle {
    pub source: String,
    pub generated_at: DateTime<Utc>,
    pub points: Vec<ForecastPoint>,
    /// "HH:MM" display strings derived from VC sunrise/sunset
    pub sunrise: Option<String>,
    pub sunset: Option<String>,
}
