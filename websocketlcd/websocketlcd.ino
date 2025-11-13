#include <WiFi.h>
#include <WebSocketsClient.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <algorithm>

// ========== CONFIGURATION LCD ==========
#define SDA_PIN 21
#define SCL_PIN 22
#define LCD_ADDRESS 0x27
#define LCD_COLUMNS 16
#define LCD_ROWS 4

LiquidCrystal_I2C lcd(LCD_ADDRESS, LCD_COLUMNS, LCD_ROWS);

// ========== CONFIGURATION ANCRE ==========
#define ANCHOR_ID 3   // 1, 2 ou 3

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

// Serveur
const char* websocket_server = "postcam-1.onrender.com";
const int websocket_port = 443;
const char* websocket_path = "/socket.io/?EIO=4&transport=websocket";

const unsigned long SCAN_INTERVAL = 2000;
unsigned long lastScan = 0;
WebSocketsClient webSocket;
String knownEmployees[10];
int knownCount = 0;
bool wsConnected = false;

// Variables pour l'affichage LCD
String lastEmployee = "";
String lastAction = "";
String lastTime = "";
unsigned long lastDisplayUpdate = 0;
const unsigned long DISPLAY_DURATION = 10000; // Afficher pendant 10 secondes

// Buffer pour affichage animé (noms longs)
int scrollPosition = 0;
unsigned long lastScrollTime = 0;
const unsigned long SCROLL_INTERVAL = 300; // Défilement toutes les 300ms

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  // ========== Initialiser LCD ==========
  Serial.println("Initialisation LCD...");
  Wire.begin(SDA_PIN, SCL_PIN);
  lcd.init();
  delay(100);
  lcd.clear();
  delay(50);
  lcd.backlight();
  
  // Message de démarrage sur LCD
  lcd.setCursor(0, 0);
  lcd.print("  SYSTEME DE");
  lcd.setCursor(0, 1);
  lcd.print("   POINTAGE");
  lcd.setCursor(0, 2);
  lcd.print("  Ancre #");
  lcd.print(ANCHOR_ID);
  delay(2000);
  
  Serial.println("\n=== ESP32 Ancre #" + String(ANCHOR_ID) + " ===");
  Serial.println("Position: (" + String(ANCHOR_X) + ", " + String(ANCHOR_Y) + ")");
  
  // ========== Connexion WiFi ==========
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);
  
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Connexion WiFi");
  Serial.print("Connexion WiFi");
  WiFi.begin(ssid, password);
  
  int dots = 0;
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
    lcd.setCursor(0, 1);
    for (int i = 0; i <= dots; i++) {
      lcd.print(".");
    }
    dots = (dots + 1) % 16;
  }
  
  Serial.println("\n✅ WiFi connecté");
  Serial.println("IP: " + WiFi.localIP().toString());
  
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("WiFi Connecte");
  lcd.setCursor(0, 1);
  lcd.print(WiFi.localIP().toString());
  delay(2000);

  // ========== Récupérer employés ==========
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Chargement");
  lcd.setCursor(0, 1);
  lcd.print("Employes...");
  fetchEmployees();
  
  lcd.setCursor(0, 2);
  lcd.print(String(knownCount) + " employes OK");
  delay(2000);

  // ========== Initialiser WebSocket ==========
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Connexion");
  lcd.setCursor(0, 1);
  lcd.print("Serveur...");
  Serial.println("Initialisation WebSocket...");
  
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
        
        String fullName = nom + " " + prenom;
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
  
  // Mise à jour de l'affichage principal
  updateMainDisplay();
  
  // Scan périodique
  if (millis() - lastScan >= SCAN_INTERVAL) {
    lastScan = millis();
    if (wsConnected) {
      scanAndSendData();
    } else {
      Serial.println("⏳ En attente de connexion WebSocket...");
    }
  }
}

void updateMainDisplay() {
  unsigned long now = millis();
  
  // Si un événement de pointage est affiché
  if (lastEmployee != "" && (now - lastDisplayUpdate) < DISPLAY_DURATION) {
    // Gérer le défilement si nom trop long
    if (lastEmployee.length() > 16 && (now - lastScrollTime) > SCROLL_INTERVAL) {
      scrollPosition++;
      if (scrollPosition > lastEmployee.length() - 16) {
        scrollPosition = 0;
      }
      lastScrollTime = now;
      
      // Réafficher avec défilement
      lcd.setCursor(0, 1);
      lcd.print("                "); // Effacer
      lcd.setCursor(0, 1);
      lcd.print(lastEmployee.substring(scrollPosition, scrollPosition + 16));
    }
    return; // Garder l'affichage du pointage
  }
  
  // Réinitialiser après expiration du pointage
  if (lastEmployee != "" && (now - lastDisplayUpdate) >= DISPLAY_DURATION) {
    lastEmployee = "";
    lastAction = "";
    lastTime = "";
    scrollPosition = 0;
    lcd.clear(); // Effacer immédiatement
  }
  
  // Affichage normal - Message d'attente
  static unsigned long lastNormalUpdate = 0;
  if (now - lastNormalUpdate < 1000) {
    return; // Ne pas rafraîchir trop souvent
  }
  lastNormalUpdate = now;
  
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("-------------------");
  lcd.setCursor(0, 1);
  lcd.print(" METTEZ VOS CARTE");
  lcd.setCursor(0, 2);
  lcd.print("  SUR L'APPAREIL");
  lcd.setCursor(0, 3);
  lcd.print("-------------------");
}

