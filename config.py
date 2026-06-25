import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

HIVEMQ_HOST = os.getenv("HIVEMQ_HOST")
HIVEMQ_PORT = int(os.getenv("HIVEMQ_PORT", 8883))
HIVEMQ_USERNAME = os.getenv("HIVEMQ_USERNAME")
HIVEMQ_PASSWORD = os.getenv("HIVEMQ_PASSWORD")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "sensor/#")

TEMP_THRESHOLD = float(os.getenv("TEMP_THRESHOLD", 33.5))
CO2_THRESHOLD = float(os.getenv("CO2_THRESHOLD", 2000))
