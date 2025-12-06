# -*- coding: utf-8 -*-
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
    
def parse_modbus_floor(data):
    TOTAL_LEN = 73
    i = 0
    while i <= len(data) - TOTAL_LEN:
        frame = data[i:i+TOTAL_LEN]

        # Controllo funzione del primo messaggio
        if frame[1] != 0x03:
            i += 1
            continue
        
        # l'id deve essere uguale fra due punti della stringa altrimenti scarto
        if frame[0] != frame[12]:
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

        temp_flow_raw  = (payload[2] << 8) | payload[3]
        temp_return_raw  = (payload[4] << 8) | payload[5]
        temp_delta_t_raw  = (payload[6] << 8) | payload[7]
        perc_circulator  = (payload[8] << 8) | payload[9]
        
        perc_mix_raw  = (payload[18] << 8) | payload[19]
        
        relay_1_raw  = (payload[32] << 8) | payload[33]
        relay_2_raw  = (payload[34] << 8) | payload[35]
        relay_3_raw  = (payload[36] << 8) | payload[37]
        relay_4_raw  = (payload[38] << 8) | payload[39]
        relay_5_raw  = (payload[40] << 8) | payload[41]
        relay_6_raw  = (payload[42] << 8) | payload[43]
        relay_7_raw  = (payload[44] << 8) | payload[45]
        relay_8_raw  = (payload[46] << 8) | payload[47]

        temp_flow = temp_flow_raw / 10.0
        temp_return  = temp_return_raw / 10.0
        temp_delta_t  = temp_delta_t_raw / 10.0
	
        perc_mix = 100 - perc_mix_raw # e' invertito!
	
        relay_1 = 1 if relay_1_raw != 0 else 0
        relay_2 = 1 if relay_2_raw != 0 else 0
        relay_3 = 1 if relay_3_raw != 0 else 0
        relay_4 = 1 if relay_4_raw != 0 else 0
        relay_5 = 1 if relay_5_raw != 0 else 0
        relay_6 = 1 if relay_6_raw != 0 else 0
        relay_7 = 1 if relay_7_raw != 0 else 0
        relay_8 = 1 if relay_8_raw != 0 else 0

        return (frame[0], temp_flow, temp_return, temp_delta_t, perc_circulator, perc_mix, relay_1, relay_2, relay_3, relay_4, relay_5, relay_6, relay_7, relay_8, i + TOTAL_LEN)

    return None