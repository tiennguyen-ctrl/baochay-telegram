import json
import ssl
import paho.mqtt.client as mqtt

from config import (
    HIVEMQ_HOST, HIVEMQ_PORT, HIVEMQ_USERNAME, HIVEMQ_PASSWORD,
    MQTT_TOPIC, TEMP_THRESHOLD, CO2_THRESHOLD,
)
from telegram_bot import send_alert

# Lưu dữ liệu và trạng thái cảnh báo theo từng node
# { "Node_abc": {"temperature": 34.0, "co2": 1800, "tvoc": 120, "alerted": {"temp":False,...}} }
_nodes = {}


def _get_node(node_id):
    if node_id not in _nodes:
        _nodes[node_id] = {
            "temperature": None,
            "co2": None,
            "tvoc": None,
            "alerted": {"temp": False, "co2": False, "both": False},
        }
    return _nodes[node_id]


def _fmt_tvoc(tvoc):
    return f"{int(tvoc)} ppb" if tvoc is not None else "N/A"


def _check_and_alert(node_id, node):
    temp = node["temperature"]
    co2  = node["co2"]
    tvoc = node["tvoc"]
    al   = node["alerted"]

    temp_over = temp is not None and temp >= TEMP_THRESHOLD
    co2_over  = co2  is not None and co2  >= CO2_THRESHOLD

    header = f"📍 Node: <b>{node_id}</b>\n"

    if temp_over and co2_over and not al["both"]:
        send_alert(
            f"🚨 <b>CẢNH BÁO NGHIÊM TRỌNG!</b>\n"
            f"{header}"
            f"🌡 Nhiệt độ: <b>{temp}°C</b> (ngưỡng: {TEMP_THRESHOLD}°C)\n"
            f"💨 CO₂: <b>{int(co2)} ppm</b> (ngưỡng: {int(CO2_THRESHOLD)} ppm)\n"
            f"🧪 TVOC: {_fmt_tvoc(tvoc)}"
        )
        al["both"] = al["temp"] = al["co2"] = True

    elif temp_over and not al["temp"]:
        send_alert(
            f"⚠️ <b>CẢNH BÁO nhiệt độ cao!</b>\n"
            f"{header}"
            f"🌡 Nhiệt độ: <b>{temp}°C</b> (ngưỡng: {TEMP_THRESHOLD}°C)\n"
            f"💨 CO₂: {int(co2) if co2 is not None else 'N/A'} ppm\n"
            f"🧪 TVOC: {_fmt_tvoc(tvoc)}"
        )
        al["temp"] = True

    elif co2_over and not al["co2"]:
        send_alert(
            f"⚠️ <b>CẢNH BÁO CO₂ cao!</b>\n"
            f"{header}"
            f"💨 CO₂: <b>{int(co2)} ppm</b> (ngưỡng: {int(CO2_THRESHOLD)} ppm)\n"
            f"🌡 Nhiệt độ: {temp if temp is not None else 'N/A'}°C\n"
            f"🧪 TVOC: {_fmt_tvoc(tvoc)}"
        )
        al["co2"] = True

    # Reset khi giá trị trở về bình thường
    if not temp_over:
        al["temp"] = False
        al["both"] = False
    if not co2_over:
        al["co2"] = False
        al["both"] = False


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

    # Lấy node_id từ JSON hoặc từ tên topic (sensor/<node_id>)
    node_id = data.get("node_id") or topic.split("/")[-1] or "unknown"
    node    = _get_node(node_id)

    if "temperature" in data:
        node["temperature"] = round(float(data["temperature"]), 1)
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
