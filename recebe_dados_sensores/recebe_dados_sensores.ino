#include <WiFi.h>
#include <PubSubClient.h>
#include "DHT.h"

// ---- Configurações Wi-Fi ----
const char* ssid = "ARIDA-lab";
const char* password = "!K1@B25#3&s";

// ---- Configurações MQTT ----
const char* mqtt_server = "192.168.0.127";  // Pode usar broker.hivemq.com também
const int mqtt_port = 1883;
const char* mqtt_topic_temp = "esp32/sensor/temperatura";
const char* mqtt_topic_hum = "esp32/sensor/umidade";
const char* mqtt_topic_sound = "esp32/sensor/som";

// ---- Pinos dos sensores ----
#define DHTPIN 4
#define DHTTYPE DHT11
#define SOUND_ANALOG_PIN 34

// ---- Objetos ----
WiFiClient espClient;
PubSubClient client(espClient);
DHT dht(DHTPIN, DHTTYPE);

// ---- Funções auxiliares ----
void reconnect() {
  while (!client.connected()) {
    Serial.print("Tentando conectar ao MQTT...");
    if (client.connect("ESP32_Client")) {
      Serial.println("Conectado!");
    } else {
      Serial.print("Falhou, rc=");
      Serial.print(client.state());
      Serial.println(" tentando novamente em 5 segundos");
      delay(5000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  dht.begin();

  // ---- Conexão Wi-Fi ----
  WiFi.begin(ssid, password);
  Serial.print("Conectando ao Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWi-Fi conectado!");
  Serial.print("Endereço IP: ");
  Serial.println(WiFi.localIP());

  // ---- Configuração MQTT ----
  client.setServer(mqtt_server, mqtt_port);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // ---- Leitura DHT11 ----
  float temp = dht.readTemperature();
  float hum = dht.readHumidity();

  if (!isnan(temp) && !isnan(hum)) {
    char tempStr[8];
    char humStr[8];
    dtostrf(temp, 1, 2, tempStr);
    dtostrf(hum, 1, 2, humStr);

    client.publish(mqtt_topic_temp, tempStr);
    client.publish(mqtt_topic_hum, humStr);

    Serial.print("Temperatura: ");
    Serial.print(tempStr);
    Serial.print(" °C | Umidade: ");
    Serial.println(humStr);
  }

  // ---- Leitura KY-037 ----
  int soundAnalog = analogRead(SOUND_ANALOG_PIN);

  char soundStr[8];
  sprintf(soundStr, "%d", soundAnalog);
  client.publish(mqtt_topic_sound, soundStr);

  Serial.print("Som (analógico): ");
  Serial.print(soundAnalog);

  delay(60000); // envia a cada 2 segundos
}
