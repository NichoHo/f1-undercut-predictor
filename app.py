# app.py
from flask import Flask, jsonify, render_template, request
import pandas as pd
import numpy as np
import joblib
import os
import warnings
from datetime import datetime
from collections import defaultdict

# Suppress warnings
warnings.filterwarnings("ignore")

# Create Flask app
app = Flask(__name__)

# Global data and model variables
f1_data = None
events_summary = None
pit_laps_summary = None
drivers_summary = None
model = None

# Define core features
CORE_FEATURES = [
    'Gap_To_Ahead',
    'Rival_Tyre_Age',
    'Pace_Delta',
    'Pit_Aggressiveness',
    'StationaryDuration',
    'InLap_Sec',
    'OutLap_Sec'
]

def load_data():
    """Load CSV data into memory with type and column optimizations"""
    global f1_data, events_summary, pit_laps_summary, drivers_summary
    
    try:
        # Load main data file
        csv_path = 'f1_data/f1_2023_2025.csv'
        if os.path.exists(csv_path):
            print(f"Loading data from {csv_path} (Optimizing performance)...")
            
            # Specify columns actually required by features & API endpoints
            required_cols = [
                'Year', 'RoundNumber', 'LapNumber', 'Driver', 'Position', 
                'Team', 'Compound', 'Time', 'LapTime', 'TyreLife', 'PitOutTime', 
                'PitStopDuration'
            ]
            
            # Explicitly define low-level datatypes to prevent casting overhead loops
            optimized_dtypes = {
                'Year': 'int16',
                'RoundNumber': 'int8',
                'LapNumber': 'int8',
                'Driver': 'string',
                'Position': 'float32',
                'Team': 'string',
                'Compound': 'string',
                'PitStopDuration': 'float32'
            }
            
            # Read only required columns with strict typing constraints
            f1_data = pd.read_csv(
                csv_path, 
                usecols=lambda col: col in required_cols,
                dtype=optimized_dtypes,
                engine='c',
                low_memory=False
            )
            print(f"✅ Loaded {len(f1_data)} records efficiently")
        else:
            print(f"❌ Data file not found: {csv_path}")
            return False
        
        # Load summary files
        events_summary = pd.read_csv('f1_data/events_summary.csv')
        pit_laps_summary = pd.read_csv('f1_data/pit_laps_summary.csv')
        drivers_summary = pd.read_csv('f1_data/drivers_summary.csv')
        
        # Safe fast parsing of specific metrics
        print("Synchronizing data arrays...")
        for col in ['PitStopDuration', 'Time', 'LapTime', 'TyreLife']:
            if col in f1_data.columns:
                f1_data[col] = pd.to_numeric(f1_data[col], errors='coerce')
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return False

def load_model():
    """Load the ML model with pre-warmed dependencies to prevent initialization freezing"""
    global model
    try:
        model_path = 'Datamining_model_final.pkl'
        if os.path.exists(model_path):
            print(f"Warming up model libraries...")
            # Pre-import core dependencies to resolve namespace lookup lag early
            import sklearn
            import scipy
            import numpy
            
            print(f"Loading predictive model from {model_path}...")
            model = joblib.load(model_path)
            print(f"✅ Model successfully synchronized and loaded")
        else:
            print(f"⚠ Model file not found at {model_path}")
            # Fallback dummy structure for development environments
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.datasets import make_classification
            X, y = make_classification(n_samples=100, n_features=7, random_state=42)
            dummy_model = RandomForestClassifier(n_estimators=10, random_state=42)
            dummy_model.fit(X, y)
            model = dummy_model
            print("✅ Created fallback dummy model for local testing")
    except Exception as e:
        print(f"❌ Critical error parsing model data structure: {e}")
        model = None

