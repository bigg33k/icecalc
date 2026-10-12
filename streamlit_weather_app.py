#!/usr/bin/env python3
"""
Ice Depth Calculator - Streamlit App
Manual weather data entry with ice depth calculations
Includes Weather Underground data scraping
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io
import requests
from bs4 import BeautifulSoup
import re
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import plotly, fall back to basic charts if not available
try:
    import plotly.express as px
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("Plotly not available. Using basic charts.")

# Configure Streamlit page
st.set_page_config(
    page_title="Ice Depth Calculator",
    page_icon="🧊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Get logo path
LOGO_PATH = Path(__file__).parent / "logo.png"

# Monetization
BUY_ME_A_COFFEE_URL = "https://buymeacoffee.com/deadreckoningtech"
ADSENSE_CLIENT = "ca-pub-7801151527639579"
ADSENSE_SLOT = "7826776203"  # "Icecalc" display ad unit

# Initialize session state
if 'weather_data' not in st.session_state:
    st.session_state.weather_data = pd.DataFrame(columns=['date', 'avg_temp_f', 'avg_wind_speed_mph'])
if 'ice_data' not in st.session_state:
    st.session_state.ice_data = pd.DataFrame()
if 'raw_weather_data' not in st.session_state:
    st.session_state.raw_weather_data = pd.DataFrame()
if 'alpha' not in st.session_state:
    st.session_state.alpha = 1.0
if 'baseline_depth' not in st.session_state:
    st.session_state.baseline_depth = 0.0
if 'baseline_date' not in st.session_state:
    st.session_state.baseline_date = None
if 'use_baseline' not in st.session_state:
    st.session_state.use_baseline = False


def recalculate_ice_with_calibration(weather_df, days_per_row=1):
    """Helper to recalculate ice depth using current calibration settings."""
    baseline_date = st.session_state.baseline_date if st.session_state.use_baseline else None
    baseline_depth = st.session_state.baseline_depth if st.session_state.use_baseline else 0.0
    return calculate_ice_depth(
        weather_df,
        days_per_row=days_per_row,
        alpha=st.session_state.alpha,
        baseline_depth=baseline_depth,
        baseline_date=baseline_date
    )


def calculate_ice_depth(df, days_per_row=7, alpha=1.0, baseline_depth=0.0, baseline_date=None):
    """
    Calculate ice depth using a simplified degree-day method
    Based on accumulated freezing degree days (AFDD)

    Args:
        df: DataFrame with date, avg_temp_f, avg_wind_speed_mph columns
        days_per_row: Number of days each row represents (7 for weekly data, 1 for daily)
        alpha: Ice growth coefficient (0.2-1.0). Lower for snow-covered or edge ice.
        baseline_depth: Measured ice depth in inches to calibrate from
        baseline_date: Date of the baseline measurement (calculations start from this point)
    """
    if df.empty or 'avg_temp_f' not in df.columns:
        return df

    # Ensure data is sorted by date
    df_calc = df.copy()
    df_calc['date'] = pd.to_datetime(df_calc['date'])
    df_calc = df_calc.sort_values('date').reset_index(drop=True)

    # If baseline date provided, filter to only include data from that date forward
    if baseline_date is not None:
        baseline_date = pd.to_datetime(baseline_date)
        df_calc = df_calc[df_calc['date'] >= baseline_date].reset_index(drop=True)
        if df_calc.empty:
            return df_calc

    # Calculate freezing degree days (temperatures below 32°F)
    # Multiply by days_per_row to account for weekly averages
    df_calc['freezing_degree_days'] = np.maximum(0, 32 - df_calc['avg_temp_f']) * days_per_row
    df_calc['thawing_degree_days'] = np.maximum(0, df_calc['avg_temp_f'] - 32) * days_per_row

    # Calculate accumulated freezing degree days
    df_calc['accumulated_fdd'] = df_calc['freezing_degree_days'].cumsum()
    df_calc['accumulated_tdd'] = df_calc['thawing_degree_days'].cumsum()

    # Net accumulated degree days (freezing minus thawing)
    df_calc['net_accumulated_dd'] = df_calc['accumulated_fdd'] - df_calc['accumulated_tdd']

    # Wind factor - wind slows ice formation by causing water movement
    # 0 mph = no reduction, 15+ mph = 30% reduction (max)
    wind_factor = np.maximum(0.7, 1 - (df_calc['avg_wind_speed_mph'] / 50))

    # Ice depth calculation using Stefan's formula
    # h = α * sqrt(AFDD) where α is the ice growth coefficient
    # Add baseline_depth to start from a known measured value
    df_calc['ice_depth_inches'] = np.maximum(0,
        baseline_depth + alpha * np.sqrt(np.maximum(0, df_calc['net_accumulated_dd'])) * wind_factor
    )

    # Ice safety categories
    def ice_safety_category(depth):
        if depth < 2:
            return "Unsafe - Stay Off"
        elif depth < 4:
            return "Caution - Walking Only"
        elif depth < 5:
            return "Ice Fishing (Walking)"
        elif depth < 8:
            return "Snowmobile/ATV"
        elif depth < 12:
            return "Car/Light Truck"
        else:
            return "Heavy Vehicle"

    df_calc['ice_safety'] = df_calc['ice_depth_inches'].apply(ice_safety_category)

    return df_calc

def get_week_dates():
    """
    Calculate the end dates for current and previous weeks.
    Weeks end on Sunday.
    Returns (current_week_end, previous_week_end) as date objects.
    """
    today = datetime.now().date()
    # weekday(): Mon=0, Tue=1, Wed=2, Thu=3, Fri=4, Sat=5, Sun=6
    days_until_sunday = (6 - today.weekday()) % 7
    # If today is Sunday, days_until_sunday is 0, which is correct
    current_week_end = today + timedelta(days=days_until_sunday)
    previous_week_end = current_week_end - timedelta(days=7)
    return current_week_end, previous_week_end


def build_weekly_url(base_url, end_date):
    """
    Build the Weather Underground weekly table URL.
    Format: https://www.wunderground.com/dashboard/pws/STATION/table/DATE/DATE/weekly
    """
    date_str = end_date.strftime('%Y-%m-%d')
    return f"{base_url}/table/{date_str}/{date_str}/weekly"


def parse_value(value_str):
    """Extract numeric value from string like '40.1 °F' or '12.0 °mph'"""
    if not value_str or value_str == '--':
        return None
    # Remove degree symbols and units
    match = re.search(r'(-?\d+\.?\d*)', value_str)
    if match:
        return float(match.group(1))
    return None


def parse_daily_weather_row(row):
    """
    Parse a daily data row from Weather Underground table.
    Expected format: Date, Temp High, Temp Avg, Temp Low, Dew High, Dew Avg, Dew Low,
                     Humidity High, Humidity Avg, Humidity Low, Speed High, Speed Avg, Speed Low, ...
    Returns dict with date, avg_temp_f, avg_wind_speed_mph or None if not a valid data row.
    """
    if len(row) < 12:
        return None

    # Check if first column looks like a date (contains /)
    date_str = row[0]
    if '/' not in date_str:
        return None

    # Try to parse the date
    try:
        # Handle format like "12/1/2025"
        date_parts = date_str.split('/')
        if len(date_parts) == 3:
            month, day, year = date_parts
            parsed_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        else:
            return None
    except Exception:
        return None

    # Extract Temp Avg (column 2) and Speed Avg (column 11)
    temp_avg = parse_value(row[2]) if len(row) > 2 else None
    wind_avg = parse_value(row[11]) if len(row) > 11 else None

    if temp_avg is None:
        return None

    return {
        'date': parsed_date,
        'avg_temp_f': temp_avg,
        'avg_wind_speed_mph': wind_avg if wind_avg is not None else 0.0
    }


def fetch_weather_underground_data(base_url):
    """
    Fetch and parse daily weather data from Weather Underground dashboard URL.
    Downloads current week and previous week of data (14 days total).
    Returns a DataFrame with daily data.
    """
    current_week_end, previous_week_end = get_week_dates()

    urls = [
        ("Previous Week", build_weekly_url(base_url, previous_week_end)),
        ("Current Week", build_weekly_url(base_url, current_week_end)),
    ]

    all_daily_data = []
    errors = []

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    for week_name, url in urls:
        logger.info(f"Fetching {week_name}: {url}")
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for all tables
            tables = soup.find_all('table')
            logger.info(f"{week_name}: Found {len(tables)} tables")

            if not tables:
                errors.append(f"{week_name}: No tables found")
                continue

            week_data_found = False

            # Process all tables to find daily data
            for table_idx, table in enumerate(tables):
                all_rows = []
                for row in table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    if cells:
                        row_data = [cell.text.strip() for cell in cells]
                        all_rows.append(row_data)

                # Log first few rows for debugging
                if all_rows:
                    logger.info(f"{week_name} table {table_idx} rows: {len(all_rows)}, first row: {all_rows[0][:5] if all_rows[0] else 'empty'}")

                # Try to parse each row as daily data
                for row in all_rows:
                    daily_data = parse_daily_weather_row(row)
                    if daily_data:
                        all_daily_data.append(daily_data)
                        week_data_found = True
                        logger.info(f"  Parsed: {daily_data['date']} - {daily_data['avg_temp_f']}°F, {daily_data['avg_wind_speed_mph']} mph")

            if not week_data_found:
                errors.append(f"{week_name}: No daily data rows found (table may be JavaScript-rendered)")

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for {week_name}: {e}")
            errors.append(f"{week_name}: {e}")
        except Exception as e:
            logger.error(f"Error fetching {week_name}: {e}")
            errors.append(f"{week_name}: {e}")

    if not all_daily_data:
        error_msg = "No daily data retrieved. Weather Underground may require JavaScript to render the table. "
        error_msg += "; ".join(errors) if errors else ""
        return None, error_msg

    # Create DataFrame and remove duplicates
    df = pd.DataFrame(all_daily_data)
    df = df.drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)

    logger.info(f"Total daily records: {len(df)}")

    error_msg = "; ".join(errors) if errors else None
    return df, error_msg

def parse_pasted_data(text_data):
    """Parse pasted CSV-like data"""
    try:
        # Try to read as CSV from string
        df = pd.read_csv(io.StringIO(text_data))
        
        # Clean column names
        df.columns = df.columns.str.strip().str.lower()
        
        # Try to map common column name variations
        column_mapping = {
            'date': ['date', 'day', 'time', 'timestamp'],
            'avg_temp_f': ['avg_temp_f', 'temperature', 'temp', 'avg_temp', 'temp_f', 'temperature_f'],
            'avg_wind_speed_mph': ['avg_wind_speed_mph', 'wind', 'wind_speed', 'windspeed', 'wind_mph']
        }
        
        for target_col, possible_names in column_mapping.items():
            for possible_name in possible_names:
                if possible_name in df.columns:
                    df = df.rename(columns={possible_name: target_col})
                    break
        
        # Keep only the columns we need
        required_cols = ['date', 'avg_temp_f', 'avg_wind_speed_mph']
        available_cols = [col for col in required_cols if col in df.columns]
        
        if 'date' not in available_cols:
            st.error("No date column found. Please include a date column.")
            return None
            
        df = df[available_cols]
        
        # Convert date column
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        
        return df
        
    except Exception as e:
        st.error(f"Error parsing data: {e}")
        return None

def main():
    """Main Streamlit app"""

    # Header
    st.title("Ice Depth Calculator")
    st.markdown("**Enter weather data to calculate ice formation and safety conditions**")

    # Sidebar controls
    with st.sidebar:
        # Logo at top of sidebar
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=100)
            st.divider()
        st.header("🎛️ Controls")

        # Weather Underground URL input
        st.subheader("Weather Underground")
        wu_base_url = st.text_input(
            "Station Base URL:",
            value="https://www.wunderground.com/dashboard/pws/KMESHAPL32",
            help="Enter the Weather Underground personal weather station base URL (without /table/...)"
        )

        # Show which weeks will be fetched
        current_week_end, previous_week_end = get_week_dates()
        st.caption(f"Will fetch: {previous_week_end.strftime('%b %d')} - {current_week_end.strftime('%b %d, %Y')}")

        if st.button("📥 Load Data", type="primary"):
            with st.spinner("Fetching weather data for current and previous week..."):
                raw_df, error = fetch_weather_underground_data(wu_base_url)
                if error and raw_df is None:
                    st.error(error)
                elif raw_df is not None:
                    if error:
                        st.warning(f"Partial data loaded: {error}")
                    st.success(f"Loaded {len(raw_df)} day(s) of data from Weather Underground")
                    st.session_state.raw_weather_data = raw_df

                    # Data is already in correct format (date, avg_temp_f, avg_wind_speed_mph)
                    weather_df = raw_df.copy()
                    weather_df['avg_wind_speed_mph'] = weather_df['avg_wind_speed_mph'].fillna(0)

                    st.session_state.weather_data = weather_df
                    st.session_state.ice_data = recalculate_ice_with_calibration(weather_df)

                    # Show preview
                    with st.expander("Preview loaded data"):
                        st.dataframe(raw_df)
                else:
                    st.warning("No data retrieved")
        
        if st.button("🗑️ Clear All Data", type="secondary"):
            st.session_state.weather_data = pd.DataFrame(columns=['date', 'avg_temp_f', 'avg_wind_speed_mph'])
            st.session_state.ice_data = pd.DataFrame()
            st.session_state.raw_weather_data = pd.DataFrame()
            st.success("Data cleared!")

        st.divider()

        # Calibration controls
        st.subheader("Calibration")

        st.session_state.alpha = st.slider(
            "Ice Growth Coefficient (α)",
            min_value=0.2,
            max_value=1.2,
            value=st.session_state.alpha,
            step=0.05,
            help="Lower values for snow-covered ice (0.5-0.8), edge measurements, or sheltered areas. Higher for clear lake ice (0.8-1.1)."
        )

        st.session_state.use_baseline = st.checkbox(
            "Use measured baseline",
            value=st.session_state.use_baseline,
            help="Start calculations from a known measured ice depth"
        )

        if st.session_state.use_baseline:
            st.session_state.baseline_depth = st.number_input(
                "Measured Ice Depth (inches)",
                min_value=0.0,
                max_value=48.0,
                value=st.session_state.baseline_depth,
                step=0.5,
                help="Enter your measured ice thickness"
            )

            # Get available dates from weather data
            if not st.session_state.weather_data.empty:
                dates = pd.to_datetime(st.session_state.weather_data['date']).dt.date.tolist()
                default_idx = len(dates) - 1 if dates else 0
                st.session_state.baseline_date = st.selectbox(
                    "Measurement Date",
                    options=dates,
                    index=default_idx,
                    help="Select the date when you measured the ice"
                )
            else:
                st.session_state.baseline_date = st.date_input(
                    "Measurement Date",
                    value=datetime.now().date(),
                    help="Select the date when you measured the ice"
                )

        if st.button("🔄 Recalculate", type="secondary"):
            if not st.session_state.weather_data.empty:
                st.session_state.ice_data = recalculate_ice_with_calibration(st.session_state.weather_data)
                st.success("Recalculated!")

        st.divider()
        
        # Download options
        if not st.session_state.ice_data.empty:
            st.subheader("📥 Download Data")
            
            csv_data = st.session_state.ice_data.to_csv(index=False)
            st.download_button(
                label="Download Results as CSV",
                data=csv_data,
                file_name=f"ice_depth_calculation_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["🧊 Ice Depth Results", "📝 Data Entry", "📊 Charts & Analysis"])
    
    with tab1:
        ice_depth_tab()
    
    with tab2:
        data_entry_tab()
    
    with tab3:
        charts_tab()

    render_ad_unit()
    render_footer()

def render_ad_unit():
    """Render a Google AdSense display ad unit, once an ad slot ID is set"""
    if ADSENSE_SLOT is None:
        return
    components.html(
        f"""
        <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={ADSENSE_CLIENT}"
             crossorigin="anonymous"></script>
        <ins class="adsbygoogle"
             style="display:block"
             data-ad-client="{ADSENSE_CLIENT}"
             data-ad-slot="{ADSENSE_SLOT}"
             data-ad-format="auto"
             data-full-width-responsive="true"></ins>
        <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
        """,
        height=120,
    )

def render_footer():
    """Footer credit and Buy Me a Coffee link"""
    st.divider()
    st.markdown(
        f"<div style='text-align: center;'>"
        f"<a href='{BUY_ME_A_COFFEE_URL}' target='_blank'>"
        f"☕ Find this useful? Buy me a coffee</a></div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div style='text-align: center; color: gray;'>Brought to you by Dead Reckoning Tech</div>",
        unsafe_allow_html=True,
    )

def ice_depth_tab():
    """Ice depth results and safety information"""
    st.header("🧊 Ice Depth Calculation Results")
    
    if st.session_state.ice_data.empty:
        st.info("🔄 No data available. Please enter weather data in the 'Data Entry' tab.")
        return
    
    df = st.session_state.ice_data
    
    # Current ice conditions (latest date)
    latest = df.iloc[-1]
    
    st.subheader("📊 Current Ice Conditions")
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="🧊 Ice Depth",
            value=f"{latest['ice_depth_inches']:.1f} inches"
        )

    with col2:
        st.metric(
            label="🌡️ Latest Temp",
            value=f"{latest['avg_temp_f']:.1f}°F"
        )

    with col3:
        st.metric(
            label="💨 Latest Wind",
            value=f"{latest['avg_wind_speed_mph']:.1f} mph"
        )
    
    # Safety status
    st.subheader("⚠️ Ice Safety Status")
    safety_status = latest['ice_safety']
    
    # Color code safety status
    if "Unsafe" in safety_status:
        st.error(f"🚫 **{safety_status}**")
    elif "Caution" in safety_status:
        st.warning(f"⚠️ **{safety_status}**")
    elif "Walking" in safety_status:
        st.success(f"🚶 **{safety_status}**")
    else:
        st.success(f"✅ **{safety_status}**")
    
    # Ice safety guidelines
    with st.expander("📋 Ice Safety Guidelines", expanded=False):
        st.markdown("""
        **General Ice Safety Guidelines:**
        - **< 2 inches**: Stay off the ice completely
        - **2-4 inches**: Cautious walking only
        - **4-5 inches**: Ice fishing (walking)
        - **5-8 inches**: Snowmobile or ATV
        - **8-12 inches**: Car or light truck
        - **12+ inches**: Heavy vehicles
        
        **⚠️ Important Notes:**
        - These are general guidelines for clear, solid ice
        - Ice conditions can vary significantly across a body of water
        - Always check ice conditions locally before venturing out
        - Consider professional ice assessment for critical decisions
        - Wind, snow cover, and water currents affect ice formation
        """)
    
    # Detailed results table
    st.subheader("📋 Detailed Results")

    # Format the display dataframe
    display_df = df[['date', 'avg_temp_f', 'avg_wind_speed_mph', 'ice_depth_inches', 'ice_safety']].copy()
    # Convert date to mm/dd/yy format
    display_df['date'] = pd.to_datetime(display_df['date']).dt.strftime('%m/%d/%y')
    display_df.columns = ['Date', 'Avg Temp (°F)', 'Avg Wind (mph)', 'Ice Depth (in)', 'Safety Status']
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            'Date': st.column_config.TextColumn('Date'),
            'Avg Temp (°F)': st.column_config.NumberColumn('Avg Temp (°F)', format="%.1f"),
            'Avg Wind (mph)': st.column_config.NumberColumn('Avg Wind (mph)', format="%.1f"),
            'Ice Depth (in)': st.column_config.NumberColumn('Ice Depth (in)', format="%.1f"),
            'Safety Status': st.column_config.TextColumn('Safety Status')
        }
    )

def data_entry_tab():
    """Data entry interface"""
    st.header("📝 Weather Data Entry")
    
    # Method selection
    entry_method = st.radio(
        "Choose data entry method:",
        ["📄 Paste CSV Data", "➕ Manual Entry", "📁 Upload CSV File"],
        horizontal=True
    )
    
    if entry_method == "📄 Paste CSV Data":
        st.subheader("Paste CSV Data")
        st.markdown("Paste your data in CSV format. Required columns: **date**, **avg_temp_f**, **avg_wind_speed_mph**")
        
        # Example format
        with st.expander("📖 Example Format", expanded=False):
            st.code("""
