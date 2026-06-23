use axum::{
    extract::Query,
    response::{Html, Redirect},
    routing::get,
    Json, Router,
};
use chrono::{Timelike, Utc};
use farm_monitor_data::models::ProviderPoint;
use farm_monitor_data::{
    normalize_provider_response, FileForecastCache, ForecastBundle, ForecastPoint, LocationRequest,
    ProviderForecastResponse, VisualCrossingProvider, WeatherProvider,
};
use farm_monitor_domain::HealthStatus;
use std::collections::HashMap;
use std::env;
use std::net::SocketAddr;
use std::{f64::consts::PI, fmt::Write};
use tracing::{info, warn};

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter("info")
        .with_target(false)
        .compact()
        .init();

    let app = Router::new()
        .route("/", get(index))
        .route("/dashboard", get(dashboard))
        .route("/healthz", get(healthz));

    let bind_addr = env::var("FM_BIND_ADDR").unwrap_or_else(|_| "0.0.0.0:8080".to_string());
    let addr: SocketAddr = bind_addr
        .parse()
        .expect("valid socket address in FM_BIND_ADDR");
    info!(%addr, "starting farm-monitor-api");

    let listener = tokio::net::TcpListener::bind(addr)
        .await
        .expect("bind listener");
    axum::serve(listener, app).await.expect("serve app");
}

async fn healthz() -> Json<HealthStatus> {
    Json(HealthStatus::ok("farm-monitor-api"))
}

async fn index() -> Redirect {
    Redirect::to("/dashboard")
}

async fn dashboard(Query(query): Query<HashMap<String, String>>) -> Html<String> {
    let settings = dashboard_settings_from_query(&query);
    match load_dashboard_bundle().await {
        Ok(bundle) => Html(dashboard_html(&bundle, &settings)),
        Err(err) => Html(error_dashboard_html(&format!(
            "failed to load dashboard data: {err}"
        ))),
    }
}

#[derive(Clone, Debug)]
struct DashboardSettings {
    mode_label: &'static str,
    is_winter_mode: bool,
    threshold_f: f64,
    temp_label: &'static str,
    use_feels_like: bool,
    kitty_wind_cutoff_mph: u8,
}

fn dashboard_settings_from_query(query: &HashMap<String, String>) -> DashboardSettings {
    let mode_raw = query
        .get("mode")
        .map(|s| s.trim().to_ascii_lowercase())
        .unwrap_or_else(|| "winter".to_string());
    let (mode_label, is_winter_mode, threshold_f) = if mode_raw == "summer" {
        ("Summer (Cooling Focus)", false, 70.0)
    } else {
        ("Winter (Warming Focus)", true, 65.0)
    };

    let temp_raw = query
        .get("temp")
        .map(|s| s.trim().to_ascii_lowercase())
        .unwrap_or_else(|| "actual".to_string());
    let (temp_label, use_feels_like) = if temp_raw == "feels_like" {
        ("Feels Like", true)
    } else {
        ("Actual", false)
    };

    let kitty_wind_cutoff_mph = query
        .get("wind_cutoff")
        .and_then(|s| s.parse::<u8>().ok())
        .map(|v| v.clamp(0, 40))
        .unwrap_or(5);

    DashboardSettings {
        mode_label,
        is_winter_mode,
        threshold_f,
        temp_label,
        use_feels_like,
        kitty_wind_cutoff_mph,
    }
}

async fn load_dashboard_bundle() -> anyhow::Result<ForecastBundle> {
    let now = Utc::now();
    let today = now.date_naive();
    let cache = FileForecastCache::new(".streamlit/rust_cache");

    if let Some(bundle) = cache.read(today)? {
        return Ok(bundle);
    }

    let location = LocationRequest {
        lat: 40.39,
        lon: -105.07,
    };
    let provider_response = match VisualCrossingProvider::from_env() {
        Ok(provider) => match provider.fetch_forecast(&location).await {
            Ok(response) => response,
            Err(err) => {
                warn!(error = %err, "visual crossing fetch failed, falling back to mock data");
                mock_provider_forecast(&location)
            }
        },
        Err(err) => {
            warn!(error = %err, "VISUAL_CROSSING_API_KEY missing, falling back to mock data");
            mock_provider_forecast(&location)
        }
    };
    let normalized = normalize_provider_response(provider_response);

    cache.write(today, &normalized)?;
    let _ = cache.cleanup_older_than(14, now);

    Ok(normalized)
}

fn mock_provider_forecast(_location: &LocationRequest) -> ProviderForecastResponse {
    let generated_at = Utc::now();
    let mut hourly = Vec::with_capacity(24);

    for hour in 0..24u8 {
        let h = hour as f64;
        let temp = 54.0 + 12.0 * ((h - 6.0) * PI / 12.0).sin();
        let feels = temp - 1.3 + 1.2 * (h * PI / 6.0).sin();
        let wind = (8.0 + 3.8 * ((h + 2.0) * PI / 12.0).sin()).max(0.0);
        let aqi = (64.0 + 34.0 * ((h - 4.0) * PI / 10.0).sin()).clamp(15.0, 220.0);
        let uv = if (6.0..=18.0).contains(&h) {
            (8.5 * ((h - 6.0) * PI / 12.0).sin()).max(0.0)
        } else {
            0.0
        };
        let cloud = (43.0 + 33.0 * ((h - 10.0) * PI / 14.0).sin()).clamp(0.0, 100.0);

        hourly.push(ProviderPoint {
            hour,
            temp_f: Some(temp),
            feels_like_f: Some(feels),
            wind_mph: Some(wind),
            aqi: Some(aqi),
            uv_index: Some(uv),
            cloud_cover_pct: Some(cloud),
        });
    }

    ProviderForecastResponse {
        source: "mock-phase-c".to_string(),
        generated_at,
        hourly,
    }
}

fn chart_xy(hour: u8, value: f64, min_y: f64, max_y: f64, width: f64, height: f64) -> (f64, f64) {
    let pad_left = 34.0;
    let pad_right = 12.0;
    let pad_top = 10.0;
    let pad_bottom = 24.0;
    let draw_w = width - pad_left - pad_right;
    let draw_h = height - pad_top - pad_bottom;
    let x = pad_left + (hour as f64 / 23.0) * draw_w;
    let y = pad_top + ((max_y - value) / (max_y - min_y)) * draw_h;
    (x, y)
}

fn polyline_points(
    points: &[(u8, f64)],
    min_y: f64,
    max_y: f64,
    width: f64,
    height: f64,
) -> String {
    points
        .iter()
        .map(|(hour, value)| {
            let (x, y) = chart_xy(*hour, *value, min_y, max_y, width, height);
            format!("{x:.1},{y:.1}")
        })
        .collect::<Vec<_>>()
        .join(" ")
}

fn line_bounds(points: &[(u8, f64)]) -> Option<(f64, f64)> {
    let mut min_v = points.iter().map(|(_, v)| *v).fold(f64::INFINITY, f64::min);
    let mut max_v = points
        .iter()
        .map(|(_, v)| *v)
        .fold(f64::NEG_INFINITY, f64::max);
    if !min_v.is_finite() || !max_v.is_finite() {
        return None;
    }
    if (max_v - min_v).abs() < 0.001 {
        max_v += 1.0;
        min_v -= 1.0;
    } else {
        let pad = (max_v - min_v) * 0.12;
        max_v += pad;
        min_v -= pad;
    }
    Some((min_v, max_v))
}

fn moving_average_series(points: &[(u8, f64)], radius: usize) -> Vec<(u8, f64)> {
    points
        .iter()
        .enumerate()
        .map(|(idx, (hour, _))| {
            let start = idx.saturating_sub(radius);
            let end = (idx + radius + 1).min(points.len());
            let window = &points[start..end];
            let avg = window.iter().map(|(_, v)| *v).sum::<f64>() / window.len() as f64;
            (*hour, avg)
        })
        .collect()
}

type HourSeries = Vec<(u8, f64)>;

fn build_context_band(
    points: &[(u8, f64)],
    band_width: f64,
    clamp_min: Option<f64>,
) -> (HourSeries, HourSeries, HourSeries) {
    let mean = moving_average_series(points, 2);
    let low = mean
        .iter()
        .map(|(h, v)| {
            let candidate = v - band_width;
            (
                *h,
                clamp_min.map_or(candidate, |min_v| candidate.max(min_v)),
            )
        })
        .collect();
    let high = mean.iter().map(|(h, v)| (*h, v + band_width)).collect();
    (low, mean, high)
}

fn area_polygon_points(
    low: &[(u8, f64)],
    high: &[(u8, f64)],
    min_y: f64,
    max_y: f64,
    width: f64,
    height: f64,
) -> String {
    let mut points: Vec<String> = high
        .iter()
        .map(|(hour, value)| {
            let (x, y) = chart_xy(*hour, *value, min_y, max_y, width, height);
            format!("{x:.1},{y:.1}")
        })
        .collect();

    for (hour, value) in low.iter().rev() {
        let (x, y) = chart_xy(*hour, *value, min_y, max_y, width, height);
        points.push(format!("{x:.1},{y:.1}"));
    }

    points.join(" ")
}

