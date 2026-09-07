import os
import random
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# Exact waypoints tracing your drawn red path (Anurag Univ -> Lake Curve -> Highway)
WAYPOINTS = [
    (17.4208, 78.6562), # Start: Near Anurag University entrance
    (17.4211, 78.6540), # Venkatapur Rd (South of lake)
    (17.4213, 78.6515), # Curve along lake bottom
    (17.4215, 78.6490), # Venkatapur Rd
    (17.4218, 78.6465), # Near Suprabhat Colony bend
    (17.4228, 78.6440), # Curving Northwest
    (17.4242, 78.6415), # Heading towards Highway
    (17.4260, 78.6385), # Westbound road section
    (17.4280, 78.6350)  # End: Junction with Hyderabad-Janagam Highway
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
        if dashboard_data['rover_status'] in ['READY', 'COMPLETED', 'STOPPED']:
            dashboard_data['rover_status'] = 'PATROL_ACTIVE'
    elif cmd == 'PAUSE':
        dashboard_data['control_state'] = 'PAUSED'
        dashboard_data['rover_status'] = 'PATROL_PAUSED'
    elif cmd == 'STOP':
        if dashboard_data['step_idx'] > 0:
            dashboard_data['control_state'] = 'RUNNING'
            dashboard_data['returning'] = True
            dashboard_data['rover_status'] = 'ABORT_RETURNING'
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
        
    return jsonify({"status": "success", "control_state": dashboard_data['control_state']})

@app.route('/api/telemetry', methods=['GET'])
def handle_telemetry():
    if dashboard_data['control_state'] == 'RUNNING':
        target_km = dashboard_data['target_km']
        
        # Reduced step increment so the machine moves slowly along the curve
        km_increment = round(target_km / 25.0, 3)

        if not dashboard_data['returning']:
            dashboard_data['avoiding_obstacle'] = False
            dashboard_data['distance_traveled_km'] = round(dashboard_data['distance_traveled_km'] + km_increment, 3)
            dashboard_data['step_idx'] = min(dashboard_data['step_idx'] + 1, len(WAYPOINTS) - 1)
            curr_lat, curr_lng = WAYPOINTS[dashboard_data['step_idx']]

            dashboard_data['current_lat'] = curr_lat
            dashboard_data['current_lng'] = curr_lng

            # Pothole detection logic along red road path
            if random.choice([True, False, False]):
                mat = round(random.uniform(0.3, 0.8), 2)
                dashboard_data['total_potholes'] += 1
                dashboard_data['total_material_kg'] = round(dashboard_data['total_material_kg'] + mat, 2)
                dashboard_data['detections'].append({"lat": curr_lat, "lng": curr_lng, "mat": mat, "step": dashboard_data['step_idx']})

            if dashboard_data['distance_traveled_km'] >= target_km or dashboard_data['step_idx'] >= len(WAYPOINTS) - 1:
                dashboard_data['distance_traveled_km'] = target_km
                dashboard_data['returning'] = True
                dashboard_data['rover_status'] = "RETURNING_TO_BASE"
            else:
                dashboard_data['rover_status'] = "PATROL_ACTIVE"
        else:
            dashboard_data['distance_traveled_km'] = round(max(0.0, dashboard_data['distance_traveled_km'] - km_increment), 3)
            dashboard_data['step_idx'] = max(0, dashboard_data['step_idx'] - 1)
            base_lat, base_lng = WAYPOINTS[dashboard_data['step_idx']]

            recorded_steps = [d['step'] for d in dashboard_data['detections']]
            if dashboard_data['step_idx'] in recorded_steps:
                dashboard_data['current_lat'] = round(base_lat + 0.0001, 5)
                dashboard_data['current_lng'] = base_lng
                dashboard_data['avoiding_obstacle'] = True
            else:
                dashboard_data['current_lat'] = base_lat
                dashboard_data['current_lng'] = base_lng
                dashboard_data['avoiding_obstacle'] = False

            if dashboard_data['distance_traveled_km'] <= 0.0 or dashboard_data['step_idx'] <= 0:
                dashboard_data['rover_status'] = "COMPLETED"
                dashboard_data['control_state'] = "STOPPED"
                dashboard_data['returning'] = False
                dashboard_data['camera_active'] = False

    return jsonify(dashboard_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
