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
import re
import sys
import modbus_parsing

sys.stdout.reconfigure(line_buffering=True)
warnings.filterwarnings("ignore", category=DeprecationWarning)

# --- OPTIONS ---
OPTIONS_FILE = "/data/options.json"

# Intervallo valido per un indirizzo slave Modbus.
MODBUS_ID_MIN = 1
MODBUS_ID_MAX = 247
# Il prefisso finisce sia nei topic MQTT che negli unique_id/entity_id di HA,
# che ammettono solo lettere, numeri, trattino e underscore.
PREFIX_RE = re.compile(r"^[A-Za-z0-9_-]+$")

def config_error(msg):
    print(f"[{datetime.now().isoformat()}] CONFIG ERROR: {msg}")
    sys.exit(1)

def config_warning(msg):
    print(f"[{datetime.now().isoformat()}] CONFIG WARNING: {msg}")

def valid_port(value, field):
    try:
        port = int(value)
    except (TypeError, ValueError):
        config_error(f"{field}: '{value}' non e' un numero di porta valido")
    if not 1 <= port <= 65535:
        config_error(f"{field}: {port} fuori dall'intervallo 1-65535")
    return port

def valid_devices(entries, kind, seen):
    """Scarta le singole voci inutilizzabili invece di far fallire tutto l'addon."""
    if not isinstance(entries, list):
        config_error(f"'{kind}s' deve essere una lista")
    valid = []
    for pos, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            config_warning(f"{kind} #{pos}: voce non valida, ignorata")
            continue
        try:
            dev_id = int(entry.get("id"))
        except (TypeError, ValueError):
            config_warning(f"{kind} #{pos}: id '{entry.get('id')}' non e' un numero, voce ignorata")
            continue
        if not MODBUS_ID_MIN <= dev_id <= MODBUS_ID_MAX:
            config_warning(f"{kind} #{pos}: id {dev_id} fuori dall'intervallo Modbus {MODBUS_ID_MIN}-{MODBUS_ID_MAX}, voce ignorata")
            continue
        # Un id Modbus identifica un solo dispositivo sul bus: se compare due
        # volte (anche fra room e floor) una delle due voci e' sbagliata.
        if dev_id in seen:
            config_warning(f"{kind} #{pos}: id {dev_id} gia' usato da {seen[dev_id]}, voce ignorata")
            continue
        name = str(entry.get("name") or "").strip()
        if not name:
            name = f"{kind.capitalize()} {dev_id}"
            config_warning(f"{kind} #{pos}: nome vuoto, uso '{name}'")
        seen[dev_id] = f"{kind} {name}"
        valid.append(dict(entry, id=dev_id, name=name))
    return valid

try:
    with open(OPTIONS_FILE, "r") as f:
        options = json.load(f)
except Exception as e:
    config_error(f"impossibile leggere {OPTIONS_FILE}: {e}")

BRIDGE_HOST = str(options.get("bridge_host") or "").strip()
if not BRIDGE_HOST:
    config_error("bridge_host non configurato")
BRIDGE_PORT = valid_port(options.get("bridge_port", 8899), "bridge_port")

MQTT_HOST = str(options.get("mqtt_host", "core-mosquitto") or "").strip()
if not MQTT_HOST:
    config_error("mqtt_host non configurato")
MQTT_PORT = valid_port(options.get("mqtt_port", 1883), "mqtt_port")
MQTT_USER = str(options.get("mqtt_user") or "")
MQTT_PASS = str(options.get("mqtt_pass") or "")
AUTOGEN_MQTT = options.get("autogen_mqtt_entities", True)

MQTT_PREFIX = str(options.get("mqtt_prefix", "templari") or "").strip()
if not PREFIX_RE.match(MQTT_PREFIX):
    config_error(f"mqtt_prefix '{MQTT_PREFIX}': ammessi solo lettere, numeri, '-' e '_'")

LOG_ENABLED = options.get("log_enabled", False)

seen_ids = {}
ROOMS = valid_devices(options.get("rooms", []), "room", seen_ids)
FLOORS = valid_devices(options.get("floors", []), "floor", seen_ids)

# La scheda deumidifica e' sempre una sola, quindi e' un singolo id opzionale e
# non una lista. Come per le singole voci di room e floor, un valore sbagliato
# disabilita solo questo sensore invece di fermare l'addon.
DEHUMIDIFIER_ID = options.get("dehumidifier_id")
if DEHUMIDIFIER_ID in (None, ""):
    DEHUMIDIFIER_ID = None