fn hourly_grid_svg() -> String {
    let mut g = String::new();
    for h in 0u8..=23 {
        let x = 34.0 + (h as f64 / 23.0) * 594.0;
        g.push_str(&format!(
            "<line class=\"trend-grid\" x1=\"{x:.1}\" y1=\"10\" x2=\"{x:.1}\" y2=\"156\" /><line class=\"trend-tick\" x1=\"{x:.1}\" y1=\"156\" x2=\"{x:.1}\" y2=\"160\" />"
        ));
    }
    for h in (0u8..=21).step_by(3) {
        let x = 34.0 + (h as f64 / 23.0) * 594.0;
        let label = format!("{h:02}:00");
        g.push_str(&format!(
            "<text class=\"trend-axis-label\" x=\"{x:.1}\" y=\"172\" text-anchor=\"middle\">{label}</text>"
        ));
    }
    g
}

fn nice_y_step(range: f64) -> f64 {
    if range <= 0.0 {
        return 1.0;
    }
    let rough = range / 4.0;
    let magnitude = 10f64.powf(rough.log10().floor());
    let normalized = rough / magnitude;
    let nice = if normalized <= 1.5 {
        1.0
    } else if normalized <= 3.0 {
        2.0
    } else if normalized <= 7.0 {
        5.0
    } else {
        10.0
    };
    nice * magnitude
}

fn y_axis_svg(min_v: f64, max_v: f64, height: f64) -> String {
    let range = (max_v - min_v).abs();
    if range < 1e-9 {
        return String::new();
    }
    let step = nice_y_step(range).max(1e-9);
    let pad_top = 10.0_f64;
    let pad_bottom = 24.0_f64;
    let draw_h = height - pad_top - pad_bottom;
    let start = (min_v / step).ceil() * step;
    let mut s = String::new();
    let mut v = start;
    while v <= max_v + step * 0.01 {
        let y = pad_top + ((max_v - v) / range) * draw_h;
        let label = if step >= 1.0 {
            format!("{:.0}", v)
        } else if step >= 0.1 {
            format!("{:.1}", v)
        } else {
            format!("{:.2}", v)
        };
        let _ = write!(
            s,
            "<line class=\"trend-tick\" x1=\"26\" y1=\"{y:.1}\" x2=\"34\" y2=\"{y:.1}\" /><text class=\"trend-axis-label\" x=\"24\" y=\"{yt:.1}\" text-anchor=\"end\">{label}</text>",
            yt = y + 3.5
        );
        v += step;
    }
    s
}

fn build_temperature_chart_svg(points: &[(u8, f64)], now_hour: u8, threshold_f: f64) -> String {
    if points.is_empty() {
        return "<div class=\"chart-note\">No chart data available.</div>".to_string();
    }
    let width = 640.0;
    let height = 180.0;
    let mut bounds_points = points.to_vec();
    bounds_points.push((0, threshold_f));
    let Some((data_min, data_max)) = line_bounds(&bounds_points) else {
        return "<div class=\"chart-note\">No chart data available.</div>".to_string();
    };
    let min_v = f64::min(30.0, data_min - 10.0);
    let max_v = f64::max(100.0, data_max + 10.0);
    let observed: Vec<(u8, f64)> = points
        .iter()
        .copied()
        .filter(|(hour, _)| *hour <= now_hour)
        .collect();
    let forecast: Vec<(u8, f64)> = points
        .iter()
        .copied()
        .filter(|(hour, _)| *hour >= now_hour)
        .collect();
    let observed_poly = polyline_points(&observed, min_v, max_v, width, height);
    let forecast_poly = polyline_points(&forecast, min_v, max_v, width, height);
    let (_, target_y) = chart_xy(0, threshold_f, min_v, max_v, width, height);
    let (hist_low, hist_mean, hist_high) = build_context_band(points, 3.2, None);
    let hist_band_poly = area_polygon_points(&hist_low, &hist_high, min_v, max_v, width, height);
    let hist_mean_poly = polyline_points(&hist_mean, min_v, max_v, width, height);

    let current = observed.last().copied().or_else(|| points.first().copied());
    let high = observed.iter().max_by(|a, b| a.1.total_cmp(&b.1)).copied();
    let low = observed.iter().min_by(|a, b| a.1.total_cmp(&b.1)).copied();

    let mut label_points: Vec<(u8, f64, f64)> = Vec::new();
    if let Some((hour, value)) = current {
        label_points.push((hour, value, -12.0));
    }
    if let Some((hour, value)) = high {
        if label_points
            .iter()
            .all(|(h, v, _)| *h != hour || (*v - value).abs() > 0.05)
        {
            label_points.push((hour, value, -12.0));
        }
    }
    if let Some((hour, value)) = low {
        if label_points
            .iter()
            .all(|(h, v, _)| *h != hour || (*v - value).abs() > 0.05)
        {
            label_points.push((hour, value, 18.0));
        }
    }

    let mut labels = String::new();
    for (hour, value, dy) in label_points {
        let (x, y) = chart_xy(hour, value, min_v, max_v, width, height);
        let anchor = if x > 600.0 { "end" } else { "start" };
        let text_x = if anchor == "end" { x - 8.0 } else { x + 8.0 };
        let _ = write!(
            labels,
            "<text class=\"trend-callout\" x=\"{text_x:.1}\" y=\"{label_y:.1}\" text-anchor=\"{anchor}\">{value:.1}°F</text>",
            label_y = y + dy
        );
    }

    let current_dot = current
        .map(|(hour, value)| {
            let (cx, cy) = chart_xy(hour, value, min_v, max_v, width, height);
            format!("<circle class=\"trend-now\" cx=\"{cx:.1}\" cy=\"{cy:.1}\" r=\"4.5\" />")
        })
        .unwrap_or_default();

    let y_ticks = y_axis_svg(min_v, max_v, height);
    let hourly_grid = hourly_grid_svg();
    format!(
        "<svg class=\"trend-svg\" viewBox=\"0 0 {width:.0} {height:.0}\" role=\"img\" aria-label=\"Temperature trend with target threshold\"><line class=\"trend-axis\" x1=\"34\" y1=\"156\" x2=\"628\" y2=\"156\" /><line class=\"trend-axis\" x1=\"34\" y1=\"10\" x2=\"34\" y2=\"156\" />{hourly_grid}{y_ticks}<polygon class=\"trend-band temp-band\" points=\"{hist_band_poly}\" /><polyline class=\"trend-line temp-hist\" points=\"{hist_mean_poly}\" /><line class=\"trend-target\" x1=\"34\" y1=\"{target_y:.1}\" x2=\"628\" y2=\"{target_y:.1}\" /><polyline class=\"trend-line temp-obs\" points=\"{observed_poly}\" /><polyline class=\"trend-line temp-fcst\" points=\"{forecast_poly}\" />{current_dot}{labels}</svg>"
    )
}

fn build_wind_chart_svg(points: &[(u8, f64)], now_hour: u8) -> String {
    if points.is_empty() {
        return "<div class=\"chart-note\">No chart data available.</div>".to_string();
    }
    let width = 640.0;
    let height = 180.0;
    let gust_points: Vec<(u8, f64)> = points
        .iter()
        .copied()
        .filter(|(hour, _)| *hour <= now_hour)
        .map(|(hour, wind)| (hour, wind * 1.35))
        .collect();
    let mut bounds_points = points.to_vec();
    bounds_points.extend(gust_points.iter().copied());
    let Some((_, data_max_w)) = line_bounds(&bounds_points) else {
        return "<div class=\"chart-note\">No chart data available.</div>".to_string();
    };
    let min_v = 0.0_f64;
    let max_v = f64::max(50.0, data_max_w + 5.0);
    let observed: Vec<(u8, f64)> = points
        .iter()
        .copied()
        .filter(|(hour, _)| *hour <= now_hour)
        .collect();
    let forecast: Vec<(u8, f64)> = points
        .iter()
        .copied()
        .filter(|(hour, _)| *hour >= now_hour)
        .collect();
    let observed_poly = polyline_points(&observed, min_v, max_v, width, height);
    let forecast_poly = polyline_points(&forecast, min_v, max_v, width, height);
    let gust_poly = polyline_points(&gust_points, min_v, max_v, width, height);
    let (hist_low, hist_mean, hist_high) = build_context_band(&observed, 1.5, Some(0.0));
    let hist_band_poly = area_polygon_points(&hist_low, &hist_high, min_v, max_v, width, height);
    let hist_mean_poly = polyline_points(&hist_mean, min_v, max_v, width, height);
    let current = observed.last().copied().or_else(|| points.first().copied());
    let strongest_wind = observed.iter().max_by(|a, b| a.1.total_cmp(&b.1)).copied();
    let strongest_gust = gust_points
        .iter()
        .max_by(|a, b| a.1.total_cmp(&b.1))
        .copied();

    let mut labels = String::new();
    for (hour, value, dy, class_name) in [
        strongest_wind.map(|(h, v)| (h, v, -12.0, "trend-callout")),
        strongest_gust.map(|(h, v)| (h, v, -24.0, "trend-callout gust")),
    ]
    .into_iter()
    .flatten()
    {
        let (x, y) = chart_xy(hour, value, min_v, max_v, width, height);
        let anchor = if x > 600.0 { "end" } else { "start" };
        let text_x = if anchor == "end" { x - 8.0 } else { x + 8.0 };
        let _ = write!(
            labels,
            "<text class=\"{class_name}\" x=\"{text_x:.1}\" y=\"{label_y:.1}\" text-anchor=\"{anchor}\">{value:.1} mph</text>",
            label_y = y + dy
        );
    }

    let current_dot = current
        .map(|(hour, value)| {
            let (cx, cy) = chart_xy(hour, value, min_v, max_v, width, height);
            format!("<circle class=\"trend-now\" cx=\"{cx:.1}\" cy=\"{cy:.1}\" r=\"4.5\" />")
        })
        .unwrap_or_default();

    let y_ticks = y_axis_svg(min_v, max_v, height);
    let hourly_grid = hourly_grid_svg();
    format!(
        "<svg class=\"trend-svg\" viewBox=\"0 0 {width:.0} {height:.0}\" role=\"img\" aria-label=\"Wind and gust trend\"><line class=\"trend-axis\" x1=\"34\" y1=\"156\" x2=\"628\" y2=\"156\" /><line class=\"trend-axis\" x1=\"34\" y1=\"10\" x2=\"34\" y2=\"156\" />{hourly_grid}{y_ticks}<polygon class=\"trend-band wind-band\" points=\"{hist_band_poly}\" /><polyline class=\"trend-line wind-hist\" points=\"{hist_mean_poly}\" /><polyline class=\"trend-line wind-obs\" points=\"{observed_poly}\" /><polyline class=\"trend-line wind-fcst\" points=\"{forecast_poly}\" /><polyline class=\"trend-line gust\" points=\"{gust_poly}\" />{current_dot}{labels}</svg>"
    )
}

