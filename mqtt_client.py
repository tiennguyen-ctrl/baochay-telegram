import json
import ssl
import paho.mqtt.client as mqtt

from config import (
    HIVEMQ_HOST, HIVEMQ_PORT, HIVEMQ_USERNAME, HIVEMQ_PASSWORD, MQTT_TOPIC,
)
from telegram_bot import send_alert

# Ngưỡng cố định
TEMP_WARN = 35.0
CO2_WARN  = 2000
TEMP_FIRE = 40.0
CO2_FIRE  = 3000

# Trạng thái của mỗi node
SAFE      = 0
HIGH_TEMP = 1
HIGH_CO2  = 2
FIRE_RISK = 3
FIRE      = 4

# { node_id: { temperature, humidity, co2, tvoc, last_state } }
_nodes = {}


def _get_node(node_id):
    if node_id not in _nodes:
        _nodes[node_id] = {
            "temperature": None,
            "humidity":    None,
            "co2":         None,
            "tvoc":        None,
            "last_state":  None,   # None = chưa từng nhận data
        }
    return _nodes[node_id]


def _classify(temp, co2):
    """Xác định trạng thái dựa trên nhiệt độ và CO2."""
    if temp is None or co2 is None:
        return SAFE
    if temp >= TEMP_FIRE and co2 >= CO2_FIRE:
        return FIRE
    if temp >= TEMP_WARN and co2 >= CO2_WARN:
        return FIRE_RISK
    if temp >= TEMP_WARN:
        return HIGH_TEMP
    if co2 >= CO2_WARN:
        return HIGH_CO2
    return SAFE


def _stats(node):
    temp = node["temperature"]
    hum  = node["humidity"]
    co2  = node["co2"]
    tvoc = node["tvoc"]
    return (
        f"🌡 Nhiệt độ: {temp if temp is not None else 'N/A'}°C\n"
        f"💧 Độ ẩm: {f'{hum:.1f}%' if hum is not None else 'N/A'}\n"
        f"💨 CO₂: {int(co2) if co2 is not None else 'N/A'} ppm\n"
        f"🧪 TVOC: {int(tvoc) if tvoc is not None else 'N/A'} ppb"
    )


def _send_state_alert(node_id, state, node):
    header = f"📍 Node: <b>{node_id}</b>\n"
    stats  = _stats(node)

    messages = {
        HIGH_TEMP: f"⚠️ <b>NHIỆT ĐỘ CAO!</b>\n{header}{stats}",
        HIGH_CO2:  f"⚠️ <b>NỒNG ĐỘ CO₂ CAO!</b>\n{header}{stats}",
        FIRE_RISK: f"🔶 <b>NGUY CƠ CHÁY!</b>\n{header}{stats}",
        FIRE:      f"🔥 <b>CÓ CHÁY!</b>\n{header}{stats}",
        SAFE:      f"✅ <b>ĐÃ AN TOÀN</b>\n{header}{stats}",
    }
    send_alert(messages[state])
    print(f"[Alert] Node {node_id} → state {state}")


def _check_and_alert(node_id, node):
    state      = _classify(node["temperature"], node["co2"])
    last_state = node["last_state"]

    if last_state is None:
        # Lần đầu nhận data: lưu state, chỉ alert nếu không phải SAFE
        node["last_state"] = state
        if state != SAFE:
            _send_state_alert(node_id, state, node)
        return

    if state != last_state:
        node["last_state"] = state
        _send_state_alert(node_id, state, node)


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"[MQTT] Kết nối thành công: {HIVEMQ_HOST}")
        client.subscribe(MQTT_TOPIC)
        print(f"[MQTT] Subscribe topic: {MQTT_TOPIC}")
    else:
        print(f"[MQTT] Kết nối thất bại, mã lỗi: {reason_code}")


def on_message(client, userdata, msg):
    topic   = msg.topic
    payload = msg.payload.decode("utf-8").strip()
    print(f"[MQTT] {topic}: {payload}")

    try:
        data = json.loads(payload)
    except (json.JSONDecodeError, ValueError):
        print(f"[MQTT] Không đọc được payload: {payload}")
        return

    node_id = data.get("node_id") or topic.split("/")[-1] or "unknown"
    node    = _get_node(node_id)

    if "temperature" in data:
        node["temperature"] = round(float(data["temperature"]), 1)
    if "humidity" in data:
        node["humidity"] = round(float(data["humidity"]), 1)
    if "co2" in data:
        node["co2"] = float(data["co2"])
    if "tvoc" in data:
        node["tvoc"] = float(data["tvoc"])

    _check_and_alert(node_id, node)


def create_client() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(HIVEMQ_USERNAME, HIVEMQ_PASSWORD)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = on_connect
    client.on_message = on_message
    return client
