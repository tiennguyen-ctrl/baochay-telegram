import json
import ssl
import threading
import time
import paho.mqtt.client as mqtt

from config import (
    HIVEMQ_HOST, HIVEMQ_PORT, HIVEMQ_USERNAME, HIVEMQ_PASSWORD, MQTT_TOPIC,
)
from telegram_bot import send_alert

# Ngưỡng hiệu chỉnh: áp dụng khi nhiệt độ thực >= 33°C
OFFSET_THRESHOLD = 35.0
TEMP_OFFSET      = 30.0
HUM_OFFSET       = 63.0

# Ngưỡng so sánh (trên giá trị đã hiệu chỉnh)
TEMP_WARN = 65.0
CO2_WARN  = 2000
TEMP_FIRE = 70.0
CO2_FIRE  = 3000

# Timeout SED: nếu node không gửi data quá 5 phút → coi là SAFE
NODE_TIMEOUT  = 5 * 60   # giây
CHECK_INTERVAL = 30       # kiểm tra mỗi 30 giây

# Trạng thái mỗi node
SAFE      = 0
HIGH_TEMP = 1
HIGH_CO2  = 2
FIRE_RISK = 3
FIRE      = 4

_nodes = {}


def _get_node(node_id):
    if node_id not in _nodes:
        _nodes[node_id] = {
            "temperature": None,
            "humidity":    None,
            "co2":         None,
            "tvoc":        None,
            "last_state":  None,
            "last_seen":   None,   # timestamp lần cuối nhận data
        }
    return _nodes[node_id]


def _display_values(node):
    temp = node["temperature"]
    hum  = node["humidity"]
    if temp is not None and temp >= OFFSET_THRESHOLD:
        d_temp = round(temp + TEMP_OFFSET, 1)
        d_hum  = round(hum - HUM_OFFSET, 1) if hum is not None else None
    else:
        d_temp = temp
        d_hum  = hum
    return d_temp, d_hum


def _classify(d_temp, co2):
    if d_temp is None or co2 is None:
        return SAFE
    if d_temp >= TEMP_FIRE and co2 >= CO2_FIRE:
        return FIRE
    if d_temp >= TEMP_WARN and co2 >= CO2_WARN:
        return FIRE_RISK
    if d_temp >= TEMP_WARN:
        return HIGH_TEMP
    if co2 >= CO2_WARN:
        return HIGH_CO2
    return SAFE


def _stats(node, state, d_temp, d_hum):
    if state == SAFE:
        temp = node["temperature"]
        hum  = node["humidity"]
    else:
        temp = d_temp
        hum  = d_hum
    co2  = node["co2"]
    tvoc = node["tvoc"]
    return (
        f"🌡 Nhiệt độ: {temp if temp is not None else 'N/A'}°C\n"
        f"💧 Độ ẩm: {f'{hum:.1f}%' if hum is not None else 'N/A'}\n"
        f"💨 CO₂: {int(co2) if co2 is not None else 'N/A'} ppm\n"
        f"🧪 TVOC: {int(tvoc) if tvoc is not None else 'N/A'} ppb"
    )


def _send_state_alert(node_id, state, node, d_temp, d_hum):
    header = f"📍 Node: <b>{node_id}</b>\n"
    stats  = _stats(node, state, d_temp, d_hum)
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
    d_temp, d_hum = _display_values(node)
    state         = _classify(d_temp, node["co2"])
    last_state    = node["last_state"]

    if last_state is None:
        node["last_state"] = state
        if state != SAFE:
            _send_state_alert(node_id, state, node, d_temp, d_hum)
        return

    if state != last_state:
        node["last_state"] = state
        _send_state_alert(node_id, state, node, d_temp, d_hum)


def _timeout_checker():
    while True:
        time.sleep(CHECK_INTERVAL)
        now = time.time()
        for node_id, node in list(_nodes.items()):
            if node["last_seen"] is None:
                continue
            if now - node["last_seen"] < NODE_TIMEOUT:
                continue
            # Node im lặng quá 5 phút
            if node["last_state"] not in (None, SAFE):
                d_temp, d_hum = _display_values(node)
                node["last_state"] = SAFE
                _send_state_alert(node_id, SAFE, node, d_temp, d_hum)
                print(f"[Timeout] Node {node_id} không gửi data > 5 phút → SAFE")


def start_timeout_checker():
    t = threading.Thread(target=_timeout_checker, daemon=True)
    t.start()
    print("[App] Timeout checker started (interval=30s, timeout=5m)")


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

    node["last_seen"] = time.time()

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
