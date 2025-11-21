import paho.mqtt.client as mqtt
import time

# --- Configurações MQTT ---
BROKER = "192.168.1.35"      # ou IP do seu servidor local
PORT = 1883
TOPIC_SENSOR = "esp32/sensor/#"    # recebe todos os sensores
TOPIC_ALERT = "esp32/alertas"      # publica os alarmes

# --- Limiares para gerar alarmes ---
TEMP_MAX = 30.0       # °C
TEMP_MIN = 10.0
HUM_MAX = 80.0        # %
SOUND_THRESHOLD = 700  # valor analógico do KY-037
ACCUMULATE_COUNT = 2  # número de leituras a acumular antes de calcular média
ALERT_COOLDOWN_SECS = 120  # tempo mínimo entre alertas (segundos)
TEMP_SPIKE_DELTA = 5.0  # diferença entre duas médias para considerar aumento súbito
HUM_SPIKE_DELTA = 5.0   # variação (p.p.) entre médias para considerar spike em umidade
SOUND_SPIKE_DELTA = 50.0  # variação entre médias para considerar spike em som

# buffer para leituras de som que excederam o threshold
pending_sound_readings = []
last_alert_time = 0

# buffers e tempos para temperatura e umidade
# agora usamos buffers que acumulam todas as leituras (não só as acima do threshold)
pending_temp_readings = []
pending_hum_readings = []

# para detectar picos rápidos: guarda a última média calculada
last_temp_avg = None
last_hum_avg = None
last_sound_avg = None

last_alert_time_temp_high = 0
last_alert_time_temp_low = 0
last_alert_time_hum = 0

# --- Callback quando conectar ---
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Conectado ao broker MQTT!")
        client.subscribe(TOPIC_SENSOR)
    else:
        print("❌ Falha na conexão, código:", rc)

