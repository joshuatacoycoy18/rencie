from flask import Flask, render_template, jsonify, request
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
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        GPIO.setup(SOUND_PIN, GPIO.IN)
        GPIO.setup(RAIN_PIN, GPIO.IN)
        GPIO.setup(BUZZER_PIN, GPIO.OUT)
        print("[OK] Hardware initialized (Sound, Rain, Buzzer)")
    except Exception as e:
        print(f"[ERROR] Hardware init failed: {e}")

# Global Data Structure (Naka-format na para sa iyong HTML)
sensor_data = {
    "connected": True,
    "sound_alert": 70,       # Threshold para sa Sound
    "rain_threshold": 30,    # Threshold para sa Rain
    "buzzer_enabled": True,  # Naka-ON ba ang buzzer sa web UI?
    "buzzer_on": False,      # Tumatunog ba ang buzzer ngayon?
    "history": []            # Dito natin i-save ang logs para sa charts
}

def read_sensors():
    while True:
        if HARDWARE_AVAILABLE:
            # Logic: LOW (0) kapag na-detect, HIGH (1) kapag wala
            sound_state = GPIO.input(SOUND_PIN) == GPIO.LOW
            rain_state = GPIO.input(RAIN_PIN) == GPIO.LOW
        else:
            # Mock Data para sa laptop
            sound_state = random.random() > 0.8
            rain_state = random.random() > 0.9

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

        # I-save sa history para sa charts
        sensor_data["history"].append({
            "time": time.strftime("%H:%M:%S"),
            "sound": sound_val,
            "wetness": rain_val,
            "raining": rain_state
        })
        
        # Limitahan sa 50 entries para hindi bumigat
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

# Ito ang endpoint na hinahanap ng HTML mo
@app.route('/api/data')
def get_data():
    return jsonify(sensor_data)

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
