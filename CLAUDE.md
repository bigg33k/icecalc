# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Streamlit-based weather data scraping application that downloads the summary table from a Wunderground personal weather station dashboard. The app scrapes the HTML table from the main dashboard page and exports it as a CSV file.

## Setup and Dependencies

The project requires the following Python packages:
- streamlit
- requests
- beautifulsoup4
- pandas

To install dependencies:
```bash
pip install streamlit requests beautifulsoup4 pandas
```

## Running the Application

```bash
streamlit run ice.py
```

## Code Structure

- `ice.py`: Main application file containing the Streamlit interface and web scraping logic
  - Uses BeautifulSoup to parse HTML and extract the summary table from Wunderground dashboard
  - Exports scraped data as a CSV file named `weather_summary.csv`

## Key Functionality

The app fetches weather data from the main dashboard URL:
`https://www.wunderground.com/dashboard/pws/KMESHAPL32`

It extracts the summary table from the page and converts it to a pandas DataFrame for CSV export.