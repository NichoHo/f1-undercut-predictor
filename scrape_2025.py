import fastf1
import pandas as pd
import os
import warnings

warnings.simplefilter(action='ignore', category=FutureWarning)

def scrape_2025_season():
    cache_dir = 'f1_cache'
    os.makedirs(cache_dir, exist_ok=True)
    fastf1.Cache.enable_cache(cache_dir)
    
    print("🚀 Starting FastF1 Extraction for the 2025 Season...")
    all_laps = []
    
    # 2025 had 24 rounds
    for round_num in range(1, 25):
        try:
            print(f"Fetching 2025 Round {round_num}...")
            session = fastf1.get_session(2025, round_num, 'R')
            session.load(telemetry=False, weather=False, messages=False)
            
            laps = session.laps
            if laps.empty:
                print(f"⚠ No lap data found for Round {round_num}. Skipping.")
                continue
                
            df = pd.DataFrame({
                'Year': 2025,
                'RoundNumber': round_num,
                'LapNumber': laps['LapNumber'],
                'Driver': laps['Driver'],
                'Position': laps['Position'],
                'Team': laps['Team'],
                'Compound': laps['Compound'],
                'Time': laps['Time'].dt.total_seconds(),
                'LapTime': laps['LapTime'].dt.total_seconds(),
                'TyreLife': laps['TyreLife'],
                'PitOutTime': laps['PitOutTime'].dt.total_seconds()
            })
            
            df['PitStopDuration'] = laps['PitOutTime'].dt.total_seconds() - laps['PitInTime'].dt.total_seconds()
            all_laps.append(df)
            print(f"✅ Round {round_num} complete.")
            
        except Exception as e:
            print(f"❌ Failed to extract Round {round_num}: {e}")

    if all_laps:
        print("\n💾 Merging 2025 data...")
        new_2025_df = pd.concat(all_laps, ignore_index=True)
        
        # Load your existing 2023-2024 dataset
        existing_csv_path = 'f1_data/f1_2022_2024.csv' 
        old_df = pd.read_csv(existing_csv_path)
        
        # Merge them and save!
        combined_df = pd.concat([new_2025_df, old_df], ignore_index=True)
        
        # Optionally rename your file to reflect the new era
        combined_df.to_csv('f1_data/f1_2023_2025.csv', index=False)
        print("🎉 Success! 2025 data merged into your main dataset.")

if __name__ == '__main__':
    scrape_2025_season()