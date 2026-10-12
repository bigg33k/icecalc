# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ice Depth Calculator: a Streamlit app that estimates lake ice thickness from Weather Underground personal weather station data using Stefan's formula with accumulated freezing degree days (AFDD). Deployed on Streamlit Cloud (hence `requirements.txt`).

- `streamlit_weather_app.py` — the actual app (entry point for Streamlit Cloud and the dev container).
- `ice.py` — an older standalone prototype that only scrapes the dashboard summary table to CSV. Not used by the main app.

## Commands

```bash
pip install -r requirements.txt
streamlit run streamlit_weather_app.py   # serves on port 8501
```

The repo root doubles as a Python virtualenv (`bin/`, `lib/`, `include/`, `pyvenv.cfg` are gitignored), so `source bin/activate` works locally. There are no tests, linter, or build step.

## Architecture (streamlit_weather_app.py)

Single-file app. Data flows through `st.session_state`:

- `weather_data` — normalized input: columns `date` (YYYY-MM-DD string), `avg_temp_f`, `avg_wind_speed_mph`. Every input path (scrape, CSV upload, paste, manual entry) must produce this shape.
- `raw_weather_data` — unmodified scrape result, shown for debugging.
- `ice_data` — output of `calculate_ice_depth`, rendered by the results and charts tabs.
- `alpha`, `use_baseline`, `baseline_depth`, `baseline_date` — calibration settings from the sidebar.

Whenever `weather_data` or calibration changes, call `recalculate_ice_with_calibration(weather_df)` to rebuild `ice_data`. It passes `days_per_row=1` (daily data); note that `calculate_ice_depth` itself defaults to `days_per_row=7`, a leftover from weekly data.

**Calculation** (`calculate_ice_depth`): per row FDD = max(0, 32 − T) and TDD = max(0, T − 32), each × `days_per_row`; net AFDD = cumsum(FDD) − cumsum(TDD); wind factor = max(0.7, 1 − wind/50); depth = max(0, baseline_depth + α·√max(0, net AFDD)·wind_factor). With a baseline, rows before `baseline_date` are dropped so accumulation starts there. Safety tiers (<2, 2–4, 4–5, 5–8, 8–12, 12+ inches) are in `ice_safety_category`; README.md documents the methodology and must stay in sync with code changes.

**Loading data**: with an API key, the sidebar shows a date range picker and `fetch_pws_history` calls `api.weather.com/v2/pws/history/daily` (cached for an hour). The API rejects ranges longer than 31 days, so it fetches in 31-day chunks and uses `imperial.tempAvg` / `imperial.windspeedAvg` from each daily observation. Without a key it falls back to scraping, described next. Scraping is unreliable: Wunderground sometimes serves pages without the data table, especially to cloud hosts like Streamlit Cloud.

**Scraping fallback** (`fetch_weather_underground_data`): builds two weekly table URLs (`{base_url}/table/{date}/{date}/weekly`, for the current and previous week via `get_week_dates`), fetches them with a browser User-Agent, and runs `parse_daily_weather_row` over every `<tr>` in every table. A row counts as data if column 0 is an `M/D/YYYY` date; Temp Avg is read from column 2 and Speed Avg from column 11. These positional indexes break if Wunderground changes its table layout. The page may also be JavaScript-rendered, in which case scraping returns no rows and users fall back to CSV/paste. Returns `(df, error_msg)`.

**Station picker** (`station_selector`): a searchable selectbox that merges favorites from `stations.csv` (tracked despite the `*.csv` gitignore rule) with live search results and a "Custom URL…" fallback, and returns the dashboard base URL. Live search only appears when `st.secrets["weather_underground"]["api_key"]` is set: it geocodes a town or ZIP with Open-Meteo (no key), then calls `api.weather.com/v3/location/near?product=pws` with the key. Locally the key lives in `.streamlit/secrets.toml` (gitignored); on Streamlit Cloud it goes in the app's Secrets settings. Never log request exceptions verbatim, because the URL contains the key.

**Monetization**: `BUY_ME_A_COFFEE_URL`, `ADSENSE_CLIENT` and `ADSENSE_SLOT` are public constants near the top of the file. `render_ad_unit` and `render_footer` run after the tabs.

**UI**: the sidebar holds the station picker, fetch/clear buttons, the alpha slider, baseline calibration, and CSV export. The main area has four tabs: `ice_depth_tab`, `data_entry_tab`, `charts_tab`, and `how_it_works_tab`. `how_it_works_tab` is a user-facing explanation of the method; keep it in sync with `calculate_ice_depth` and README.md. Plotly is optional (`PLOTLY_AVAILABLE`), and charts fall back to native Streamlit charts without it.
