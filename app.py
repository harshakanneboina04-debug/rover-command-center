import os
import random
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Precise GPS coordinates strictly along Venkatapur Road (Anurag Univ -> Venkatapur Rd -> Highway)
WAYPOINTS = [
    (17.4210, 78.6560), # Start: Anurag University Entrance
    (17.4211, 78.6545), # Venkatapur Rd
    (17.4212, 78.6530), # Venkatapur Rd
    (17.4213, 78.6515), # Venkatapur Rd (South of lake)
    (17.4214, 78.6500), # Venkatapur Rd
    (17.4215, 78.6485), # Venkatapur Rd
    (17.4218, 78.6470), # Venkatapur Rd (Near Suprabhat Colony)
    (17.4223, 78.6455), # Venkatapur Rd Curve
    (17.4230, 78.6442), # Venkatapur Rd
    (17.4238, 78.6428), # Venkatapur Rd
    (17.4248, 78.6410), # Towards Highway Junction
    (17.4260, 78.6390), # Highway Feeder
    (17.4275, 78.6365)  # Hyderabad-Janagam Highway Junction
]

dashboard_data = {
    "rover_status": "READY",
    "control_state": "STOPPED",
    "target_km": 10.0,
    "distance_traveled_km": 0.0,
    "total_potholes": 0,
    "total_material_kg": 0.0,
    "current_lat": 17.4210,
    "current_lng": 78.6560,
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
            dashboard_data['current_lat'] = 17.4210
            dashboard_data['current_lng'] = 78.6560
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
        km_increment = round(target_km / 30.0, 3)

        dashboard_data['battery_pct'] = max(0.0, round(dashboard_data['battery_pct'] - round(random.uniform(1.5, 2.8), 1), 1))

        if not dashboard_data['returning']:
            if dashboard_data['battery_pct'] <= 20.0:
                dashboard_data['returning'] = True
                dashboard_data['warning_msg'] = "⚠️ LOW BATTERY DETECTED (<20%)! RETURNING HOME..."
                dashboard_data['rover_status'] = "AUTO_RETURNING"
            elif dashboard_data['material_level_pct'] <= 15.0:
                dashboard_data['returning'] = True
                dashboard_data['warning_msg'] = "⚠️ LOW MATERIAL LEVEL (<15%)! RETURNING HOME..."
                dashboard_data['rover_status'] = "AUTO_RETURNING"
            else:
                obstacle_ahead = random.choice([False, False, True, False])
                dashboard_data['step_idx'] = min(dashboard_data['step_idx'] + 1, len(WAYPOINTS) - 1)
                base_lat, base_lng = WAYPOINTS[dashboard_data['step_idx']]

                if obstacle_ahead:
                    dashboard_data['avoiding_obstacle'] = True
                    dashboard_data['warning_msg'] = "⚠️ OBSTACLE DETECTED ON VENKATAPUR RD! BYPASSING..."
                    dashboard_data['current_lat'] = round(base_lat + 0.00008, 5)
                    dashboard_data['current_lng'] = round(base_lng - 0.00005, 5)
                else:
                    dashboard_data['avoiding_obstacle'] = False
                    if not dashboard_data['warning_msg'].startswith("⚠️ LOW"):
                        dashboard_data['warning_msg'] = ""
                    dashboard_data['current_lat'] = base_lat
                    dashboard_data['current_lng'] = base_lng

                dashboard_data['distance_traveled_km'] = round(dashboard_data['distance_traveled_km'] + km_increment, 3)

                # Record pothole detections with full metadata
                if random.choice([True, False, False]):
                    mat = round(random.uniform(0.3, 0.8), 2)
                    dashboard_data['total_potholes'] += 1
                    dashboard_data['total_material_kg'] = round(dashboard_data['total_material_kg'] + mat, 2)
                    dashboard_data['material_level_pct'] = max(0.0, round(dashboard_data['material_level_pct'] - round(mat * 6, 1), 1))
                    
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
                    dashboard_data['warning_msg'] = "ℹ️ TARGET REACHED. RETURNING HOME ALONG VENKATAPUR RD..."
                else:
                    if not dashboard_data['warning_msg']:
                        dashboard_data['rover_status'] = "PATROL_ACTIVE"
        else:
            # RETURNING MODE: Treat previously recorded potholes as obstacles
            dashboard_data['distance_traveled_km'] = round(max(0.0, dashboard_data['distance_traveled_km'] - km_increment), 3)
            dashboard_data['step_idx'] = max(0, dashboard_data['step_idx'] - 1)
            base_lat, base_lng = WAYPOINTS[dashboard_data['step_idx']]

            # Check if current step index has a recorded pothole
            recorded_potholes = [d['step'] for d in dashboard_data['detections']]
            if dashboard_data['step_idx'] in recorded_potholes:
                # Bypass maneuver around pothole obstacle
                dashboard_data['avoiding_obstacle'] = True
                dashboard_data['warning_msg'] = f"⚠️ POTHOLE OBSTACLE DETECTED AT STEP {dashboard_data['step_idx']}! DETOURING..."
                dashboard_data['current_lat'] = round(base_lat + 0.00010, 5)
                dashboard_data['current_lng'] = round(base_lng - 0.00008, 5)
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
