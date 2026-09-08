import os
import random
import time
from datetime import datetime
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Precise GPS Coordinates strictly along Venkatapur Road
WAYPOINTS = [
    (17.42080, 78.65620), # Step 0: Anurag Main Gate
    (17.42050, 78.65540), # Step 1
    (17.42030, 78.65480), # Step 2: [FIXED VEHICLE 1]
    (17.42010, 78.65410), # Step 3
    (17.42000, 78.65350), # Step 4
    (17.42010, 78.65280), # Step 5: [FIXED VEHICLE 2]
    (17.42020, 78.65210), # Step 6
    (17.42050, 78.65140), # Step 7
    (17.42080, 78.65080), # Step 8: [FIXED VEHICLE 3]
    (17.42125, 78.65020), # Step 9
    (17.42170, 78.64960), # Step 10
    (17.42215, 78.64880), # Step 11
    (17.42260, 78.64800), # Step 12
    (17.42320, 78.64690), # Step 13
    (17.42380, 78.64580), # Step 14
    (17.42440, 78.64465), # Step 15
    (17.42500, 78.64350), # Step 16
    (17.42560, 78.64225), # Step 17
    (17.42620, 78.64100), # Step 18
    (17.42700, 78.63950), # Step 19
    (17.42780, 78.63800)  # Step 20: Highway Junction
]

VEHICLE_STEPS = [2, 5, 8]

# Persistent memory for previously repaired pothole steps across runs
permanently_repaired_steps = set()
mission_history = []

dashboard_data = {
    "rover_status": "READY",
    "control_state": "STOPPED",
    "target_km": 10.0,
    "distance_traveled_km": 0.0,
    "total_potholes": 0,
    "total_material_kg": 0.0,
    "current_lat": 17.42080,
    "current_lng": 78.65620,
    "step_idx": 0,
    "returning": False,
    "avoiding_obstacle": False,
    "camera_active": False,
    "battery_pct": 100.0,
    "material_level_pct": 100.0,
    "warning_msg": "",
    "detections": [],
    "mission_start_time": None,
    "return_location": None,
    "mission_history": []
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['POST'])
def handle_config():
    data = request.json or {}
    dashboard_data['target_km'] = float(data.get('target_km', 10.0))
    return jsonify({"status": "success", "target_km": dashboard_data['target_km']})

@app.route('/api/control', methods=['POST'])
def handle_control():
    data = request.json or {}
    cmd = data.get('command')
    
    if cmd == 'START':
        dashboard_data['control_state'] = 'RUNNING'
        dashboard_data['camera_active'] = True
        dashboard_data['warning_msg'] = ""
        dashboard_data['mission_start_time'] = time.time()
        
        if dashboard_data['rover_status'] in ['READY', 'COMPLETED', 'STOPPED']:
            dashboard_data['rover_status'] = 'PATROL_ACTIVE'
            dashboard_data['battery_pct'] = 100.0
            dashboard_data['material_level_pct'] = 100.0
            dashboard_data['distance_traveled_km'] = 0.0
            dashboard_data['step_idx'] = 0
            dashboard_data['detections'] = []
            dashboard_data['total_potholes'] = 0
            dashboard_data['total_material_kg'] = 0.0
            dashboard_data['return_location'] = None

    elif cmd == 'PAUSE':
        dashboard_data['control_state'] = 'PAUSED'
        dashboard_data['rover_status'] = 'PATROL_PAUSED'

    elif cmd == 'STOP':
        if dashboard_data['step_idx'] > 0:
            dashboard_data['control_state'] = 'RUNNING'
            dashboard_data['returning'] = True
            dashboard_data['rover_status'] = 'ABORT_RETURNING'
            dashboard_data['return_location'] = {
                "lat": dashboard_data['current_lat'],
                "lng": dashboard_data['current_lng']
            }
            dashboard_data['warning_msg'] = "⚠️ MANUAL ABORT: RETURNING HOME"
        else:
            dashboard_data['control_state'] = 'STOPPED'
            dashboard_data['rover_status'] = 'STOPPED'
            dashboard_data['camera_active'] = False
            dashboard_data['distance_traveled_km'] = 0.0
            dashboard_data['total_potholes'] = 0
            dashboard_data['total_material_kg'] = 0.0
            dashboard_data['detections'] = []
            dashboard_data['current_lat'] = 17.42080
            dashboard_data['current_lng'] = 78.65620
            dashboard_data['step_idx'] = 0
            dashboard_data['returning'] = False
            dashboard_data['avoiding_obstacle'] = False
            dashboard_data['battery_pct'] = 100.0
            dashboard_data['material_level_pct'] = 100.0
            dashboard_data['warning_msg'] = ""
        
    return jsonify({"status": "success", "control_state": dashboard_data['control_state']})

