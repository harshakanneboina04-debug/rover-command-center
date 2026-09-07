import sys
import os
import cv2
import time
import random
import numpy as np
from flask import Flask, render_template, request, jsonify, Response

if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    app = Flask(__name__, template_folder=template_folder)
else:
    app = Flask(__name__)

# System State Storage
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
    "step_idx": 0,
    "returning": False,
    "detections": []
}

WAYPOINTS = [
    (17.3850, 78.4867), (17.3851, 78.4869), (17.3852, 78.4871), 
    (17.3853, 78.4873), (17.3854, 78.4875), (17.3855, 78.4877),
    (17.3856, 78.4879), (17.3857, 78.4881), (17.3858, 78.4883)
]

# Camera initialization with safety checks
try:
    camera = cv2.VideoCapture(0)
except Exception:
    camera = None

def generate_video_frames():
    frame_count = 0
    while True:
        success = False
        frame = None

        if camera is not None and camera.isOpened():
            success, frame = camera.read()

        # Cloud Fallback Stream
        if not success or frame is None:
            time.sleep(0.06)
            frame_count += 1
            frame = np.zeros((360, 640, 3), dtype=np.uint8)
            frame[:] = (20, 25, 35)

            # Simulated road lanes
            offset = (frame_count * 8) % 80
            cv2.line(frame, (200, 360), (300, 0), (100, 100, 100), 2)
            cv2.line(frame, (440, 360), (340, 0), (100, 100, 100), 2)

            for y in range(0, 360, 80):
                line_y = (y + offset) % 360
                cv2.line(frame, (320, line_y), (320, min(line_y + 40, 360)), (0, 215, 255), 3)

            status = dashboard_data['rover_status']
            dist = dashboard_data['distance_traveled_km']
            cv2.putText(frame, "CLOUD CAMERA FEED (ONLINE)", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
            cv2.putText(frame, f"STATUS: {status}", (20, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
            cv2.putText(frame, f"COVERAGE: {dist} KM", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            if status == "PATROL_ACTIVE" and frame_count % 30 < 15:
                cv2.rectangle(frame, (220, 180), (420, 280), (0, 0, 255), 2)
                cv2.putText(frame, "POTHOLE DETECTED [94%]", (220, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(generate_video_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/api/config', methods=['POST'])
def handle_config():
    data = request.json
    dashboard_data['target_km'] = float(data.get('target_km', 0.05))
    return jsonify({"status": "success", "target_km": dashboard_data['target_km']})

@app.route('/api/control', methods=['POST'])
def handle_control():
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
        dashboard_data['step_idx'] = 0
        dashboard_data['returning'] = False
    
    return jsonify({"status": "success", "control_state": dashboard_data['control_state']})

# Browser-Triggered Movement Engine (Guarantees movement on cloud links)
@app.route('/api/telemetry', methods=['GET'])
def handle_telemetry():
    if dashboard_data['control_state'] == 'RUNNING':
        target_km = dashboard_data['target_km']
        km_increment = round(target_km / 12.0, 3)

        if not dashboard_data['returning']:
            dashboard_data['distance_traveled_km'] = round(dashboard_data['distance_traveled_km'] + km_increment, 3)
            dashboard_data['step_idx'] = min(dashboard_data['step_idx'] + 1, len(WAYPOINTS) - 1)
            curr_lat, curr_lng = WAYPOINTS[dashboard_data['step_idx']]

            dashboard_data['current_lat'] = curr_lat
            dashboard_data['current_lng'] = curr_lng

            if dashboard_data['distance_traveled_km'] >= target_km:
                dashboard_data['distance_traveled_km'] = target_km
                dashboard_data['returning'] = True
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
            dashboard_data['step_idx'] = max(0, dashboard_data['step_idx'] - 1)
            curr_lat, curr_lng = WAYPOINTS[dashboard_data['step_idx']]

            dashboard_data['current_lat'] = curr_lat
            dashboard_data['current_lng'] = curr_lng

            if dashboard_data['distance_traveled_km'] <= 0.0 or dashboard_data['step_idx'] <= 0:
                dashboard_data['rover_status'] = "COMPLETED"
                dashboard_data['control_state'] = "STOPPED"

    return jsonify(dashboard_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)