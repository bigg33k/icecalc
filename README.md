# Weather Data Downloader

A Streamlit web application that scrapes weather summary data from a Weather Underground personal weather station dashboard and exports it as a CSV file.

## Features

- Fetches weather data from a Weather Underground personal weather station
- Parses HTML tables from the dashboard page
- Displays extracted data in an interactive table
- Exports data to CSV format with a download button

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd icecalc
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the Streamlit app:
```bash
streamlit run ice.py
```

The app will open in your browser. Click the "Load Data" button to fetch and display weather data from the configured weather station.

## Configuration

The app is currently configured to fetch data from:
```
https://www.wunderground.com/dashboard/pws/KMESHAPL32
```

To use a different weather station, modify the `url` variable in `ice.py`.

## Dependencies

- streamlit
- requests
- beautifulsoup4
- pandas
- numpy
- plotly

## License

MIT
