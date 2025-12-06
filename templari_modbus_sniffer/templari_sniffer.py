#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
FLOORS = options.get("floors", [])
MQTT_HOST = options.get("mqtt_host", "core-mosquitto")
MQTT_PORT = options.get("mqtt_port", 1883)
MQTT_USER = options.get("mqtt_user", "")
MQTT_PASS = options.get("mqtt_pass", "")
AUTOGEN_MQTT = options.get("autogen_mqtt_entities", True)
MQTT_PREFIX = options.get("mqtt_prefix", "templari")
LOG_ENABLED = options.get("log_enabled", False)

LOGFILE = "/homeassistant/modbus_templari_sniffer.log"

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

sock = connect_bridge()
buffer = bytearray()

if ROOMS:
    room_ids = [int(room["id"]) for room in ROOMS]
    room_by_id = {int(r["id"]): r for r in ROOMS}
    room_list_str = ", ".join(f"{rid} ({room_by_id[rid]['name']})" for rid in room_ids)
    print(f"[{datetime.now().isoformat()}] Monitoraggio ROOM: {room_list_str}")

if FLOORS:
    floor_ids = [int(floor["id"]) for floor in FLOORS]
    floor_by_id = {int(f["id"]): f for f in FLOORS}
    floor_list_str = ", ".join(f"{fid} ({floor_by_id[fid]['name']})" for fid in floor_ids)
    print(f"[{datetime.now().isoformat()}] Monitoraggio FLOOR: {floor_list_str}")