@app.route('/api/telemetry', methods=['GET'])
def handle_telemetry():
    if dashboard_data['control_state'] == 'RUNNING':
        target_km = dashboard_data['target_km']
        km_increment = round(target_km / 60.0, 3)

        dashboard_data['battery_pct'] = max(0.0, round(dashboard_data['battery_pct'] - round(random.uniform(0.5, 1.2), 1), 1))

        if not dashboard_data['returning']:
            if dashboard_data['battery_pct'] <= 20.0:
                dashboard_data['returning'] = True
                dashboard_data['return_location'] = {"lat": dashboard_data['current_lat'], "lng": dashboard_data['current_lng']}
                dashboard_data['warning_msg'] = "⚠️ LOW BATTERY (<20%)! RETURNING HOME..."
                dashboard_data['rover_status'] = "AUTO_RETURNING"
            elif dashboard_data['material_level_pct'] <= 15.0:
                dashboard_data['returning'] = True
                dashboard_data['return_location'] = {"lat": dashboard_data['current_lat'], "lng": dashboard_data['current_lng']}
                dashboard_data['warning_msg'] = "⚠️ LOW MATERIAL (<15%)! RETURNING HOME..."
                dashboard_data['rover_status'] = "AUTO_RETURNING"
            else:
                dashboard_data['step_idx'] = min(dashboard_data['step_idx'] + 1, len(WAYPOINTS) - 1)
                base_lat, base_lng = WAYPOINTS[dashboard_data['step_idx']]

                if dashboard_data['step_idx'] in VEHICLE_STEPS:
                    vehicle_num = VEHICLE_STEPS.index(dashboard_data['step_idx']) + 1
                    dashboard_data['avoiding_obstacle'] = True
                    dashboard_data['warning_msg'] = f"⚠️ VEHICLE OBSTACLE {vehicle_num} AHEAD! MANEUVERING..."
                    dashboard_data['current_lat'] = round(base_lat + 0.00018, 5)
                    dashboard_data['current_lng'] = round(base_lng - 0.00018, 5)
                else:
                    dashboard_data['avoiding_obstacle'] = False
                    if not dashboard_data['warning_msg'].startswith("⚠️ LOW"):
                        dashboard_data['warning_msg'] = ""
                    dashboard_data['current_lat'] = base_lat
                    dashboard_data['current_lng'] = base_lng

                dashboard_data['distance_traveled_km'] = round(dashboard_data['distance_traveled_km'] + km_increment, 3)

                # Ignore steps that have already been repaired in prior runs
                current_step = dashboard_data['step_idx']
                if current_step not in permanently_repaired_steps:
                    if len(dashboard_data['detections']) < 4 or random.choice([True, True, False]):
                        if not any(d['step'] == current_step for d in dashboard_data['detections']):
                            mat = round(random.uniform(0.4, 0.9), 2)
                            dashboard_data['total_potholes'] += 1
                            dashboard_data['total_material_kg'] = round(dashboard_data['total_material_kg'] + mat, 2)
                            dashboard_data['material_level_pct'] = max(0.0, round(dashboard_data['material_level_pct'] - round(mat * 4, 1), 1))
                            
                            dashboard_data['detections'].append({
                                "id": f"PH-{len(dashboard_data['detections']) + 1:02d}",
                                "lat": dashboard_data['current_lat'],
                                "lng": dashboard_data['current_lng'],
                                "mat": mat,
                                "step": current_step
                            })
                            # Record as repaired
                            permanently_repaired_steps.add(current_step)
                else:
                    dashboard_data['warning_msg'] = f"ℹ️ SKIPPING PREVIOUSLY FILLED POTHOLE AT STEP {current_step}"

                if dashboard_data['distance_traveled_km'] >= target_km or dashboard_data['step_idx'] >= len(WAYPOINTS) - 1:
                    dashboard_data['distance_traveled_km'] = target_km
                    dashboard_data['returning'] = True
                    dashboard_data['return_location'] = {"lat": dashboard_data['current_lat'], "lng": dashboard_data['current_lng']}
                    dashboard_data['rover_status'] = "RETURNING_TO_BASE"
                    dashboard_data['warning_msg'] = "ℹ️ TARGET REACHED. RETURNING HOME..."
                else:
                    if not dashboard_data['warning_msg'].startswith("ℹ️ SKIPPING"):
                        dashboard_data['rover_status'] = "PATROL_ACTIVE"
        else:
            # RETURN MODE
            dashboard_data['distance_traveled_km'] = round(max(0.0, dashboard_data['distance_traveled_km'] - km_increment), 3)
            dashboard_data['step_idx'] = max(0, dashboard_data['step_idx'] - 1)
            base_lat, base_lng = WAYPOINTS[dashboard_data['step_idx']]

            recorded_pothole_steps = [d['step'] for d in dashboard_data['detections']]
            
            if dashboard_data['step_idx'] in VEHICLE_STEPS:
                vehicle_num = VEHICLE_STEPS.index(dashboard_data['step_idx']) + 1
                dashboard_data['avoiding_obstacle'] = True
                dashboard_data['warning_msg'] = f"⚠️ VEHICLE {vehicle_num} DETECTED! DETOURING ON RETURN..."
                dashboard_data['current_lat'] = round(base_lat + 0.00022, 5)
                dashboard_data['current_lng'] = round(base_lng - 0.00022, 5)
            elif dashboard_data['step_idx'] in recorded_pothole_steps:
                dashboard_data['avoiding_obstacle'] = True
                dashboard_data['warning_msg'] = "⚠️ POTHOLE DETECTED! MOVING AWAY FROM POTHOLE AREA..."
                dashboard_data['current_lat'] = round(base_lat + 0.00025, 5)
                dashboard_data['current_lng'] = round(base_lng - 0.00025, 5)
            else:
                dashboard_data['avoiding_obstacle'] = False
                if not dashboard_data['warning_msg'].startswith("⚠️ LOW") and not dashboard_data['warning_msg'].startswith("⚠️ MANUAL"):
                    dashboard_data['warning_msg'] = "ℹ️ RETURNING TO BASE..."
                dashboard_data['current_lat'] = base_lat
                dashboard_data['current_lng'] = base_lng

            if dashboard_data['distance_traveled_km'] <= 0.0 or dashboard_data['step_idx'] <= 0:
                dashboard_data['rover_status'] = "COMPLETED"
                dashboard_data['control_state'] = "STOPPED"
                dashboard_data['returning'] = False
                dashboard_data['camera_active'] = False
                dashboard_data['warning_msg'] = "✅ SAFELY RETURNED TO ANURAG BASE."

                # Log history entry upon return completion
                duration_sec = int(time.time() - (dashboard_data['mission_start_time'] or time.time()))
                mins, secs = divmod(duration_sec, 60)
                
                ret_loc = dashboard_data['return_location'] or {"lat": base_lat, "lng": base_lng}

                history_entry = {
                    "id": f"RUN-{len(mission_history) + 1:03d}",
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "start_place": "Anurag Main Gate",
                    "return_place": f"({ret_loc['lat']:.4f}, {ret_loc['lng']:.4f})",
                    "duration": f"{mins}m {secs}s",
                    "potholes_filled": dashboard_data['total_potholes'],
                    "material_used": f"{dashboard_data['total_material_kg']} kg"
                }
                
                mission_history.insert(0, history_entry)
                dashboard_data['mission_history'] = mission_history

    return jsonify(dashboard_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