fn build_precip_chart_svg(points: &[(u8, f64)], now_hour: u8) -> String {
    if points.is_empty() {
        return "<div class=\"chart-note\">No chart data available.</div>".to_string();
    }
    let width = 640.0;
    let height = 180.0;
    let data_max_p = points.iter().map(|(_, v)| *v).fold(0.0_f64, f64::max);
    let min_v = 0.0_f64;
    let max_v = f64::max(0.3, data_max_p + 0.05);
    let observed: Vec<(u8, f64)> = points
        .iter()
        .copied()
        .filter(|(hour, _)| *hour <= now_hour)
        .collect();
    let mut forecast: Vec<(u8, f64)> = points
        .iter()
        .copied()
        .filter(|(hour, _)| *hour >= now_hour)
        .collect();
    if forecast.is_empty() {
        forecast = observed.last().copied().into_iter().collect();
    }
    let observed_poly = polyline_points(&observed, min_v, max_v, width, height);
    let forecast_poly = polyline_points(&forecast, min_v, max_v, width, height);
    let (hist_low, hist_mean, hist_high) = build_context_band(&observed, 0.05, Some(0.0));
    let hist_band_poly = area_polygon_points(&hist_low, &hist_high, min_v, max_v, width, height);
    let hist_mean_poly = polyline_points(&hist_mean, min_v, max_v, width, height);
    let current = observed.last().copied().or_else(|| points.first().copied());
    let current_dot = current
        .map(|(hour, value)| {
            let (cx, cy) = chart_xy(hour, value, min_v, max_v, width, height);
            format!("<circle class=\"trend-now\" cx=\"{cx:.1}\" cy=\"{cy:.1}\" r=\"4.3\" />")
        })
        .unwrap_or_default();
    let y_ticks = y_axis_svg(min_v, max_v, height);
    let hourly_grid = hourly_grid_svg();
    format!(
        "<svg class=\"trend-svg\" viewBox=\"0 0 {width:.0} {height:.0}\" role=\"img\" aria-label=\"Precipitation trend\"><line class=\"trend-axis\" x1=\"34\" y1=\"156\" x2=\"628\" y2=\"156\" /><line class=\"trend-axis\" x1=\"34\" y1=\"10\" x2=\"34\" y2=\"156\" />{hourly_grid}{y_ticks}<polygon class=\"trend-band precip-band\" points=\"{hist_band_poly}\" /><polyline class=\"trend-line precip-hist\" points=\"{hist_mean_poly}\" /><polyline class=\"trend-line precip-obs\" points=\"{observed_poly}\" /><polyline class=\"trend-line precip-fcst\" points=\"{forecast_poly}\" />{current_dot}</svg>"
    )
}

fn build_aqi_chart_svg(points: &[(u8, f64)], now_hour: u8) -> String {
    if points.is_empty() {
        return "<div class=\"chart-note\">No chart data available.</div>".to_string();
    }
    let width = 640.0;
    let height = 180.0;
    let Some((_, data_max_a)) = line_bounds(points) else {
        return "<div class=\"chart-note\">No chart data available.</div>".to_string();
    };
    let min_v = 0.0_f64;
    let max_v = f64::max(120.0, data_max_a + 15.0);
    let observed: Vec<(u8, f64)> = points
        .iter()
        .copied()
        .filter(|(hour, _)| *hour <= now_hour)
        .collect();
    let forecast: Vec<(u8, f64)> = points
        .iter()
        .copied()
        .filter(|(hour, _)| *hour >= now_hour)
        .collect();
    let observed_poly = polyline_points(&observed, min_v, max_v, width, height);
    let forecast_poly = polyline_points(&forecast, min_v, max_v, width, height);
    let current = observed.last().copied().or_else(|| points.first().copied());
    let split_x = observed
        .iter()
        .find(|(hour, _)| *hour == now_hour)
        .map(|(h, _)| chart_xy(*h, min_v, min_v, max_v, width, height).0)
        .unwrap_or(34.0);
    let high = observed.iter().max_by(|a, b| a.1.total_cmp(&b.1)).copied();
    let low = observed.iter().min_by(|a, b| a.1.total_cmp(&b.1)).copied();

    let mut labels = String::new();
    for (prefix, point, dy, class_name) in [
        ("High", high, -12.0, "trend-callout aqi-high"),
        ("Low", low, 18.0, "trend-callout aqi-low"),
    ] {
        if let Some((hour, value)) = point {
            let (x, y) = chart_xy(hour, value, min_v, max_v, width, height);
            let anchor = if x > 600.0 { "end" } else { "start" };
            let text_x = if anchor == "end" { x - 8.0 } else { x + 8.0 };
            let _ = write!(
                labels,
                "<text class=\"{class_name}\" x=\"{text_x:.1}\" y=\"{label_y:.1}\" text-anchor=\"{anchor}\">{prefix}: {value:.0}</text>",
                label_y = y + dy
            );
        }
    }

    let current_dot = current
        .map(|(hour, value)| {
            let (cx, cy) = chart_xy(hour, value, min_v, max_v, width, height);
            format!("<circle class=\"trend-now\" cx=\"{cx:.1}\" cy=\"{cy:.1}\" r=\"4.3\" />")
        })
        .unwrap_or_default();

    let (hist_low_a, hist_mean_a, hist_high_a) = build_context_band(&observed, 15.0, Some(0.0));
    let hist_band_poly = area_polygon_points(&hist_low_a, &hist_high_a, min_v, max_v, width, height);
    let hist_mean_poly = polyline_points(&hist_mean_a, min_v, max_v, width, height);
    let y_ticks = y_axis_svg(min_v, max_v, height);
    let hourly_grid = hourly_grid_svg();
    format!(
        "<svg class=\"trend-svg\" viewBox=\"0 0 {width:.0} {height:.0}\" role=\"img\" aria-label=\"AQI trend\"><line class=\"trend-axis\" x1=\"34\" y1=\"156\" x2=\"628\" y2=\"156\" /><line class=\"trend-axis\" x1=\"34\" y1=\"10\" x2=\"34\" y2=\"156\" />{hourly_grid}{y_ticks}<polygon class=\"trend-band aqi-band\" points=\"{hist_band_poly}\" /><polyline class=\"trend-line aqi-hist\" points=\"{hist_mean_poly}\" /><line class=\"trend-split\" x1=\"{split_x:.1}\" y1=\"10\" x2=\"{split_x:.1}\" y2=\"156\" /><polyline class=\"trend-line aqi-obs\" points=\"{observed_poly}\"><title>Observed AQI up to current hour</title></polyline><polyline class=\"trend-line aqi-fcst\" points=\"{forecast_poly}\"><title>Forecast AQI from current hour onward</title></polyline>{current_dot}{labels}</svg>"
    )
}

fn build_brightness_chart_svg(points: &[(u8, f64, f64)], now_hour: u8) -> String {
    if points.is_empty() {
        return "<div class=\"chart-note\">No chart data available.</div>".to_string();
    }
    let width = 640.0;
    let height = 180.0;
    let uv_scaled: Vec<(u8, f64)> = points
        .iter()
        .map(|(h, uv, _)| (*h, ((uv / 11.0) * 100.0).clamp(0.0, 100.0)))
        .collect();
    let cloud_scaled: Vec<(u8, f64)> = points
        .iter()
        .map(|(h, _, c)| (*h, (*c).clamp(0.0, 100.0)))
        .collect();

    let uv_obs: Vec<(u8, f64)> = uv_scaled
        .iter()
        .copied()
        .filter(|(h, _)| *h <= now_hour)
        .collect();
    let uv_fcst: Vec<(u8, f64)> = uv_scaled
        .iter()
        .copied()
        .filter(|(h, _)| *h >= now_hour)
        .collect();

    let uv_obs_poly = polyline_points(&uv_obs, 0.0, 100.0, width, height);
    let uv_fcst_poly = polyline_points(&uv_fcst, 0.0, 100.0, width, height);

    let mut cloud_poly = String::from("34.0,156.0 ");
    cloud_poly.push_str(&polyline_points(&cloud_scaled, 0.0, 100.0, width, height));
    cloud_poly.push_str(" 628.0,156.0");

    let hourly_grid = hourly_grid_svg();
    format!(
        "<svg class=\"trend-svg\" viewBox=\"0 0 {width:.0} {height:.0}\" role=\"img\" aria-label=\"UV and cloud cover trend\"><line class=\"trend-axis\" x1=\"34\" y1=\"156\" x2=\"628\" y2=\"156\" /><line class=\"trend-axis\" x1=\"34\" y1=\"10\" x2=\"34\" y2=\"156\" /><line class=\"trend-axis-right\" x1=\"628\" y1=\"10\" x2=\"628\" y2=\"156\" />{hourly_grid}<polygon class=\"trend-cloud-area\" points=\"{cloud_poly}\"><title>Cloud cover area (right axis, %)</title></polygon><polyline class=\"trend-line uv obs\" points=\"{uv_obs_poly}\"><title>Observed UV index (left axis)</title></polyline><polyline class=\"trend-line uv fcst\" points=\"{uv_fcst_poly}\"><title>Forecast UV index (left axis)</title></polyline></svg>"
    )
}

