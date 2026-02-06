# App Home Assistant per sniffer Modbus Templari
Le pompe di calore Templari hanno recentemente ricevuto un aggiornamento che permette di interfacciarsi via modbus per vedere i principali parametri della PdC (<a href="https://github.com/wergio/templari-modbus-home-assistant">vedi questo altro mio progetto</a> per l'interfacciamento con HA) ma ci sono alcune cose, come la lettura delle temperature e umidità rilevate dalle sonde room, che non è ancora possibile leggere da domotica.

Questo progetto è un'app (ex "Addon") per HA che può essere utile se si vogliono recuperare anche questi dati utilizzando un dispositivo hardware per "sniffare" la catena modbus e renderli quindi disponibili ad home assistant come sensori MQTT tramite il broker Mosquitto.

Al momento rilevo dai sensori room circa ogni 30 secondi i seguenti dati: temperatura, umidità, set point attivo, punto di rugiata, stato (aperto o chiuso) della testina termostatica; delle schede floor leggo le temperature di mandata/ritorno, il delta t, la percentuale del circolatore e di miscelazione, più lo stato dei relè; in futuro potrei inserire altri sensori o dati, ma questi sono i principali di sicura utilità per la maggior parte di noi.

Ci sono vari dispositivi che si possono usare per lo sniffing, quello che ho utilizzato con successo io è il DR164 reperibile su aliexpress qui https://it.aliexpress.com/item/1005008220892003.html (attenzione a non confonderlo col DR162 che non va bene). Va inserito fisicamente all'interno della catena modbus dei sensori room per leggere passivamente i messaggi che passano sul bus senza interferire in nessun modo. Rispetto ad altri dispositivi questo ha il vantaggio di essere economico, molto piccolo, facilmente configurabile via wifi e sopratutto si alimenta con la stessa alimentazione dei room, può quindi essere piazzato ovunque, anche all'interno di un cartogesso o in zone difficilmente raggiungibili.

Esempio della mia installazione "spartana" di fianco ad un room :-)

![installazione](https://github.com/user-attachments/assets/7b654a62-35a5-4e64-8687-8364e8cddb7b)

NOTA BENE: mettere le mani sul bus dei sensori è una cosa che va fatta solo da chi ha un minimo di esperienza con i cablaggi. Ovviamente non mi assumo nessuna responsabilità in caso di eventuali danni.

Ricordo che il bus modbus è una catena, quindi il seguente cablaggio che vi troverete tipicamente in un sensore room, va separato (a rete spenta) e replicato tale e quale con un nuovo spezzone di filo al dispositivo di sniffing assicurandosi di mantenere i dispositivi in una catena
![modbus-room](https://github.com/user-attachments/assets/66cdac2f-b0d2-41eb-ba7f-427a74b6712c)
se avete più spazio potete metterlo anche vicino ad una floor, si consiglia di non mettere il dispositivo alla fine della catena ma in una qualsiasiasi posizione in mezzo, ricordo che è fondamentale non sbagliare la polarità o invertire i fili A e B, e non serve collegare la terra del dispositivo di sniffing, è buona pratica collegare fra loro eventuali calze dei fili del bus per garantire una buona schermatura.

Una volta installato il dispositivo è necessario configurarlo, al seguente link trovate il manuale ufficiale https://www.pusr.com/uploads/20241212/c0e4f462ecead06a7e47e13fee88a488.pdf a pag 8 è spiegato come si entra la prima volta, dopodichè vi consiglio di agganciarlo al vostro WiFi in modalità "STA only", la procedura è abbastanza intuitiva, è necessario dare un ip fisso o da interfaccia o col router per poterlo raggiungere senza problemi. Di seguito le due pagine di settaggi fondamentali per lo sniffing, non usate altri settaggi random per evitare problemi:
<img width="2777" height="798" alt="schermate" src="https://github.com/user-attachments/assets/7adbf0f7-9e7c-4b96-9f76-8529e97ed5ad" />

Ora bisogna installare questa app, per farlo andate nell'app store di HA https://my.home-assistant.io/redirect/supervisor_store cliccate i 3 pallini in alto a destra -> archivi digitali e copiate l'url di questo repository git https://github.com/wergio/addon-templari-modbus-sniffer/ e cliccate aggiungi, vi troverete Templari Modbus Sniffing fra i componenti, installatelo e prima di avviarlo aprite la configurazione per inserite i dati necessari, fra cui, fondamentale, l'elenco delle sonde ROOM e FLOOR da monitorare (faccio presente che con la matita si può cambiare il nome della stanza e scegliere se abilitare o disabilitare alcuni sensori delle floor), ricordo che dovete già avere installato il broker MQTT Mosquitto, se non ce l'avete ci sono decine di tutorial in rete che spiegano come fare, dopodichè avviate il componente, consiglio anche watchdog e avvio automatico, nel registro vedete subito se si collega e come rileva i dati ogni circa 30 secondi.

L'app si occupa di generare automaticamente in HA i vari sensori MQTT sulla base degli id e nomi stanza che gli avete fornito in fase di configurazione. Una volta create le entità al primo avvio potete tranquillamente rinominare anche gli entity_id come preferite e continueranno sempre ad aggiornarsi.

Una card molto comoda per mostrare alcune di queste entità è la <a href="https://github.com/benct/lovelace-multiple-entity-row">Multiple Entity Row Card</a>
<img width="1588" height="613" alt="multi-entity" src="https://github.com/user-attachments/assets/52b80ce7-d5cd-43a4-ab02-df7ceba446f5" />
vi lascio un esempio con una riga:
```yaml
type: entities
entities:
  - type: custom:multiple-entity-row
    name: Sala
    entity: sensor.templari_p1_room_122_temperature
    state_header: Temperatura
    icon: mdi:thermometer-water
    entities:
      - entity: sensor.templari_p1_room_122_humidity
        name: Umidità
      - entity: sensor.templari_p1_room_122_dew_point
        name: Punto Rugiada
      - entity: sensor.templari_p1_room_122_set_point
        name: Set Point
      - entity: binary_sensor.templari_p1_room_122_request
        name: Testina
```

Se volete potete anche disabilitare la generazione automatica delle entità mqtt tramite l'apposito flag nella configurazione dell'app, così potete farlo voi manualmente in configuration.yaml o dove volete voi.

E con questo è tutto, se avete dubbi o rilevate problemi aprite pure un'issue su github.

PS: versioni diverse del software del pannello templari potrebbero portare variazioni nella rilevazione io ho la 1.8.55 del pannello e la 13.88.26 (o 21.0.37) del firmware macchina, se notate anomalie con altre versioni fatemi sapere e vedremo cosa si può fare

Credit a Carlo Cavallin per il primo reverse engineering del protocollo templari di qualche anno fa, io ho solo "attualizzato" la sua tecnica!

Di seguito riporto altri device che mi sono stati segnalati come compatibili con il mio software:

![ws](https://github.com/user-attachments/assets/c6f55eca-b17d-4c34-8ac4-54cc0f8e08f7)
