use axum::{
    response::{Html, Redirect},
    routing::get,
    Json, Router,
};
use farm_monitor_domain::HealthStatus;
use std::net::SocketAddr;
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
    Html(dashboard_html())
}

fn dashboard_html() -> String {
    let html = r#"<!doctype html>
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
            <p>UI parity shell in progress. This page mirrors section structure while data-backed charts are phased in.</p>
        </section>

        <section class="grid">
            <article class="card span-8">
                <h2>Temperature Trend</h2>
                <p>Chart placeholder for actual vs forecast temperature with threshold and historical context.</p>
            </article>
            <article class="card span-4">
                <h2>Current Conditions</h2>
                <p>Live now card placeholder for temperature, feels-like, wind, and quick status badges.</p>
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
                <p>Visual Crossing, Open-Meteo, and AQI integrations will be wired in during subsequent Phase C milestones.</p>
            </article>
        </section>
    </main>
</body>
</html>
"#;
    html.to_string()
}

#[cfg(test)]
mod tests {
    use super::dashboard_html;

    #[test]
    fn dashboard_contains_core_phase_c_sections() {
        let html = dashboard_html();
        assert!(html.contains("Temperature Trend"));
        assert!(html.contains("Wind Outlook"));
        assert!(html.contains("Air Quality"));
        assert!(html.contains("Sunrise / Sunset / Brightness"));
    }
}
