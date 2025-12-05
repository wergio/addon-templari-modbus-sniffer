def crc16_modbus(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc

def parse_modbus_room(data):
    """
    Cerca nel blocco di byte un possibile frame Modbus RTU del sensore room:
    Restituisce (slave, temperature, humidity, ecc) se trova una risposta valida
    oppure None.
    """
    # Scorro il blob per trovare pattern possibile
    TOTAL_LEN = 43
    i = 0
    while i <= len(data) - TOTAL_LEN:
        frame = data[i:i+TOTAL_LEN]

        # Controllo funzione del primo messaggio
        if frame[1] != 0x03:
            i += 1
            continue

        # --- Primo CRC (header) ---
        crc1_received = frame[6] | (frame[7] << 8)
        crc1_calculated = crc16_modbus(frame[0:6])
        if crc1_received != crc1_calculated:
            i += 1
            continue

        # --- Secondo CRC (messaggio payload) ---
        second_msg = frame[8:]  # dal byte subito dopo il primo CRC fino alla fine
        crc2_received = second_msg[-2] | (second_msg[-1] << 8)
        crc2_calculated = crc16_modbus(second_msg[:-2])
        if crc2_received != crc2_calculated:
            i += 1
            continue

        # --- Estrazione payload ---
        payload = second_msg[3:-2]  # skip dati iniziali del secondo messaggio, poi escludi CRC finale

        temp_raw = (payload[0] << 8) | payload[1]
        hum_raw  = (payload[2] << 8) | payload[3]
        dew_raw  = (payload[4] << 8) | payload[5]
        set_raw  = (payload[18] << 8) | payload[19]
        req_raw  = (payload[20] << 8) | payload[21]

        temp = temp_raw / 10.0
        hum  = hum_raw / 10.0
        dew  = dew_raw / 10.0
        set = set_raw / 10.0
        req = 1 if req_raw != 0 else 0

        return (frame[0], temp, hum, dew, set, req, i + TOTAL_LEN)

    return None