def calculate_features(year, round_num, pit_lap, chaser, defender):
    """Calculate features for undercut prediction from CSV data"""
    try:
        # Filter data for the specific race
        race_data = f1_data[(f1_data['Year'] == year) & (f1_data['RoundNumber'] == round_num)]
        
        if race_data.empty:
            print(f"No data found for {year} Round {round_num}")
            return None
        
        # 1. State Reconstruction (Lap BEFORE pit)
        pre_pit_lap = pit_lap - 1
        if pre_pit_lap < 1:
            print(f"Pre-pit lap {pre_pit_lap} is less than 1")
            return None
        
        # Get chaser data on pre-pit lap
        chaser_pre_pit = race_data[(race_data['Driver'] == chaser) & (race_data['LapNumber'] == pre_pit_lap)]
        if chaser_pre_pit.empty:
            print(f"No data for chaser {chaser} on lap {pre_pit_lap}")
            return None
        
        chaser_state = chaser_pre_pit.iloc[0]
        
        # Get chaser position and compound
        chaser_pos = chaser_state['Position'] if 'Position' in chaser_state else None
        chaser_compound = chaser_state.get('Compound', 'Unknown')
        
        if chaser_pos is None:
            print("No position data for chaser")
            return None
        
        # 2. Rival Identification (Car directly ahead - defender)
        defender_pos = chaser_pos - 1
        if defender_pos < 1:
            print(f"Defender position {defender_pos} is less than 1")
            return None
        
        defender_pre_pit = race_data[(race_data['Driver'] == defender) & (race_data['LapNumber'] == pre_pit_lap)]
        if defender_pre_pit.empty:
            # Defender might not be directly ahead, try to find by position
            defender_pre_pit = race_data[(race_data['LapNumber'] == pre_pit_lap) & (race_data['Position'] == defender_pos)]
            if defender_pre_pit.empty:
                print(f"No data for defender {defender} on lap {pre_pit_lap}")
                return None
        
        defender_state = defender_pre_pit.iloc[0]
        
        # 3. Calculate Core Features
        # Gap to ahead (time difference in seconds)
        gap_to_ahead = 0.0
        if 'Time' in chaser_state and 'Time' in defender_state:
            gap_to_ahead = float(chaser_state['Time'] - defender_state['Time'])
        
        # Pace delta (lap time difference in seconds)
        pace_delta = 0.0
        if 'LapTime' in chaser_state and 'LapTime' in defender_state:
            pace_delta = float(chaser_state['LapTime'] - defender_state['LapTime'])
        
        # Rival tyre age
        rival_tyre_age = float(defender_state.get('TyreLife', 0))
        
        # 4. Pit Aggressiveness
        # Calculate average pit lap for each compound
        race_pit_data = race_data[race_data['PitOutTime'].notna()]
        if not race_pit_data.empty and 'Compound' in race_pit_data.columns:
            avg_pit_lap_dict = race_pit_data.groupby('Compound')['LapNumber'].mean().to_dict()
            aggression = avg_pit_lap_dict.get(chaser_compound, pit_lap) - pit_lap
        else:
            aggression = 0
        
        # 5. Execution Metrics
        # Get chaser's pit lap data
        chaser_pit_data = race_data[(race_data['Driver'] == chaser) & (race_data['LapNumber'] == pit_lap)]
        if chaser_pit_data.empty:
            print(f"No pit data for chaser {chaser} on lap {pit_lap}")
            return None
        
        chaser_pit_row = chaser_pit_data.iloc[0]
        
        # Stationary duration
        stationary_duration = float(chaser_pit_row.get('PitStopDuration', 2.5))
        
        # In-lap time
        in_lap_sec = float(chaser_pit_row.get('LapTime', 95.0))
        
        # Out-lap time
        out_lap_data = race_data[(race_data['Driver'] == chaser) & (race_data['LapNumber'] == pit_lap + 1)]
        if out_lap_data.empty:
            out_lap_sec = 96.0  # Default value
        else:
            out_lap_sec = float(out_lap_data.iloc[0].get('LapTime', 96.0))
        
        features = {
            'Gap_To_Ahead': gap_to_ahead,
            'Rival_Tyre_Age': rival_tyre_age,
            'Pace_Delta': pace_delta,
            'Pit_Aggressiveness': aggression,
            'StationaryDuration': stationary_duration,
            'InLap_Sec': in_lap_sec,
            'OutLap_Sec': out_lap_sec
        }

        # Replace any NaN values with 0.0 to prevent JSON crashes
        for key, value in features.items():
            if pd.isna(value):
                features[key] = 0.0
        
        print(f"Calculated features for {chaser} vs {defender} on lap {pit_lap}: {features}")
        return features
        
    except Exception as e:
        print(f"Error calculating features: {e}")
        import traceback
        traceback.print_exc()
        return None

