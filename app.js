// ================================================
//  HydroSmart — ESP32-S3
//  VERSION HTTP PURE — pas de WebSocket
//
//  LOGIQUE RELAIS :
//  Démarrage → LOW  → relais OFF → vanne FERMÉE
//  Vanne ON  → HIGH → relais ON  → vanne OUVERTE
//  Vanne OFF → LOW  → relais OFF → vanne FERMÉE
//
//  Bibliotheques requises :
//    - ArduinoJson        (Benoit Blanchon)
//    - DHT sensor library (Adafruit)
// ================================================

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <DHT.h>

// ── 1. RESEAU ────────────────────────────────────
#define WIFI_SSID     "OPPO"
#define WIFI_PASSWORD "1234567801"

// ── 2. SERVEUR ───────────────────────────────────
#define SERVER_URL  "https://hydrosmart-groupe-iot.fly.dev"
#define API_KEY     "hydrosmart-esp32-key-2024"

// ── 3. BROCHES ESP32-S3 ──────────────────────────
#define DHTPIN     4
#define DHTTYPE    DHT22
#define SOIL_PIN   34
#define VALVE1_PIN 2
#define VALVE2_PIN 14

// ── Objets globaux ───────────────────────────────
DHT dht(DHTPIN, DHTTYPE);
WiFiClientSecure secureClient;

// ── Etat vannes ──────────────────────────────────
bool v1 = false;
bool v2 = false;

// ── Timers ───────────────────────────────────────
unsigned long tSensor  = 0;
unsigned long tCommand = 0;

// ================================================
//  HELPER RELAIS
//  true  → HIGH → relais ON  → vanne OUVERTE
//  false → LOW  → relais OFF → vanne FERMÉE
// ================================================
void setValve(int pin, bool state) {
  digitalWrite(pin, state ? HIGH : LOW);
}

// ================================================
//  SETUP
// ================================================
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n🌿 HydroSmart ESP32 — HTTP PURE");

  // ── Broches relais en sortie ──
  pinMode(VALVE1_PIN, OUTPUT);
  pinMode(VALVE2_PIN, OUTPUT);

  // ── Démarrage : LOW → relais OFF → vannes FERMÉES ──
  digitalWrite(VALVE1_PIN, LOW);
  digitalWrite(VALVE2_PIN, LOW);
  Serial.println("🔌 Init: LOW → relais OFF → vannes FERMEES");

  dht.begin();

  // Connexion WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connexion WiFi");
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries++ < 40) {
    delay(500);
    Serial.print(".");
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n❌ WiFi echoue — reboot dans 3s");
    delay(3000);
    ESP.restart();
  }
  Serial.println("\n✅ WiFi OK — IP: " + WiFi.localIP().toString());

  // Accepter tous les certificats SSL
  secureClient.setInsecure();
}

// ================================================
//  LOOP
// ================================================
void loop() {
  // Reconnexion WiFi si perdu
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("⚠️ WiFi perdu — reconnexion...");
    WiFi.reconnect();
    delay(3000);
    return;
  }

  // ── Capteurs toutes les 2s ──
  if (millis() - tSensor > 2000 || tSensor == 0) {
    tSensor = millis();

    float h = dht.readHumidity();
    float t = dht.readTemperature();

    int raw  = analogRead(SOIL_PIN);
    Serial.printf("🌱 RAW sol: %d\n", raw);
    // sec ≈ 4095 → 0%  |  mouillé ≈ 1200 → 100%
    int soil = constrain(map(raw, 4095, 1200, 0, 100), 0, 100);

    if (!isnan(h) && !isnan(t)) {
      sendSensors(t, h, soil);
    } else {
      Serial.println("⚠️ DHT22 erreur lecture");
    }
  }

  // ── Polling commandes toutes les 800ms ──
  if (millis() - tCommand > 800 || tCommand == 0) {
    tCommand = millis();
    pollCommands();
  }
}

// ================================================
//  HTTP — envoi capteurs
// ================================================
void sendSensors(float temp, float hum, int soil) {
  HTTPClient http;
  http.begin(secureClient, String(SERVER_URL) + "/api/sensors");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("x-api-key", API_KEY);
  http.setTimeout(8000);

  StaticJsonDocument<128> doc;
  doc["temp"] = temp;
  doc["hum"]  = hum;
  doc["soil"] = soil;
  String body;
  serializeJson(doc, body);

  int code = http.POST(body);
  if (code == 200)
    Serial.printf("📡 OK  T=%.1f°C  H=%.1f%%  Sol=%d%%\n", temp, hum, soil);
  else
    Serial.println("❌ /api/sensors HTTP " + String(code));
  http.end();
}

// ================================================
//  HTTP — polling commandes
// ================================================
void pollCommands() {
  HTTPClient http;
  http.begin(secureClient, String(SERVER_URL) + "/api/commands");
  http.addHeader("x-api-key", API_KEY);
  http.setTimeout(8000);

  int code = http.GET();
  if (code == 200) {
    StaticJsonDocument<128> doc;
    DeserializationError err = deserializeJson(doc, http.getString());
    if (!err) {
      bool nv1 = doc["sw1"] | false;
      bool nv2 = doc["sw2"] | false;

      // Vanne 1 changement ?
      if (nv1 != v1) {
        v1 = nv1;
        setValve(VALVE1_PIN, v1);
        Serial.printf("🚿 V1 %s → PIN %s\n", v1?"ON":"OFF", v1?"HIGH":"LOW");
        sendFeedback();
      }

      // Vanne 2 changement ?
      if (nv2 != v2) {
        v2 = nv2;
        setValve(VALVE2_PIN, v2);
        Serial.printf("🚿 V2 %s → PIN %s\n", v2?"ON":"OFF", v2?"HIGH":"LOW");
        sendFeedback();
      }
    }
  } else {
    Serial.println("❌ /api/commands HTTP " + String(code));
  }
  http.end();
}

// ================================================
//  HTTP — feedback état vannes
// ================================================
void sendFeedback() {
  HTTPClient http;
  http.begin(secureClient, String(SERVER_URL) + "/api/valve-feedback");
  http.addHeader("Content-Type", "application/json");
  http.addHeader("x-api-key", API_KEY);
  http.setTimeout(8000);

  StaticJsonDocument<64> doc;
  doc["v1"] = v1;
  doc["v2"] = v2;
  String body;
  serializeJson(doc, body);

  int code = http.POST(body);
  Serial.printf("📤 Feedback: V1=%d V2=%d → HTTP %d\n", v1, v2, code);
  http.end();
}