else:
    try:
        DEHUMIDIFIER_ID = int(DEHUMIDIFIER_ID)
    except (TypeError, ValueError):
        config_warning(f"dehumidifier_id: '{DEHUMIDIFIER_ID}' non e' un numero, deumidifica ignorata")
        DEHUMIDIFIER_ID = None
    else:
        if not MODBUS_ID_MIN <= DEHUMIDIFIER_ID <= MODBUS_ID_MAX:
            config_warning(f"dehumidifier_id: {DEHUMIDIFIER_ID} fuori dall'intervallo Modbus "
                           f"{MODBUS_ID_MIN}-{MODBUS_ID_MAX}, deumidifica ignorata")
            DEHUMIDIFIER_ID = None
        elif DEHUMIDIFIER_ID in seen_ids:
            config_warning(f"dehumidifier_id: {DEHUMIDIFIER_ID} gia' usato da "
                           f"{seen_ids[DEHUMIDIFIER_ID]}, deumidifica ignorata")
            DEHUMIDIFIER_ID = None
        else:
            seen_ids[DEHUMIDIFIER_ID] = "deumidifica"

if not ROOMS and not FLOORS and DEHUMIDIFIER_ID is None:
    config_error("nessuna room, floor o deumidifica valida configurata, non c'e' nulla da monitorare")

LOGFILE = "/homeassistant/modbus_templari_sniffer.log"

# --- TIMING ---
# Timeout della singola recv(): il bus zitto per qualche secondo NON e' un errore,
# serve solo a non restare bloccati per sempre dentro la recv.
RECV_TIMEOUT = 5
# Secondi senza NESSUN frame valido prima di sospettare una connessione half-open
# (es. il WiFi del bridge cade e il FIN non arriva mai). Va tenuto ben sopra al
# ciclo di polling del pannello, altrimenti si riconnette per un semplice ritardo.
NO_FRAME_TIMEOUT = 180
# Attesa fra due tentativi di connessione al bridge falliti.
CONNECT_RETRY_DELAY = 30
# Backoff prima di riconnettere dopo un errore certo (peer che chiude, errore di
# rete, pagina HTTP al posto dei dati): evita di ciclare a vuoto se il bridge
# accetta la connessione e la chiude subito.
RECONNECT_BACKOFF = 5

# --- BUFFER ---
# Byte da conservare quando nessun parser aggancia niente. Quando i
# parser falliscono su un buffer lungo L, ogni posizione i con L-i >= lunghezza
# del frame e' gia' stata testata, e i byte non cambiano piu': quelle posizioni
# non potranno mai diventare valide. Resta da verificare solo la coda, che
# potrebbe contenere un frame ancora incompleto.
# Va ricavato dal massimo delle lunghezze gestite: se un domani si aggiunge un
# parser per frame piu' lunghi, questo deve crescere con lui.
BUFFER_KEEP = max(modbus_parsing.ROOM_FRAME_LEN,
                  modbus_parsing.FLOOR_FRAME_LEN,
                  modbus_parsing.DEHUMIDIFIER_FRAME_LEN) - 1
# Ogni quanti secondi riportare quanto traffico non riconosciuto passa sul bus.
STATS_INTERVAL = 3600

# --- FUNZIONI ---
def close_socket(sock):
    if sock is None:
        return
    try:
        sock.close()
    except Exception:
        pass

def looks_like_http(data):
    """
    Alcuni bridge, quando sono in difficolta', rispondono con una pagina di errore
    HTTP invece che con i dati seriali.
    """
    lowered = data.lower()
    return b"<html" in lowered or b"http/1." in lowered

def log_raw(data):
    hex_data = data.hex()
    ts = datetime.now().isoformat()
    try:
        with open(LOGFILE, "a") as f:
            f.write(f"{ts} {hex_data}\n")
    except Exception as e:
        print(f"[{ts}] ERROR writing log: {e}") 

def safe_publish(topic, payload):
    ts = datetime.now().isoformat()
    try:
        info = client.publish(topic, payload)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"[{ts}] MQTT PUBLISH ERROR rc={info.rc} topic={topic}")
    except Exception as e:
        print(f"[{ts}] MQTT publish EXCEPTION topic={topic}: {e}")

