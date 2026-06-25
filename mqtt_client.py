import json
import ssl
import paho.mqtt.client as mqtt

from config import (
    HIVEMQ_HOST, HIVEMQ_PORT, HIVEMQ_USERNAME, HIVEMQ_PASSWORD,
    MQTT_TOPIC, TEMP_THRESHOLD, CO2_THRESHOLD,
)
from telegram_bot import send_alert

sensor_data = {"temperature": None, "co2": None}

# Trạng thái cảnh báo — tránh spam khi giá trị dao động quanh ngưỡng
_alerted = {"temp": False, "co2": False, "both": False}


def _check_and_alert():
    temp = sensor_data["temperature"]
    co2 = sensor_data["co2"]

    temp_over = temp is not None and temp >= TEMP_THRESHOLD
    co2_over = co2 is not None and co2 >= CO2_THRESHOLD

    if temp_over and co2_over and not _alerted["both"]:
        send_alert(
            f"🚨 <b>CẢNH BÁO NGHIÊM TRỌNG!</b>\n"
            f"Cả 2 chỉ số vượt ngưỡng an toàn:\n"
            f"🌡 Nhiệt độ: <b>{temp}°C</b> (ngưỡng: {TEMP_THRESHOLD}°C)\n"
            f"💨 CO₂: <b>{int(co2)} ppm</b> (ngưỡng: {int(CO2_THRESHOLD)} ppm)"
        )
        _alerted["both"] = True
        _alerted["temp"] = True
        _alerted["co2"] = True

    elif temp_over and not _alerted["temp"]:
        send_alert(
            f"⚠️ <b>CẢNH BÁO nhiệt độ cao!</b>\n"
            f"🌡 Nhiệt độ: <b>{temp}°C</b> (ngưỡng: {TEMP_THRESHOLD}°C)\n"
            f"💨 CO₂ hiện tại: {int(co2) if co2 is not None else 'N/A'} ppm"
        )
        _alerted["temp"] = True

    elif co2_over and not _alerted["co2"]:
        send_alert(
            f"⚠️ <b>CẢNH BÁO CO₂ cao!</b>\n"
            f"💨 CO₂: <b>{int(co2)} ppm</b> (ngưỡng: {int(CO2_THRESHOLD)} ppm)\n"
            f"🌡 Nhiệt độ hiện tại: {temp if temp is not None else 'N/A'}°C"
        )
        _alerted["co2"] = True

    # Reset cảnh báo khi giá trị trở về bình thường
    if not temp_over:
        _alerted["temp"] = False
        _alerted["both"] = False
    if not co2_over:
        _alerted["co2"] = False
        _alerted["both"] = False


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"[MQTT] Kết nối thành công: {HIVEMQ_HOST}")
        client.subscribe(MQTT_TOPIC)
        print(f"[MQTT] Subscribe topic: {MQTT_TOPIC}")
    else:
        print(f"[MQTT] Kết nối thất bại, mã lỗi: {reason_code}")


def on_message(client, userdata, msg):
    topic = msg.topic
    payload = msg.payload.decode("utf-8").strip()
    print(f"[MQTT] {topic}: {payload}")

    try:
        # Thử parse JSON trước (vd: {"temperature": 34.1, "co2": 1500})
        data = json.loads(payload)
        if "temperature" in data:
            sensor_data["temperature"] = float(data["temperature"])
        if "co2" in data:
            sensor_data["co2"] = float(data["co2"])
        elif "CO2" in data:
            sensor_data["co2"] = float(data["CO2"])
    except (json.JSONDecodeError, ValueError):
        # Nếu payload là giá trị đơn (vd: "34.1")
        try:
            value = float(payload)
            topic_lower = topic.lower()
            if "temp" in topic_lower:
                sensor_data["temperature"] = value
            elif "co2" in topic_lower:
                sensor_data["co2"] = value
        except ValueError:
            print(f"[MQTT] Không đọc được payload: {payload}")
            return

    _check_and_alert()


def create_client() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(HIVEMQ_USERNAME, HIVEMQ_PASSWORD)
    client.tls_set(tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.on_connect = on_connect
    client.on_message = on_message
    return client
