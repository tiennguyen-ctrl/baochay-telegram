import time
from mqtt_client import create_client
from config import HIVEMQ_HOST, HIVEMQ_PORT


def main():
    print("[App] Khởi động dịch vụ HiveMQ → Telegram Alert...")
    while True:
        client = create_client()
        try:
            client.connect(HIVEMQ_HOST, HIVEMQ_PORT)
            client.loop_forever()
        except KeyboardInterrupt:
            print("[App] Dừng bởi người dùng.")
            break
        except Exception as e:
            print(f"[App] Lỗi kết nối: {e}. Thử lại sau 10 giây...")
            time.sleep(10)


if __name__ == "__main__":
    main()
