#!/usr/bin/env bash
set -e

CONFIG_FILE=/data/options.json

BRIDGE_HOST=$(jq -r '.bridge_host' "$CONFIG_FILE")
BRIDGE_PORT=$(jq -r '.bridge_port' "$CONFIG_FILE")
ROOMS=$(jq -r '.rooms' "$CONFIG_FILE")
MQTT_HOST=$(jq -r '.mqtt_host' "$CONFIG_FILE")
MQTT_PORT=$(jq -r '.mqtt_port' "$CONFIG_FILE")
MQTT_USER=$(jq -r '.mqtt_user' "$CONFIG_FILE")
MQTT_PASS=$(jq -r '.mqtt_pass' "$CONFIG_FILE")
LOG_ENABLED=$(jq -r '.log_enabled' "$CONFIG_FILE")

# Se log_enabled è true → aggiunge --log
if [[ "$LOG_ENABLED" == "true" ]]; then
  LOG_FLAG="--log"
else
  LOG_FLAG=""
fi

echo "Eseguo: python3 /app/templari_sniffer.py --bridge-host \"$BRIDGE_HOST\" --bridge-port \"$BRIDGE_PORT\" --rooms \"$ROOMS\" --mqtt-host \"$MQTT_HOST\" --mqtt-port \"$MQTT_PORT\" ${MQTT_USER:+--mqtt-user \"$MQTT_USER\"} ${MQTT_PASS:+--mqtt-pass \"$MQTT_PASS\"} $LOG_FLAG"

python3 /app/templari_sniffer.py \
  --bridge-host "$BRIDGE_HOST" \
  --bridge-port "$BRIDGE_PORT" \
  --rooms "$ROOMS" \
  --mqtt-host "$MQTT_HOST" \
  --mqtt-port "$MQTT_PORT" \
  ${MQTT_USER:+--mqtt-user "$MQTT_USER"} \
  ${MQTT_PASS:+--mqtt-pass "$MQTT_PASS"} \
  $LOG_FLAG

