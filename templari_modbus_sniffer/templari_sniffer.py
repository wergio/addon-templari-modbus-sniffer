#!/usr/bin/env python3
import socket
import time
from datetime import datetime
import argparse
import paho.mqtt.client as mqtt
import warnings
import json
import os
import sys
import modbus_parsing

sys.stdout.reconfigure(line_buffering=True)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- OPTIONS ---
OPTIONS_FILE = "/data/options.json"

with open(OPTIONS_FILE, "r") as f:
    options = json.load(f)

BRIDGE_HOST = options.get("bridge_host")
BRIDGE_PORT = options.get("bridge_port", 8899)
ROOMS = options.get("rooms", [])
MQTT_HOST = options.get("mqtt_host", "core-mosquitto")
MQTT_PORT = options.get("mqtt_port", 1883)
MQTT_USER = options.get("mqtt_user", "")
MQTT_PASS = options.get("mqtt_pass", "")
AUTOGEN_MQTT = options.get("autogen_mqtt_entities", True)
MQTT_PREFIX = options.get("mqtt_prefix", "templari")
LOG_ENABLED = options.get("log_enabled", False)

LOGFILE = "/homeassistant/modbus_templari_sniffer.log"

# --- MQTT SETUP ---
client = mqtt.Client()
if MQTT_USER:
    client.username_pw_set(MQTT_USER, MQTT_PASS)

try:
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.loop_start()
    print(f"[{datetime.now().isoformat()}] Connected to MQTT broker {MQTT_HOST}:{MQTT_PORT}")
except Exception as e:
    print(f"[{datetime.now().isoformat()}] MQTT connection failed:", e)
    sys.exit(1) 

# --- FUNZIONI ---
def log_raw(data):
    hex_data = data.hex()
    ts = datetime.now().isoformat()
    try:
        with open(LOGFILE, "a") as f:
            f.write(f"{ts} {hex_data}\n")
    except Exception as e:
        print(f"[{ts}] ERROR writing log: {e}")
        sys.exit(1) 

def safe_publish(topic, payload):
    ts = datetime.now().isoformat()
    try:
        info = client.publish(topic, payload)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"[{ts}] MQTT PUBLISH ERROR rc={info.rc} topic={topic}")
    except Exception as e:
        print(f"[{ts}] MQTT publish EXCEPTION topic={topic}: {e}")

# --- SOCKET INIT ---
def connect_bridge():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        print(f"[{datetime.now().isoformat()}] Connecting to bridge device {BRIDGE_HOST}:{BRIDGE_PORT}")
        sock.connect((BRIDGE_HOST, BRIDGE_PORT))
        print(f"[{datetime.now().isoformat()}] Connected to bridge device")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERROR: Cannot connect to bridge device: {e}")
        sys.exit(1) 
    return sock

sock = connect_bridge()
buffer = bytearray()

room_ids = [int(room["id"]) for room in ROOMS]
room_names = {int(room["id"]): room["name"] for room in ROOMS}
room_list_str = ", ".join(f"{rid} ({room_names[rid]})" for rid in room_ids)
print(f"[{datetime.now().isoformat()}] Inizio monitoraggio ROOM: {room_list_str}")

if AUTOGEN_MQTT:
    for room in ROOMS:
        rid = room["id"]
        rname = room["name"]
    
        # sensor da creare
        sensors = [
            ("temperature", "Temperatura", "°C", "temperature"),
            ("humidity", "Umidità", "%", "humidity"),
            ("dew_point", "Punto di Rugiada", "°C", "temperature"),
            ("set_point", "Set Point", "°C", "temperature"),
        ]
    
        for key, label, unit, device_class in sensors:
            topic = f"homeassistant/sensor/{MQTT_PREFIX}_room_{rid}_{key}/config"
            payload = {
                "unique_id": f"{MQTT_PREFIX}_room_{rid}_{key}",
                "default_entity_id": f"sensor.{MQTT_PREFIX}_room_{rid}_{key}",
                "name": f"{label} {rname}",
                "state_topic": f"{MQTT_PREFIX}/room/{rid}/{key}",
                "unit_of_measurement": unit,
                "device_class": device_class,
                "state_class": "measurement",
                "expire_after": 300
            }
            result = client.publish(topic, json.dumps(payload), retain=True)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"[{datetime.now().isoformat()}] ERROR publishing discovery for sensor {s['unique_id']}")
                sys.exit(1) 
    
        # binary sensor da creare
        topic_bin = f"homeassistant/binary_sensor/{MQTT_PREFIX}_room_{rid}_request/config"
        payload_bin = {
            "unique_id": f"{MQTT_PREFIX}_room_{rid}_request",
            "default_entity_id": f"binary_sensor.{MQTT_PREFIX}_room_{rid}_request",
            "name": f"Testina {rname}",
            "state_topic": f"{MQTT_PREFIX}/room/{rid}/request",
            "payload_on": "1",
            "payload_off": "0",
            "device_class": "opening",
            "expire_after": 300
        }
        result = client.publish(topic_bin, json.dumps(payload_bin), retain=True)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"[{datetime.now().isoformat()}] ERROR publishing discovery for binary sensor {binary['unique_id']}")
            sys.exit(1) 

    print(f"[{datetime.now().isoformat()}] Generati automaticamente sensori MQTT")
    
# --- LOOP PRINCIPALE ---
while True:
    try:
        data = sock.recv(2048)
        # print(f"[{datetime.now().isoformat()}] Loop tick, bytes received: {len(data)}")
    except socket.timeout:
        data = b""
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERROR receiving data: {e}")
        time.sleep(1)
        sock = connect_bridge()
        continue

    # Se non arriva nulla
    if not data:
        print(f"[{datetime.now().isoformat()}] No data received, socket closed? Reconnecting...")
        try:
            sock.close()
        except:
            pass
        time.sleep(10)
        sock = connect_bridge()
        buffer = bytearray()
        continue

    # --- FILTRO HTML/504 ---
    try:
        text_data = data.decode(errors="ignore")
    except:
        text_data = ""

    if "<html>" in text_data or "504" in text_data:
        print(f"[{datetime.now().isoformat()}] Bridge sent HTML/504, reconnecting...")
        buffer = bytearray()
        try:
    	    sock.close()
        except:
    	    pass
        time.sleep(10)
        sock = connect_bridge()
        continue

    if LOG_ENABLED:
        log_raw(data)
    
    buffer.extend(data)

    # --- PARSING MODBUS ---
    while True:
        parsed = modbus_parsing.parse_modbus_room(buffer)
        if not parsed:
            break
        slave, temp, hum, dew, set, req, end_idx = parsed
        buffer = buffer[end_idx:]

        if slave in room_ids:
            room_name = room_names[slave]
            ts = datetime.now().isoformat()
            
            safe_publish(f"{MQTT_PREFIX}/room/{slave}/temperature", temp)
            safe_publish(f"{MQTT_PREFIX}/room/{slave}/humidity", hum)
            safe_publish(f"{MQTT_PREFIX}/room/{slave}/dew_point", dew)
            safe_publish(f"{MQTT_PREFIX}/room/{slave}/set_point", set)
            safe_publish(f"{MQTT_PREFIX}/room/{slave}/request", req)
            
            print(f"[{ts}] [Room {slave} {room_name}] Temp={temp}°C Hum={hum}% Dew={dew}°C Set Point={set}°C Req={req}")

    time.sleep(0.01)