# --- Callback ao receber mensagens ---
def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode()
    print(f"📥 {topic}: {payload}")

    alerta = None
    # permite modificar buffers e timestamps globais
    global pending_sound_readings, last_alert_time
    global pending_temp_readings, pending_hum_readings
    global last_alert_time_temp_high, last_alert_time_temp_low, last_alert_time_hum
    global last_temp_avg, last_hum_avg, last_sound_avg

    # --- Lógica de alarme ---
    if "temperatura" in topic:
        try:
            temp = float(payload)
            # acumula todas as leituras de temperatura
            pending_temp_readings.append(temp)
            if len(pending_temp_readings) > ACCUMULATE_COUNT:
                pending_temp_readings.pop(0)
            print(f"🌡️ Temp recebida ({temp}). Acumuladas: {len(pending_temp_readings)}/{ACCUMULATE_COUNT}")
            if len(pending_temp_readings) >= ACCUMULATE_COUNT:
                avg = sum(pending_temp_readings) / len(pending_temp_readings)
                print(f"📊 Média TEMP das últimas {len(pending_temp_readings)}: {avg:.2f} °C")
                now = time.time()
                # determina permissões de alerta considerando cooldowns
                is_high_allowed = (avg > TEMP_MAX) and ((now - last_alert_time_temp_high) >= ALERT_COOLDOWN_SECS)
                is_low_allowed = (avg < TEMP_MIN) and ((now - last_alert_time_temp_low) >= ALERT_COOLDOWN_SECS)
                is_spike_allowed = False
                delta = None
                if last_temp_avg is not None:
                    delta = avg - last_temp_avg
                    is_spike_allowed = (delta >= TEMP_SPIKE_DELTA)

                # Combina alertas quando aplicável: spike + alta / spike + baixa
                if is_spike_allowed and is_high_allowed:
                    alerta = f"ALERTA: Aumento súbito de temperatura (+{delta:.1f} °C) e temperatura alta (média {avg:.1f} °C)"
                    last_alert_time_temp_high = now
                elif is_spike_allowed and is_low_allowed:
                    alerta = f"ALERTA: Aumento súbito de temperatura (+{delta:.1f} °C) e temperatura muito baixa (média {avg:.1f} °C)"
                    last_alert_time_temp_low = now
                elif is_high_allowed:
                    alerta = f"ALERTA: Temperatura alta (média {avg:.1f} °C)"
                    last_alert_time_temp_high = now
                elif is_low_allowed:
                    alerta = f"ALERTA: Temperatura muito baixa (média {avg:.1f} °C)"
                    last_alert_time_temp_low = now
                elif is_spike_allowed:
                    alerta = f"ALERTA: Aumento súbito de temperatura (+{delta:.1f} °C, média atual {avg:.1f} °C)"

                # atualiza a última média de temperatura e limpa buffer
                last_temp_avg = avg
                pending_temp_readings = []
        except ValueError:
            pass

    elif "umidade" in topic:
        try:
            hum = float(payload)
            # acumula todas as leituras de umidade
            pending_hum_readings.append(hum)
            if len(pending_hum_readings) > ACCUMULATE_COUNT:
                pending_hum_readings.pop(0)
            print(f"💧 Umidade recebida ({hum}%). Acumuladas: {len(pending_hum_readings)}/{ACCUMULATE_COUNT}")
            if len(pending_hum_readings) >= ACCUMULATE_COUNT:
                avg = sum(pending_hum_readings) / len(pending_hum_readings)
                print(f"📊 Média HUM das últimas {len(pending_hum_readings)}: {avg:.1f}%")
                now = time.time()
                # verifica alta de umidade com cooldown
                is_high_allowed = (avg > HUM_MAX) and ((now - last_alert_time_hum) >= ALERT_COOLDOWN_SECS)
                # checa aumento súbito comparando com a última média (sem cooldown específico)
                is_spike_allowed = False
                delta_hum = None
                if last_hum_avg is not None:
                    delta_hum = avg - last_hum_avg
                    is_spike_allowed = (delta_hum >= HUM_SPIKE_DELTA)

                if is_spike_allowed and is_high_allowed:
                    alerta = f"ALERTA: Aumento súbito de umidade (+{delta_hum:.1f} p.p.) e umidade alta (média {avg:.1f}%)"
                    last_alert_time_hum = now
                elif is_high_allowed:
                    alerta = f"ALERTA: Umidade excessiva (média {avg:.1f}%)"
                    last_alert_time_hum = now
                elif is_spike_allowed:
                    alerta = f"ALERTA: Aumento súbito de umidade (+{delta_hum:.1f} p.p., média atual {avg:.1f}%)"

                last_hum_avg = avg
                pending_hum_readings = []
        except ValueError:
            pass

    elif "som" in topic:
        try:
            sound = int(payload)
            # acumula todas as leituras de som
            pending_sound_readings.append(sound)
            if len(pending_sound_readings) > ACCUMULATE_COUNT:
                pending_sound_readings.pop(0)
            print(f"🔊 Som recebido ({sound}). Acumuladas: {len(pending_sound_readings)}/{ACCUMULATE_COUNT}")
            if len(pending_sound_readings) >= ACCUMULATE_COUNT:
                avg = sum(pending_sound_readings) / len(pending_sound_readings)
                print(f"📊 Média das últimas {len(pending_sound_readings)} leituras: {avg:.1f}")
                now = time.time()
                # condição de ruído (mantém cooldown existente)
                is_sound_threshold = (avg < SOUND_THRESHOLD) and ((now - last_alert_time) >= ALERT_COOLDOWN_SECS)
                # checa aumento súbito em som comparando com a última média
                is_sound_spike = False
                delta_sound = None
                if last_sound_avg is not None:
                    delta_sound = avg - last_sound_avg
                    # para o sensor de som que retorna valores menores quando o ruído é maior,
                    # um 'spike' de ruído é representado por uma queda no valor.
                    is_sound_spike = (delta_sound <= -SOUND_SPIKE_DELTA)

                if is_sound_spike and is_sound_threshold:
                    alerta = f"ALERTA: Aumento súbito de som (variação {abs(delta_sound):.1f}) e ruído elevado (média {avg:.1f})"
                    last_alert_time = now
                elif is_sound_threshold:
                    alerta = f"ALERTA: Ruído elevado (média {avg:.1f})"
                    last_alert_time = now
                elif is_sound_spike:
                    alerta = f"ALERTA: Aumento súbito de som (variação {abs(delta_sound):.1f}, média atual {avg:.1f})"

                last_sound_avg = avg
                pending_sound_readings = []
        except ValueError:
            pass

    # --- Se tiver alerta, publica ---
    if alerta:
        print("🚨 Publicando alerta:", alerta)
        client.publish(TOPIC_ALERT, alerta)

# --- Inicializa o cliente MQTT ---
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

# --- Conecta e mantém loop ativo ---
client.connect(BROKER, PORT, 60)
print("🔄 Monitorando dados...")

client.loop_forever()
