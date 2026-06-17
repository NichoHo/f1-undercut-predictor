import pandas as pd
import os

def rebuild_summaries():
    # Make sure this matches the filename you used for your newly merged dataset!
    # If you kept it as f1_2022_2024.csv, change the name here.
    main_dataset_path = 'f1_data/f1_2023_2025.csv' 
    
    if not os.path.exists(main_dataset_path):
        print(f"❌ Could not find {main_dataset_path}. Please check your filename.")
        return

    print("Loading main telemetry dataset...")
    df = pd.read_csv(main_dataset_path, low_memory=False)

    # ---------------------------------------------------------
    # 1. REBUILD PIT LAPS SUMMARY
    # ---------------------------------------------------------
    print("Extracting pit stop laps...")
    # Find every row where a pit stop occurred
    pit_data = df[df['PitOutTime'].notna()]
    
    # Extract just the Year, Round, and Lap Number, remove duplicates, and sort
    pit_summary = pit_data[['Year', 'RoundNumber', 'LapNumber']].drop_duplicates()
    pit_summary = pit_summary.sort_values(by=['Year', 'RoundNumber', 'LapNumber'])
    
    pit_summary.to_csv('f1_data/pit_laps_summary.csv', index=False)
    print(f"✅ pit_laps_summary.csv updated! ({len(pit_summary)} unique pit laps found)")

    # ---------------------------------------------------------
    # 2. REBUILD DRIVERS SUMMARY (For the 2025 Rookies)
    # ---------------------------------------------------------
    print("Extracting driver rosters...")
    # We also need to update this so the UI knows about any new 2025 rookies
    drivers_summary = df[['Year', 'RoundNumber', 'Driver']].drop_duplicates()
    drivers_summary = drivers_summary.sort_values(by=['Year', 'RoundNumber', 'Driver'])
    
    drivers_summary.to_csv('f1_data/drivers_summary.csv', index=False)
    print(f"✅ drivers_summary.csv updated!")

if __name__ == '__main__':
    rebuild_summaries()