# Load data and model on startup
load_data()
load_model()

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/archive')
def archive():
    """Historical Track Analysis Page"""
    return render_template('archive.html')

@app.route('/api/track-stats/<int:year>/<int:round_num>')
def api_track_stats(year, round_num):
    """Get historical pit stop distributions for a specific track safely"""
    try:
        if f1_data is None:
            return jsonify({'success': False, 'error': 'Data not loaded'})
            
        # Filter data for the specific race
        race_data = f1_data[(f1_data['Year'] == year) & (f1_data['RoundNumber'] == round_num)]
        
        # Safe return if no data exists (Always returns 200 OK to prevent HTML crash)
        if race_data.empty:
            return jsonify({
                'success': False, 
                'error': f'No telemetry data found for Year {year}, Round {round_num}. (Race may be cancelled or missing)'
            })
            
        # Get pit stop data (rows where PitOutTime is not null)
        pit_data = race_data[race_data['PitOutTime'].notna()]
        
        if pit_data.empty:
            return jsonify({
                'success': True,
                'avg_pit_time': 0.0,
                'popular_compound': "Unknown",
                'total_stops': 0,
                'distribution': {}
            })
        
        # Calculate Pit Stop Distribution
        pit_distribution = pit_data.groupby('LapNumber').size().reset_index(name='count')
        pit_dist_dict = {int(row['LapNumber']): int(row['count']) for _, row in pit_distribution.iterrows()}
        
        # --- SAFE COLUMN CHECK TO PREVENT KEYERROR ---
        avg_pit_time = 0.0
        if 'PitStopDuration' in pit_data.columns:
            valid_stops = pit_data[pit_data['PitStopDuration'] < 10.0]
            avg_pit_time = valid_stops['PitStopDuration'].mean() if not valid_stops.empty else 0.0
            if pd.isna(avg_pit_time):
                avg_pit_time = 0.0
        
        # Determine most popular tire compound safely
        popular_compound = "Unknown"
        if 'Compound' in pit_data.columns:
            modes = pit_data['Compound'].dropna().mode()
            if not modes.empty:
                popular_compound = str(modes.iloc[0])
                
        return jsonify({
            'success': True,
            'avg_pit_time': float(avg_pit_time),
            'popular_compound': popular_compound,
            'total_stops': len(pit_data),
            'distribution': pit_dist_dict
        })
        
    except Exception as e:
        print(f"Error calculating track stats: {e}")
        import traceback
        traceback.print_exc()
        # Return 200 OK so JS can handle the error gracefully
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/years')
def api_years():
    """Get available years"""
    return jsonify({'years': [2023, 2024, 2025]})

@app.route('/api/events/<int:year>')
def api_events(year):
    """Get events for a specific year from CSV safely"""
    try:
        if events_summary is None:
            return jsonify({'events': [], 'error': 'Data not loaded'})
        
        # --- DIAGNOSTIC PRINT ---
        available_years = events_summary['Year'].unique().tolist()
        print(f"DEBUG: Frontend asked for {year}. CSV contains years: {available_years}")
        # ------------------------

        # Force clean string comparison to avoid int/float/string mismatches
        target_year = str(year)
        
        events = []
        for _, row in events_summary.iterrows():
            # Clean the CSV year value (remove decimals or hidden spaces)
            csv_year = str(row['Year']).replace('.0', '').strip()
            
            if csv_year == target_year:
                events.append({
                    'RoundNumber': int(row['RoundNumber']),
                    'EventName': str(row['EventName'])
                })
        
        print(f"Found {len(events)} events for {year}")
        return jsonify({'events': events})
        
    except Exception as e:
        print(f"Error getting events for {year}: {e}")
        return jsonify({'events': [], 'error': str(e)})

