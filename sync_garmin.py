import os
import json
import sys
import requests
from datetime import datetime, timedelta
from google.oauth2.service_account import Credentials
import gspread

# --- HILFSFUNKTIONEN ---
def safe_num(val, default=0):
    return float(val) if val is not None else default

def main():
    print("🚀 Skript gestartet (Intervals.icu Clean Edition v3)...")
    
    intervals_id = os.environ.get('INTERVALS_ID')
    intervals_api_key = os.environ.get('INTERVALS_API_KEY')
    google_creds_json = os.environ.get('GOOGLE_CREDENTIALS')
    sheet_id = os.environ.get('SHEET_ID')

    if not all([intervals_id, intervals_api_key, google_creds_json, sheet_id]):
        print("❌ Fehler: Umgebungsvariablen fehlen.")
        sys.exit(1)

    # --- GOOGLE SHEETS SETUP ---
    creds_dict = json.loads(google_creds_json)
    creds = Credentials.from_service_account_info(creds_dict, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(sheet_id)

    # --- INTERVALS.ICU API SETUP ---
    auth = requests.auth.HTTPBasicAuth('API_KEY', intervals_api_key)
    base_url = f"https://intervals.icu/api/v1/athlete/{intervals_id}"
    
    now = datetime.now()
    oldest_workout = (now - timedelta(days=45)).strftime("%Y-%m-%dT00:00:00")
    newest = now.strftime("%Y-%m-%dT23:59:59")
    oldest_health = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    # --- TEIL 1: WORKOUTS ---
    print("🏃 Synchronisiere Workouts...")
    try:
        workout_sheet = spreadsheet.worksheet("workout_database")
        all_rows = workout_sheet.get_all_values()
        existing_workouts = {f"{row[0]} {row[1]}" for row in all_rows if len(row) > 1}
        
        act_url = f"{base_url}/activities?oldest={oldest_workout}&newest={newest}"
        response = requests.get(act_url, auth=auth)
        response.raise_for_status()
        activities = response.json()
        
        activities = sorted(activities, key=lambda x: x.get('start_date_local', ''))
        
        for act in activities:
            start_local = act.get('start_date_local', '')
            if not start_local: continue
            
            date_part, time_part = start_local.split("T")
            
            if f"{date_part} {time_part}" not in existing_workouts:
                
                # --- INTELLIGENTE LOGIK FÜR KADENZ & HÖHE ---
                raw_type = (act.get('type') or '').lower()
                raw_cadence = safe_num(act.get('average_cadence'))
                
                # Verdoppelt Kadenz für ALLES was 'run' oder 'treadmill' enthält
                if 'run' in raw_type or 'treadmill' in raw_type:
                    cadence = round(raw_cadence * 2)
                else:
                    cadence = round(raw_cadence)
                
                # Fallback für Höhenmeter (verschiedene API-Keys)
                min_elev = act.get('min_altitude') or act.get('icu_min_altitude') or 0
                max_elev = act.get('max_altitude') or act.get('icu_max_altitude') or 0
                
                avg_pwr = safe_num(act.get('icu_average_watts') or act.get('device_watts') or act.get('average_watts'))
                max_pwr = safe_num(act.get('icu_pm_p_max') or act.get('p_max') or act.get('max_watts'))
                
                # Die exakten 22 Spalten für dein Sheet
                row = [
                    date_part,                  # A
                    time_part,                  # B
                    act.get('type') or '',      # C
                    act.get('name') or '',      # D
                    round(safe_num(act.get('distance')) / 1000, 2), # E
                    safe_num(act.get('calories')), # F
                    round(safe_num(act.get('moving_time')) / 60, 2), # G
                    safe_num(act.get('average_heartrate')), # H
                    safe_num(act.get('max_heartrate')), # I
                    cadence,                    # J
                    round(safe_num(act.get('average_speed')) * 3.6, 2), # K
                    round(safe_num(act.get('max_speed')) * 3.6, 2), # L
                    safe_num(act.get('total_elevation_gain')), # M
                    safe_num(act.get('total_elevation_loss')), # N
                    round(safe_num(act
