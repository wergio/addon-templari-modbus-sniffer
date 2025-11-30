# Addon Home Assistant per sniffer Modbus Templari
Le pompe di calore Templari hanno recentemente ricevuto un aggiornamento che permette di interfacciarsi via modbus per vedere i principali parametri della PdC (<a href="https://github.com/wergio/templari-modbus-home-assistant">vedi questo altro mio progetto</a> per l'interfacciamento con HA) ma ci sono alcune cose, come la lettura delle temperature e umidità rilevate dalle sonde room, che non è ancora possibile leggere da domotica.

Questo progetto può essere utile se si vogliono recuperare anche questi dati utilizzando un dispositivo hardware per "sniffare" la catena modbus e renderli quindi disponibili ad home assistant come sensori MQTT tramite il broker Mosquitto.

Al momento rilevo solo temperatura e umidità dei sensori room, in futuro ho in mente di aggiungere altre informazioni, anche delle schede floor.

Il dispositivo che ho utilizzato con successo per questo fine è il DR164 reperibile su aliexpress qui https://it.aliexpress.com/item/1005008220892003.html (attenzione a non confonderlo col DR162 che non va bene). Va inserito fisicamente all'interno della catena modbus dei sensori room per leggere passivamente i messaggi che passano sul bus senza interferire in nessun modo. Esistono molti altri dispositivi simili ma questo ha il vantaggio di essere economico, molto piccolo, facilmente configurabile via wifi e sopratutto si alimenta con la stessa alimentazione dei room, può quindi essere piazzato ovunque, anche all'interno di un cartogesso o in zone difficilmente raggiungibili.

esempio installazione "spartana" vicino a room :-)

![installazione](https://github.com/user-attachments/assets/7b654a62-35a5-4e64-8687-8364e8cddb7b)

NOTA BENE: mettere le mani sul bus dei sensori è una cosa che va fatta solo da chi ha un minimo di esperienza con i cablaggi. Ovviamente non mi assumo nessuna responsabilità in caso di eventuali danni.

Ricordo che il bus modbus è una catena, quindi il seguente cablaggio che vi troverete tipicamente in un sensore room, va separato e replicato tale e quale con un nuovo spezzone di filo al dispositivo di sniffing assicurandosi di mantenere i dispositivi in una catena
![modbus-room](https://github.com/user-attachments/assets/66cdac2f-b0d2-41eb-ba7f-427a74b6712c)
se avete più spazio potete metterlo anche vicino ad una floor, si consiglia di non mettere il dispositivo alla fine della catena ma in una qualsiasiasi posizione in mezzo, ricordo che è fondamentale non sbagliare la polarità o invertire i fili A e B, e non serve collegare la terra del dispositivo di sniffing, è buona pratica collegare fra loro eventuali calze dei fili del bus per garantire una buona schermatura.

Una volta installato il dispositivo è necessario configurarlo, al seguente link trovate il manuale ufficiale https://www.pusr.com/uploads/20241212/c0e4f462ecead06a7e47e13fee88a488.pdf a pag 8 è spiegato come si entra la prima volta, dopodichè vi consiglio di agganciarlo al vostro WiFi in modalità "STA only", la procedura è abbastanza intuitiva, suggerisco di dare un ip fisso o da interfaccia o col router per comodità. Di seguito le due pagina di settaggi fondamentali per lo sniffing, non usate altri settaggi random per evitare problemi:
<img width="2777" height="798" alt="schermate" src="https://github.com/user-attachments/assets/7adbf0f7-9e7c-4b96-9f76-8529e97ed5ad" />

Ora bisogna installare questo addon, per farlo andate nell'addon store di HA https://my.home-assistant.io/redirect/supervisor_store cliccate i 3 pallini in alto a destra -> archivi digitali e copiate l'url di questo repository git https://github.com/wergio/addon-templari-modbus-sniffer/ e cliccate aggiungi, vi troverete Templari Modbus Sniffing fra i componenti, installatelo, aprite la configurazione e inserite i dati necessari, ricordo che dovete già avere installato Mosquitto, se non ce l'avete ci sono decine di tutorial che spiegano come fare, dopodichè avviate il componente, consiglio anche watchdog e avvio automatico, nel registro vedete subito se si collega e come rileva le temperatura ogni circa 30 secondi.

L'ultimo passaggio sarà quello di configurare i vari sensori MQTT, ecco un esempio di un sensore di temperatura e uno di umidità da mettere in configuration.yaml o dove volete voi, gli id delle varie stanze (nell'esempio 121) li dovete sapere voi e li trovate nel menu avanzate X dell'HCC

```yaml
mqtt:
  sensor:
    - unique_id: templari_temperatura_cucina
      name: "Temperatura Cucina"
      state_topic: "templari/room/121/temperature"
      device_class: temperature
      state_class: measurement
    - unique_id: templari_umidita_cucina
      name: "Umidità Cucina"
      state_topic: "templari/room/121/humidity"
      device_class: humidity
      state_class: measurement
```

E con questo è tutto, se avete dubbi o rilevate problemi aprite pure un'issue su github.
