#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <algorithm>
// ========== CONFIGURATION ==========
#define ANCHOR_ID  1  // 1, 2 ou 3

#if ANCHOR_ID == 1
  #define ANCHOR_X 0.2
  #define ANCHOR_Y 0.2
#elif ANCHOR_ID == 2
  #define ANCHOR_X 0.2
  #define ANCHOR_Y 4.8
#elif ANCHOR_ID == 3
  #define ANCHOR_X 5.8
  #define ANCHOR_Y 4.8
#else
  #error "ANCHOR_ID invalide !"
#endif

// WiFi
const char* ssid = "OPPO";
const char* password = "1234567809";

// Serveur Render (WebSocket + API)
const char* websocket_server = "postcam-1.onrender.com";
const int websocket_port = 443;
const char* websocket_path = "/socket.io/?EIO=4&transport=websocket";

const unsigned long SCAN_INTERVAL = 2000;
unsigned long lastScan = 0;
WebSocketsClient webSocket;
String knownEmployees[10];
int knownCount = 0;
bool wsConnected = false;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== ESP32 Ancre #" + String(ANCHOR_ID) + " ===");
  Serial.println("Position: (" + String(ANCHOR_X) + ", " + String(ANCHOR_Y) + ")");
  // Connexion WiFi
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);
  Serial.print("Connexion WiFi");
  WiFi.begin(ssid, password);
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("\n✅ WiFi connecté");
  Serial.println("IP: " + WiFi.localIP().toString());

  // Récupérer la liste des employés
  fetchEmployees();

  delay(2000);

  // Initialiser WebSocket avec SSL
  Serial.println("Initialisation WebSocket...");
  
  // Configuration SSL pour ignorer la validation du certificat
  webSocket.beginSSL(websocket_server, websocket_port, websocket_path);
  webSocket.onEvent(webSocketEvent);
  webSocket.setReconnectInterval(5000);
  
  Serial.println("Connexion WebSocket initiée à wss://" + String(websocket_server) + websocket_path);
}

void fetchEmployees() {
  HTTPClient http;
  http.begin("https://postcam-1.onrender.com/api/employees");
  http.setTimeout(15000);
  
  Serial.println("📥 Récupération liste employés...");
  int httpCode = http.GET();
  
  if (httpCode == 200) {
    String payload = http.getString();
    Serial.println("✅ Réponse reçue (" + String(payload.length()) + " octets)");
    StaticJsonDocument<4096> doc;
    DeserializationError error = deserializeJson(doc, payload);
    if (!error && doc["success"]) {
      JsonArray employees = doc["employees"];
      knownCount = min((int)employees.size(), 10);
      Serial.println("📋 " + String(knownCount) + " employés chargés:");
      for (int i = 0; i < knownCount; i++) {
        String nom = employees[i]["nom"].as<String>();
        String prenom = employees[i]["prenom"].as<String>();
        
        String fullName =nom + " " + prenom;
        //fullName.toLowerCase();
        knownEmployees[i] = fullName;
        Serial.println("  " + String(i+1) + ". " + knownEmployees[i]);
      }
    } else {
      Serial.println("❌ Erreur parsing JSON: " + String(error.c_str()));
      useFallbackList();
    }
  } else {
    Serial.println("❌ Erreur HTTP: " + String(httpCode));
    useFallbackList();
  }
  
  http.end();
}
void useFallbackList() {
  Serial.println("⚠️ Utilisation liste de secours");
  knownEmployees[0] = "tero fun";
  knownEmployees[1] = "jean dupont";
  knownEmployees[2] = "sophie martin";
  knownCount = 3;
  
  for (int i = 0; i < knownCount; i++) {
    Serial.println("  " + String(i+1) + ". " + knownEmployees[i]);
  }
}
void loop() {
  webSocket.loop();
  if (millis() - lastScan >= SCAN_INTERVAL) {
    lastScan = millis();
    if (wsConnected) {
      scanAndSendData();
    } else {
      Serial.println("⏳ En attente de connexion WebSocket...");
    }
  }
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      wsConnected = false;
      Serial.println("❌ WebSocket déconnecté");
      break;
      
    case WStype_CONNECTED:
      wsConnected = true;
      Serial.println("✅ WebSocket connecté: " + String((char*)payload));
      webSocket.sendTXT("40/api/rssi-data,");

      break;
      
    case WStype_TEXT: {
      Serial.println("📩 Message: " + String((char*)payload));
      String msg = String((char*)payload);
      if (msg.startsWith("42")) {
        Serial.println("  → Message Socket.IO traité");
      }
      break;
    } 
    case WStype_ERROR:
      Serial.println("❌ Erreur WebSocket");
      break; 
    case WStype_BIN:
      Serial.println("📥 Données binaires (ignorées)");
      break;
    case WStype_PING:
      Serial.println("🏓 Ping reçu");
      break;
    case WStype_PONG:
      Serial.println("🏓 Pong reçu");
      break;
      
    default:
      Serial.println("⚠️ Événement WebSocket inconnu: " + String(type));
      break;
  }
}
void scanAndSendData() {
  Serial.println("\n--- Scan WiFi ---");
  int n = WiFi.scanNetworks(false, true, false, 500);
  if (n == 0) {
    Serial.println("Aucun réseau détecté");
    return;
  }
  Serial.println(String(n) + " réseaux trouvés");
  StaticJsonDocument<2048> doc;
  doc["anchor_id"] = ANCHOR_ID;
  doc["anchor_x"] = ANCHOR_X;
  doc["anchor_y"] = ANCHOR_Y;
  doc["timestamp"] = millis();
  JsonArray badges = doc.createNestedArray("badges");

  int badgesDetected = 0;
  for (int i = 0; i < n; i++) {
    String ssidFound = WiFi.SSID(i);
    int rssi = WiFi.RSSI(i);
    String mac = WiFi.BSSIDstr(i);
    
    if (ssidFound.length() == 0) continue;
    
    Serial.println("  [" + String(i) + "] '" + ssidFound + "' | " + String(rssi) + " dBm | " + mac);
    
    String ssidLower = ssidFound;
    //ssidLower.toLowerCase();
    
    bool isBadge = false;
    for (int j = 0; j < knownCount; j++) {
      if (ssidLower.equals(knownEmployees[j])) {
        isBadge = true;
        break;
      }
    }
    
    if (isBadge) {
      JsonObject badge = badges.createNestedObject();
      badge["ssid"] = ssidFound;
      badge["mac"] = mac;
      badge["rssi"] = rssi;
      
      Serial.println("    ✅ Badge détecté");
      badgesDetected++;
    }
  }
  
  WiFi.scanDelete();
  
  if (badgesDetected == 0) {
    Serial.println("⚠️ Aucun badge détecté");
    return;
  }
  
  Serial.println("📤 Envoi de " + String(badgesDetected) + " badges");
  sendToServer(doc);
}

void sendToServer(StaticJsonDocument<2048>& doc) {
  if (!wsConnected) {
    Serial.println("❌ WebSocket non connecté");
    return;
  }
  
  String jsonString;
  serializeJson(doc, jsonString);
  
 String socketIOMessage = "42/api/rssi-data,[\"rssi_data\"," + jsonString + "]";

  
  Serial.println("JSON: " + jsonString.substring(0, 100) + "...");
  webSocket.sendTXT(socketIOMessage);
  Serial.println("✅ Envoyé via WebSocket");
}