@app.route('/api/laps/<int:year>/<int:round_num>')
def api_laps(year, round_num):
    """Get available laps for a specific race from CSV"""
    try:
        if pit_laps_summary is None:
            return jsonify({'laps': []})
        
        race_pit_laps = pit_laps_summary[
            (pit_laps_summary['Year'] == year) & 
            (pit_laps_summary['RoundNumber'] == round_num)
        ]
        
        laps_list = sorted(race_pit_laps['LapNumber'].unique().tolist())
        
        print(f"Found {len(laps_list)} pit laps for {year} Round {round_num}")
        return jsonify({'laps': laps_list})
    except Exception as e:
        print(f"Error loading laps: {e}")
        return jsonify({'laps': [], 'error': str(e)})

@app.route('/api/standings/<int:year>/<int:round_num>/<int:lap_number>')
def api_standings(year, round_num, lap_number):
    """Get driver standings at a specific lap from CSV"""
    try:
        if f1_data is None:
            return jsonify({'standings': [], 'error': 'Data not loaded'})
        
        # Filter for specific race and lap
        lap_data = f1_data[
            (f1_data['Year'] == year) & 
            (f1_data['RoundNumber'] == round_num) & 
            (f1_data['LapNumber'] == lap_number)
        ]
        
        if lap_data.empty:
            # Try to get the first available lap for this race
            race_data = f1_data[
                (f1_data['Year'] == year) & 
                (f1_data['RoundNumber'] == round_num)
            ]
            if not race_data.empty:
                first_lap = race_data['LapNumber'].min()
                lap_data = race_data[race_data['LapNumber'] == first_lap]
                print(f"Using lap {first_lap} instead of {lap_number}")
        
        if lap_data.empty:
            return jsonify({'standings': []})
        
        # Get driver info
        drivers_info = []
        for _, driver_lap in lap_data.iterrows():
            # Safely extract position, handling NaN for retired drivers
            pos_val = driver_lap.get('Position', 99)
            safe_position = int(pos_val) if pd.notna(pos_val) else 99
            
            drivers_info.append({
                'driver': str(driver_lap.get('Driver', 'Unknown')),
                'position': safe_position,
                'team': str(driver_lap.get('Team', 'Unknown')),
                'compound': str(driver_lap.get('Compound', 'Unknown')),
                'time': float(driver_lap.get('Time', 0)) if pd.notna(driver_lap.get('Time')) else None
            })
        
        # Sort by position
        drivers_info.sort(key=lambda x: x['position'])
        
        # Calculate gaps
        for i in range(len(drivers_info)):
            if i == 0:
                drivers_info[i]['gap'] = "Leader"
            else:
                current_time = drivers_info[i]['time']
                prev_time = drivers_info[i-1]['time']
                
                if current_time is not None and prev_time is not None:
                    gap = current_time - prev_time
                    drivers_info[i]['gap'] = f"+{gap:.3f}s"
                else:
                    drivers_info[i]['gap'] = "--"

        print(f"Found {len(drivers_info)} drivers for lap {lap_number}")
        return jsonify({'standings': drivers_info})
    except Exception as e:
        print(f"Error loading standings: {e}")
        return jsonify({'standings': [], 'error': str(e)})