void displayPointage(String nom, String prenom, String action, String timeStr) {
  // Combiner nom et prénom
  String fullName = prenom + " " + nom;
  fullName.toUpperCase(); // Majuscules pour meilleure visibilité
  
  lastEmployee = fullName;
  lastAction = action;
  lastTime = timeStr;
  lastDisplayUpdate = millis();
  scrollPosition = 0;
  
  lcd.clear();
  
  // ========== LIGNE 1: Action ==========
  lcd.setCursor(0, 0);
  if (action == "ENTREE") {
    lcd.print(">>> ENTREE <<<");
  } else if (action == "SORTIE") {
    lcd.print("<<< SORTIE >>>");
  } else {
    // Pour "arrivee" ou "depart" de l'APK
    lcd.print(">> ");
    lcd.print(action);
    lcd.print(" <<");
  }
  
  // ========== LIGNE 2: Nom Prénom ==========
  lcd.setCursor(0, 1);
  if (fullName.length() <= 16) {
    // Centrer si possible
    int padding = (16 - fullName.length()) / 2;
    for (int i = 0; i < padding; i++) {
      lcd.print(" ");
    }
    lcd.print(fullName);
  } else {
    // Afficher le début (défilement géré dans loop)
    lcd.print(fullName.substring(0, 16));
  }
  
  // ========== LIGNE 3: Séparateur ==========
  lcd.setCursor(0, 2);
  lcd.print("----------------");
  
  // ========== LIGNE 4: Date et Heure ==========
  lcd.setCursor(0, 3);
  lcd.print(timeStr);
  
  // Log série
  Serial.println("📺 LCD AFFICHAGE:");
  Serial.println("   Action: " + action);
  Serial.println("   Nom: " + fullName);
  Serial.println("   Heure: " + timeStr);
}

void webSocketEvent(WStype_t type, uint8_t * payload, size_t length) {
  switch(type) {
    case WStype_DISCONNECTED:
      wsConnected = false;
      Serial.println("❌ WebSocket déconnecté");
      lcd.clear();
      lcd.setCursor(0, 1);
      lcd.print("  DECONNECTE");
      break;
      
    case WStype_CONNECTED:
      wsConnected = true;
      Serial.println("✅ WebSocket connecté: " + String((char*)payload));
      webSocket.sendTXT("40/api/rssi-data,");
      
      lcd.clear();
      lcd.setCursor(0, 1);
      lcd.print("  CONNECTE !");
      delay(1500);
      break;
      
    case WStype_TEXT: {
      String msg = String((char*)payload);
      Serial.println("📩 Message WS: " + msg);
      
      // Parser les messages Socket.IO format: 42[event, data]
      if (msg.startsWith("42")) {
        int jsonStart = msg.indexOf('[');
        if (jsonStart > 0) {
          String jsonPart = msg.substring(jsonStart);
          
          StaticJsonDocument<1024> doc;
          DeserializationError error = deserializeJson(doc, jsonPart);
          
          if (!error) {
            const char* eventType = doc[0];
            
            if (eventType && String(eventType) == "pointage_event") {
              JsonObject data = doc[1];
              
              String nom = data["nom"].as<String>();
              String prenom = data["prenom"].as<String>();
              String action = data["type"].as<String>();
              String dateStr = data["date"].as<String>();
              String timeStr = data["time"].as<String>();
              
              // Ajouter +3 heures au temps reçu
              int hours = timeStr.substring(0, 2).toInt();
              int minutes = timeStr.substring(3, 5).toInt();
              
              hours += 3; // Ajouter 3 heures
              if (hours >= 24) {
                hours -= 24; // Gérer le dépassement de 24h
              }
              
              // Reformater l'heure
              String adjustedTime = "";
              if (hours < 10) adjustedTime += "0";
              adjustedTime += String(hours) + ":";
              if (minutes < 10) adjustedTime += "0";
              adjustedTime += String(minutes);
              
              // Format: "DD/MM/YY HH:MM"
              String displayTime = dateStr.substring(0, 8) + " " + adjustedTime;
              
              Serial.println("✅ Pointage reçu:");
              Serial.println("   Nom: " + nom);
              Serial.println("   Prénom: " + prenom);
              Serial.println("   Action: " + action);
              Serial.println("   Heure: " + displayTime);
              
              // Afficher sur LCD
              displayPointage(nom, prenom, action, displayTime);
            }
          } else {
            Serial.println("❌ Erreur parsing JSON: " + String(error.c_str()));
          }
        }
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
      
      Serial.println("    ✅ Badge détecté: " + ssidFound);
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