use axum::{
    response::{Html, Redirect},
    routing::get,
    Json, Router,
};
use chrono::{Timelike, Utc};
use farm_monitor_data::models::ProviderPoint;
use farm_monitor_data::{
    normalize_provider_response, FileForecastCache, ForecastBundle, ForecastPoint, LocationRequest,
    ProviderForecastResponse,
};
use farm_monitor_domain::HealthStatus;
use std::net::SocketAddr;
use std::{f64::consts::PI, fmt::Write};
use tracing::info;

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

    let addr: SocketAddr = "127.0.0.1:8080".parse().expect("valid socket address");
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

async fn dashboard() -> Html<String> {
    match load_dashboard_bundle() {
        Ok(bundle) => Html(dashboard_html(&bundle)),
        Err(err) => Html(error_dashboard_html(&format!(
            "failed to load dashboard data: {err}"
        ))),
    }
}

fn load_dashboard_bundle() -> anyhow::Result<ForecastBundle> {
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
    let provider = mock_provider_forecast(&location);
    let normalized = normalize_provider_response(provider);

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

fn dashboard_html(bundle: &ForecastBundle) -> String {
    let now_hour = Utc::now().hour() as u8;
    let current = find_current_point(&bundle.points, now_hour)
        .or_else(|| bundle.points.first())
        .cloned();

    let mut hourly_rows = String::new();
    for point in bundle.points.iter().take(8) {
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

    let (temp_now, feels_now, wind_now, aqi_now) = match current {
        Some(p) => (
            format!("{:.1}°F", p.temp_f),
            format!("{:.1}°F", p.feels_like_f),
            format!("{:.1} mph", p.wind_mph),
            p.aqi
                .map(|v| format!("{v:.0}"))
                .unwrap_or_else(|| "-".to_string()),
        ),
        None => (
            "-".to_string(),
            "-".to_string(),
            "-".to_string(),
            "-".to_string(),
        ),
    };

    let template = r#"<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>The Farm Monitor (Rust)</title>
    <style>
        :root {
            --bg: #0e1117;
            --panel: #161b22;
            --text: #e6edf3;
            --muted: #9da7b3;
            --accent: #22d3ee;
            --good: #9ad162;
            --warn: #f5b800;
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
            background: radial-gradient(circle at 20% 0%, #1d2735, var(--bg) 45%);
            color: var(--text);
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 1.25rem;
        }
        .hero {
            background: linear-gradient(135deg, #142033, #101827);
            border: 1px solid #273244;
            border-radius: 14px;
            padding: 1rem 1.25rem;
            margin-bottom: 1rem;
        }
        .hero h1 {
            margin: 0 0 0.35rem 0;
            font-size: 1.45rem;
        }
        .hero p {
            margin: 0;
            color: var(--muted);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(12, 1fr);
            gap: 0.9rem;
        }
        .card {
            background: var(--panel);
            border: 1px solid #2a3342;
            border-radius: 12px;
            padding: 0.9rem;
            min-height: 120px;
        }
        .card h2 {
            margin: 0 0 0.5rem 0;
            font-size: 1rem;
        }
        .card p {
            margin: 0;
            color: var(--muted);
            line-height: 1.4;
        }
        .span-4 { grid-column: span 4; }
        .span-6 { grid-column: span 6; }
        .span-8 { grid-column: span 8; }
        .span-12 { grid-column: span 12; }
        .legend {
            font-size: 0.92rem;
            color: var(--muted);
            margin-top: 0.55rem;
        }
        .legend .uv { color: var(--warn); font-weight: 600; }
        .legend .cloud { color: var(--accent); font-weight: 600; }
        .badge {
            display: inline-block;
            margin-left: 0.4rem;
            font-size: 0.75rem;
            border-radius: 999px;
            padding: 0.15rem 0.5rem;
            color: #09101a;
            background: var(--good);
            vertical-align: middle;
        }
        @media (max-width: 900px) {
            .span-4, .span-6, .span-8, .span-12 { grid-column: span 12; }
        }
    </style>
</head>
<body>
    <main class="container">
        <section class="hero">
            <h1>The Farm Monitor: How's the Weather? <span class="badge">Rust Phase C</span></h1>
            <p>Live model-backed preview using normalized forecast data (__SOURCE__).</p>
        </section>

        <section class="grid">
            <article class="card span-8">
                <h2>Temperature Trend</h2>
                <p>Preview rows (hour, temp, wind, AQI, UV):</p>
                <table style="width:100%;border-collapse:collapse;margin-top:0.5rem;font-size:0.92rem;">
                    <thead>
                        <tr style="text-align:left;color:#9da7b3;">
                            <th style="padding:0.25rem 0;">Hour</th>
                            <th>Temp</th>
                            <th>Wind</th>
                            <th>AQI</th>
                            <th>UV</th>
                        </tr>
                    </thead>
                    <tbody>__HOURLY_ROWS__</tbody>
                </table>
            </article>
            <article class="card span-4">
                <h2>Current Conditions</h2>
                <p><strong>Now Temp:</strong> __TEMP_NOW__</p>
                <p><strong>Feels Like:</strong> __FEELS_NOW__</p>
                <p><strong>Wind:</strong> __WIND_NOW__</p>
                <p><strong>AQI:</strong> __AQI_NOW__</p>
            </article>

            <article class="card span-6">
                <h2>Wind Outlook</h2>
                <p>Placeholder for wind speed and gust trend with observed/forecast split.</p>
            </article>
            <article class="card span-6">
                <h2>Air Quality</h2>
                <p>Placeholder for AQI trend and pollutant details table.</p>
            </article>

            <article class="card span-12">
                <h2>Sunrise / Sunset / Brightness</h2>
                <p>Placeholder for sunrise/sunset timing deltas and UV/cloud cover chart.</p>
                <p class="legend"><span class="uv">━ UV Index</span> (left axis) and <span class="cloud">█ Cloud Cover %</span> (right axis).</p>
            </article>

            <article class="card span-12">
                <h2>Data Sources</h2>
                <p>Current source: <code>__SOURCE__</code> | Generated at: __GENERATED_AT__</p>
            </article>
        </section>
    </main>
</body>
</html>
"#;

    template
        .replace("__SOURCE__", &bundle.source)
        .replace("__GENERATED_AT__", &bundle.generated_at.to_rfc3339())
        .replace("__HOURLY_ROWS__", &hourly_rows)
        .replace("__TEMP_NOW__", &temp_now)
        .replace("__FEELS_NOW__", &feels_now)
        .replace("__WIND_NOW__", &wind_now)
        .replace("__AQI_NOW__", &aqi_now)
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
    use super::{dashboard_html, find_current_point};
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

    #[test]
    fn dashboard_contains_core_phase_c_sections() {
        let html = dashboard_html(&sample_bundle());
        assert!(html.contains("Temperature Trend"));
        assert!(html.contains("Wind Outlook"));
        assert!(html.contains("Air Quality"));
        assert!(html.contains("Sunrise / Sunset / Brightness"));
    }

    #[test]
    fn dashboard_renders_data_rows_from_bundle() {
        let html = dashboard_html(&sample_bundle());
        assert!(html.contains("test-source"));
        assert!(html.contains("09:00"));
        assert!(html.contains("55.1°F"));
    }

    #[test]
    fn find_current_point_returns_match_when_hour_exists() {
        let bundle = sample_bundle();
        let point = find_current_point(&bundle.points, 10).expect("point exists");
        assert_eq!(point.temp_f, 57.3);
    }
}