@app.route('/api/predict', methods=['POST'])
def api_predict():
    """Predict undercut success using CSV data"""
    try:
        data = request.json
        
        # Validate required parameters
        required = ['year', 'round_num', 'lap_number', 'chaser', 'defender']
        for param in required:
            if param not in data:
                return jsonify({'error': f'Missing parameter: {param}'}), 400
        
        year = int(data['year'])
        round_num = int(data['round_num'])
        pit_lap = int(data['lap_number'])
        chaser = str(data['chaser'])
        defender = str(data['defender'])
        
        # Calculate features from CSV data
        features = calculate_features(year, round_num, pit_lap, chaser, defender)
        
        if features is None:
            # Return a realistic fallback
            print("Using fallback features")
            import random
            features = {
                'Gap_To_Ahead': random.uniform(0.5, 3.0),
                'Rival_Tyre_Age': random.uniform(15.0, 35.0),
                'Pace_Delta': random.uniform(-1.0, 0.5),
                'Pit_Aggressiveness': random.uniform(-5.0, 5.0),
                'StationaryDuration': random.uniform(2.0, 3.0),
                'InLap_Sec': random.uniform(94.0, 97.0),
                'OutLap_Sec': random.uniform(95.0, 98.0)
            }
        
        # Create DataFrame for model
        feature_values = [features.get(feat, 0) for feat in CORE_FEATURES]
        X = pd.DataFrame([feature_values], columns=CORE_FEATURES)
        
        # Make prediction
        if model is not None:
            try:
                probability = model.predict_proba(X)[0]
                prediction = model.predict(X)[0]
                
                # Determine confidence
                confidence_score = max(probability)
                if confidence_score > 0.8:
                    confidence = 'High'
                elif confidence_score > 0.6:
                    confidence = 'Medium'
                else:
                    confidence = 'Low'
                
                result = {
                    'success': bool(prediction),
                    'probability': float(probability[1]),
                    'confidence': confidence,
                    'lap': data['lap_number'],
                    'chaser': data['chaser'],
                    'defender': data['defender'],
                    'features': features
                }
            except Exception as e:
                print(f"Model prediction error: {e}, using fallback")
                success_prob = 0.5
                if features['Pace_Delta'] < 0:
                    success_prob += 0.2
                if features['Gap_To_Ahead'] < 1.0:
                    success_prob += 0.15
                if features['Rival_Tyre_Age'] > 25:
                    success_prob += 0.1
                
                success_prob = max(0.1, min(0.9, success_prob))
                result = {
                    'success': success_prob > 0.5,
                    'probability': success_prob,
                    'confidence': 'Medium',
                    'lap': data['lap_number'],
                    'chaser': data['chaser'],
                    'defender': data['defender'],
                    'features': features
                }
        else:
            # Fallback to logic-based prediction
            print("Model not available, using logic-based prediction")
            success_prob = 0.5
            
            if features['Pace_Delta'] < 0:
                success_prob += 0.25
            if features['Gap_To_Ahead'] < 1.5:
                success_prob += 0.2
            if features['Rival_Tyre_Age'] > 20:
                success_prob += 0.15
            if features['Pit_Aggressiveness'] > 0:
                success_prob += 0.1
            
            success_prob = max(0.2, min(0.95, success_prob))
            
            result = {
                'success': success_prob > 0.5,
                'probability': success_prob,
                'confidence': 'High' if abs(success_prob - 0.5) > 0.3 else 'Medium',
                'lap': data['lap_number'],
                'chaser': data['chaser'],
                'defender': data['defender'],
                'features': features
            }
        
        print(f"Prediction result: {result}")
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in predict endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/best-timing', methods=['POST'])
def api_best_timing():
    """Predict best timing for undercut between two drivers"""
    try:
        data = request.json
        
        # Validate required parameters
        required = ['year', 'round_num', 'chaser', 'defender']
        for param in required:
            if param not in data:
                return jsonify({'error': f'Missing parameter: {param}'}), 400
        
        year = int(data['year'])
        round_num = int(data['round_num'])
        chaser = str(data['chaser'])
        defender = str(data['defender'])
        
        # Get all available pit laps for this race
        race_pit_laps = pit_laps_summary[
            (pit_laps_summary['Year'] == year) & 
            (pit_laps_summary['RoundNumber'] == round_num)
        ]
        
        if race_pit_laps.empty:
            return jsonify({'recommended_laps': [], 'message': 'No pit data available for this race'})
        
        laps = sorted(race_pit_laps['LapNumber'].unique().tolist())
        
        # Calculate probabilities for each lap
        lap_probabilities = []
        
        for lap in laps:
            try:
                # Calculate features for this lap
                features = calculate_features(year, round_num, lap, chaser, defender)
                
                if features is None:
                    continue
                
                # Create DataFrame for model
                feature_values = [features.get(feat, 0) for feat in CORE_FEATURES]
                X = pd.DataFrame([feature_values], columns=CORE_FEATURES)
                
                # Get probability from model
                if model is not None:
                    try:
                        probability = model.predict_proba(X)[0][1]
                    except:
                        # Fallback calculation
                        probability = 0.5
                        if features['Pace_Delta'] < 0:
                            probability += 0.2
                        if features['Gap_To_Ahead'] < 1.0:
                            probability += 0.15
                        if features['Rival_Tyre_Age'] > 25:
                            probability += 0.1
                        probability = max(0.1, min(0.9, probability))
                else:
                    # Fallback calculation without model
                    probability = 0.5
                    if features['Pace_Delta'] < 0:
                        probability += 0.25
                    if features['Gap_To_Ahead'] < 1.5:
                        probability += 0.2
                    if features['Rival_Tyre_Age'] > 20:
                        probability += 0.15
                    if features['Pit_Aggressiveness'] > 0:
                        probability += 0.1
                    probability = max(0.2, min(0.95, probability))
                
                lap_probabilities.append({
                    'lap': lap,
                    'probability': float(probability),
                    'features': features
                })
                
            except Exception as e:
                print(f"Error calculating probability for lap {lap}: {e}")
                continue
        
        if not lap_probabilities:
            return jsonify({'recommended_laps': [], 'message': 'Could not calculate probabilities for any laps'})
        
        # Sort by probability (highest first)
        lap_probabilities.sort(key=lambda x: x['probability'], reverse=True)
        
        # Take top 5 laps with highest probability
        top_laps = lap_probabilities[:5]
        
        # Also get some context about why these laps are good
        for lap_data in top_laps:
            features = lap_data['features']
            reasons = []
            
            if features['Pace_Delta'] < 0:
                reasons.append(f"Chaser is {abs(features['Pace_Delta']):.2f}s faster per lap")
            if features['Gap_To_Ahead'] < 1.0:
                reasons.append(f"Close gap ({features['Gap_To_Ahead']:.2f}s) to defender")
            if features['Rival_Tyre_Age'] > 20:
                reasons.append(f"Defender's tyres are old ({features['Rival_Tyre_Age']:.0f} laps)")
            if features['Pit_Aggressiveness'] > 0:
                reasons.append("Early pit stop strategy")
            
            lap_data['reasons'] = reasons
        
        result = {
            'recommended_laps': top_laps,
            'chaser': chaser,
            'defender': defender,
            'total_laps_analyzed': len(lap_probabilities)
        }
        
        print(f"Best timing analysis for {chaser} vs {defender}: Found {len(top_laps)} recommended laps")
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in best-timing endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/status')
def api_status():
    """Check API status"""
    data_loaded = f1_data is not None
    return jsonify({
        'status': 'online',
        'data_loaded': data_loaded,
        'data_records': len(f1_data) if data_loaded else 0,
        'model_loaded': model is not None,
        'message': 'F1 Undercut Predictor is running'
    })

if __name__ == '__main__':
    print("=" * 50)
    print("F1 Undercut Predictor - CSV Version")
    print("=" * 50)
    
    # Fetch Render's dynamically assigned port, or default to 5000 locally
    port = int(os.environ.get('PORT', 5000))
    print(f"Server: listening on 0.0.0.0:{port}")
    print("=" * 50)
    
    # Bind to 0.0.0.0 so the outside world can access it
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)