# --- AUTOGENERAZIONE SENSORI MQTT HOME ASSISTANT ---
if AUTOGEN_MQTT:
    for room in ROOMS:
        rid = room["id"]
        rname = room["name"]
    
        # sensor da creare sempre
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
                print(f"[{datetime.now().isoformat()}] ERROR publishing discovery for sensor {payload['unique_id']}")
                sys.exit(1) 
    
        # binary_sensor da creare sempre
        topic = f"homeassistant/binary_sensor/{MQTT_PREFIX}_room_{rid}_request/config"
        payload = {
            "unique_id": f"{MQTT_PREFIX}_room_{rid}_request",
            "default_entity_id": f"binary_sensor.{MQTT_PREFIX}_room_{rid}_request",
            "name": f"Testina {rname}",
            "state_topic": f"{MQTT_PREFIX}/room/{rid}/request",
            "payload_on": "1",
            "payload_off": "0",
            "device_class": "opening",
            "expire_after": 300
        }
        result = client.publish(topic, json.dumps(payload), retain=True)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"[{datetime.now().isoformat()}] ERROR publishing discovery for sensor {payload['unique_id']}")
            sys.exit(1) 

    for floor in FLOORS:
        fid = floor["id"]
        fname = floor["name"]
    
        # sensor da creare sempre
        sensors = [
            ("flow_temperature", "Temperatura Mandata", "°C", "temperature"),
            ("return_temperature", "Temperatura Ritorno", "°C", "temperature"),
            ("delta_t", "Delta T", "°C", "temperature"),
        ]
    
        for key, label, unit, device_class in sensors:
            topic = f"homeassistant/sensor/{MQTT_PREFIX}_floor_{fid}_{key}/config"
            payload = {
                "unique_id": f"{MQTT_PREFIX}_floor_{fid}_{key}",
                "default_entity_id": f"sensor.{MQTT_PREFIX}_floor_{fid}_{key}",
                "name": f"{label} {fname}",
                "state_topic": f"{MQTT_PREFIX}/floor/{fid}/{key}",
                "unit_of_measurement": unit,
                "device_class": device_class,
                "state_class": "measurement",
                "expire_after": 300
            }
            result = client.publish(topic, json.dumps(payload), retain=True)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"[{datetime.now().isoformat()}] ERROR publishing discovery for sensor {payload['unique_id']}")
                sys.exit(1) 
    
        # sensori opzionali
        if floor_by_id[int(fid)].get("circulator_sensor", False):
            topic = f"homeassistant/sensor/{MQTT_PREFIX}_floor_{fid}_circulator_percentage/config"
            payload = {
                "unique_id": f"{MQTT_PREFIX}_floor_{fid}_circulator_percentage",
                "default_entity_id": f"sensor.{MQTT_PREFIX}_floor_{fid}_circulator_percentage",
                "name": f"Percentuale Circolatore {fname}",
                "state_topic": f"{MQTT_PREFIX}/floor/{fid}/circulator_percentage",
                "unit_of_measurement": "%",
                "state_class": "measurement",
                "expire_after": 300
            }
            result = client.publish(topic, json.dumps(payload), retain=True)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"[{datetime.now().isoformat()}] ERROR publishing discovery for sensor {payload['unique_id']}")
                sys.exit(1) 
        
        if floor_by_id[int(fid)].get("mixing_sensor", False):
            topic = f"homeassistant/sensor/{MQTT_PREFIX}_floor_{fid}_mixing_percentage/config"
            payload = {
                "unique_id": f"{MQTT_PREFIX}_floor_{fid}_mixing_percentage",
                "default_entity_id": f"sensor.{MQTT_PREFIX}_floor_{fid}_mixing_percentage",
                "name": f"Percentuale Miscelazione {fname}",
                "state_topic": f"{MQTT_PREFIX}/floor/{fid}/mixing_percentage",
                "unit_of_measurement": "%",
                "state_class": "measurement",
                "expire_after": 300
            }
            result = client.publish(topic, json.dumps(payload), retain=True)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"[{datetime.now().isoformat()}] ERROR publishing discovery for sensor {payload['unique_id']}")
                sys.exit(1) 
                
        # ciclo relè da 1 a 8
        for i in range(1, 8 + 1):
            if floor_by_id[int(fid)].get(f"relay_{i}_sensor", False):
            
                topic = f"homeassistant/binary_sensor/{MQTT_PREFIX}_floor_{fid}_relay_{i}/config"
                payload = {
                    "unique_id": f"{MQTT_PREFIX}_floor_{fid}_relay_{i}",
                    "default_entity_id": f"binary_sensor.{MQTT_PREFIX}_floor_{fid}_relay_{i}",
                    "name": f"Relè {i} {fname}",
                    "state_topic": f"{MQTT_PREFIX}/floor/{fid}/relay_{i}",
                    "payload_on": "1",
                    "payload_off": "0",
                    "device_class": "opening",
                    "expire_after": 300
                }
                result = client.publish(topic, json.dumps(payload), retain=True)
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    print(f"[{datetime.now().isoformat()}] ERROR publishing discovery for sensor {payload['unique_id']}")
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

    # --- FILTRO ERRORE HTML/504 CHE ALCUNI BRIDGE POSSONO DARE OGNI TANTO ---
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

    # eventuale log modbus completo
    if LOG_ENABLED:
        log_raw(data)
    
    buffer.extend(data)

    # --- PARSING MODBUS ---
    while True:

        if (parsed := modbus_parsing.parse_modbus_room(buffer)) is not None:
        
            slave, temp, hum, dew, set, req, end_idx = parsed
            buffer = buffer[end_idx:]

            if slave in room_ids:
                ts = datetime.now().isoformat()
            
                safe_publish(f"{MQTT_PREFIX}/room/{slave}/temperature", temp)
                safe_publish(f"{MQTT_PREFIX}/room/{slave}/humidity", hum)
                safe_publish(f"{MQTT_PREFIX}/room/{slave}/dew_point", dew)
                safe_publish(f"{MQTT_PREFIX}/room/{slave}/set_point", set)
                safe_publish(f"{MQTT_PREFIX}/room/{slave}/request", req)
            
                print(f"[{ts}] [Room {slave} {room_by_id[slave]['name']}] Temp={temp}°C Hum={hum}% Dew={dew}°C Set Point={set}°C Req={req}")

        elif (parsed := modbus_parsing.parse_modbus_floor(buffer)) is not None:

            slave, temp_flow, temp_return, temp_delta_t, perc_circulator, perc_mix, relay_1, relay_2, relay_3, relay_4, relay_5, relay_6, relay_7, relay_8, end_idx = parsed
            buffer = buffer[end_idx:]

            if slave in floor_ids:
                ts = datetime.now().isoformat()
            
                safe_publish(f"{MQTT_PREFIX}/floor/{slave}/flow_temperature", temp_flow)
                safe_publish(f"{MQTT_PREFIX}/floor/{slave}/return_temperature", temp_return)
                safe_publish(f"{MQTT_PREFIX}/floor/{slave}/delta_t", temp_delta_t)
                
                if floor_by_id[slave].get("circulator_sensor", False):
                    safe_publish(f"{MQTT_PREFIX}/floor/{slave}/circulator_percentage", perc_circulator)
                
                if floor_by_id[slave].get("mixing_sensor", False):
                    safe_publish(f"{MQTT_PREFIX}/floor/{slave}/mixing_percentage", perc_mix)
                
                if floor_by_id[slave].get("relay_1_sensor", False):
                    safe_publish(f"{MQTT_PREFIX}/floor/{slave}/relay_1", relay_1)
                
                if floor_by_id[slave].get("relay_2_sensor", False):
                    safe_publish(f"{MQTT_PREFIX}/floor/{slave}/relay_2", relay_2)
                
                if floor_by_id[slave].get("relay_3_sensor", False):
                    safe_publish(f"{MQTT_PREFIX}/floor/{slave}/relay_3", relay_3)
                
                if floor_by_id[slave].get("relay_4_sensor", False):
                    safe_publish(f"{MQTT_PREFIX}/floor/{slave}/relay_4", relay_4)
                
                if floor_by_id[slave].get("relay_5_sensor", False):
                    safe_publish(f"{MQTT_PREFIX}/floor/{slave}/relay_5", relay_5)
                
                if floor_by_id[slave].get("relay_6_sensor", False):
                    safe_publish(f"{MQTT_PREFIX}/floor/{slave}/relay_6", relay_6)
                
                if floor_by_id[slave].get("relay_7_sensor", False):
                    safe_publish(f"{MQTT_PREFIX}/floor/{slave}/relay_7", relay_7)
                
                if floor_by_id[slave].get("relay_8_sensor", False):
                    safe_publish(f"{MQTT_PREFIX}/floor/{slave}/relay_8", relay_8)
            
                print(f"[{ts}] [Floor {slave} {floor_by_id[slave]['name']}] Flow={temp_flow}°C Return={temp_return}°C DeltaT={temp_delta_t}°C Circulator={perc_circulator}% Mix={perc_mix}% Relays={relay_1} {relay_2} {relay_3} {relay_4} {relay_5} {relay_6} {relay_7} {relay_8}")

        else:
            break

    time.sleep(0.01)
