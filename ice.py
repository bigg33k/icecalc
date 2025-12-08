import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import date

# Streamlit app
st.title("Weather Data Downloader")

# Wunderground URL - main dashboard page
url = "https://www.wunderground.com/dashboard/pws/KMESHAPL32"

st.write(f"Fetching data from: {url}")

# Button to scrape data
if st.button("Load Data"):
    try:
        # Send a request to the webpage
        response = requests.get(url)
        response.raise_for_status()

        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')

        # Locate the table in the webpage - look for summary table
        tables = soup.find_all('table')
        
        if tables:
            all_dfs = []
            
            # Process each table
            for i, table in enumerate(tables):
                st.write(f"\n**Processing Table {i+1}:**")
                
                # Extract all rows first
                all_rows = []
                for row in table.find_all('tr'):
                    # Get all cells (both td and th)
                    cells = row.find_all(['td', 'th'])
                    if cells:
                        row_data = [cell.text.strip() for cell in cells]
                        all_rows.append(row_data)
                
                if not all_rows:
                    continue
                
                # The first row is likely headers
                headers = all_rows[0] if all_rows else []
                data_rows = all_rows[1:] if len(all_rows) > 1 else []
                
                st.write(f"Headers: {headers}")
                st.write(f"Number of data rows: {len(data_rows)}")
                
                # Create a cleaned dataset
                cleaned_data = []
                for row in data_rows:
                    # Skip rows that are sub-headers (like the repeated header rows)
                    if row == headers or row == ['', 'High', 'Low', 'Average']:
                        continue
                    # Only keep rows with actual data
                    if any(cell and cell not in ['', 'High', 'Low', 'Average'] for cell in row):
                        # Pad row with empty strings if it's shorter than headers
                        while len(row) < len(headers):
                            row.append('')
                        # Trim row if it's longer than headers
                        row = row[:len(headers)]
                        cleaned_data.append(row)
                
                if cleaned_data:
                    try:
                        df = pd.DataFrame(cleaned_data, columns=headers)
                        st.write(f"Successfully created DataFrame with shape: {df.shape}")
                        st.dataframe(df)  # Show the dataframe in Streamlit
                        all_dfs.append(df)
                    except Exception as e:
                        st.write(f"Could not create DataFrame: {e}")
            
            # Combine all dataframes if multiple tables found
            if all_dfs:
                if len(all_dfs) > 1:
                    # Combine multiple tables horizontally or vertically as needed
                    st.write("\n**Combining all tables...**")
                    df = pd.concat(all_dfs, axis=0, ignore_index=True)
                else:
                    df = all_dfs[0]
                
                st.write(f"\n**Final combined data shape:** {df.shape}")
            else:
                df = None
            
            if df is not None and not df.empty:
                # Save to CSV
                csv_filename = "weather_summary.csv"
                df.to_csv(csv_filename, index=False)

                st.success(f"Data successfully saved to {csv_filename}")

                # Provide download link
                st.download_button(
                    label="Download CSV",
                    data=df.to_csv(index=False).encode('utf-8'),
                    file_name=csv_filename,
                    mime='text/csv'
                )
            else:
                st.error("No valid data found to save")
        else:
            st.error("No table found on the webpage. Please check the URL or the structure of the page.")
    except Exception as e:
        st.error(f"An error occurred: {e}")