date,avg_temp_f,avg_wind_speed_mph
2024-12-01,28.5,12.3
2024-12-02,25.1,8.7
2024-12-03,22.8,15.2
            """)
        
        pasted_data = st.text_area(
            "Paste your CSV data here:",
            height=200,
            placeholder="date,avg_temp_f,avg_wind_speed_mph\n2024-12-01,28.5,12.3\n2024-12-02,25.1,8.7"
        )
        
        if st.button("📊 Process Pasted Data") and pasted_data.strip():
            parsed_df = parse_pasted_data(pasted_data)
            if parsed_df is not None:
                st.session_state.weather_data = parsed_df
                st.session_state.ice_data = recalculate_ice_with_calibration(st.session_state.weather_data)
                st.success(f"Successfully processed {len(parsed_df)} rows of data!")
                st.dataframe(parsed_df, use_container_width=True)
    
    elif entry_method == "📁 Upload CSV File":
        st.subheader("Upload CSV File")
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
                st.write("Preview of uploaded data:")
                st.dataframe(df.head(), use_container_width=True)
                
                if st.button("📊 Process Uploaded Data"):
                    # Convert to string format for parsing
                    csv_string = df.to_csv(index=False)
                    parsed_df = parse_pasted_data(csv_string)
                    if parsed_df is not None:
                        st.session_state.weather_data = parsed_df
                        st.session_state.ice_data = recalculate_ice_with_calibration(st.session_state.weather_data)
                        st.success(f"Successfully processed {len(parsed_df)} rows of data!")
            except Exception as e:
                st.error(f"Error reading file: {e}")
    
    elif entry_method == "➕ Manual Entry":
        st.subheader("Manual Data Entry")
        
        with st.form("manual_entry_form"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                entry_date = st.date_input("Date", value=datetime.now().date())
            
            with col2:
                avg_temp = st.number_input("Average Temperature (°F)", value=32.0, step=0.1)
            
            with col3:
                avg_wind = st.number_input("Average Wind Speed (mph)", value=5.0, min_value=0.0, step=0.1)
            
            submitted = st.form_submit_button("➕ Add Entry")
            
            if submitted:
                new_entry = pd.DataFrame({
                    'date': [entry_date.strftime('%Y-%m-%d')],
                    'avg_temp_f': [avg_temp],
                    'avg_wind_speed_mph': [avg_wind]
                })
                
                if st.session_state.weather_data.empty:
                    st.session_state.weather_data = new_entry
                else:
                    st.session_state.weather_data = pd.concat([st.session_state.weather_data, new_entry], ignore_index=True)

                st.session_state.ice_data = recalculate_ice_with_calibration(st.session_state.weather_data)
                st.success("Entry added successfully!")
    
    # Show current data
    if not st.session_state.weather_data.empty:
        st.subheader("📋 Current Weather Data")
        st.dataframe(st.session_state.weather_data, use_container_width=True, hide_index=True)

        if st.button("🔄 Recalculate Ice Depth"):
            st.session_state.ice_data = recalculate_ice_with_calibration(st.session_state.weather_data)
            st.success("Ice depth recalculated!")

def charts_tab():
    """Charts and analysis"""
    st.header("📊 Charts & Analysis")

    if st.session_state.ice_data.empty:
        st.info("No data available for charts. Please enter data first.")
        return

    df = st.session_state.ice_data
    df['date'] = pd.to_datetime(df['date'])

    # Calculation methodology section
    with st.expander("📐 Calculation Methodology", expanded=False):
        st.markdown("""
        ### Ice Depth Calculation Method

        This application uses **Stefan's Formula** combined with the **Accumulated Freezing Degree Days (AFDD)** method to estimate ice thickness.

        #### Core Formula

        ```
        Ice Depth (inches) = α × √(Net AFDD) × Wind Factor
        ```

        Where:
        - **α (alpha)** = Ice growth coefficient (default: 1.0 inches per √degree-day)
          - Clear lake ice: 0.8 - 1.1
          - Snow-covered ice: 0.5 - 0.8

        #### Freezing Degree Days (FDD)

        ```
        FDD = max(0, 32°F - Average Daily Temperature)
        ```

        For each day where the average temperature is below freezing (32°F), the FDD equals the number of degrees below freezing.

        #### Thawing Degree Days (TDD)

        ```
        TDD = max(0, Average Daily Temperature - 32°F)
        ```

        For each day where the average temperature is above freezing, the TDD equals the number of degrees above freezing.

        #### Net Accumulated Degree Days

        ```
        Net AFDD = Σ(FDD) - Σ(TDD)
        ```

        The cumulative sum of freezing degree days minus thawing degree days over time.

        #### Wind Factor

        ```
        Wind Factor = max(0.7, 1 - (Average Wind Speed / 50))
        ```

        Wind slows ice formation by causing water movement beneath the ice:
        - 0 mph wind = no reduction (factor = 1.0)
        - 15 mph wind = 30% reduction (factor = 0.7, minimum)

        #### Ice Safety Categories

        | Ice Depth | Safety Rating |
        |-----------|---------------|
        | < 2 inches | Unsafe - Stay Off |
        | 2-4 inches | Caution - Walking Only |
        | 4-5 inches | Ice Fishing (Walking) |
        | 5-8 inches | Snowmobile/ATV |
        | 8-12 inches | Car/Light Truck |
        | 12+ inches | Heavy Vehicle |

        #### Important Caveats

        - These calculations provide **estimates only** and should not replace on-site ice assessment
        - Ice conditions vary significantly across a body of water
        - Factors not accounted for: snow cover, water currents, springs, ice quality
        - Always verify ice conditions locally before venturing out
        """)
    
    # Ice depth chart
    if PLOTLY_AVAILABLE:
        fig1 = px.line(df, x='date', y='ice_depth_inches', 
                      title='Ice Depth Over Time',
                      labels={'ice_depth_inches': 'Ice Depth (inches)', 'date': 'Date'})
        fig1.update_traces(line=dict(color='#4fc3f7', width=3))
        st.plotly_chart(fig1, use_container_width=True)
    else:
        st.subheader("🧊 Ice Depth Over Time")
        chart_data = df.set_index('date')[['ice_depth_inches']]
        st.line_chart(chart_data)
    
    # Temperature chart
    if PLOTLY_AVAILABLE:
        fig2 = px.line(df, x='date', y='avg_temp_f',
                      title='Average Temperature Over Time',
                      labels={'avg_temp_f': 'Temperature (°F)', 'date': 'Date'})
        fig2.add_hline(y=32, line_dash="dash", line_color="red", 
                      annotation_text="Freezing Point (32°F)")
        fig2.update_traces(line=dict(color='#ff6b6b', width=3))
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.subheader("🌡️ Temperature Over Time")
        chart_data = df.set_index('date')[['avg_temp_f']]
        st.line_chart(chart_data)
    
    # Combined chart
    if PLOTLY_AVAILABLE:
        fig3 = make_subplots(specs=[[{"secondary_y": True}]])
        
        fig3.add_trace(
            go.Scatter(x=df['date'], y=df['ice_depth_inches'], name="Ice Depth",
                      line=dict(color='#4fc3f7', width=3)),
            secondary_y=False,
        )
        
        fig3.add_trace(
            go.Scatter(x=df['date'], y=df['avg_temp_f'], name="Temperature",
                      line=dict(color='#ff6b6b', width=2)),
            secondary_y=True,
        )
        
        fig3.update_yaxes(title_text="Ice Depth (inches)", secondary_y=False)
        fig3.update_yaxes(title_text="Temperature (°F)", secondary_y=True)
        fig3.update_layout(title_text="Ice Depth vs Temperature")
        
        st.plotly_chart(fig3, use_container_width=True)
    
    # Statistics
    st.subheader("📈 Statistics Summary")
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Ice Depth Statistics:**")
        ice_stats = df['ice_depth_inches'].describe()
        st.dataframe(ice_stats, use_container_width=True)
    
    with col2:
        st.write("**Temperature Statistics:**")
        temp_stats = df['avg_temp_f'].describe()
        st.dataframe(temp_stats, use_container_width=True)

if __name__ == "__main__":
    main()
