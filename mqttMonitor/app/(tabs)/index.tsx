import React, { useEffect, useState, useRef } from "react";
import { View, Text, ScrollView, Dimensions, Alert, StyleSheet, Vibration } from "react-native";
import { LineChart } from "react-native-chart-kit";
import mqtt from "mqtt/dist/mqtt";
import { Audio } from "expo-av";

const MQTT_BROKER = "ws://192.168.0.127:8080";
const TOPIC_TEMP = "esp32/sensor/temperatura";
const TOPIC_HUM = "esp32/sensor/umidade";
const TOPIC_SOUND = "esp32/sensor/som";
const TOPIC_ALERT = "esp32/alertas";

export default function Index() {
  const [temperatureData, setTemperatureData] = useState<number[]>([]);
  const [humidityData, setHumidityData] = useState<number[]>([]);
  const [soundData, setSoundData] = useState<number[]>([]);
  const soundRef = useRef<Audio.Sound | null>(null);

  useEffect(() => {
    const client = mqtt.connect(MQTT_BROKER);

    // carrega o som de alerta uma vez e reutiliza
    (async () => {
      try {
        const { sound } = await Audio.Sound.createAsync(
          // uso de URL pública curta para evitar adicionar asset binário ao repositório
          { uri: "https://actions.google.com/sounds/v1/alarms/beep_short.ogg" },
          { shouldPlay: false }
        );
        soundRef.current = sound;
      } catch (e) {
        console.warn("Erro ao carregar som de alerta:", e);
      }
    })();

    client.on("connect", () => {
      console.log("✅ Conectado ao MQTT");
      client.subscribe([TOPIC_TEMP, TOPIC_HUM, TOPIC_SOUND, TOPIC_ALERT]);
    });

  client.on("message", async (topic: string, message: Buffer) => {
      console.log("📩 Mensagem recebida:", topic, message.toString());
      const strValue = message.toString();
      const value = parseFloat(strValue);

      // só atualiza se o valor for um número válido e finito
      if (!isNaN(value) && isFinite(value)) {
        if (topic === TOPIC_TEMP) setTemperatureData((old) => [...old.slice(-19), value]);
        if (topic === TOPIC_HUM) setHumidityData((old) => [...old.slice(-19), value]);
        if (topic === TOPIC_SOUND) setSoundData((old) => [...old.slice(-19), value]);
      } else if (topic === TOPIC_ALERT) {
        const msg = message.toString();
        Alert.alert("🚨 Alerta recebido", msg);

        // tocar som (usa soundRef se carregado, senão tenta criar e tocar)
        try {
          if (soundRef.current) {
            // replayAsync garante tocar desde o início
            await soundRef.current.replayAsync();
          } else {
            const { sound } = await Audio.Sound.createAsync({ uri: "https://actions.google.com/sounds/v1/alarms/beep_short.ogg" });
            soundRef.current = sound;
            await soundRef.current.playAsync();
          }
        } catch (e) {
          console.warn("Erro ao tocar som de alerta:", e);
        }

        // vibrar o aparelho (padrão de pulso: pausa 0ms, vibrar 500ms, pausa 200ms, vibrar 500ms)
        try {
          Vibration.vibrate([0, 500, 200, 500]);
        } catch (e) {
          console.warn("Erro ao vibrar:", e);
        }
      } else {
        console.warn(`⚠️ Valor MQTT inválido no tópico ${topic}:`, strValue);
      }
    });

    return () => {
      client.end();
      if (soundRef.current) {
        soundRef.current.unloadAsync().catch(() => {});
      }
    };
  }, []);

  const chartConfig = {
    backgroundColor: "#222",
    backgroundGradientFrom: "#222",
    backgroundGradientTo: "#444",
    color: (opacity = 1) => `rgba(255,255,255,${opacity})`,
  };

  return (
    <ScrollView style={styles.container}>
      <Text style={styles.title}>Monitor IoT via MQTT</Text>

      <Chart title="Temperatura (°C)" data={temperatureData} suffix="°C" chartConfig={chartConfig} />
      <Chart title="Umidade (%)" data={humidityData} suffix="%" chartConfig={chartConfig} />
      <Chart title="Som" data={soundData} suffix="" chartConfig={chartConfig} />
    </ScrollView>
  );
}

function Chart({ title, data, suffix, chartConfig }: any) {
  // Evita erros se data estiver vazio ou contiver valores inválidos
  const safeData =
    Array.isArray(data) && data.length > 0
      ? data.filter((v) => !isNaN(v) && isFinite(v))
      : [0]; // valor inicial padrão

  return (
    <View style={{ marginBottom: 20 }}>
      <LineChart
        data={{
          labels: Array(safeData.length).fill(""),
          datasets: [{ data: safeData }],
        }}
        width={Math.max(Dimensions.get("window").width, 320)}
        height={200}
        yAxisSuffix={suffix}
        chartConfig={chartConfig}
        bezier
      />
      <Text style={{ color: "#fff", textAlign: "center" }}>{title}</Text>
    </View>
  );
}


const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#111",
    padding: 10,
  },
  title: {
    color: "#fff",
    fontSize: 20,
    marginBottom: 10,
    textAlign: "center",
  },
});
