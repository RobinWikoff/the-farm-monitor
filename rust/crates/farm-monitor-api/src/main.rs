use axum::{routing::get, Json, Router};
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

    let app = Router::new().route("/healthz", get(healthz));

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
