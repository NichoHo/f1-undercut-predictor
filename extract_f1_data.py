# extract_f1_data.py
import fastf1
import pandas as pd
import numpy as np
import os
from datetime import timedelta
import warnings

warnings.filterwarnings("ignore")

def extract_all_data():
    """Extract F1 data from 2022-2024 and save to CSV files"""
    
    # Create data directory
    if not os.path.exists('f1_data'):
        os.makedirs('f1_data')
    
    # Enable cache
    fastf1.Cache.enable_cache('cache', ignore_version=True)
    
    all_data = []
    
    for year in [2022, 2023, 2024]:
        print(f"Extracting data for {year}...")
        
        try:
            # Get schedule
            schedule = fastf1.get_event_schedule(year)
            races = schedule[schedule['RoundNumber'] > 0]
            
            for _, event in races.iterrows():
                round_num = int(event['RoundNumber'])
                event_name = event['EventName']
                
                print(f"  Round {round_num}: {event_name}")
                
                try:
                    # Load race session
                    session = fastf1.get_session(year, round_num, 'R')
                    session.load(telemetry=False, weather=False, messages=False, laps=True)
                    
                    # Get laps data
                    laps = session.laps
                    
                    # Add event info to each lap
                    laps['Year'] = year
                    laps['RoundNumber'] = round_num
                    laps['EventName'] = event_name
                    
                    # Convert timedelta columns to seconds
                    time_cols = ['Time', 'LapTime', 'PitOutTime', 'PitInTime', 'Sector1Time', 
                                'Sector2Time', 'Sector3Time', 'Sector1SessionTime', 
                                'Sector2SessionTime', 'Sector3SessionTime']
                    
                    for col in time_cols:
                        if col in laps.columns:
                            laps[col] = laps[col].dt.total_seconds()
                    
                    # Handle PitStopDuration
                    if 'PitStopDuration' in laps.columns:
                        laps['PitStopDuration'] = laps['PitStopDuration'].dt.total_seconds()
                    
                    all_data.append(laps)
                    
                except Exception as e:
                    print(f"    Error loading race {round_num}: {e}")
                    continue
        
        except Exception as e:
            print(f"Error processing year {year}: {e}")
            continue
    
    # Combine all data
    if all_data:
        combined_data = pd.concat(all_data, ignore_index=True)
        
        # Save to CSV
        csv_path = 'f1_data/f1_2022_2024.csv'
        combined_data.to_csv(csv_path, index=False)
        print(f"\n✅ Data saved to {csv_path}")
        print(f"Total records: {len(combined_data)}")
        
        # Also save year-by-year files
        for year in [2022, 2023, 2024]:
            year_data = combined_data[combined_data['Year'] == year]
            if not year_data.empty:
                year_data.to_csv(f'f1_data/f1_{year}.csv', index=False)
                print(f"  {year}: {len(year_data)} records")
        
        return combined_data
    else:
        print("No data extracted")
        return None

def create_summary_files(full_data):
    """Create summary CSV files for easier querying"""
    
    # Create events summary
    events = full_data[['Year', 'RoundNumber', 'EventName']].drop_duplicates()
    events = events.sort_values(['Year', 'RoundNumber'])
    events.to_csv('f1_data/events_summary.csv', index=False)
    
    # Create pit laps summary
    pit_laps = full_data[full_data['PitOutTime'].notna()][['Year', 'RoundNumber', 'LapNumber']].drop_duplicates()
    pit_laps = pit_laps.sort_values(['Year', 'RoundNumber', 'LapNumber'])
    pit_laps.to_csv('f1_data/pit_laps_summary.csv', index=False)
    
    # Create drivers summary
    drivers = full_data[['Year', 'RoundNumber', 'Driver', 'Team']].drop_duplicates()
    drivers.to_csv('f1_data/drivers_summary.csv', index=False)
    
    print("\n✅ Summary files created in f1_data/ directory")

if __name__ == '__main__':
    print("Extracting F1 data from 2022-2024...")
    print("This may take several minutes...")
    data = extract_all_data()
    
    if data is not None:
        create_summary_files(data)
        print("\n✅ Data extraction complete!")
    else:
        print("\n❌ Data extraction failed")