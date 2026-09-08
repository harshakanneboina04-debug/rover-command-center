import os
import random
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

WAYPOINTS = [
    (17.4208, 78.6562), # Start: Anurag Univ Entrance
    (17.4211, 78.6540), # Venkatapur Rd (South of lake)
    (17.4213, 78.6515), 
    (17.4215, 78.6490), 
    (17.4218, 78.6465), 
    (17.4228, 78.6440), 
    (17.4242, 78.6415), 
    (17.4260, 78.6385), 
    (17.4280, 78.6350)  # Highway Junction
]

dashboard_data = {
    "rover_status": "READY",
    "control_state": "STOPPED",
    "target_km": 10.0,
    "distance_traveled_km": 0.0,
    "total_potholes": 0,
    "total_material_kg": 0.0,
    "current_lat": 17.4208,
    "current_lng": 78.6562,
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
            # Reset levels on fresh start
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
            dashboard_data['current_lat'] = 17.4208
            dashboard_data['current_lng'] = 78.6562
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
        km_increment = round(target_km / 25.0, 3)

        # Deplete battery & material during movement
        dashboard_data['battery_pct'] = max(0.0, round(dashboard_data['battery_pct'] - round(random.uniform(2.5, 4.0), 1), 1))

        if not dashboard_data['returning']:
            # Check for low battery or low material triggers
            if dashboard_data['battery_pct'] <= 20.0:
                dashboard_data['returning'] = True
                dashboard_data['warning_msg'] = "⚠️ LOW BATTERY DETECTED (<20%)! RETURNING HOME..."
                dashboard_data['rover_status'] = "AUTO_RETURNING"
            elif dashboard_data['material_level_pct'] <= 15.0:
                dashboard_data['returning'] = True
                dashboard_data['warning_msg'] = "⚠️ LOW MATERIAL LEVEL (<15%)! RETURNING HOME..."
                dashboard_data['rover_status'] = "AUTO_RETURNING"
            else:
                # Random Obstacle Detection logic along Venkatapur Road
                obstacle_ahead = random.choice([False, False, True, False])
                
                dashboard_data['step_idx'] = min(dashboard_data['step_idx'] + 1, len(WAYPOINTS) - 1)
                base_lat, base_lng = WAYPOINTS[dashboard_data['step_idx']]

                if obstacle_ahead:
                    # Reroute maneuver (offset coordinate to bypass obstacle safely)
                    dashboard_data['avoiding_obstacle'] = True
                    dashboard_data['warning_msg'] = "⚠️ OBSTACLE DETECTED! REROUTING PATH..."
                    dashboard_data['current_lat'] = round(base_lat + 0.0002, 5)
                    dashboard_data['current_lng'] = round(base_lng - 0.0001, 5)
                else:
                    dashboard_data['avoiding_obstacle'] = False
                    if not dashboard_data['warning_msg'].startswith("⚠️ LOW"):
                        dashboard_data['warning_msg'] = ""
                    dashboard_data['current_lat'] = base_lat
                    dashboard_data['current_lng'] = base_lng

                dashboard_data['distance_traveled_km'] = round(dashboard_data['distance_traveled_km'] + km_increment, 3)

                # Pothole repair simulation
                if random.choice([True, False, False]):
                    mat = round(random.uniform(0.3, 0.8), 2)
                    dashboard_data['total_potholes'] += 1
                    dashboard_data['total_material_kg'] = round(dashboard_data['total_material_kg'] + mat, 2)
                    # Deplete material percentage
                    dashboard_data['material_level_pct'] = max(0.0, round(dashboard_data['material_level_pct'] - round(mat * 8, 1), 1))
                    dashboard_data['detections'].append({"lat": dashboard_data['current_lat'], "lng": dashboard_data['current_lng'], "mat": mat, "step": dashboard_data['step_idx']})

                if dashboard_data['distance_traveled_km'] >= target_km or dashboard_data['step_idx'] >= len(WAYPOINTS) - 1:
                    dashboard_data['distance_traveled_km'] = target_km
                    dashboard_data['returning'] = True
                    dashboard_data['rover_status'] = "RETURNING_TO_BASE"
                    dashboard_data['warning_msg'] = "ℹ️ MISSION TARGET REACHED. RETURNING HOME..."
                else:
                    if not dashboard_data['warning_msg']:
                        dashboard_data['rover_status'] = "PATROL_ACTIVE"
        else:
            # Returning to Base execution
            dashboard_data['distance_traveled_km'] = round(max(0.0, dashboard_data['distance_traveled_km'] - km_increment), 3)
            dashboard_data['step_idx'] = max(0, dashboard_data['step_idx'] - 1)
            base_lat, base_lng = WAYPOINTS[dashboard_data['step_idx']]

            dashboard_data['current_lat'] = base_lat
            dashboard_data['current_lng'] = base_lng
            dashboard_data['avoiding_obstacle'] = False

            if dashboard_data['distance_traveled_km'] <= 0.0 or dashboard_data['step_idx'] <= 0:
                dashboard_data['rover_status'] = "COMPLETED"
                dashboard_data['control_state'] = "STOPPED"
                dashboard_data['returning'] = False
                dashboard_data['camera_active'] = False
                dashboard_data['warning_msg'] = "✅ SAFELY RETURNED TO HOME BASE."

    return jsonify(dashboard_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