def connect_bridge(old_sock=None):
    # La socket precedente va sempre chiusa, altrimenti ogni riconnessione
    # si lascia dietro un file descriptor aperto.
    close_socket(old_sock)
    while True:
        # Una socket il cui connect() e' fallito non e' riutilizzabile: va
        # ricreata a ogni tentativo, altrimenti su Linux i retry successivi
        # possono fallire per sempre anche quando il bridge torna raggiungibile.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(RECV_TIMEOUT)
        try:
            print(f"[{datetime.now().isoformat()}] Connecting to bridge device {BRIDGE_HOST}:{BRIDGE_PORT}")
            sock.connect((BRIDGE_HOST, BRIDGE_PORT))
            print(f"[{datetime.now().isoformat()}] Connected to bridge device")
            return sock
        except Exception as e:
            close_socket(sock)
            print(f"[{datetime.now().isoformat()}] ERROR: Cannot connect to bridge device: {e}, retry in {CONNECT_RETRY_DELAY} seconds")
            time.sleep(CONNECT_RETRY_DELAY)

# --- MQTT SETUP ---
client = mqtt.Client()
if MQTT_USER:
    client.username_pw_set(MQTT_USER, MQTT_PASS)

while True:
    try:
        client.connect(MQTT_HOST, MQTT_PORT, 60)
        client.loop_start()
        print(f"[{datetime.now().isoformat()}] Connected to MQTT broker {MQTT_HOST}:{MQTT_PORT}")
        break
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] MQTT connection failed: {e}, retry in {CONNECT_RETRY_DELAY} seconds")
        time.sleep(CONNECT_RETRY_DELAY)

sock = connect_bridge()
buffer = bytearray()

# Vanno definiti sempre, anche a liste vuote: il loop principale li consulta a
# ogni frame riconosciuto. Gli id sono gia' interi validati da valid_devices().
room_ids = [room["id"] for room in ROOMS]
room_by_id = {r["id"]: r for r in ROOMS}
floor_ids = [floor["id"] for floor in FLOORS]
floor_by_id = {f["id"]: f for f in FLOORS}

if ROOMS:
    room_list_str = ", ".join(f"{rid} ({room_by_id[rid]['name']})" for rid in room_ids)
    print(f"[{datetime.now().isoformat()}] Monitoraggio ROOM: {room_list_str}")

if FLOORS:
    floor_list_str = ", ".join(f"{fid} ({floor_by_id[fid]['name']})" for fid in floor_ids)
    print(f"[{datetime.now().isoformat()}] Monitoraggio FLOOR: {floor_list_str}")

if DEHUMIDIFIER_ID is not None:
    print(f"[{datetime.now().isoformat()}] Monitoraggio DEUMIDIFICA: {DEHUMIDIFIER_ID}")

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

    # La deumidifica e' una sola: l'id non entra nel topic ne' nell'unique_id,
    # cosi' cambiarlo in configurazione non lascia entita' orfane in HA.
    if DEHUMIDIFIER_ID is not None:
        topic = f"homeassistant/binary_sensor/{MQTT_PREFIX}_dehumidifier_state/config"
        payload = {
            "unique_id": f"{MQTT_PREFIX}_dehumidifier_state",
            "default_entity_id": f"binary_sensor.{MQTT_PREFIX}_dehumidifier_state",
            "name": "Deumidifica",
            "state_topic": f"{MQTT_PREFIX}/dehumidifier/state",
            "payload_on": "1",
            "payload_off": "0",
            "device_class": "running",
            "expire_after": 300
        }
        result = client.publish(topic, json.dumps(payload), retain=True)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"[{datetime.now().isoformat()}] ERROR publishing discovery for sensor {payload['unique_id']}")

    print(f"[{datetime.now().isoformat()}] Generati automaticamente sensori MQTT")
    
# --- LOOP PRINCIPALE ---
# Istante dell'ultimo frame Modbus valido: e' su questo che si basa il watchdog,
# non sulla singola recv() andata in timeout.
last_frame_ts = time.monotonic()
last_stats_ts = time.monotonic()
stats_frames = 0
stats_discarded = 0

