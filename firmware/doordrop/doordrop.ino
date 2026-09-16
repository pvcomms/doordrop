// DoorDrop OTP Receptionist
// ESP32 polls Vercel endpoint for latest OTP, displays huge on OLED
// for delivery driver to read at door.

#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <ArduinoJson.h>

// ---- CONFIG ----
const char* WIFI_SSID     = "REPLACE_ME";
const char* WIFI_PASSWORD = "REPLACE_ME";
const char* OTP_URL       = "https://doordrop-otp.vercel.app/api/otp/latest";
const char* OTP_TOKEN     = "REPLACE_ME";  // Bearer token, must match server
const uint32_t POLL_MS    = 10000;
// -----------------

Adafruit_SSD1306 display(128, 64, &Wire, -1);
String currentOtp = "";
String currentLabel = "";
uint32_t lastPoll = 0;

void drawStatus(const String& msg) {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(WHITE);
  display.setCursor(0, 28);
  display.println(msg);
  display.display();
}

void drawOtp(const String& label, const String& otp) {
  display.clearDisplay();
  display.setTextColor(WHITE);

  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println(label.length() ? label : "DoorDrop");

  display.setTextSize(3);
  int16_t x1, y1; uint16_t w, h;
  display.getTextBounds(otp, 0, 0, &x1, &y1, &w, &h);
  int16_t x = (128 - w) / 2;
  display.setCursor(x < 0 ? 0 : x, 28);
  display.println(otp);
  display.display();
}

void connectWifi() {
  drawStatus("Wifi: connecting...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  uint32_t start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
    delay(250);
  }
  if (WiFi.status() == WL_CONNECTED) {
    drawStatus("Wifi: " + WiFi.localIP().toString());
  } else {
    drawStatus("Wifi: FAILED");
  }
}

void pollOtp() {
  if (WiFi.status() != WL_CONNECTED) { connectWifi(); return; }

  HTTPClient http;
  http.begin(OTP_URL);
  http.addHeader("Authorization", String("Bearer ") + OTP_TOKEN);
  int code = http.GET();
  if (code == 200) {
    String body = http.getString();
    StaticJsonDocument<512> doc;
    if (!deserializeJson(doc, body)) {
      String otp   = doc["otp"]   | "";
      String label = doc["label"] | "";
      if (otp.length() && otp != currentOtp) {
        currentOtp = otp;
        currentLabel = label;
        drawOtp(currentLabel, currentOtp);
      } else if (currentOtp.length() == 0) {
        drawStatus("Waiting for OTP...");
      }
    }
  } else if (code > 0) {
    drawStatus("HTTP " + String(code));
  } else {
    drawStatus("Net err " + String(code));
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("OLED init failed");
    while (true) delay(1000);
  }
  drawStatus("DoorDrop boot...");
  connectWifi();
  pollOtp();
  lastPoll = millis();
}

void loop() {
  if (millis() - lastPoll >= POLL_MS) {
    pollOtp();
    lastPoll = millis();
  }
  delay(50);
}
