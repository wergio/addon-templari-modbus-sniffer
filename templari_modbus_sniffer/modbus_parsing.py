# -*- coding: utf-8 -*-

# Lunghezza totale (richiesta + risposta) dei frame riconosciuti.
# Servono anche al chiamante per risalire dall'end_idx restituito
# alla posizione di inizio del frame dentro al buffer.
ROOM_FRAME_LEN = 43
FLOOR_FRAME_LEN = 73
# La scheda deumidifica non viene interrogata: il pannello le SCRIVE lo stato
# con la funzione 0x10 (11 byte di richiesta) e la scheda risponde con l'eco
# (8 byte). Il ciclo si ripete ogni ~25 secondi.
DEHUMIDIFIER_FRAME_LEN = 19
# Registro che porta lo stato della deumidifica: 1 = attiva, 0 = ferma.
# Il pannello scrive anche i registri 11 e 13, che qui non interessano.
DEHUMIDIFIER_STATE_REGISTER = 10

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
    TOTAL_LEN = ROOM_FRAME_LEN
    i = 0
    while i <= len(data) - TOTAL_LEN:

        # Controllo funzione del primo messaggio. Va fatto PRIMA della slice:
        # scarta quasi tutte le posizioni, e affettare TOTAL_LEN byte a ogni
        # posizione del buffer costa piu' del controllo stesso.
        if data[i+1] != 0x03:
            i += 1
            continue

        frame = data[i:i+TOTAL_LEN]

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
    TOTAL_LEN = FLOOR_FRAME_LEN
    i = 0
    while i <= len(data) - TOTAL_LEN:

        # Controllo funzione del primo messaggio, prima della slice (vedi
        # parse_modbus_room per il motivo)
        if data[i+1] != 0x03:
            i += 1
            continue

        frame = data[i:i+TOTAL_LEN]

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

def parse_modbus_dehumidifier(data):
    """
    Cerca la scrittura (funzione 0x10) con cui il pannello comanda lo stato
    della scheda deumidifica, seguita dall'eco di conferma della scheda.
    Restituisce (slave, stato, end_idx) oppure None.

    Struttura dei 19 byte:
      [0]      indirizzo slave          [11]     indirizzo slave (eco)
      [1]      funzione 0x10            [12]     funzione 0x10
      [2:4]    registro scritto         [13:15]  registro scritto
      [4:6]    numero registri (1)      [15:17]  numero registri (1)
      [6]      byte count (2)           [17:19]  CRC
      [7:9]    valore
      [9:11]   CRC
    """
    TOTAL_LEN = DEHUMIDIFIER_FRAME_LEN
    i = 0
    while i <= len(data) - TOTAL_LEN:

        # Controllo funzione prima della slice, come negli altri parser
        if data[i+1] != 0x10:
            i += 1
            continue

        frame = data[i:i+TOTAL_LEN]

        # Deve scrivere UN solo registro, quello di stato, con 2 byte di dato.
        # Il pannello scrive anche i registri 11 e 13, che vanno scartati qui.
        if (frame[2] << 8 | frame[3]) != DEHUMIDIFIER_STATE_REGISTER:
            i += 1
            continue
        if (frame[4] << 8 | frame[5]) != 1 or frame[6] != 2:
            i += 1
            continue

        # --- CRC della richiesta ---
        if (frame[9] | (frame[10] << 8)) != crc16_modbus(frame[0:9]):
            i += 1
            continue

        # --- Eco della scheda: stesso slave, stessa funzione, stesso registro ---
        # Serve anche a distinguere le schede realmente presenti da quelle che
        # il pannello comanda pur non essendo installate: quelle non rispondono.
        echo = frame[11:]
        if echo[0] != frame[0] or echo[1] != 0x10:
            i += 1
            continue
        if (echo[2] << 8 | echo[3]) != DEHUMIDIFIER_STATE_REGISTER:
            i += 1
            continue
        if (echo[4] << 8 | echo[5]) != 1:
            i += 1
            continue
        if (echo[6] | (echo[7] << 8)) != crc16_modbus(echo[0:6]):
            i += 1
            continue

        # Lo stato e' acceso/spento. Il registro 10 viene scritto anche alle
        # room (set point attivo) e alle floor (350): scartando tutto cio' che
        # non e' 0 o 1 restano solo le vere schede a rele'. Se un domani una
        # scheda usasse altri valori, meglio nessun dato che un dato inventato.
        state = (frame[7] << 8) | frame[8]
        if state > 1:
            i += 1
            continue

        return (frame[0], state, i + TOTAL_LEN)

    return None