while True:
    try:
        data = sock.recv(2048)
        # print(f"[{datetime.now().isoformat()}] Loop tick, bytes received: {len(data)}")
    except socket.timeout:
        # Qualche secondo di silenzio sul bus non e' un errore. Lo diventa solo se
        # non arriva nessun frame valido per NO_FRAME_TIMEOUT: a quel punto e'
        # probabile che la connessione sia morta senza che ce ne siamo accorti.
        if time.monotonic() - last_frame_ts > NO_FRAME_TIMEOUT:
            print(f"[{datetime.now().isoformat()}] No valid frame for {NO_FRAME_TIMEOUT}s, connection probably half-open, reconnecting...")
            sock = connect_bridge(sock)
            buffer = bytearray()
            last_frame_ts = time.monotonic()
        continue
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] ERROR receiving data: {e}")
        time.sleep(RECONNECT_BACKOFF)
        sock = connect_bridge(sock)
        buffer = bytearray()
        last_frame_ts = time.monotonic()
        continue

    # recv() che restituisce b"" significa che il peer ha chiuso davvero
    if not data:
        print(f"[{datetime.now().isoformat()}] Bridge closed the connection, reconnecting...")
        time.sleep(RECONNECT_BACKOFF)
        sock = connect_bridge(sock)
        buffer = bytearray()
        last_frame_ts = time.monotonic()
        continue

    # eventuale log modbus completo
    if LOG_ENABLED:
        log_raw(data)

    # --- FILTRO ERRORE HTML CHE ALCUNI BRIDGE POSSONO DARE OGNI TANTO ---
    if looks_like_http(data):
        print(f"[{datetime.now().isoformat()}] Bridge sent an HTTP error page, reconnecting...")
        time.sleep(RECONNECT_BACKOFF)
        sock = connect_bridge(sock)
        buffer = bytearray()
        last_frame_ts = time.monotonic()
        continue

    buffer.extend(data)

    # --- PARSING MODBUS ---
    while True:

        # I parser scandiscono TUTTO il buffer, quindi vanno provati
        # tutti e va consumato il frame che inizia PRIMA.
        candidates = []
        for kind, parse, frame_len in (
            ("room", modbus_parsing.parse_modbus_room, modbus_parsing.ROOM_FRAME_LEN),
            ("floor", modbus_parsing.parse_modbus_floor, modbus_parsing.FLOOR_FRAME_LEN),
            ("dehumidifier", modbus_parsing.parse_modbus_dehumidifier, modbus_parsing.DEHUMIDIFIER_FRAME_LEN),
        ):
            parsed = parse(buffer)
            if parsed is not None:
                candidates.append((parsed[-1] - frame_len, kind, parsed))

        if not candidates:
            # Nessun frame agganciato: tutto quello che precede la coda e' gia'
            # stato testato senza successo e non potra' mai diventare valido,
            # quindi si puo' buttare. Senza questa potatura il buffer cresce fino
            # al prossimo frame utile, e i parser lo riscandiscono tutto a ogni
            # recv (misurato: 6 KB di picco e 44x di CPU in piu').
            if len(buffer) > BUFFER_KEEP:
                stats_discarded += len(buffer) - BUFFER_KEEP
                buffer = buffer[-BUFFER_KEEP:]
            break

        _, kind, parsed = min(candidates, key=lambda c: c[0])
        buffer = buffer[parsed[-1]:]
        last_frame_ts = time.monotonic()
        stats_frames += 1

        if kind == "room":

            slave, temp, hum, dew, set, req, end_idx = parsed

            if slave in room_ids:
                ts = datetime.now().isoformat()
            
                safe_publish(f"{MQTT_PREFIX}/room/{slave}/temperature", temp)
                safe_publish(f"{MQTT_PREFIX}/room/{slave}/humidity", hum)
                safe_publish(f"{MQTT_PREFIX}/room/{slave}/dew_point", dew)
                safe_publish(f"{MQTT_PREFIX}/room/{slave}/set_point", set)
                safe_publish(f"{MQTT_PREFIX}/room/{slave}/request", req)
            
                print(f"[{ts}] [Room {slave} {room_by_id[slave]['name']}] Temp={temp}°C Hum={hum}% Dew={dew}°C Set Point={set}°C Req={req}")

        elif kind == "floor":

            slave, temp_flow, temp_return, temp_delta_t, perc_circulator, perc_mix, relay_1, relay_2, relay_3, relay_4, relay_5, relay_6, relay_7, relay_8, end_idx = parsed

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

        elif kind == "dehumidifier":

            slave, state, end_idx = parsed

            if slave == DEHUMIDIFIER_ID:
                ts = datetime.now().isoformat()

                safe_publish(f"{MQTT_PREFIX}/dehumidifier/state", state)

                print(f"[{ts}] [Deumidifica {slave}] Stato={state}")

    if time.monotonic() - last_stats_ts >= STATS_INTERVAL:
        print(f"[{datetime.now().isoformat()}] Statistiche ultima ora: {stats_frames} frame decodificati, "
              f"{stats_discarded} byte di traffico non riconosciuto scartati")
        last_stats_ts = time.monotonic()
        stats_frames = 0
        stats_discarded = 0

    time.sleep(0.01)
