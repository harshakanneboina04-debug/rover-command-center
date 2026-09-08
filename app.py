import os
import random
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Precise On-Road GPS Coordinates along Venkatapur Road
WAYPOINTS = [
    (17.42080, 78.65620), # Start: Anurag Main Gate
    (17.42030, 78.65480), # Venkatapur Rd (South of Lake)
    (17.42000, 78.65350), # Venkatapur Rd (Curve past CVSR)
    (17.42020, 78.65210), # Venkatapur Rd (South-West Bend)
    (17.42080, 78.65080), # Venkatapur Rd (Passing NESTA CAFE)
    (17.42170, 78.64960), # Venkatapur Rd Junction
    (17.42260, 78.64800), # Venkatapur Rd (North-West Stretch)
    (17.42380, 78.64580), # Venkatapur Rd
    (17.42500, 78.64350), # Venkatapur Rd (Towards Neelima Hospitals)
    (17.42620, 78.64100), # Venkatapur Rd Extension
    (17.42780, 78.63800)  # Highway Junction
]

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
    "detections": []
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
        if dashboard_data['rover_status'] in ['READY', 'COMPLETED', 'STOPPED']:
            dashboard_data['rover_status'] = 'PATROL_ACTIVE'
            dashboard_data['battery_pct'] = 100.0
            dashboard_data['material_level_pct'] = 100.0
    elif cmd == 'PAUSE':
        dashboard_data['control_state'] = 'PAUSED'
        dashboard_data['rover_status'] = 'PATROL_PAUSED'
    elif cmd == 'STOP':
        if dashboard_data['step_idx'] > 0:
            dashboard_data['control_state'] = 'RUNNING'
            dashboard_data['returning'] = True
            dashboard_data['rover_status'] = 'ABORT_RETURNING'
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
        # Reduced step increment for much slower movement speed
        km_increment = round(target_km / 60.0, 3)

        # Deplete battery at a slower rate per tick
        dashboard_data['battery_pct'] = max(0.0, round(dashboard_data['battery_pct'] - round(random.uniform(0.5, 1.2), 1), 1))

        if not dashboard_data['returning']:
            if dashboard_data['battery_pct'] <= 20.0:
                dashboard_data['returning'] = True
                dashboard_data['warning_msg'] = "⚠️ LOW BATTERY (<20%)! RETURNING HOME..."
                dashboard_data['rover_status'] = "AUTO_RETURNING"
            elif dashboard_data['material_level_pct'] <= 15.0:
                dashboard_data['returning'] = True
                dashboard_data['warning_msg'] = "⚠️ LOW MATERIAL (<15%)! RETURNING HOME..."
                dashboard_data['rover_status'] = "AUTO_RETURNING"
            else:
                obstacle_ahead = random.choice([False, False, False, True, False])
                dashboard_data['step_idx'] = min(dashboard_data['step_idx'] + 1, len(WAYPOINTS) - 1)
                base_lat, base_lng = WAYPOINTS[dashboard_data['step_idx']]

                if obstacle_ahead:
                    dashboard_data['avoiding_obstacle'] = True
                    dashboard_data['warning_msg'] = "⚠️ OBSTACLE ON VENKATAPUR RD! DETOURING..."
                    dashboard_data['current_lat'] = round(base_lat + 0.00015, 5)
                    dashboard_data['current_lng'] = round(base_lng - 0.00015, 5)
                else:
                    dashboard_data['avoiding_obstacle'] = False
                    if not dashboard_data['warning_msg'].startswith("⚠️ LOW"):
                        dashboard_data['warning_msg'] = ""
                    dashboard_data['current_lat'] = base_lat
                    dashboard_data['current_lng'] = base_lng

                dashboard_data['distance_traveled_km'] = round(dashboard_data['distance_traveled_km'] + km_increment, 3)

                if random.choice([True, False, False, False]):
                    mat = round(random.uniform(0.3, 0.8), 2)
                    dashboard_data['total_potholes'] += 1
                    dashboard_data['total_material_kg'] = round(dashboard_data['total_material_kg'] + mat, 2)
                    dashboard_data['material_level_pct'] = max(0.0, round(dashboard_data['material_level_pct'] - round(mat * 4, 1), 1))
                    
                    dashboard_data['detections'].append({
                        "id": f"PH-{len(dashboard_data['detections']) + 1:02d}",
                        "lat": dashboard_data['current_lat'],
                        "lng": dashboard_data['current_lng'],
                        "mat": mat,
                        "step": dashboard_data['step_idx']
                    })

                if dashboard_data['distance_traveled_km'] >= target_km or dashboard_data['step_idx'] >= len(WAYPOINTS) - 1:
                    dashboard_data['distance_traveled_km'] = target_km
                    dashboard_data['returning'] = True
                    dashboard_data['rover_status'] = "RETURNING_TO_BASE"
                    dashboard_data['warning_msg'] = "ℹ️ TARGET REACHED. RETURNING HOME..."
                else:
                    if not dashboard_data['warning_msg']:
                        dashboard_data['rover_status'] = "PATROL_ACTIVE"
        else:
            # RETURN MODE
            dashboard_data['distance_traveled_km'] = round(max(0.0, dashboard_data['distance_traveled_km'] - km_increment), 3)
            dashboard_data['step_idx'] = max(0, dashboard_data['step_idx'] - 1)
            base_lat, base_lng = WAYPOINTS[dashboard_data['step_idx']]

            recorded_pothole_steps = [d['step'] for d in dashboard_data['detections']]
            
            if dashboard_data['step_idx'] in recorded_pothole_steps:
                dashboard_data['avoiding_obstacle'] = True
                dashboard_data['warning_msg'] = f"⚠️ POTHOLE OBSTACLE DETECTED! MOVING AWAY FROM POTHOLE AREA..."
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

    return jsonify(dashboard_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