fn dashboard_html(bundle: &ForecastBundle, settings: &DashboardSettings) -> String {
    let now_hour = Utc::now().hour() as u8;
    let current = find_current_point(&bundle.points, now_hour)
        .or_else(|| bundle.points.first())
        .cloned();

    let mut hourly_rows = String::new();
    let mut wind_rows = String::new();
    let mut precip_rows = String::new();
    let mut aqi_rows = String::new();
    let mut brightness_rows = String::new();
    let mut temp_series: Vec<(u8, f64)> = Vec::new();
    let mut wind_series: Vec<(u8, f64)> = Vec::new();
    let mut precip_series: Vec<(u8, f64)> = Vec::new();
    let mut aqi_series: Vec<(u8, f64)> = Vec::new();
    let mut brightness_series: Vec<(u8, f64, f64)> = Vec::new();

    let selected_temp_f = |p: &ForecastPoint| {
        if settings.use_feels_like {
            p.feels_like_f
        } else {
            p.temp_f
        }
    };

    let max_wind = bundle
        .points
        .iter()
        .map(|p| p.wind_mph)
        .fold(1.0_f64, f64::max);
    let max_aqi = bundle
        .points
        .iter()
        .filter_map(|p| p.aqi)
        .fold(1.0_f64, f64::max);

    let mut precip_total = 0.0;
    let mut precip_now_prob: Option<u8> = None;
    let mut humidity_now: Option<u8> = None;
    let mut rain_or_snow_recently = false;

    let mut current_aqi: Option<f64> = None;
    let mut highest_aqi: Option<(f64, u8)> = None;
    let mut lowest_aqi: Option<(f64, u8)> = None;
    let mut peak_uv: Option<(f64, u8)> = None;

    for point in &bundle.points {
        let status = if point.hour <= now_hour {
            "Observed"
        } else {
            "Forecast"
        };

        temp_series.push((point.hour, selected_temp_f(point)));
        wind_series.push((point.hour, point.wind_mph));
        if let Some(aqi) = point.aqi {
            aqi_series.push((point.hour, aqi));
        }

        if point.hour < 8 {
            let _ = write!(
                hourly_rows,
                "<tr><td>{:02}:00</td><td>{:.1}°F</td><td>{:.1} mph</td><td>{}</td><td>{:.1}</td></tr>",
                point.hour,
                point.temp_f,
                point.wind_mph,
                point
                    .aqi
                    .map(|v| format!("{v:.0}"))
                    .unwrap_or_else(|| "-".to_string()),
                point.uv_index.unwrap_or(0.0)
            );
        }

        let cloud = point.cloud_cover_pct.unwrap_or(0.0);
        let uv = point.uv_index.unwrap_or(0.0);
        let precip_prob = ((cloud * 0.78) + if uv < 1.0 { 22.0 } else { 0.0 })
            .round()
            .clamp(0.0, 100.0) as u8;
        let precip_in = if precip_prob >= 70 {
            ((precip_prob as f64 - 66.0) / 125.0).clamp(0.0, 0.8)
        } else {
            0.0
        };
        let humidity = (44.0 + cloud * 0.52).round().clamp(22.0, 98.0) as u8;
        let snow_in = if point.temp_f <= 32.0 && precip_in > 0.0 {
            (precip_in * 6.0).round() / 10.0
        } else {
            0.0
        };
        precip_series.push((point.hour, precip_in));
        brightness_series.push((point.hour, uv, cloud));

        if point.hour < 12 {
            let gust = point.wind_mph * 1.35;
            let wind_bar = ((point.wind_mph / max_wind) * 100.0)
                .round()
                .clamp(0.0, 100.0);
            let _ = write!(
                wind_rows,
                "<tr><td>{:02}:00</td><td>{}</td><td>{:.1} mph</td><td>{:.1} mph</td><td><div class='bar'><span style='width:{:.0}%;'></span></div></td></tr>",
                point.hour,
                status,
                point.wind_mph,
                gust,
                wind_bar
            );

            let aqi = point.aqi.unwrap_or(0.0);
            let aqi_bar = ((aqi / max_aqi) * 100.0).round().clamp(0.0, 100.0);
            let _ = write!(
                aqi_rows,
                "<tr><td>{:02}:00</td><td>{}</td><td>{:.0}</td><td>{}</td><td><div class='bar aqi'><span style='width:{:.0}%;'></span></div></td></tr>",
                point.hour,
                status,
                aqi,
                aqi_label(aqi),
                aqi_bar
            );

            let uv_bar = ((uv / 11.0) * 100.0).round().clamp(0.0, 100.0);
            let cloud_bar = cloud.round().clamp(0.0, 100.0);
            let _ = write!(
                brightness_rows,
                "<tr><td>{:02}:00</td><td>{:.1}</td><td>{:.0}%</td><td><div class='bar uv'><span style='width:{:.0}%;'></span></div></td><td><div class='bar cloud'><span style='width:{:.0}%;'></span></div></td></tr>",
                point.hour,
                uv,
                cloud,
                uv_bar,
                cloud_bar
            );

            let _ = write!(
                precip_rows,
                "<tr><td>{:02}:00</td><td>{:.2} in</td><td>{}%</td><td>{}%</td><td>{:.1} in</td></tr>",
                point.hour,
                precip_in,
                precip_prob,
                humidity,
                snow_in
            );
            if point.hour <= now_hour {
                precip_total += precip_in;
                if precip_in > 0.0 || snow_in > 0.0 {
                    rain_or_snow_recently = true;
                }
            }
            if point.hour == now_hour {
                precip_now_prob = Some(precip_prob);
                humidity_now = Some(humidity);
            }
        }

        if point.hour <= now_hour {
            if point.hour == now_hour {
                current_aqi = point.aqi;
            }
            if let Some(v) = point.aqi {
                if highest_aqi.is_none_or(|(h, _)| v > h) {
                    highest_aqi = Some((v, point.hour));
                }
                if lowest_aqi.is_none_or(|(l, _)| v < l) {
                    lowest_aqi = Some((v, point.hour));
                }
            }
            if let Some(uv) = point.uv_index {
                if uv > 0.0 && peak_uv.is_none_or(|(p, _)| uv > p) {
                    peak_uv = Some((uv, point.hour));
                }
            }
        }
    }

    let (temp_now, wind_now) = match current {
        Some(ref p) => (
            format!("{:.1}°F", selected_temp_f(p)),
            format!("{:.1} mph", p.wind_mph),
        ),
        None => ("-".to_string(), "-".to_string()),
    };

    let local_time_txt = Utc::now().format("%H:%M:%S").to_string();
    let prior_hour = now_hour.saturating_sub(1);
    let temp_high_txt = bundle
        .points
        .iter()
        .filter(|p| p.hour <= now_hour)
        .map(selected_temp_f)
        .max_by(|a, b| a.total_cmp(b))
        .map(|v| format!("{v:.1}°F"))
        .unwrap_or_else(|| "N/A".to_string());
    let temp_low_txt = bundle
        .points
        .iter()
        .filter(|p| p.hour <= now_hour)
        .map(selected_temp_f)
        .min_by(|a, b| a.total_cmp(b))
        .map(|v| format!("{v:.1}°F"))
        .unwrap_or_else(|| "N/A".to_string());
    let prior_temp = find_current_point(&bundle.points, prior_hour).map(selected_temp_f);
    let temp_delta_txt = match (current.as_ref().map(selected_temp_f), prior_temp) {
        (Some(now), Some(prior)) => format!("{:+.1}°F since {:02}:00", now - prior, prior_hour),
        _ => "N/A".to_string(),
    };

    let wind_direction_txt = {
        const DIRS: [&str; 16] = [
            "N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW",
            "NW", "NNW",
        ];
        let degrees = (now_hour as f64 * 15.0) % 360.0;
        let idx = ((degrees / 22.5).round() as usize) % DIRS.len();
        DIRS[idx]
    };

    let seasonal_status_txt = {
        let threshold = settings.threshold_f;
        match current.as_ref().map(selected_temp_f) {
            Some(temp) if settings.is_winter_mode && temp >= threshold => {
                format!("Winter status: OK now ({temp:.1}°F >= {threshold:.1}°F).")
            }
            Some(temp) if settings.is_winter_mode => {
                let reaches_later = bundle
                    .points
                    .iter()
                    .any(|p| p.hour >= now_hour && selected_temp_f(p) >= threshold);
                if reaches_later {
                    format!("Winter status: below threshold now ({temp:.1}°F), forecast reaches {threshold:.1}°F later today.")
                } else {
                    format!("Winter status: below threshold now ({temp:.1}°F) and not forecast to reach {threshold:.1}°F today.")
                }
            }
            Some(temp) if temp <= threshold => {
                format!("Summer status: OK now ({temp:.1}°F <= {threshold:.1}°F).")
            }
            Some(temp) => {
                let reaches_later = bundle
                    .points
                    .iter()
                    .any(|p| p.hour >= now_hour && selected_temp_f(p) <= threshold);
                if reaches_later {
                    format!("Summer status: above threshold now ({temp:.1}°F), forecast cools to {threshold:.1}°F later today.")
                } else {
                    format!("Summer status: above threshold now ({temp:.1}°F) and not forecast to cool to {threshold:.1}°F today.")
                }
            }
            None => "Winter status unavailable (missing temperature data).".to_string(),
        }
    };

    let kitty_status_txt = {
        const KITTY_TEMP_MIN_F: f64 = 32.0;
        const KITTY_TEMP_MAX_F: f64 = 85.0;
        let temp_now = current.as_ref().map(selected_temp_f);
        let wind_now = current.as_ref().map(|p| p.wind_mph);
        let temp_ok = current
            .as_ref()
            .map(|p| {
                selected_temp_f(p) > KITTY_TEMP_MIN_F && selected_temp_f(p) <= KITTY_TEMP_MAX_F
            })
            .unwrap_or(false);
        let wind_ok = current
            .as_ref()
            .map(|p| p.wind_mph <= settings.kitty_wind_cutoff_mph as f64)
            .unwrap_or(true);
        let precip_ok = !rain_or_snow_recently;
        let overall = temp_ok && wind_ok && precip_ok;
        let temp_status = match temp_now {
            Some(temp) if temp <= KITTY_TEMP_MIN_F => format!(
                "Brr too cold for Kitties: {temp:.1}°F -- (At or below {KITTY_TEMP_MIN_F:.0}°F, freezing)"
            ),
            Some(temp) if temp > KITTY_TEMP_MAX_F => format!(
                "Too hot for Kitties: {temp:.1}°F -- (More than {KITTY_TEMP_MAX_F:.0}°F)"
            ),
            Some(temp) => format!(
                "Good Temperature for Kitties: {temp:.1}°F -- ({KITTY_TEMP_MIN_F:.0}°F - {KITTY_TEMP_MAX_F:.0}°F)"
            ),
            None => "Temperature data unavailable for Kitties.".to_string(),
        };
        let wind_status = match wind_now {
            Some(wind) if wind_ok => format!(
                "Not too windy for Kitties: {wind:.0} mph -- ({} mph or less)",
                settings.kitty_wind_cutoff_mph
            ),
            Some(wind) => format!(
                "Too windy for Kitties: {wind:.0} mph -- (More than {} mph)",
                settings.kitty_wind_cutoff_mph
            ),
            None => "Wind data unavailable for Kitties.".to_string(),
        };
        let precip_status = if !precip_ok {
            Some("Kitties don't like rain or snow: Yes -- (Rain or snow detected)".to_string())
        } else {
            None
        };
        let mut details = vec![temp_status, wind_status];
        if let Some(precip) = precip_status {
            details.push(precip);
        }
        format!(
            "Kitty Comfort Threshold: {} | {}",
            if overall { "Yes" } else { "No" },
            details.join(" | ")
        )
    };

    let fastest_wind_point = bundle
        .points
        .iter()
        .max_by(|a, b| a.wind_mph.total_cmp(&b.wind_mph));
    let fastest_wind_txt = fastest_wind_point
        .map(|p| format!("{:.1} mph at {:02}:00", p.wind_mph, p.hour))
        .unwrap_or_else(|| "N/A".to_string());

    let wind_banner_txt = {
        let cutoff = settings.kitty_wind_cutoff_mph as f64;
        match fastest_wind_point {
            Some(p) => {
                let base = format!(
                    "Today's Fastest Wind Forecasted: {:.1} mph at {:02}:00.",
                    p.wind_mph, p.hour
                );
                if p.wind_mph > cutoff {
                    format!("{base} Exceeds kitty wind cutoff ({cutoff:.0} mph).")
                } else {
                    base
                }
            }
            None => "Wind information is currently unavailable.".to_string(),
        }
    };

    let strongest_gust_point = bundle
        .points
        .iter()
        .filter(|p| p.hour <= now_hour)
        .max_by(|a, b| a.wind_mph.total_cmp(&b.wind_mph));
    let strongest_gust_txt = match strongest_gust_point {
        Some(p) if p.wind_mph > 0.0 => {
            format!("{:.1} mph at {:02}:00", p.wind_mph * 1.35, p.hour)
        }
        _ => "N/A".to_string(),
    };

    let current_aqi_value = current_aqi.or_else(|| current.as_ref().and_then(|p| p.aqi));
    let current_aqi_txt = current_aqi_value
        .map(|v| format!("{v:.0}"))
        .unwrap_or_else(|| "N/A".to_string());
    let high_aqi_txt = highest_aqi
        .map(|(v, h)| format!("{v:.0} at {h:02}:00"))
        .unwrap_or_else(|| "N/A".to_string());
    let low_aqi_txt = lowest_aqi
        .map(|(v, h)| format!("{v:.0} at {h:02}:00"))
        .unwrap_or_else(|| "N/A".to_string());
    let peak_uv_txt = peak_uv
        .map(|(v, h)| format!("{v:.0} ({}) at {h:02}:00", uv_label(v)))
        .unwrap_or_else(|| "N/A".to_string());

    let current_aqi_for_pollutants = current_aqi_value.unwrap_or(42.0);
    let pm25 = (current_aqi_for_pollutants * 0.42).max(3.0);
    let pm10 = (current_aqi_for_pollutants * 0.77).max(6.0);
    let o3 = (current_aqi_for_pollutants * 0.58).max(4.0);
    let no2 = (current_aqi_for_pollutants * 0.33).max(3.0);
    let co = (current_aqi_for_pollutants / 90.0).max(0.2);

    let temp_chart_svg = build_temperature_chart_svg(&temp_series, now_hour, settings.threshold_f);
    let wind_chart_svg = build_wind_chart_svg(&wind_series, now_hour);
    let precip_chart_svg = build_precip_chart_svg(&precip_series, now_hour);
    let aqi_chart_svg = build_aqi_chart_svg(&aqi_series, now_hour);
    let brightness_chart_svg = build_brightness_chart_svg(&brightness_series, now_hour);

    let template = r#"<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>The Farm Monitor (Rust)</title>
    <style>
        :root {
            --bg: #f7f9fc;
            --panel: #ffffff;
            --text: #1f2937;
            --muted: #5f6b7a;
            --accent: #2563eb;
            --good: #22a06b;
            --warn: #d97706;
            --border: #dbe3ee;
            --shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: "Inter", "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
            background: var(--bg);
            color: var(--text);
        }
        .container {
            max-width: 1120px;
            margin: 0 auto;
            padding: 1.25rem 1rem 2rem;
        }
        .hero {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1rem 1.1rem;
            margin-bottom: 0.9rem;
            box-shadow: var(--shadow);
        }
        .control-strip {
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid #e2eaf5;
            border-radius: 10px;
            padding: 0.42rem 0.55rem;
            margin-top: 0.55rem;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
        }
        .controls {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.4rem;
            align-items: end;
        }
        .control {
            display: grid;
            gap: 0.2rem;
        }
        .control label {
            font-size: 0.64rem;
            text-transform: uppercase;
            letter-spacing: 0.03em;
            color: #5f7184;
        }
        .control select,
        .control input,
        .controls button {
            border: 1px solid #c9d7e8;
            border-radius: 8px;
            padding: 0.28rem 0.4rem;
            font-size: 0.8rem;
            background: #fff;
            color: #1f2937;
        }
        .controls button {
            background: #eef4fb;
            color: #214d7b;
            border-color: #c8d8eb;
            font-weight: 600;
        }
        .control-meta {
            margin-top: 0.28rem;
            font-size: 0.72rem;
            color: #5f7184;
        }
        .hero h1 { margin: 0 0 0.35rem 0; font-size: 1.32rem; letter-spacing: 0.01em; }
        .hero p { margin: 0; color: var(--muted); }
        .layout {
            display: grid;
            gap: 0.9rem;
        }
        .layout-row {
            display: grid;
            grid-template-columns: 1fr;
            gap: 0.9rem;
        }
        .stack {
            display: grid;
            gap: 0.9rem;
        }
        .section-divider {
            border: 0;
            border-top: 1px solid var(--border);
            margin: 0.2rem 0 0.4rem;
        }
        .card {
            background: var(--panel);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 0.95rem 1.05rem;
            min-height: 120px;
            box-shadow: var(--shadow);
        }
        .card h2 {
            margin: 0;
            font-size: 1.02rem;
            letter-spacing: 0.01em;
            border-bottom: 1px solid #e6edf7;
            padding-bottom: 0.45rem;
        }
        .card p { margin: 0; color: var(--muted); line-height: 1.4; }
        .metrics {
            display: grid;
            gap: 0.55rem;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            margin-top: 0.5rem;
            margin-bottom: 0.65rem;
        }
        .span-3 .metrics { grid-template-columns: 1fr; }
        .metric {
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 0.48rem 0.6rem;
            background: #f8fbff;
        }
        .metric .k { color: #617287; font-size: 0.74rem; margin-bottom: 0.2rem; text-transform: uppercase; letter-spacing: 0.03em; }
        .metric .v { font-size: 0.93rem; font-weight: 650; color: #1f2937; line-height: 1.25; }
        .settings-note { margin-top: 0.5rem; color: #607286; font-size: 0.85rem; }
        .chart {
            margin-top: 0.55rem;
            border: 1px dashed #c9d7e8;
            border-radius: 10px;
            padding: 0.65rem;
            background: linear-gradient(180deg, #fbfdff 0%, #f5f9ff 100%);
            color: #48627c;
            font-size: 0.86rem;
        }
        .chart-legend {
            margin-top: 0.5rem;
            display: flex;
            flex-direction: column;
            gap: 0.3rem;
        }
        .legend-row {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.78rem;
            color: #35556f;
        }
        .legend-swatch {
            flex-shrink: 0;
            width: 36px;
            height: 12px;
            background: #eef4fb;
            border-radius: 3px;
            overflow: visible;
        }
        .legend-note {
            margin-top: 0.1rem;
            font-size: 0.75rem;
            color: #5b6f84;
            font-style: italic;
        }
        .mini-bars {
            margin-top: 0.5rem;
            display: grid;
            grid-template-columns: repeat(12, minmax(0, 1fr));
            gap: 0.2rem;
            align-items: end;
            height: 56px;
            padding: 0.25rem;
            border: 1px solid #dfe8f5;
            border-radius: 8px;
            background: #ffffff;
        }
        .bar {
            display: block;
            width: 100%;
            border-radius: 4px 4px 2px 2px;
            background: #a9c2e9;
            min-height: 22%;
        }
        .bar.obs { background: #5b8fe0; }
        .bar.fcst { background: #74b6c7; }
        .bar.aqi-bar { background: #96b6e8; }
        .bar.cloud-bar { background: #8bb4ef; }
        .bar.uv-bar { background: #f2bf63; }
        .trend-svg {
            margin-top: 0.5rem;
            width: 100%;
            height: auto;
            display: block;
            border: 1px solid #dfe8f5;
            border-radius: 8px;
            background: #ffffff;
        }
        .trend-axis {
            stroke: #d4deec;
            stroke-width: 1.2;
        }
        .trend-line {
            fill: none;
            stroke-width: 3.2;
            stroke-linecap: round;
            stroke-linejoin: round;
        }
        .trend-line.obs { stroke: #4f8fdc; }
        .trend-line.fcst {
            stroke: #74b6c7;
            stroke-dasharray: 7 6;
        }
        .trend-line.temp-obs { stroke: #00cfe8; }
        .trend-line.temp-fcst {
            stroke: #80d4e6;
            stroke-dasharray: 7 6;
        }
        .trend-line.wind-obs { stroke: #00cfe8; }
        .trend-line.wind-fcst {
            stroke: #7fc4d8;
            stroke-dasharray: 7 6;
        }
        .trend-line.gust {
            stroke: #ff8a8a;
            stroke-width: 2.2;
            opacity: 0.75;
        }
        .trend-line.precip-obs { stroke: #4db6ff; }
        .trend-line.precip-fcst {
            stroke: #a0c4ff;
            stroke-dasharray: 8 5;
        }
        .trend-line.aqi-obs { stroke: #9ad162; }
        .trend-line.aqi-fcst {
            stroke: #ffb347;
            stroke-dasharray: 8 5;
        }
        .trend-line.uv { stroke: #f2bf63; }
        .trend-target {
            stroke: #32cd32;
            stroke-width: 1.8;
            stroke-dasharray: 8 4;
        }
        .trend-band {
            stroke: none;
        }
        .trend-band.temp-band {
            fill: #a0c4ff;
            fill-opacity: 0.18;
        }
        .trend-band.wind-band {
            fill: #c7d7f0;
            fill-opacity: 0.18;
        }
        .trend-line.temp-hist {
            stroke: #a0c4ff;
            stroke-width: 2.0;
            stroke-dasharray: 3 3;
        }
        .trend-line.wind-hist {
            stroke: #9fb4d6;
            stroke-width: 2.0;
            stroke-dasharray: 3 3;
        }
        .trend-band.aqi-band {
            fill: #9ad162;
            fill-opacity: 0.12;
        }
        .trend-line.aqi-hist {
            stroke: #78a840;
            stroke-width: 1.8;
            stroke-dasharray: 3 3;
            opacity: 0.7;
        }
        .trend-band.precip-band {
            fill: #4db6ff;
            fill-opacity: 0.14;
        }
        .trend-line.precip-hist {
            stroke: #2090d0;
            stroke-width: 1.8;
            stroke-dasharray: 3 3;
            opacity: 0.7;
        }
        .trend-axis-label {
            fill: #607286;
            font-size: 9px;
            font-family: "Inter", "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        }
        .trend-cloud-area {
            fill: #8bb4ef;
            fill-opacity: 0.34;
            stroke: #8bb4ef;
            stroke-width: 1.2;
        }
        .trend-axis-right {
            stroke: #8bb4ef;
            stroke-width: 1.2;
        }
        .trend-split {
            stroke: #d4deec;
            stroke-width: 1.1;
            stroke-dasharray: 4 5;
        }
        .trend-now {
            fill: #00b7ff;
            stroke: #ffffff;
            stroke-width: 2;
        }
        .trend-grid {
            stroke: #c8d9ec;
            stroke-width: 0.6;
            opacity: 0.55;
        }
        .trend-tick {
            stroke: #8099b3;
            stroke-width: 1.0;
        }
        .trend-callout {
            fill: #1e3a5c;
            font-size: 12px;
            font-weight: 700;
            font-family: "Inter", "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        }
        .trend-callout.gust { fill: #ffb0b0; }
        .trend-callout.aqi-high { fill: #ffb347; }
        .trend-callout.aqi-low { fill: #9ad162; }
        .chart-axes-wrap {
            display: flex;
            align-items: stretch;
            gap: 0;
        }
        .y-axis-label {
            writing-mode: vertical-lr;
            transform: rotate(180deg);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.70rem;
            color: #5b6f84;
            padding: 0 0.2rem;
            flex-shrink: 0;
            min-width: 16px;
            letter-spacing: 0.02em;
        }
        .y-axis-label.right {
            color: #4a6d8c;
        }
        .chart-body {
            flex: 1;
            min-width: 0;
        }
        .x-axis-label {
            text-align: center;
            font-size: 0.70rem;
            color: #5b6f84;
            margin-top: 0.1rem;
            padding-bottom: 0.15rem;
            letter-spacing: 0.02em;
        }
        .mini-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 0.6rem;
            font-size: 0.87rem;
            border: 1px solid #e6edf7;
            border-radius: 10px;
            overflow: hidden;
        }
        .mini-table th {
            text-align: left;
            color: #607286;
            border-bottom: 1px solid var(--border);
            padding: 0.4rem 0.35rem;
            background: #f5f8fd;
            text-transform: uppercase;
            font-size: 0.72rem;
            letter-spacing: 0.03em;
        }
        .mini-table td {
            border-bottom: 1px solid #edf1f7;
            color: #374151;
            padding: 0.38rem 0.35rem;
            vertical-align: middle;
        }
        .mini-table tbody tr:nth-child(even) td { background: #fbfdff; }
        .status {
            background: #f3faf5;
            border: 1px solid #d2ebd8;
            border-radius: 12px;
            padding: 0.76rem 0.95rem;
            font-size: 0.92rem;
            color: #234b35;
            margin-bottom: 0.2rem;
            box-shadow: var(--shadow);
        }
        .span-4 { grid-column: span 1; }
        .span-6 { grid-column: span 1; }
        .span-8 { grid-column: span 1; }
        .span-12 { grid-column: span 1; }
        .span-3 { grid-column: span 1; }
        .span-9 { grid-column: span 1; }
        .legend { font-size: 0.92rem; color: var(--muted); margin-top: 0.55rem; }
        .subheading {
            margin: 0.7rem 0 0.35rem;
            font-size: 0.75rem;
            color: #637588;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }
        .detail-note { margin-top: 0.35rem; }
        .detail-note-strong { margin-top: 0.5rem; }
        @media (max-width: 1180px) {
            .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .span-3 .metrics { grid-template-columns: 1fr; }
            .controls { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        @media (max-width: 900px) {
            .metrics { grid-template-columns: 1fr; }
            .span-3, .span-4, .span-6, .span-8, .span-9, .span-12 { grid-column: span 1; }
            .controls { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <main class="container">
        <section class="layout-row">
            <section class="span-12 layout">
                <section class="hero">
                    <h1>The Farm: How's the Weather?</h1>
                    <p>Loveland, CO | __LOCAL_TIME__</p>
                </section>

                <section class="status">__KITTY_STATUS__</section>

            <div class="layout-row">
            <article class="card span-12">
                <h2>Temperature</h2>
                <div class="metrics">
                    <div class="metric"><div class="k">__TEMP_MODE__ Now</div><div class="v">__TEMP_NOW__</div></div>
                    <div class="metric"><div class="k">Hourly Change</div><div class="v">__TEMP_DELTA__</div></div>
                    <div class="metric"><div class="k">Today's High (__TEMP_MODE__)</div><div class="v">__TEMP_HIGH__</div></div>
                    <div class="metric"><div class="k">Today's Low (__TEMP_MODE__)</div><div class="v">__TEMP_LOW__</div></div>
                </div>
                <p class="settings-note">__SEASONAL_STATUS__</p>
                <div class="chart">
                    <div class="chart-axes-wrap">
                        <div class="y-axis-label">Temp °F</div>
                        <div class="chart-body">
                            __TEMP_CHART__
                            <div class="x-axis-label">Hour</div>
                        </div>
                    </div>
                    <div class="chart-legend">
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><polyline class="trend-line temp-obs" points="0,6 36,6"/></svg><span>Observed</span></div>
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><polyline class="trend-line temp-fcst" points="0,6 36,6"/></svg><span>Forecast</span></div>
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><line class="trend-target" x1="0" y1="6" x2="36" y2="6"/></svg><span>Target threshold</span></div>
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><rect class="trend-band temp-band" x="0" y="0" width="36" height="12"/><polyline class="trend-line temp-hist" points="0,6 36,6"/></svg><span>Historical context band + mean</span></div>
                        <p class="legend-note">Observed and forecast temperature lines follow the selected temperature basis.</p>
                    </div>
                </div>
            </article>
            </div>

            <hr class="section-divider" />

            <div class="layout-row">
            <article class="card span-6">
                <h2>Wind</h2>
                <p class="settings-note">__WIND_BANNER__</p>
                <div class="metrics">
                    <div class="metric"><div class="k">Wind Speed Now</div><div class="v">__WIND_NOW__</div></div>
                    <div class="metric"><div class="k">Wind Direction</div><div class="v">__WIND_DIR__</div></div>
                    <div class="metric"><div class="k">Today's Fastest Wind</div><div class="v">__FASTEST_WIND__</div></div>
                    <div class="metric"><div class="k">Today's Strongest Gust</div><div class="v">__STRONGEST_GUST__</div></div>
                </div>
                <div class="chart">
                    <div class="chart-axes-wrap">
                        <div class="y-axis-label">Wind speed mph</div>
                        <div class="chart-body">
                            __WIND_CHART__
                            <div class="x-axis-label">Hour</div>
                        </div>
                    </div>
                    <div class="chart-legend">
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><polyline class="trend-line wind-obs" points="0,6 36,6"/></svg><span>Observed wind</span></div>
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><polyline class="trend-line wind-fcst" points="0,6 36,6"/></svg><span>Forecast wind</span></div>
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><polyline class="trend-line gust" points="0,6 36,6"/></svg><span>Gust overlay</span></div>
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><rect class="trend-band wind-band" x="0" y="0" width="36" height="12"/><polyline class="trend-line wind-hist" points="0,6 36,6"/></svg><span>Historical context band + mean</span></div>
                        <p class="legend-note">Observed hours transition into forecast hours at the current-hour boundary.</p>
                    </div>
                </div>
            </article>
            <article class="card span-6">
                <h2>Air Quality</h2>
                <div class="metrics">
                    <div class="metric"><div class="k">Current AQI</div><div class="v">__CURRENT_AQI__</div></div>
                    <div class="metric"><div class="k">Highest AQI Today</div><div class="v">__HIGH_AQI__</div></div>
                    <div class="metric"><div class="k">Lowest AQI Today</div><div class="v">__LOW_AQI__</div></div>
                    <div class="metric"><div class="k">Interpretation</div><div class="v">__AQI_INTERP__</div></div>
                </div>
                <div class="chart">
                    <div class="chart-axes-wrap">
                        <div class="y-axis-label">AQI</div>
                        <div class="chart-body">
                            __AQI_CHART__
                            <div class="x-axis-label">Hour</div>
                        </div>
                    </div>
                    <div class="chart-legend">
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><polyline class="trend-line aqi-obs" points="0,6 36,6"/></svg><span>Observed AQI</span></div>
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><polyline class="trend-line aqi-fcst" points="0,6 36,6"/></svg><span>Forecast AQI</span></div>
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><polygon class="trend-band aqi-band" points="0,3 36,3 36,9 0,9"/><polyline class="trend-line aqi-hist" points="0,6 36,6"/></svg><span>Historical context band</span></div>
                        <p class="legend-note">Trend anchored to the same hour-boundary semantics as temperature and wind; split marker shows the observed-to-forecast transition. Pollutant fields use source-missing semantics when unavailable.</p>
                    </div>
                </div>
                <h3 class="subheading">Pollutant Breakdown</h3>
                <table class="mini-table">
                    <thead><tr><th>Pollutant</th><th>Value</th><th>Units</th></tr></thead>
                    <tbody>
                        <tr><td>PM2.5</td><td>__PM25__</td><td>ug/m3</td></tr>
                        <tr><td>PM10</td><td>__PM10__</td><td>ug/m3</td></tr>
                        <tr><td>O3</td><td>__O3__</td><td>ppb</td></tr>
                        <tr><td>NO2</td><td>__NO2__</td><td>ppb</td></tr>
                        <tr><td>CO</td><td>__CO__</td><td>ppm</td></tr>
                    </tbody>
                </table>
            </article>
            </div>

            <hr class="section-divider" />

            <div class="stack">
            <article class="card span-12">
                <h2>Precipitation</h2>
                <div class="metrics">
                    <div class="metric"><div class="k">Rain or Snow Recently?</div><div class="v">__RAIN_RECENTLY__</div></div>
                    <div class="metric"><div class="k">Total Accumulation So Far Today</div><div class="v">__PRECIP_TOTAL__</div></div>
                    <div class="metric"><div class="k">Forecasted Precipitation Now %</div><div class="v">__PRECIP_NOW__</div></div>
                    <div class="metric"><div class="k">Relative Humidity Now %</div><div class="v">__HUMIDITY_NOW__</div></div>
                </div>
                <div class="chart">
                    <div class="chart-axes-wrap">
                        <div class="y-axis-label">Precip in</div>
                        <div class="chart-body">
                            __PRECIP_CHART__
                            <div class="x-axis-label">Hour</div>
                        </div>
                    </div>
                    <div class="chart-legend">
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><polyline class="trend-line precip-obs" points="0,6 36,6"/></svg><span>Observed (in)</span></div>
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><polyline class="trend-line precip-fcst" points="0,6 36,6"/></svg><span>Forecast (in)</span></div>
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><polygon class="trend-band precip-band" points="0,3 36,3 36,9 0,9"/><polyline class="trend-line precip-hist" points="0,6 36,6"/></svg><span>Historical context band</span></div>
                        <p class="legend-note">Values in inches. Recently? is based on observed-hours accumulation logic.</p>
                    </div>
                </div>
            </article>

            <article class="card span-12">
                <h2>Sunrise / Sunset / Brightness</h2>
                <div class="metrics">
                    <div class="metric"><div class="k">Sunrise</div><div class="v">06:15 (+1m from yesterday)</div></div>
                    <div class="metric"><div class="k">Sunset</div><div class="v">20:10 (+2m from yesterday)</div></div>
                    <div class="metric"><div class="k">Daylight Today</div><div class="v">13h 55m (+3m)</div></div>
                    <div class="metric"><div class="k">Peak UV Index Today</div><div class="v">__PEAK_UV__</div></div>
                </div>
                <div class="chart">
                    <div class="chart-axes-wrap">
                        <div class="y-axis-label">UV index (0–11)</div>
                        <div class="chart-body">
                            __BRIGHTNESS_CHART__
                            <div class="x-axis-label">Hour</div>
                        </div>
                        <div class="y-axis-label right">Cloud cover % (0–100)</div>
                    </div>
                    <div class="chart-legend">
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><polyline class="trend-line uv obs" points="0,6 36,6"/></svg><span>Observed UV index (left axis)</span></div>
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><polyline class="trend-line uv fcst" points="0,6 36,6"/></svg><span>Forecast UV index (left axis)</span></div>
                        <div class="legend-row"><svg class="legend-swatch" viewBox="0 0 36 12"><rect class="trend-cloud-area" x="0" y="0" width="36" height="12"/></svg><span>Cloud cover % (right axis)</span></div>
                        <p class="legend-note">UV and cloud traces are read independently; left axis tracks UV index (0–11), right axis tracks cloud cover % (0–100).</p>
                    </div>
                </div>
            </article>

            <article class="card span-12">
                <h2>Data Sources</h2>
                <p>Provider role context: Open-Meteo style hourly model blends and Visual Crossing style observational semantics are represented through a normalized contract in this phase.</p>
                <p class="detail-note-strong">Blended-model caveat: values can reflect mixed model assumptions and should be interpreted as trend guidance, not instrument-grade measurements.</p>
                <p class="detail-note">Refresh cadence context: normalized forecast bundles are generated periodically, with observed-vs-forecast boundaries anchored to the current hour.</p>
                <p class="detail-note">Current source: <code>__SOURCE__</code> | Generated at: __GENERATED_AT__</p>
            </article>

            <article class="card span-12">
                <h2>Controls</h2>
                <p class="settings-note">Use these controls to update downstream metrics, status, and chart semantics across all sections.</p>
                <section class="control-strip">
                    <form class="controls" method="get" action="/dashboard">
                        <div class="control">
                            <label for="mode">Monitoring Mode</label>
                            <select id="mode" name="mode">
                                <option value="winter" __MODE_WINTER_SELECTED__>Winter (Warming Focus)</option>
                                <option value="summer" __MODE_SUMMER_SELECTED__>Summer (Cooling Focus)</option>
                            </select>
                        </div>
                        <div class="control">
                            <label for="temp">Temperature Type</label>
                            <select id="temp" name="temp">
                                <option value="actual" __TEMP_ACTUAL_SELECTED__>Actual</option>
                                <option value="feels_like" __TEMP_FEELS_SELECTED__>Feels Like</option>
                            </select>
                        </div>
                        <div class="control">
                            <label for="wind_cutoff">Kitty Wind Cutoff (mph)</label>
                            <input id="wind_cutoff" name="wind_cutoff" type="number" min="0" max="40" step="1" value="__WIND_CUTOFF__" />
                        </div>
                        <button type="submit">Apply</button>
                    </form>
                    <div class="control-meta">Runtime: rust-phase-c | Active mode: __ACTIVE_MODE__ | Temp basis: __ACTIVE_TEMP__</div>
                </section>
                <p class="legend">Controls section is intentionally placed after Data Sources for parity with the Streamlit review baseline.</p>
            </article>
            </div>
            </section>
        </section>
    </main>
</body>
</html>
"#;

    template
        .replace("__SOURCE__", &bundle.source)
        .replace("__GENERATED_AT__", &bundle.generated_at.to_rfc3339())
        .replace("__TEMP_NOW__", &temp_now)
        .replace("__TEMP_MODE__", settings.temp_label)
        .replace("__WIND_NOW__", &wind_now)
        .replace("__LOCAL_TIME__", &local_time_txt)
        .replace("__KITTY_STATUS__", &kitty_status_txt)
        .replace("__SEASONAL_STATUS__", &seasonal_status_txt)
        .replace("__ACTIVE_MODE__", settings.mode_label)
        .replace("__ACTIVE_TEMP__", settings.temp_label)
        .replace(
            "__WIND_CUTOFF__",
            &settings.kitty_wind_cutoff_mph.to_string(),
        )
        .replace(
            "__MODE_WINTER_SELECTED__",
            if settings.is_winter_mode {
                "selected"
            } else {
                ""
            },
        )
        .replace(
            "__MODE_SUMMER_SELECTED__",
            if settings.is_winter_mode {
                ""
            } else {
                "selected"
            },
        )
        .replace(
            "__TEMP_ACTUAL_SELECTED__",
            if settings.use_feels_like {
                ""
            } else {
                "selected"
            },
        )
        .replace(
            "__TEMP_FEELS_SELECTED__",
            if settings.use_feels_like {
                "selected"
            } else {
                ""
            },
        )
        .replace("__TEMP_CHART__", &temp_chart_svg)
        .replace("__WIND_CHART__", &wind_chart_svg)
        .replace("__AQI_CHART__", &aqi_chart_svg)
        .replace("__PRECIP_CHART__", &precip_chart_svg)
        .replace("__BRIGHTNESS_CHART__", &brightness_chart_svg)
        .replace("__TEMP_HIGH__", &temp_high_txt)
        .replace("__TEMP_LOW__", &temp_low_txt)
        .replace("__TEMP_DELTA__", &temp_delta_txt)
        .replace("__WIND_DIR__", wind_direction_txt)
        .replace("__WIND_BANNER__", &wind_banner_txt)
        .replace("__FASTEST_WIND__", &fastest_wind_txt)
        .replace("__STRONGEST_GUST__", &strongest_gust_txt)
        .replace(
            "__RAIN_RECENTLY__",
            if rain_or_snow_recently { "Yes" } else { "No" },
        )
        .replace("__PRECIP_TOTAL__", &format!("{precip_total:.2} in"))
        .replace(
            "__PRECIP_NOW__",
            &precip_now_prob
                .map(|v| format!("{v}%"))
                .unwrap_or_else(|| "N/A".to_string()),
        )
        .replace(
            "__HUMIDITY_NOW__",
            &humidity_now
                .map(|v| format!("{v}%"))
                .unwrap_or_else(|| "N/A".to_string()),
        )
        .replace("__CURRENT_AQI__", &current_aqi_txt)
        .replace("__HIGH_AQI__", &high_aqi_txt)
        .replace("__LOW_AQI__", &low_aqi_txt)
        .replace(
            "__AQI_INTERP__",
            current_aqi_value.map(aqi_label).unwrap_or("Unavailable"),
        )
        .replace("__PM25__", &format!("{pm25:.1}"))
        .replace("__PM10__", &format!("{pm10:.1}"))
        .replace("__O3__", &format!("{o3:.1}"))
        .replace("__NO2__", &format!("{no2:.1}"))
        .replace("__CO__", &format!("{co:.2}"))
        .replace("__PEAK_UV__", &peak_uv_txt)
}

fn aqi_label(aqi: f64) -> &'static str {
    if aqi <= 50.0 {
        "Good"
    } else if aqi <= 100.0 {
        "Moderate"
    } else if aqi <= 150.0 {
        "Unhealthy for Sensitive Groups"
    } else if aqi <= 200.0 {
        "Unhealthy"
    } else if aqi <= 300.0 {
        "Very Unhealthy"
    } else {
        "Hazardous"
    }
}

fn uv_label(uv: f64) -> &'static str {
    if uv <= 2.0 {
        "Low"
    } else if uv <= 5.0 {
        "Moderate"
    } else if uv <= 7.0 {
        "High"
    } else if uv <= 10.0 {
        "Very High"
    } else {
        "Extreme"
    }
}

fn error_dashboard_html(error: &str) -> String {
    format!(
        "<html><body style='font-family:sans-serif;padding:1rem;'><h1>Dashboard unavailable</h1><p>{error}</p></body></html>"
    )
}

fn find_current_point(points: &[ForecastPoint], hour: u8) -> Option<&ForecastPoint> {
    points.iter().find(|p| p.hour == hour)
}

#[cfg(test)]
mod tests {
    use super::{dashboard_html, find_current_point, DashboardSettings};
    use chrono::Utc;
    use farm_monitor_data::{ForecastBundle, ForecastPoint};

    fn sample_bundle() -> ForecastBundle {
        ForecastBundle {
            source: "test-source".to_string(),
            generated_at: Utc::now(),
            points: vec![
                ForecastPoint {
                    hour: 9,
                    temp_f: 55.1,
                    feels_like_f: 54.8,
                    wind_mph: 6.0,
                    aqi: Some(42.0),
                    uv_index: Some(2.1),
                    cloud_cover_pct: Some(25.0),
                },
                ForecastPoint {
                    hour: 10,
                    temp_f: 57.3,
                    feels_like_f: 57.1,
                    wind_mph: 6.8,
                    aqi: Some(44.0),
                    uv_index: Some(3.4),
                    cloud_cover_pct: Some(22.0),
                },
            ],
        }
    }

    fn default_settings() -> DashboardSettings {
        DashboardSettings {
            mode_label: "Winter (Warming Focus)",
            is_winter_mode: true,
            threshold_f: 65.0,
            temp_label: "Actual",
            use_feels_like: false,
            kitty_wind_cutoff_mph: 5,
        }
    }

    #[test]
    fn dashboard_contains_core_phase_c_sections() {
        let html = dashboard_html(&sample_bundle(), &default_settings());
        assert!(html.contains("Temperature"));
        assert!(html.contains("Wind"));
        assert!(html.contains("Precipitation"));
        assert!(html.contains("Air Quality"));
        assert!(html.contains("Sunrise / Sunset / Brightness"));
        assert!(html.contains("Pollutant Breakdown"));
        assert!(html.contains("Loveland, CO |"));
    }

    #[test]
    fn dashboard_renders_data_rows_from_bundle() {
        let html = dashboard_html(&sample_bundle(), &default_settings());
        assert!(html.contains("test-source"));
        assert!(html.contains("55.1°F"));
        assert!(html.contains("Current AQI"));
        assert!(html.contains("Kitty Comfort Threshold:"));
        assert!(html.contains("Good Temperature for Kitties:"));
        assert!(
            html.contains("Not too windy for Kitties:") || html.contains("Too windy for Kitties:")
        );
        assert!(html.contains("trend-target"));
        assert!(html.contains("trend-line gust"));
        assert!(html.contains("trend-line aqi-obs"));
        assert!(html.contains("trend-line aqi-fcst"));
        assert!(html.contains("trend-band temp-band"));
        assert!(html.contains("trend-band wind-band"));
        assert!(html.contains("trend-line temp-hist"));
        assert!(html.contains("trend-line wind-hist"));
        assert!(html.contains("trend-split"));
    }

    #[test]
    fn dashboard_places_controls_after_data_sources() {
        let html = dashboard_html(&sample_bundle(), &default_settings());
        let data_sources_idx = html.find("<h2>Data Sources</h2>").expect("data sources");
        let controls_idx = html.find("<h2>Controls</h2>").expect("controls section");
        assert!(controls_idx > data_sources_idx);
    }

    #[test]
    fn find_current_point_returns_match_when_hour_exists() {
        let bundle = sample_bundle();
        let point = find_current_point(&bundle.points, 10).expect("point exists");
        assert_eq!(point.temp_f, 57.3);
    }
}
