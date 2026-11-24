// ESP32 integration example. Replace Wi-Fi credentials and DEVICE_TOKEN.
// Example sensor numbers below are placeholders: connect and calibrate your actual sensors.
#include <WiFi.h>
#include <HTTPClient.h>
const char* WIFI_NAME = "YOUR_WIFI";
const char* WIFI_PASSWORD = "YOUR_PASSWORD";
const char* SERVER = "http://YOUR_COMPUTER_LAN_IP:5000/api/device/readings";
const char* DEVICE_TOKEN = "YOUR_DEVICE_TOKEN";
const int FARM_ID = 1;
void setup() {
  Serial.begin(115200);
  WiFi.begin(WIFI_NAME, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("WiFi connected");
}
void loop() {
  if (WiFi.status() == WL_CONNECTED) {
    // Replace these placeholders with calibrated sensor readings.
    float moisture = 30.0;
    float soilEC = 1.0;
    float soilTemp = 25.0;
    HTTPClient http;
    http.begin(SERVER);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("X-Device-Token", DEVICE_TOKEN);
    String body = "{\"farm_id\":1,\"zone_code\":\"A1\",\"moisture\":" + String(moisture,1) +
                  ",\"ec\":" + String(soilEC,2) + ",\"soil_temp\":" + String(soilTemp,1) + "}";
    int code = http.POST(body);
    Serial.printf("Server response: %d\n", code);
    http.end();
  }
  delay(30000);
}
