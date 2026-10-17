"""
Sound & Raindrop Monitor - Raspberry Pi 4B version (GPIO, no Pico needed)

Wiring (use 3.3V, not 5V):
  Sound sensor  DO -> GPIO17 (pin 11)   VCC -> 3V3 (pin 1)   GND -> GND (pin 6)
  Rain sensor   DO -> GPIO27 (pin 13)   VCC -> 3V3 (pin 17)  GND -> GND (pin 9)
  Buzzer        +  -> GPIO22 (pin 15)   -   -> GND (pin 14)

Run:   python3 app.py
Open:  http://localhost:5000
       landing page = /     dashboard = /dashboard
"""
import os
import socket
import threading
import time
from collections import deque

from flask import Flask, jsonify, render_template, request
from gpiozero import Buzzer, DigitalInputDevice

# ---------------- Settings ----------------
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))
HISTORY_SIZE = 120            # readings kept for the charts
SOUND_ALERT_PERCENT = 5       # buzzer beeps at/above this sound level (0-100)
RAIN_THRESHOLD_PERCENT = 30   # wetness at/above this = "raining"
OFFLINE_AFTER_SECONDS = 5     # no reading for this long = sensor offline

# ---------------- Hardware ----------------
sound_pin = DigitalInputDevice(17, pull_up=True)   # is_active = True when DO is LOW
rain_pin = DigitalInputDevice(27, pull_up=True)
buzzer = Buzzer(22)

# ---------------- Shared state ----------------
history = deque(maxlen=HISTORY_SIZE)
state = {"buzzer_enabled": True, "buzzer_on": False, "last_seen": 0.0}
lock = threading.Lock()

app = Flask(_name_)


def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def handle_reading(sound, wetness):
    """Store a reading and return True if the buzzer should be on."""
    raining = wetness >= RAIN_THRESHOLD_PERCENT
    alert = raining or sound >= SOUND_ALERT_PERCENT
    with lock:
        state["last_seen"] = time.time()
        state["buzzer_on"] = alert and state["buzzer_enabled"]
        history.append({
            "time": time.strftime("%H:%M:%S"),
            "sound": sound,
            "wetness": wetness,
            "raining": raining,
        })
        return state["buzzer_on"]


def sensor_loop():
    """Background thread: read the sensors, control the buzzer."""
    while True:
        # sound: how many times it detected in 100 samples (~0.1s) = 0-100
        hits = 0
        for _ in range(100):
            if sound_pin.is_active:
                hits += 1
            time.sleep(0.001)
        sound = float(hits)

        # rain: digital only, so 100 when wet, 0 when dry
        wetness = 100.0 if rain_pin.is_active else 0.0

        if handle_reading(sound, wetness):
            buzzer.on()
        else:
            buzzer.off()

        time.sleep(0.4)


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/data")
def api_data():
    with lock:
        connected = (time.time() - state["last_seen"]) < OFFLINE_AFTER_SECONDS
        return jsonify({
            "history": list(history),
            "connected": connected,
            "buzzer_enabled": state["buzzer_enabled"],
            "buzzer_on": state["buzzer_on"] and connected,
            "sound_alert": SOUND_ALERT_PERCENT,
            "rain_threshold": RAIN_THRESHOLD_PERCENT,
        })


@app.route("/api/buzzer", methods=["POST"])
def api_buzzer():
    with lock:
        state["buzzer_enabled"] = bool((request.get_json(silent=True) or {}).get("enabled", True))
        if not state["buzzer_enabled"]:
            state["buzzer_on"] = False
    return jsonify(ok=True, buzzer_enabled=state["buzzer_enabled"])


if _name_ == "_main_":
    threading.Thread(target=sensor_loop, daemon=True).start()
    print(f"\nDashboard on this computer:  http://localhost:{PORT}/dashboard")
    if HOST == "0.0.0.0":
        print(f"From another device (same Wi-Fi): http://{get_local_ip()}:{PORT}/dashboard\n", flush=True)
    # debug is off on purpose: the reloader would start the sensor thread twice
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
