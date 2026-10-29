#include <WiFi.h>
#include <HTTPClient.h>

// Wire sensor AO pins to GPIO 34/35 and connect all grounds together.
// Power the sensor modules at 3.3 V so their AO outputs stay safe for the ESP32.
const char* WIFI_SSID = "HUAWEI-5G-pT4w";
const char* WIFI_PASSWORD = "tacoycoyfamily";
const char* SERVER_URL = "http://192.168.137.156:5000/api/sensors";

// For a classic ESP32 DevKit, GPIO 34 and 35 are ADC input pins.
const int RAIN_PIN = 34;
const int SOUND_PIN = 35;

// Calibrate these after checking the raw ADC values in Serial Monitor.
// Set each pair to the readings observed at 0% and 100%.
const int RAIN_DRY_ADC = 4095;
const int RAIN_WET_ADC = 0;
const int SOUND_QUIET_RANGE = 10;
const int SOUND_LOUD_RANGE = 800;

int toPercent(int value, int atZero, int atHundred) {
  if (atZero == atHundred) {
    return 0;
  }

  long percent = (long)(value - atZero) * 100 / (atHundred - atZero);
  return constrain(percent, 0, 100);
}

int readRainAdc() {
  long total = 0;
  for (int i = 0; i < 10; i++) {
    total += analogRead(RAIN_PIN);
    delay(5);
  }
  return total / 10;
}

int readSoundRange() {
  int minimum = 4095;
  int maximum = 0;
  unsigned long startedAt = millis();

  while (millis() - startedAt < 40) {
    int sample = analogRead(SOUND_PIN);
    if (sample < minimum) minimum = sample;
    if (sample > maximum) maximum = sample;
  }

  return maximum - minimum;
}

void connectToWifi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected. ESP32 IP: ");
  Serial.println(WiFi.localIP());
}

void setup() {
  Serial.begin(115200);
  analogReadResolution(12);
  connectToWifi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    WiFi.reconnect();
    delay(1000);
    return;
  }

  int rainAdc = readRainAdc();
  int soundRange = readSoundRange();
  int wetness = toPercent(rainAdc, RAIN_DRY_ADC, RAIN_WET_ADC);
  int sound = toPercent(soundRange, SOUND_QUIET_RANGE, SOUND_LOUD_RANGE);

  Serial.printf(
    "Rain ADC: %d, sound range: %d, wetness: %d%%, sound: %d%%\n",
    rainAdc, soundRange, wetness, sound
  );

  HTTPClient http;
  http.setTimeout(2000);
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");

  String payload = "{\"wetness\":" + String(wetness) +
                   ",\"sound\":" + String(sound) + "}";
  int responseCode = http.POST(payload);
  Serial.printf("Raspberry Pi response: %d\n", responseCode);
  http.end();

  delay(1000);
}
