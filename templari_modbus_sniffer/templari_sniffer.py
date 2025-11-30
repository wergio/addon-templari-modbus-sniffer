#!/usr/bin/env python3
import socket
import time
from datetime import datetime
import argparse
import paho.mqtt.client as mqtt
import warnings
import sys
sys.stdout.reconfigure(line_buffering=True)
warnings.filterwarnings("ignore", category=DeprecationWarning)

parser = argparse.ArgumentParser()
parser.add_argument("--bridge-host")
parser.add_argument("--bridge-port", type=int)
parser.add_argument("--rooms")  # elenco separato da virgola
parser.add_argument("--mqtt-host")
parser.add_argument("--mqtt-port", type=int)
parser.add_argument("--mqtt-user", default="")
parser.add_argument("--mqtt-pass", default="")
parser.add_argument("--log", action="store_true")
args = parser.parse_args()

# --- CONFIG ---
BRIDGE_HOST = args.bridge_host
BRIDGE_PORT = args.bridge_port
ROOMS = [int(r.strip()) for r in args.rooms.split(",")]

MQTT_BROKER = args.mqtt_host
MQTT_PORT = args.mqtt_port
MQTT_USER = args.mqtt_user
MQTT_PASS = args.mqtt_pass

LOG_ENABLED = args.log
LOGFILE = "/config/modbus_templari_sniffer.log"

# --- MQTT ---
client = mqtt.Client()
if MQTT_USER:
    client.username_pw_set(MQTT_USER, MQTT_PASS)

try:
    client.connect(MQTT_BROKER, MQTT_PORT, 60)
    client.loop_start()
    print(f"[{datetime.now().isoformat()}] Connected to MQTT broker {MQTT_BROKER}:{MQTT_PORT}")
except Exception as e:
    print(f"[{datetime.now().isoformat()}] MQTT connection failed:", e)

# --- FUNZIONI ---
def log_raw(data_hex):
    if LOG_ENABLED:
        ts = datetime.now().isoformat()
        with open(LOGFILE, "a") as f:
            f.write(f"{ts} {data_hex}\n")

def parse_modbus(data):
    """
    Cerca nel blocco di byte un possibile frame Modbus RTU di tipo:
    [slave][0x03][byte_count][payload...]
    Restituisce (slave, temperature, humidity) se trova una risposta valida
    oppure None.
    """
    # Scorro il blob per trovare pattern possibile
    i = 0
    while i <= len(data) - 5:
        slave = data[i]
        fc = data[i+1]
        if fc != 0x03:
            i += 1
            continue
        byte_count = data[i+2]
        end = i + 3 + byte_count
        if end <= len(data):
            # payload estraibile
            payload = data[i+3:end]
            if len(payload) >= 4:
                temp_raw = (payload[0] << 8) | payload[1]
                hum_raw  = (payload[2] << 8) | payload[3]
                temp = temp_raw / 10.0
                hum = hum_raw / 10.0
                return slave, temp, hum, end  # ritorno anche end index per avanzare
        i += 1
    return None

# --- SOCKET ---
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(5)

try:
    print(f"[{datetime.now().isoformat()}] Connecting to bridge device {BRIDGE_HOST}:{BRIDGE_PORT}")
    sock.connect((BRIDGE_HOST, BRIDGE_PORT))
    print(f"[{datetime.now().isoformat()}] Connected to bridge device")
except Exception as e:
    print(f"[{datetime.now().isoformat()}] ERROR: Cannot connect to bridge device: {e}")
    exit(1)

buffer = bytearray()

# --- LOOP PRINCIPALE ---
while True:
    try:
        data = sock.recv(2048)
    except socket.timeout:
        data = b""
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERROR receiving data: {e}")
        time.sleep(1)
        continue

    if not data:
        time.sleep(0.05)
        continue

    hex_data = data.hex()
    log_raw(hex_data)
    buffer.extend(data)

    while True:
        parsed = parse_modbus(buffer)
        if not parsed:
            break

        slave, temp, hum, end_idx = parsed
        buffer = buffer[end_idx:]

        if slave in ROOMS:
            ts = datetime.now().isoformat()
            topic_temp = f"templari/room/{slave}/temperature"
            topic_hum  = f"templari/room/{slave}/humidity"
            client.publish(topic_temp, temp)
            client.publish(topic_hum, hum)
            print(f"[{ts}] [Room {slave}] Temp={temp}°C Hum={hum}%")

    time.sleep(0.01)

