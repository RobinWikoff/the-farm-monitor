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

    let (temp_now, wind_now) = match current {
        Some(ref p) => (
            format!("{:.1}°F", p.temp_f),
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
        .map(|p| p.temp_f)
        .max_by(|a, b| a.total_cmp(b))
        .map(|v| format!("{v:.1}°F"))
        .unwrap_or_else(|| "N/A".to_string());
    let temp_low_txt = bundle
        .points
        .iter()
        .filter(|p| p.hour <= now_hour)
        .map(|p| p.temp_f)
        .min_by(|a, b| a.total_cmp(b))
        .map(|v| format!("{v:.1}°F"))
        .unwrap_or_else(|| "N/A".to_string());
    let prior_temp = find_current_point(&bundle.points, prior_hour).map(|p| p.temp_f);
    let temp_delta_txt = match (current.as_ref().map(|p| p.temp_f), prior_temp) {
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
        let threshold = 65.0;
        match current.as_ref().map(|p| p.temp_f) {
            Some(temp) if temp >= threshold => {
                format!("Winter status: OK now ({temp:.1}°F >= {threshold:.1}°F).")
            }
            Some(temp) => {
                let reaches_later = bundle
                    .points
                    .iter()
                    .any(|p| p.hour >= now_hour && p.temp_f >= threshold);
                if reaches_later {
                    format!("Winter status: below threshold now ({temp:.1}°F), forecast reaches {threshold:.1}°F later today.")
                } else {
                    format!("Winter status: below threshold now ({temp:.1}°F) and not forecast to reach {threshold:.1}°F today.")
                }
            }
            None => "Winter status unavailable (missing temperature data).".to_string(),
        }
    };

    let kitty_status_txt = {
        let temp_ok = current
            .as_ref()
            .map(|p| p.temp_f > 32.0 && p.temp_f <= 85.0)
            .unwrap_or(false);
        let wind_ok = current.as_ref().map(|p| p.wind_mph <= 5.0).unwrap_or(true);
        let precip_ok = !rain_or_snow_recently;
        let overall = temp_ok && wind_ok && precip_ok;
        format!(
            "Kitty Comfort Threshold: {} | Temp: {} | Wind: {} | Rain/Snow: {}",
            if overall { "Yes" } else { "No" },
            if temp_ok { "OK" } else { "Not OK" },
            if wind_ok { "OK" } else { "Not OK" },
            if precip_ok { "No" } else { "Yes" }
        )
    };

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
        .hero h1 { margin: 0 0 0.35rem 0; font-size: 1.32rem; letter-spacing: 0.01em; }
        .hero p { margin: 0; color: var(--muted); }
        .layout {
            display: grid;
            gap: 0.9rem;
        }
        .layout-row {
            display: grid;
            grid-template-columns: repeat(12, minmax(0, 1fr));
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
        .chart-title {
            font-size: 0.82rem;
            color: #29445e;
            font-weight: 650;
            letter-spacing: 0.01em;
        }
        .chart-note {
            margin-top: 0.2rem;
            color: #5b6f84;
            font-size: 0.78rem;
        }
        .chart-ribbon {
            margin-top: 0.5rem;
            display: flex;
            flex-wrap: wrap;
            gap: 0.35rem;
        }
        .chip {
            border: 1px solid #ced9e8;
            background: #f7fbff;
            color: #35556f;
            border-radius: 999px;
            padding: 0.16rem 0.45rem;
            font-size: 0.72rem;
            letter-spacing: 0.01em;
        }
        .chip.obs {
            border-color: #79a6f6;
            background: #edf4ff;
            color: #1f4e95;
        }
        .chip.fcst {
            border-color: #85b9c9;
            background: #eef9fc;
            color: #245a67;
        }
        .chip.uv-chip {
            border-color: #f1c36d;
            background: #fff7e8;
            color: #8a5b08;
        }
        .chip.cloud-chip {
            border-color: #8bb4ef;
            background: #eef4ff;
            color: #1f4e95;
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
        .axis-tags {
            margin-top: 0.42rem;
            display: flex;
            justify-content: space-between;
            gap: 0.35rem;
            flex-wrap: wrap;
        }
        .axis-tag {
            font-size: 0.72rem;
            color: #5f7184;
            text-transform: uppercase;
            letter-spacing: 0.03em;
        }
        .axis-tag.left { color: #26547f; }
        .axis-tag.right { color: #8a5b08; }
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
        .span-4 { grid-column: span 4; }
        .span-6 { grid-column: span 6; }
        .span-8 { grid-column: span 8; }
        .span-12 { grid-column: span 12; }
        .span-3 { grid-column: span 3; }
        .span-9 { grid-column: span 9; }
        .legend { font-size: 0.92rem; color: var(--muted); margin-top: 0.55rem; }
        .legend .uv { color: var(--warn); font-weight: 600; }
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
        }
        .legend .cloud { color: var(--accent); font-weight: 600; }
        @media (max-width: 900px) {
            .metrics { grid-template-columns: 1fr; }
            .span-3, .span-4, .span-6, .span-8, .span-9, .span-12 { grid-column: span 12; }
        }
    </style>
</head>
<body>
    <main class="container">
        <section class="layout-row">
            <aside class="card span-3">
                <h2>Settings</h2>
                <div class="metrics">
                    <div class="metric"><div class="k">Monitoring Mode</div><div class="v">Winter (Warming Focus)</div></div>
                    <div class="metric"><div class="k">Temperature Type</div><div class="v">Actual</div></div>
                    <div class="metric"><div class="k">Kitty Wind Cutoff (mph)</div><div class="v">5</div></div>
                    <div class="metric"><div class="k">Runtime</div><div class="v">rust-phase-c</div></div>
                </div>
            </aside>

            <section class="span-9 layout">
                <section class="hero">
                    <h1>The Farm: How's the Weather?</h1>
                    <p>Loveland, CO | __LOCAL_TIME__</p>
                </section>

                <section class="status">__KITTY_STATUS__</section>

            <div class="layout-row">
            <article class="card span-12">
                <h2>Temperature</h2>
                <div class="metrics">
                    <div class="metric"><div class="k">Temp Now</div><div class="v">__TEMP_NOW__</div></div>
                    <div class="metric"><div class="k">Today's High</div><div class="v">__TEMP_HIGH__</div></div>
                    <div class="metric"><div class="k">Today's Low</div><div class="v">__TEMP_LOW__</div></div>
                    <div class="metric"><div class="k">1-hour Delta</div><div class="v">__TEMP_DELTA__</div></div>
                </div>
                <p class="settings-note">__SEASONAL_STATUS__</p>
                <div class="chart">Temperature chart: observed vs forecast semantics.</div>
                <p class="legend">Legend: observed segment and forecast segment reflect the selected temperature type.</p>
            </article>
            </div>

            <hr class="section-divider" />

            <div class="layout-row">
            <article class="card span-6">
                <h2>Wind</h2>
                <div class="metrics">
                    <div class="metric"><div class="k">Wind Speed Now</div><div class="v">__WIND_NOW__</div></div>
                    <div class="metric"><div class="k">Wind Direction</div><div class="v">__WIND_DIR__</div></div>
                    <div class="metric"><div class="k">Today's Fastest Wind</div><div class="v">__FASTEST_WIND__</div></div>
                    <div class="metric"><div class="k">Today's Strongest Gust</div><div class="v">__STRONGEST_GUST__</div></div>
                </div>
                <div class="chart">
                    <div class="chart-title">Wind speed trend with gust context</div>
                    <div class="chart-note">Observed hours transition into forecast hours at the current-hour boundary.</div>
                    <div class="chart-ribbon"><span class="chip obs">Observed</span><span class="chip fcst">Forecast</span></div>
                    <div class="mini-bars">
                        <span class="bar obs" style="height:42%"></span><span class="bar obs" style="height:55%"></span><span class="bar obs" style="height:46%"></span><span class="bar obs" style="height:62%"></span><span class="bar obs" style="height:51%"></span><span class="bar obs" style="height:66%"></span><span class="bar fcst" style="height:58%"></span><span class="bar fcst" style="height:72%"></span><span class="bar fcst" style="height:64%"></span><span class="bar fcst" style="height:78%"></span><span class="bar fcst" style="height:69%"></span><span class="bar fcst" style="height:74%"></span>
                    </div>
                    <div class="axis-tags"><span class="axis-tag left">Y-axis: wind speed mph</span><span class="axis-tag">X-axis: local hour</span></div>
                </div>
                <p class="legend">Caption: wind cutoff evaluation uses configured kitty wind threshold.</p>
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
                    <div class="chart-title">AQI trend with observed-to-forecast split</div>
                    <div class="chart-note">Trend readability is anchored to the same hour-boundary semantics as temperature and wind.</div>
                    <div class="chart-ribbon"><span class="chip obs">Observed AQI</span><span class="chip fcst">Forecast AQI</span></div>
                    <div class="mini-bars">
                        <span class="bar aqi-bar obs" style="height:40%"></span><span class="bar aqi-bar obs" style="height:48%"></span><span class="bar aqi-bar obs" style="height:45%"></span><span class="bar aqi-bar obs" style="height:53%"></span><span class="bar aqi-bar obs" style="height:50%"></span><span class="bar aqi-bar obs" style="height:57%"></span><span class="bar aqi-bar fcst" style="height:52%"></span><span class="bar aqi-bar fcst" style="height:59%"></span><span class="bar aqi-bar fcst" style="height:56%"></span><span class="bar aqi-bar fcst" style="height:63%"></span><span class="bar aqi-bar fcst" style="height:58%"></span><span class="bar aqi-bar fcst" style="height:61%"></span>
                    </div>
                    <div class="axis-tags"><span class="axis-tag left">Y-axis: AQI scale</span><span class="axis-tag">X-axis: local hour</span></div>
                </div>
                <p class="legend">Caption: pollutant fields use source-missing semantics when unavailable.</p>
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
                <div class="chart">Precipitation chart: hourly observed precipitation semantics.</div>
                <p class="legend">Caption: Recently? is based on observed-hours accumulation logic.</p>
            </article>

            <article class="card span-12">
                <h2>Sunrise / Sunset / Brightness</h2>
                <div class="metrics">
                    <div class="metric"><div class="k">Sunrise</div><div class="v">06:15 (+1m vs yesterday)</div></div>
                    <div class="metric"><div class="k">Sunset</div><div class="v">20:10 (+2m vs yesterday)</div></div>
                    <div class="metric"><div class="k">Daylight Today</div><div class="v">13h 55m (+3m)</div></div>
                    <div class="metric"><div class="k">Peak UV Index Today</div><div class="v">__PEAK_UV__</div></div>
                </div>
                <div class="chart">
                    <div class="chart-title">Brightness trend: UV and cloud dual-axis view</div>
                    <div class="chart-note">UV and cloud traces are read independently while sharing hourly alignment.</div>
                    <div class="chart-ribbon"><span class="chip uv-chip">UV Index</span><span class="chip cloud-chip">Cloud Cover %</span></div>
                    <div class="mini-bars">
                        <span class="bar uv-bar" style="height:10%"></span><span class="bar cloud-bar" style="height:56%"></span><span class="bar uv-bar" style="height:22%"></span><span class="bar cloud-bar" style="height:48%"></span><span class="bar uv-bar" style="height:45%"></span><span class="bar cloud-bar" style="height:38%"></span><span class="bar uv-bar" style="height:72%"></span><span class="bar cloud-bar" style="height:31%"></span><span class="bar uv-bar" style="height:66%"></span><span class="bar cloud-bar" style="height:42%"></span><span class="bar uv-bar" style="height:34%"></span><span class="bar cloud-bar" style="height:54%"></span>
                    </div>
                    <div class="axis-tags"><span class="axis-tag right">Left axis: UV index</span><span class="axis-tag left">Right axis: cloud cover %</span></div>
                </div>
                <p class="legend"><span class="uv">━ UV Index</span> (left axis) and <span class="cloud">█ Cloud Cover %</span> (right axis).</p>
            </article>

            <article class="card span-12">
                <h2>Data Sources</h2>
                <p>Provider role context: Open-Meteo style hourly model blends and Visual Crossing style observational semantics are represented through a normalized contract in this phase.</p>
                <p class="detail-note-strong">Blended-model caveat: values can reflect mixed model assumptions and should be interpreted as trend guidance, not instrument-grade measurements.</p>
                <p class="detail-note">Refresh cadence context: normalized forecast bundles are generated periodically, with observed-vs-forecast boundaries anchored to the current hour.</p>
                <p class="detail-note">Current source: <code>__SOURCE__</code> | Generated at: __GENERATED_AT__</p>
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
        .replace("__WIND_NOW__", &wind_now)
        .replace("__LOCAL_TIME__", &local_time_txt)
        .replace("__KITTY_STATUS__", &kitty_status_txt)
        .replace("__SEASONAL_STATUS__", &seasonal_status_txt)
        .replace("__TEMP_HIGH__", &temp_high_txt)
        .replace("__TEMP_LOW__", &temp_low_txt)
        .replace("__TEMP_DELTA__", &temp_delta_txt)
        .replace("__WIND_DIR__", wind_direction_txt)
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
        let html = dashboard_html(&sample_bundle());
        assert!(html.contains("test-source"));
        assert!(html.contains("55.1°F"));
        assert!(html.contains("Current AQI"));
        assert!(html.contains("Kitty Comfort Threshold:"));
    }

    #[test]
    fn find_current_point_returns_match_when_hour_exists() {
        let bundle = sample_bundle();
        let point = find_current_point(&bundle.points, 10).expect("point exists");
        assert_eq!(point.temp_f, 57.3);
    }
}
