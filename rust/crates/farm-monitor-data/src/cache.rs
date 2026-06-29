use crate::models::ForecastBundle;
use anyhow::{Context, Result};
use chrono::{DateTime, NaiveDate, Utc};
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Debug, Clone)]
pub struct FileForecastCache {
    root_dir: PathBuf,
}

impl FileForecastCache {
    pub fn new(root_dir: impl AsRef<Path>) -> Self {
        Self {
            root_dir: root_dir.as_ref().to_path_buf(),
        }
    }

    fn ensure_dir(&self) -> Result<()> {
        fs::create_dir_all(&self.root_dir).context("create cache directory")
    }

    fn path_for(&self, date: NaiveDate) -> PathBuf {
        self.root_dir
            .join(format!("forecast_{}.json", date.format("%Y-%m-%d")))
    }

    pub fn write(&self, date: NaiveDate, bundle: &ForecastBundle) -> Result<()> {
        self.ensure_dir()?;
        let payload = serde_json::to_string_pretty(bundle).context("serialize forecast bundle")?;
        fs::write(self.path_for(date), payload).context("write cache file")
    }

    pub fn read(&self, date: NaiveDate) -> Result<Option<ForecastBundle>> {
        let path = self.path_for(date);
        if !path.exists() {
            return Ok(None);
        }

        let raw = fs::read_to_string(path).context("read cache file")?;
        let parsed = serde_json::from_str::<ForecastBundle>(&raw).context("parse cache file")?;
        Ok(Some(parsed))
    }

    pub fn cleanup_older_than(&self, retention_days: i64, now: DateTime<Utc>) -> Result<usize> {
        if !self.root_dir.exists() {
            return Ok(0);
        }

        let cutoff = now.date_naive() - chrono::Duration::days(retention_days);
        let mut removed = 0usize;

        for entry in fs::read_dir(&self.root_dir).context("read cache directory")? {
            let entry = entry.context("read directory entry")?;
            let path = entry.path();
            let Some(filename) = path.file_name().and_then(|f| f.to_str()) else {
                continue;
            };

            if !(filename.starts_with("forecast_") && filename.ends_with(".json")) {
                continue;
            }

            let date_part = filename
                .trim_start_matches("forecast_")
                .trim_end_matches(".json");
            let Ok(file_date) = NaiveDate::parse_from_str(date_part, "%Y-%m-%d") else {
                continue;
            };

            if file_date < cutoff {
                fs::remove_file(&path)
                    .with_context(|| format!("remove old cache file: {filename}"))?;
                removed += 1;
            }
        }

        Ok(removed)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::models::{ForecastBundle, ForecastPoint};

    fn sample_bundle() -> ForecastBundle {
        ForecastBundle {
            source: "test".to_string(),
            generated_at: Utc::now(),
            sunrise: None,
            sunset: None,
            points: vec![ForecastPoint {
                hour: 9,
                temp_f: 55.0,
                feels_like_f: 54.0,
                wind_mph: 6.0,
                aqi: Some(42.0),
                uv_index: Some(3.0),
                cloud_cover_pct: Some(25.0),
                humidity_pct: None,
                precip_prob_pct: None,
                precip_hr_in: None,
            }],
        }
    }

    #[test]
    fn cache_write_and_read_round_trip() {
        let tmp = std::env::temp_dir().join(format!(
            "farm_monitor_cache_{}",
            Utc::now().timestamp_nanos_opt().unwrap_or_default()
        ));
        let cache = FileForecastCache::new(&tmp);
        let date = NaiveDate::from_ymd_opt(2026, 5, 25).expect("valid date");

        cache.write(date, &sample_bundle()).expect("write cache");
        let loaded = cache.read(date).expect("read cache").expect("cache exists");
        assert_eq!(loaded.source, "test");
        assert_eq!(loaded.points.len(), 1);

        let _ = fs::remove_dir_all(tmp);
    }
}
