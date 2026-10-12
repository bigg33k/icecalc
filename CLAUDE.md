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

**Scraping** (`fetch_weather_underground_data`): builds two weekly table URLs (`{base_url}/table/{date}/{date}/weekly`, for the current and previous week via `get_week_dates`), fetches them with a browser User-Agent, and runs `parse_daily_weather_row` over every `<tr>` in every table. A row counts as data if column 0 is an `M/D/YYYY` date; Temp Avg is read from column 2 and Speed Avg from column 11. These positional indexes break if Wunderground changes its table layout. The page may also be JavaScript-rendered, in which case scraping returns no rows and users fall back to CSV/paste. Returns `(df, error_msg)`.

**UI**: the sidebar holds the station URL (default `https://www.wunderground.com/dashboard/pws/KMESHAPL32`), fetch/clear buttons, the alpha slider, baseline calibration, and CSV export. The main area has three tabs: `ice_depth_tab`, `data_entry_tab`, and a charts tab. Plotly is optional (`PLOTLY_AVAILABLE`), and charts fall back to native Streamlit charts without it.
