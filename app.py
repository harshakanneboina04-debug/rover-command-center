import os
import random
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# State storage
dashboard_data = {
    "rover_status": "READY",
    "control_state": "STOPPED",
    "target_km": 0.05,
    "distance_traveled_km": 0.0,
    "total_potholes": 0,
    "total_material_kg": 0.0,
    "current_lat": 17.3850,
    "current_lng": 78.4867,
    "step_idx": 0,
    "returning": False,
    "detections": []
}

WAYPOINTS = [
    (17.3850, 78.4867), (17.3851, 78.4869), (17.3852, 78.4871), 
    (17.3853, 78.4873), (17.3854, 78.4875), (17.3855, 78.4877),
    (17.3856, 78.4879), (17.3857, 78.4881), (17.3858, 78.4883)
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['POST'])
def handle_config():
    data = request.json or {}
    dashboard_data['target_km'] = float(data.get('target_km', 0.05))
    return jsonify({"status": "success", "target_km": dashboard_data['target_km']})

@app.route('/api/control', methods=['POST'])
def handle_control():
    data = request.json or {}
    cmd = data.get('command')
    
    if cmd == 'START':
        dashboard_data['control_state'] = 'RUNNING'
        if dashboard_data['rover_status'] in ['READY', 'COMPLETED', 'STOPPED']:
            dashboard_data['rover_status'] = 'PATROL_ACTIVE'
    elif cmd == 'PAUSE':
        dashboard_data['control_state'] = 'PAUSED'
        dashboard_data['rover_status'] = 'PATROL_PAUSED'
    elif cmd == 'STOP':
        dashboard_data['control_state'] = 'STOPPED'
        dashboard_data['rover_status'] = 'STOPPED'
        dashboard_data['distance_traveled_km'] = 0.0
        dashboard_data['total_potholes'] = 0
        dashboard_data['total_material_kg'] = 0.0
        dashboard_data['detections'] = []
        dashboard_data['current_lat'] = 17.3850
        dashboard_data['current_lng'] = 78.4867
        dashboard_data['step_idx'] = 0
        dashboard_data['returning'] = False
        
    return jsonify({"status": "success", "control_state": dashboard_data['control_state']})

@app.route('/api/telemetry', methods=['GET'])
def handle_telemetry():
    if dashboard_data['control_state'] == 'RUNNING':
        target_km = dashboard_data['target_km']
        km_increment = round(target_km / 8.0, 3)

        if not dashboard_data['returning']:
            dashboard_data['distance_traveled_km'] = round(dashboard_data['distance_traveled_km'] + km_increment, 3)
            dashboard_data['step_idx'] = min(dashboard_data['step_idx'] + 1, len(WAYPOINTS) - 1)
            curr_lat, curr_lng = WAYPOINTS[dashboard_data['step_idx']]

            dashboard_data['current_lat'] = curr_lat
            dashboard_data['current_lng'] = curr_lng

            # Pothole repair logic
            if random.choice([True, False]):
                mat = round(random.uniform(0.3, 0.8), 2)
                dashboard_data['total_potholes'] += 1
                dashboard_data['total_material_kg'] = round(dashboard_data['total_material_kg'] + mat, 2)
                dashboard_data['detections'].append({"lat": curr_lat, "lng": curr_lng, "mat": mat})

            if dashboard_data['distance_traveled_km'] >= target_km or dashboard_data['step_idx'] >= len(WAYPOINTS) - 1:
                dashboard_data['distance_traveled_km'] = target_km
                dashboard_data['returning'] = True
                dashboard_data['rover_status'] = "RETURNING_TO_BASE"
            else:
                dashboard_data['rover_status'] = "PATROL_ACTIVE"
        else:
            dashboard_data['distance_traveled_km'] = round(max(0.0, dashboard_data['distance_traveled_km'] - km_increment), 3)
            dashboard_data['step_idx'] = max(0, dashboard_data['step_idx'] - 1)
            curr_lat, curr_lng = WAYPOINTS[dashboard_data['step_idx']]

            dashboard_data['current_lat'] = curr_lat
            dashboard_data['current_lng'] = curr_lng

            if dashboard_data['distance_traveled_km'] <= 0.0 or dashboard_data['step_idx'] <= 0:
                dashboard_data['rover_status'] = "COMPLETED"
                dashboard_data['control_state'] = "STOPPED"

    return jsonify(dashboard_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
