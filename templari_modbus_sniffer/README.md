# Templari Modbus Sniffer

Questa app legge passivamente il bus Modbus delle pompe di calore Templari
tramite un dispositivo di sniffing collegato alla catena, e ne pubblica i dati su
MQTT come sensori di Home Assistant: temperatura, umidità, punto di rugiada, set
point e stato della testina di ogni sonda room, temperature di mandata e ritorno,
delta T, circolatore, miscelazione e relè di ogni scheda floor, più lo stato
della deumidifica.

Non scrive nulla sul bus e non interferisce in alcun modo con il funzionamento
dell'impianto.

Per l'installazione del dispositivo di sniffing, il cablaggio sul bus, la sua
configurazione e tutto il resto della documentazione:

**[Documentazione completa su GitHub](https://github.com/wergio/addon-templari-modbus-sniffer)**
