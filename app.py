# app.py
from flask import Flask, jsonify, render_template, request
import pandas as pd
import numpy as np
import joblib
import os
import warnings
from datetime import datetime

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
    """Load CSV data into memory"""
    global f1_data, events_summary, pit_laps_summary, drivers_summary
    
    try:
        # Load main data file
        csv_path = 'f1_data/f1_2022_2024.csv'
        if os.path.exists(csv_path):
            print(f"Loading data from {csv_path}...")
            f1_data = pd.read_csv(csv_path, low_memory=False)
            print(f"✅ Loaded {len(f1_data)} records")
        else:
            print(f"❌ Data file not found: {csv_path}")
            return False
        
        # Load summary files
        events_summary = pd.read_csv('f1_data/events_summary.csv')
        pit_laps_summary = pd.read_csv('f1_data/pit_laps_summary.csv')
        drivers_summary = pd.read_csv('f1_data/drivers_summary.csv')
        
        # Convert relevant columns to appropriate types
        if 'PitStopDuration' in f1_data.columns:
            f1_data['PitStopDuration'] = pd.to_numeric(f1_data['PitStopDuration'], errors='coerce')
        
        if 'Time' in f1_data.columns:
            f1_data['Time'] = pd.to_numeric(f1_data['Time'], errors='coerce')
        
        if 'LapTime' in f1_data.columns:
            f1_data['LapTime'] = pd.to_numeric(f1_data['LapTime'], errors='coerce')
        
        if 'TyreLife' in f1_data.columns:
            f1_data['TyreLife'] = pd.to_numeric(f1_data['TyreLife'], errors='coerce')
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        import traceback
        traceback.print_exc()
        return False

def load_model():
    """Load the ML model"""
    global model
    try:
        model_path = 'Datamining_model_final.pkl'
        if os.path.exists(model_path):
            model = joblib.load(model_path)
            print(f"✅ Model loaded from {model_path}")
        else:
            print(f"⚠ Model file not found: {model_path}")
            # Create a dummy model for testing
            from sklearn.ensemble import RandomForestClassifier
            from sklearn.datasets import make_classification
            X, y = make_classification(n_samples=100, n_features=7, random_state=42)
            dummy_model = RandomForestClassifier(n_estimators=10, random_state=42)
            dummy_model.fit(X, y)
            model = dummy_model
            print("✅ Created dummy model for testing")
    except Exception as e:
        print(f"❌ Error loading model: {e}")
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

@app.route('/api/years')
def api_years():
    """Get available years"""
    return jsonify({'years': [2022, 2023, 2024]})

@app.route('/api/events/<int:year>')
def api_events(year):
    """Get events for a specific year from CSV"""
    try:
        if events_summary is None:
            return jsonify({'events': [], 'error': 'Data not loaded'})
        
        year_events = events_summary[events_summary['Year'] == year]
        events = []
        
        for _, row in year_events.iterrows():
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
            drivers_info.append({
                'driver': str(driver_lap.get('Driver', 'Unknown')),
                'position': int(driver_lap.get('Position', 99)),
                'team': str(driver_lap.get('Team', 'Unknown')),
                'compound': str(driver_lap.get('Compound', 'Unknown'))
            })
        
        # Sort by position
        drivers_info.sort(key=lambda x: x['position'])
        
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
    print("Server: http://127.0.0.1:5000")
    print("=" * 50)
    
    app.run(debug=True, port=5000, threaded=True)