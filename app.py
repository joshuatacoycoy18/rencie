from flask import Flask, render_template, jsonify
import threading
import time
import random

try:
    import RPi.GPIO as GPIO
    HARDWARE_AVAILABLE = True
except ImportError:
    HARDWARE_AVAILABLE = False
    print("[WARN] RPi.GPIO not found. Using Mock Mode.")

app = Flask(__name__)

# GPIO PINS
SOUND_PIN = 17
RAIN_PIN = 27
BUZZER_PIN = 23

if HARDWARE_AVAILABLE:
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    GPIO.setup(SOUND_PIN, GPIO.IN)
    GPIO.setup(RAIN_PIN, GPIO.IN)
    GPIO.setup(BUZZER_PIN, GPIO.OUT)
    print("[OK] Hardware initialized (Sound, Rain, Buzzer)")

# Global Data
sensor_data = {
    "sound_detected": False,
    "rain_detected": False,
    "sound_history": [0] * 20, # Initial empty data para may simula ang graph
    "rain_history": [0] * 20,
    "buzzer_active": False
}

def read_sensors():
    while True:
        if HARDWARE_AVAILABLE:
            sound_state = GPIO.input(SOUND_PIN) == GPIO.LOW
            rain_state = GPIO.input(RAIN_PIN) == GPIO.LOW
        else:
            sound_state = random.random() > 0.8
            rain_state = random.random() > 0.9

        sensor_data["sound_detected"] = sound_state
        sensor_data["rain_detected"] = rain_state
        
        if sound_state or rain_state:
            sensor_data["buzzer_active"] = True
            if HARDWARE_AVAILABLE: GPIO.output(BUZZER_PIN, True)
        else:
            sensor_data["buzzer_active"] = False
            if HARDWARE_AVAILABLE: GPIO.output(BUZZER_PIN, False)

        sensor_data["sound_history"].append(1 if sound_state else 0)
        sensor_data["rain_history"].append(1 if rain_state else 0)
        
        if len(sensor_data["sound_history"]) > 40:
            sensor_data["sound_history"].pop(0)
            sensor_data["rain_history"].pop(0)

        time.sleep(1)

thread = threading.Thread(target=read_sensors, daemon=True)
thread.start()

# --- ROUTES ---
@app.route('/')
def landing():
    return render_template('landing.html') # Welcome Page

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html') # Main Dashboard

@app.route('/get_sensors')
def get_sensors():
    return jsonify(sensor_data)

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        if HARDWARE_AVAILABLE: GPIO.cleanup()
