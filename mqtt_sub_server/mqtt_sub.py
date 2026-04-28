import paho.mqtt.client as mqtt
import os
import time
import json
from datetime import datetime

MQTT_BROKER = os.getenv("MQTT_BROKER", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "iot/sensors/#")
DATA_FILE = "sensors_data.json"
STATUS_FILE = "status_data.json"

# Heartbeat tracking
heartbeats = {}
last_statuses = {}  # Track last recorded status to avoid duplicates
TIMEOUT = 4  # seconds


def on_connect(client, userdata, flags, rc, properties=None):
    try:
        local_ip = client.socket().getsockname()[0]
    except Exception:
        local_ip = "Unknown"

    print(f"MQTT Client Local IP: {local_ip}", flush=True)
    print(f"Connected to MQTT Broker: {MQTT_BROKER}", flush=True)
    client.subscribe(MQTT_TOPIC)
    print(f"Subscribed to topic: {MQTT_TOPIC}", flush=True)


def on_message(client, userdata, msg):
    try:
        payload = msg.payload.decode()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if "iot/sensors/status" in msg.topic:
            board_name = msg.topic.split("/")[-1]
            if board_name == "home-iot":
                if payload == "online":
                    status = True
                    heartbeats[board_name] = time.time()
                elif payload == "offline":
                    status = False
                    if board_name in heartbeats:
                        del heartbeats[board_name]
                else:
                    return  # Exit if unknown payload for this board
            else:
                status = ""

            # Record status only if it changed
            if board_name not in last_statuses or last_statuses[board_name] != status:
                record = {
                    "timestamp": timestamp,
                    "board_name": board_name,
                    "status": status
                }

                with open(STATUS_FILE, "a") as f:
                    f.write(json.dumps(record) + "\n")
                last_statuses[board_name] = status
                print(f"[{timestamp}] [STATUS] {board_name} is now {status}", flush=True)

        elif "iot/sensors" in msg.topic:
            print(f"[{timestamp}] [{msg.topic}] {payload}", flush=True)
            sensor_name = msg.topic.split("/")[-1]
            if sensor_name == "air_temp":
                value = float(payload)
            elif sensor_name == "light":
                if payload == "on":
                    value = True
                elif payload == "off":
                    value = False
                else:
                    value = payload

            # Prepare record
            record = {
                "timestamp": timestamp,
                "sensor_name": sensor_name,
                "value": value
            }

            # Store to JSON (line-delimited format for efficient appending)
            with open(DATA_FILE, "a") as f:
                f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"Error processing message: {e}", flush=True)


def main():
    # Load existing statuses to avoid duplicating records on restart
    if os.path.exists(STATUS_FILE):
        try:
            with open(STATUS_FILE, "r") as f:
                for line in f:
                    if line.strip():
                        record = json.loads(line)
                        last_statuses[record["board_name"]] = record["status"]
        except Exception:
            pass

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"Connecting to {MQTT_BROKER}:{MQTT_PORT}...")

    connected = False
    while not connected:
        try:
            client.connect(MQTT_BROKER, MQTT_PORT, 60)
            connected = True
        except Exception as e:
            print(f"Waiting for broker... ({e})")
            time.sleep(1)

    while True:
        client.loop(1)

        # Check for timeouts
        now = time.time()
        for board_name, last_time in list(heartbeats.items()):
            if now - last_time > TIMEOUT:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Update status to offline ONLY if it changed
                if board_name not in last_statuses or last_statuses[board_name] != False:
                    record = {
                        "timestamp": timestamp,
                        "board_name": board_name,
                        "status": False
                    }
                    with open(STATUS_FILE, "a") as f:
                        f.write(json.dumps(record) + "\n")
                    last_statuses[board_name] = False
                    print(f"[{timestamp}] [STATUS] {board_name} timed out (offline)", flush=True)

                del heartbeats[board_name]


if __name__ == "__main__":
    main()
