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
