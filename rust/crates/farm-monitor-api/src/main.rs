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
    let mut wind_rows = String::new();
    let mut precip_rows = String::new();
    let mut aqi_rows = String::new();
    let mut brightness_rows = String::new();

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

            let cloud = point.cloud_cover_pct.unwrap_or(0.0);
            let uv = point.uv_index.unwrap_or(0.0);
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

    let (temp_now, feels_now, wind_now, aqi_now) = match current {
        Some(ref p) => (
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

    let wind_now_value = current.as_ref().map(|p| p.wind_mph).unwrap_or_default();
    let prior_hour = now_hour.saturating_sub(1);
    let prior_wind = find_current_point(&bundle.points, prior_hour).map(|p| p.wind_mph);
    let wind_delta_txt = prior_wind
        .map(|prior| {
            format!(
                "{:+.1} mph since {:02}:00",
                wind_now_value - prior,
                prior_hour
            )
        })
        .unwrap_or_else(|| "N/A".to_string());

    let fastest_wind_txt = bundle
        .points
        .iter()
        .max_by(|a, b| a.wind_mph.total_cmp(&b.wind_mph))
        .map(|p| format!("{:.1} mph at {:02}:00", p.wind_mph, p.hour))
        .unwrap_or_else(|| "N/A".to_string());

    let strongest_gust = bundle
        .points
        .iter()
        .filter(|p| p.hour <= now_hour)
        .map(|p| p.wind_mph * 1.35)
        .fold(0.0_f64, f64::max);
    let strongest_gust_txt = if strongest_gust > 0.0 {
        format!("{strongest_gust:.1} mph")
    } else {
        "N/A".to_string()
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
        .container { max-width: 1200px; margin: 0 auto; padding: 1.25rem; }
        .hero {
            background: linear-gradient(135deg, #142033, #101827);
            border: 1px solid #273244;
            border-radius: 14px;
            padding: 1rem 1.25rem;
            margin-bottom: 1rem;
        }
        .hero h1 { margin: 0 0 0.35rem 0; font-size: 1.45rem; }
        .hero p { margin: 0; color: var(--muted); }
        .grid { display: grid; grid-template-columns: repeat(12, 1fr); gap: 0.9rem; }
        .card {
            background: var(--panel);
            border: 1px solid #2a3342;
            border-radius: 12px;
            padding: 0.9rem;
            min-height: 120px;
        }
        .card h2 { margin: 0 0 0.5rem 0; font-size: 1rem; }
        .card p { margin: 0; color: var(--muted); line-height: 1.4; }
        .metrics {
            display: grid;
            gap: 0.55rem;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            margin-top: 0.5rem;
            margin-bottom: 0.65rem;
        }
        .metric {
            border: 1px solid #2f3a4c;
            border-radius: 9px;
            padding: 0.45rem 0.55rem;
            background: #111a27;
        }
        .metric .k { color: #95a7be; font-size: 0.78rem; margin-bottom: 0.2rem; }
        .metric .v { font-size: 0.92rem; font-weight: 600; color: #dbe9f6; }
        .mini-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 0.5rem;
            font-size: 0.87rem;
        }
        .mini-table th {
            text-align: left;
            color: #97a8bc;
            border-bottom: 1px solid #2b384a;
            padding: 0.3rem 0.2rem;
        }
        .mini-table td {
            border-bottom: 1px solid #223044;
            color: #d5e2ef;
            padding: 0.32rem 0.2rem;
            vertical-align: middle;
        }
        .bar {
            width: 100%;
            background: #172131;
            border-radius: 999px;
            overflow: hidden;
            height: 0.52rem;
        }
        .bar span { display: block; height: 100%; background: linear-gradient(90deg, #29c0f8, #67e8f9); }
        .bar.aqi span { background: linear-gradient(90deg, #f5b800, #ff6b6b); }
        .bar.uv span { background: linear-gradient(90deg, #f5b800, #f97316); }
        .bar.cloud span { background: linear-gradient(90deg, #4ea8d2, #7cc7e8); }
        .span-4 { grid-column: span 4; }
        .span-6 { grid-column: span 6; }
        .span-8 { grid-column: span 8; }
        .span-12 { grid-column: span 12; }
        .legend { font-size: 0.92rem; color: var(--muted); margin-top: 0.55rem; }
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
                <table class="mini-table">
                    <thead><tr><th>Hour</th><th>Temp</th><th>Wind</th><th>AQI</th><th>UV</th></tr></thead>
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
                <div class="metrics">
                    <div class="metric"><div class="k">Wind Speed Now</div><div class="v">__WIND_NOW__</div></div>
                    <div class="metric"><div class="k">1-hour Delta</div><div class="v">__WIND_DELTA__</div></div>
                    <div class="metric"><div class="k">Today's Fastest Wind</div><div class="v">__FASTEST_WIND__</div></div>
                    <div class="metric"><div class="k">Strongest Gust (Observed)</div><div class="v">__STRONGEST_GUST__</div></div>
                </div>
                <table class="mini-table">
                    <thead><tr><th>Hour</th><th>Series</th><th>Speed</th><th>Gust</th><th>Trend</th></tr></thead>
                    <tbody>__WIND_ROWS__</tbody>
                </table>
            </article>

            <article class="card span-6">
                <h2>Air Quality</h2>
                <div class="metrics">
                    <div class="metric"><div class="k">Current AQI</div><div class="v">__CURRENT_AQI__</div></div>
                    <div class="metric"><div class="k">Highest AQI Today</div><div class="v">__HIGH_AQI__</div></div>
                    <div class="metric"><div class="k">Lowest AQI Today</div><div class="v">__LOW_AQI__</div></div>
                    <div class="metric"><div class="k">Interpretation</div><div class="v">__AQI_INTERP__</div></div>
                </div>
                <table class="mini-table">
                    <thead><tr><th>Hour</th><th>Series</th><th>AQI</th><th>Label</th><th>Trend</th></tr></thead>
                    <tbody>__AQI_ROWS__</tbody>
                </table>
                <p style="margin-top:0.55rem;">Pollutant Breakdown: PM2.5 __PM25__ ug/m3 | PM10 __PM10__ ug/m3 | O3 __O3__ ppb | NO2 __NO2__ ppb | CO __CO__ ppm</p>
            </article>

            <article class="card span-12">
                <h2>Precipitation</h2>
                <div class="metrics">
                    <div class="metric"><div class="k">Rain or Snow Recently?</div><div class="v">__RAIN_RECENTLY__</div></div>
                    <div class="metric"><div class="k">Total Accumulation So Far</div><div class="v">__PRECIP_TOTAL__</div></div>
                    <div class="metric"><div class="k">Precipitation Probability Now</div><div class="v">__PRECIP_NOW__</div></div>
                    <div class="metric"><div class="k">Relative Humidity Now</div><div class="v">__HUMIDITY_NOW__</div></div>
                </div>
                <table class="mini-table">
                    <thead><tr><th>Hour</th><th>Precip</th><th>Prob</th><th>Humidity</th><th>Snow</th></tr></thead>
                    <tbody>__PRECIP_ROWS__</tbody>
                </table>
            </article>

            <article class="card span-12">
                <h2>Sunrise / Sunset / Brightness</h2>
                <div class="metrics">
                    <div class="metric"><div class="k">Sunrise</div><div class="v">06:15 (+1m vs yesterday)</div></div>
                    <div class="metric"><div class="k">Sunset</div><div class="v">20:10 (+2m vs yesterday)</div></div>
                    <div class="metric"><div class="k">Daylight Today</div><div class="v">13h 55m (+3m)</div></div>
                    <div class="metric"><div class="k">Peak UV Index Today</div><div class="v">__PEAK_UV__</div></div>
                </div>
                <table class="mini-table">
                    <thead><tr><th>Hour</th><th>UV</th><th>Cloud</th><th>UV Axis</th><th>Cloud Axis</th></tr></thead>
                    <tbody>__BRIGHTNESS_ROWS__</tbody>
                </table>
                <p class="legend"><span class="uv">━ UV Index</span> (left axis) and <span class="cloud">█ Cloud Cover %</span> (right axis).</p>
            </article>

            <article class="card span-12">
                <h2>Data Sources</h2>
                <p>Current source: <code>__SOURCE__</code> | Generated at: __GENERATED_AT__</p>
                <p style="margin-top:0.5rem;">Open-Meteo and Visual Crossing semantics are represented in this phase by a normalized source contract; series are shown as observed and forecast for parity behavior review.</p>
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
        .replace("__WIND_ROWS__", &wind_rows)
        .replace("__PRECIP_ROWS__", &precip_rows)
        .replace("__AQI_ROWS__", &aqi_rows)
        .replace("__BRIGHTNESS_ROWS__", &brightness_rows)
        .replace("__TEMP_NOW__", &temp_now)
        .replace("__FEELS_NOW__", &feels_now)
        .replace("__WIND_NOW__", &wind_now)
        .replace("__AQI_NOW__", &aqi_now)
        .replace("__WIND_DELTA__", &wind_delta_txt)
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
        assert!(html.contains("Precipitation"));
        assert!(html.contains("Air Quality"));
        assert!(html.contains("Sunrise / Sunset / Brightness"));
        assert!(html.contains("Pollutant Breakdown"));
    }

    #[test]
    fn dashboard_renders_data_rows_from_bundle() {
        let html = dashboard_html(&sample_bundle());
        assert!(html.contains("test-source"));
        assert!(html.contains("09:00"));
        assert!(html.contains("55.1°F"));
        assert!(html.contains("Observed"));
        assert!(html.contains("Current AQI"));
    }

    #[test]
    fn find_current_point_returns_match_when_hour_exists() {
        let bundle = sample_bundle();
        let point = find_current_point(&bundle.points, 10).expect("point exists");
        assert_eq!(point.temp_f, 57.3);
    }
}
