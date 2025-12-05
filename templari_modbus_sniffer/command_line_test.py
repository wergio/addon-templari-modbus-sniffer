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

    result = modbus_parsing.parse_modbus_room(data)
    if result:
        print("Trovata corrispondenza ROOM:")
        slave, temp, hum, dew, set, req, len = result
        print("ID ROOM:", slave)
        print("Temperatura:", temp)
        print("Umidita:", hum)        
        print("Rugiada:", dew)        
        print("Set Point:", set)        
        print("Testina:", req)        
        print("Lunghezza frame rilevato:", len, "byte")        

    else:
        print("Nessun frame valido trovato")

