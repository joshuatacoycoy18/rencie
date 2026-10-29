from flask import Flask, render_template, jsonify, request
import threading
import time
import random
import math

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
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(SOUND_PIN, GPIO.IN)
        GPIO.setup(RAIN_PIN, GPIO.IN)
        GPIO.setup(BUZZER_PIN, GPIO.OUT)
        print("[OK] Hardware initialized (Sound, Rain, Buzzer)")
    except Exception as e:
        print(f"[ERROR] Hardware init failed: {e}")

# Global Data Structure (Naka-format para sa HTML/Charts)
sensor_data = {
    "connected": True,
    "sound_alert": 70,       # Threshold para sa Sound
    "rain_threshold": 30,    # Threshold para sa Rain
    "buzzer_enabled": True,  # Naka-ON ba ang buzzer sa web UI?
    "buzzer_on": False,      # Tumatunog ba ang buzzer ngayon?
    "history": []            # Dito natin i-save ang logs para sa charts
}

ESP32_TIMEOUT_SECONDS = 5
state_lock = threading.Lock()
esp32_reading = None
last_esp32_update = None
active_source = "pi"

def read_sensors():
    last_sound_trigger = 0  # <--- ITO ANG FIX: Cooldown timer para sa Sound Sensor

    while True:
        current_time = time.time()

        with state_lock:
            source = active_source
            reading = esp32_reading.copy() if esp32_reading else None
            reading_age = (
                time.monotonic() - last_esp32_update
                if last_esp32_update is not None
                else None
            )

        if source == "esp32":
            connected = (
                reading is not None
                and reading_age is not None
                and reading_age <= ESP32_TIMEOUT_SECONDS
            )
            sound_val = reading["sound"] if connected else 0
            rain_val = reading["wetness"] if connected else 0
            sound_state = sound_val >= sensor_data["sound_alert"]
            rain_state = rain_val >= sensor_data["rain_threshold"]
            sensor_data["connected"] = connected
        elif HARDWARE_AVAILABLE:
            # SOUND SENSOR: Basahin lang kung lumipas na ang 2 segundo mula sa huling trigger
            # Para hindi marinig ang sariling tunog ng buzzer (Feedback Loop fix)
            if current_time - last_sound_trigger > 2:
                sound_state = GPIO.input(SOUND_PIN) == GPIO.LOW
                if sound_state:
                    last_sound_trigger = current_time  # I-update ang timer
            else:
                sound_state = False  # I-ignore ang sound habang nag-cooldown

            # RAIN SENSOR: Walang cooldown dahil hindi naman ito naapektuhan ng buzzer
            rain_state = GPIO.input(RAIN_PIN) == GPIO.LOW
        else:
            # Mock Data para sa laptop
            sound_state = random.random() > 0.8
            rain_state = random.random() > 0.9

        if source != "esp32":
            sensor_data["connected"] = True
            # Convert natin sa percentage para gumana ang charts (100% kung detected, 0% kung wala)
            sound_val = 100 if sound_state else 0
            rain_val = 100 if rain_state else 0

        # Buzzer Logic
        buzzer_should_beep = (sound_state or rain_state)
        
        if sensor_data["buzzer_enabled"]:
            sensor_data["buzzer_on"] = buzzer_should_beep
            if HARDWARE_AVAILABLE:
                GPIO.output(BUZZER_PIN, buzzer_should_beep)
        else:
            sensor_data["buzzer_on"] = False
            if HARDWARE_AVAILABLE:
                GPIO.output(BUZZER_PIN, False)

        if source != "esp32" or sensor_data["connected"]:
            # I-save sa history para sa charts
            sensor_data["history"].append({
                "time": time.strftime("%H:%M:%S"),
                "sound": sound_val,
                "wetness": rain_val,
                "raining": rain_state
            })

            # Limitahan sa 50 entries para hindi bumigat ang browser
            if len(sensor_data["history"]) > 50:
                sensor_data["history"].pop(0)

        time.sleep(1)

# Start reading sensors sa background
thread = threading.Thread(target=read_sensors, daemon=True)
thread.start()

# --- ROUTES ---
@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

# Ito ang endpoint na hinahanap ng HTML mo para sa data
@app.route('/api/data')
def get_data():
    return jsonify(sensor_data)

@app.route('/api/sensors', methods=['POST'])
def receive_sensor_data():
    global esp32_reading, last_esp32_update, active_source

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object"}), 400

    sound = data.get("sound")
    wetness = data.get("wetness")
    for name, value in (("sound", sound), ("wetness", wetness)):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not 0 <= value <= 100
            or not math.isfinite(value)
        ):
            return jsonify({
                "error": f"{name} must be a number from 0 to 100"
            }), 400

    with state_lock:
        esp32_reading = {"sound": sound, "wetness": wetness}
        last_esp32_update = time.monotonic()
        active_source = "esp32"

    return jsonify({"status": "received"}), 200

# Ito ang endpoint para sa "Mute Alert" button mo
@app.route('/api/buzzer', methods=['POST'])
def toggle_buzzer():
    data = request.get_json()
    if 'enabled' in data:
        sensor_data["buzzer_enabled"] = data['enabled']
    return jsonify({"status": "success"})

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    finally:
        if HARDWARE_AVAILABLE: 
            GPIO.cleanup()
