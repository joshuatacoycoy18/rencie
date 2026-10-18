from flask import Flask, render_template, jsonify
import threading
import time
import random

# Hardware Libraries
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
    "sound_history": [],
    "rain_history": [],
    "buzzer_active": False
}

def read_sensors():
    while True:
        if HARDWARE_AVAILABLE:
            # Usually, these sensors output LOW (0) when triggered
            sound_state = GPIO.input(SOUND_PIN) == GPIO.LOW
            rain_state = GPIO.input(RAIN_PIN) == GPIO.LOW
        else:
            # MOCK DATA for testing without hardware
            sound_state = random.random() > 0.8  # 20% chance may tunog
            rain_state = random.random() > 0.9   # 10% chance may ulan

        sensor_data["sound_detected"] = sound_state
        sensor_data["rain_detected"] = rain_state
        
        # Buzzer Logic (Additional Task): Tumunog kung may sound o rain
        if sound_state or rain_state:
            sensor_data["buzzer_active"] = True
            if HARDWARE_AVAILABLE:
                GPIO.output(BUZZER_PIN, True)
        else:
            sensor_data["buzzer_active"] = False
            if HARDWARE_AVAILABLE:
                GPIO.output(BUZZER_PIN, False)

        # I-save sa history para sa graph (1 kung detected, 0 kung wala)
        sensor_data["sound_history"].append(1 if sound_state else 0)
        sensor_data["rain_history"].append(1 if rain_state else 0)
        
        # Limitahan ang history para hindi bumigat
        if len(sensor_data["sound_history"]) > 50:
            sensor_data["sound_history"].pop(0)
            sensor_data["rain_history"].pop(0)

        time.sleep(1) # Update every 1 second

# Start reading sensors in background
thread = threading.Thread(target=read_sensors, daemon=True)
thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_sensors')
def get_sensors():
    return jsonify(sensor_data)

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        if HARDWARE_AVAILABLE:
            GPIO.cleanup()
