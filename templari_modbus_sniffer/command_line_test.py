# -*- coding: utf-8 -*-
import sys
import modbus_parsing

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python command_line_test.py <stringa_esadecimale_contenente_risposta_room_o_floor>")
        sys.exit(1)

    hex_string = sys.argv[1]
    try:
        data = bytearray.fromhex(hex_string)
    except ValueError:
        print("Stringa esadecimale non valida!")
        sys.exit(1)

    resultr = modbus_parsing.parse_modbus_room(data)
    resultf = modbus_parsing.parse_modbus_floor(data)
    if resultr:
        print("Trovata corrispondenza ROOM:")
        slave, temp, hum, dew, set, req, len = resultr
        print("ID ROOM:", slave)
        print("Temperatura:", temp)
        print("Umidita:", hum)        
        print("Rugiada:", dew)        
        print("Set Point:", set)        
        print("Testina:", req)        
        print("Lunghezza frame rilevato:", len, "byte")        

    elif resultf:
        print("Trovata corrispondenza FLOOR:")
        slave, temp_flow, temp_return, temp_delta_t, perc_circulator, perc_mix, relay_1, relay_2, relay_3, relay_4, relay_5, relay_6, relay_7, relay_8, len = resultf
        print("ID FLOOR:", slave)
        print("Temperatura Mandata:", temp_flow)
        print("Temperatura Ritorno:", temp_return)
        print("Delta T:", temp_delta_t)        
        print("Percentuale Circolatore:", perc_circulator)        
        print("Percentuale Miscelazione:", perc_mix)        
        print("Rele' 1:", relay_1)        
        print("Rele' 2:", relay_2)        
        print("Rele' 3:", relay_3)        
        print("Rele' 4:", relay_4)        
        print("Rele' 5:", relay_5)        
        print("Rele' 6:", relay_6)        
        print("Rele' 7:", relay_7)        
        print("Rele' 8:", relay_8)        
        print("Lunghezza frame rilevato:", len, "byte")        

    else:
        print("Nessun frame valido trovato")

