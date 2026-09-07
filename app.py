import sys
import os
import cv2
import time
import random
import threading
from flask import Flask, render_template, request, jsonify, Response

if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    app = Flask(__name__, template_folder=template_folder)
else:
    app = Flask(__name__)

dashboard_data = {
    "total_potholes": 0,
    "battery_pct": 100,
    "network_signal": "Strong (4G)",
    "total_material_kg": 0.0,
    "last_completion_time_sec": 0.0,
    "rover_status": "READY",
    "control_state": "STOPPED",
    "target_km": 0.05,
    "distance_traveled_km": 0.0,
    "current_lat": 17.3850,
    "current_lng": 78.4867,
    "detections": []
}

WAYPOINTS = [
    (17.3850, 78.4867), (17.3851, 78.4869), (17.3852, 78.4871), 
    (17.3853, 78.4873), (17.3854, 78.4875), (17.3855, 78.4877),
    (17.3856, 78.4879), (17.3857, 78.4881), (17.3858, 78.4883)
]

camera = cv2.VideoCapture(0)

# Movement Simulation Engine Thread (Slowing down the machine pace)
def rover_simulation_loop():
    global dashboard_data
    step_idx = 0
    returning = False

    while True:
        # Pacing Delay: 1.2s sleep slows movement down to a steady, realistic speed
        time.sleep(1.2)

        if dashboard_data['control_state'] != 'RUNNING':
            if dashboard_data['control_state'] == 'STOPPED':
                step_idx = 0
                returning = False
            continue

        target_km = float(dashboard_data['target_km'])
        km_increment = round(target_km / 12.0, 3)

        if not returning:
            dashboard_data['distance_traveled_km'] = round(dashboard_data['distance_traveled_km'] + km_increment, 3)
            step_idx = min(step_idx + 1, len(WAYPOINTS) - 1)
            curr_lat, curr_lng = WAYPOINTS[step_idx]

            dashboard_data['current_lat'] = curr_lat
            dashboard_data['current_lng'] = curr_lng

            if dashboard_data['distance_traveled_km'] >= target_km:
                dashboard_data['distance_traveled_km'] = target_km
                returning = True
                dashboard_data['rover_status'] = "RETURNING_TO_START"
            else:
                dashboard_data['rover_status'] = "PATROL_ACTIVE"
                if random.choice([True, False, False]):
                    cement_used = round((random.randint(250, 500) * 2.0) / 1000.0, 2)
                    dashboard_data['total_potholes'] += 1
                    dashboard_data['total_material_kg'] = round(dashboard_data['total_material_kg'] + cement_used, 2)
                    dashboard_data['last_completion_time_sec'] = round(random.uniform(1.8, 3.5), 1)
                    dashboard_data['detections'].append({"lat": curr_lat, "lng": curr_lng, "cement_used_kg": cement_used})
        else:
            dashboard_data['distance_traveled_km'] = round(max(0.0, dashboard_data['distance_traveled_km'] - km_increment), 3)
            step_idx = max(0, step_idx - 1)
            curr_lat, curr_lng = WAYPOINTS[step_idx]

            dashboard_data['current_lat'] = curr_lat
            dashboard_data['current_lng'] = curr_lng

            if dashboard_data['distance_traveled_km'] <= 0.0 or step_idx <= 0:
                dashboard_data['rover_status'] = "COMPLETED"
                dashboard_data['control_state'] = "STOPPED"

threading.Thread(target=rover_simulation_loop, daemon=True).start()

def generate_video_frames():
    while True:
        success, frame = camera.read()
        if not success:
            # Fallback black frame if no camera is plugged in
            frame = cv2.imread('fallback.jpg') if os.path.exists('fallback.jpg') else None
            if frame is None:
                time.sleep(0.1)
                continue

        text = f"MODE: {dashboard_data['rover_status']} | DIST: {dashboard_data['distance_traveled_km']} KM"
        cv2.putText(frame, text, (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_video_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    global dashboard_data
    if request.method == 'POST':
        data = request.json
        dashboard_data['target_km'] = data.get('target_km', 0.05)
        return jsonify({"status": "success", "target_km": dashboard_data['target_km']})
    return jsonify({"target_km": dashboard_data['target_km']})

@app.route('/api/control', methods=['POST'])
def handle_control():
    global dashboard_data
    cmd = request.json.get('command')
    if cmd == 'START':
        dashboard_data['control_state'] = 'RUNNING'
        if dashboard_data['rover_status'] in ['READY', 'COMPLETED', 'STOPPED']:
            dashboard_data['rover_status'] = 'PATROL_ACTIVE'
    elif cmd == 'PAUSE':
        dashboard_data['control_state'] = 'PAUSED'
    elif cmd == 'STOP':
        dashboard_data['control_state'] = 'STOPPED'
        dashboard_data['rover_status'] = 'STOPPED'
        dashboard_data['distance_traveled_km'] = 0.0
        dashboard_data['total_potholes'] = 0
        dashboard_data['total_material_kg'] = 0.0
        dashboard_data['detections'] = []
        dashboard_data['current_lat'] = 17.3850
        dashboard_data['current_lng'] = 78.4867
    
    return jsonify({"status": "success", "control_state": dashboard_data['control_state']})

@app.route('/api/telemetry', methods=['GET'])
def handle_telemetry():
    return jsonify(dashboard_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)