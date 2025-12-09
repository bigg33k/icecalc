# Ice Depth Calculator

A Streamlit web application that calculates ice thickness based on weather data from Weather Underground personal weather stations. The app uses the Stefan's Formula with Accumulated Freezing Degree Days (AFDD) to estimate ice depth and safety conditions.

## Features

- Fetches weather data from Weather Underground personal weather stations
- Calculates ice depth using Stefan's Formula
- Displays ice safety ratings based on calculated thickness
- Interactive charts showing ice depth and temperature trends
- Multiple data entry options: Weather Underground API, CSV upload, or manual entry
- Exports calculation results to CSV

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
streamlit run streamlit_weather_app.py
```

The app will open in your browser with three tabs:
- **Ice Depth Results**: View current ice conditions and safety status
- **Data Entry**: Enter weather data manually, upload CSV, or paste data
- **Charts & Analysis**: Visualize ice depth and temperature trends

## Ice Depth Calculation Methodology

### Core Formula

```
Ice Depth (inches) = α × √(Net AFDD) × Wind Factor
```

Where **α (alpha)** is the ice growth coefficient:
- Clear lake ice: 0.8 - 1.1 (default: 1.0)
- Snow-covered ice: 0.5 - 0.8

### Freezing Degree Days (FDD)

```
FDD = max(0, 32°F - Average Daily Temperature)
```

For each day where the average temperature is below freezing (32°F), the FDD equals the number of degrees below freezing.

### Thawing Degree Days (TDD)

```
TDD = max(0, Average Daily Temperature - 32°F)
```

For each day where the average temperature is above freezing, the TDD equals the number of degrees above freezing.

### Net Accumulated Degree Days

```
Net AFDD = Σ(FDD) - Σ(TDD)
```

The cumulative sum of freezing degree days minus thawing degree days over time.

### Wind Factor

```
Wind Factor = max(0.7, 1 - (Average Wind Speed / 50))
```

Wind slows ice formation by causing water movement beneath the ice:
- 0 mph wind = no reduction (factor = 1.0)
- 15+ mph wind = 30% reduction (factor = 0.7, minimum)

### Ice Safety Categories

| Ice Depth | Safety Rating |
|-----------|---------------|
| < 2 inches | Unsafe - Stay Off |
| 2-4 inches | Caution - Walking Only |
| 4-5 inches | Ice Fishing (Walking) |
| 5-8 inches | Snowmobile/ATV |
| 8-12 inches | Car/Light Truck |
| 12+ inches | Heavy Vehicle |

### Important Caveats

- These calculations provide **estimates only** and should not replace on-site ice assessment
- Ice conditions vary significantly across a body of water
- Factors not accounted for: snow cover, water currents, springs, ice quality
- Always verify ice conditions locally before venturing out

## Configuration

The app is configured by default to fetch data from:
```
https://www.wunderground.com/dashboard/pws/KMESHAPL32
```

You can change the weather station URL in the sidebar of the application.

## Dependencies

- streamlit
- requests
- beautifulsoup4
- pandas
- numpy
- plotly

## License

MIT
