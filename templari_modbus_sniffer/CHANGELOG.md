# Changelog

## 1.1.1

### Novità

- Gestione della scheda **deumidifica** (opzionale): vi crea il binary sensor
  `binary_sensor.templari_dehumidifier_state`, che riporta se la deumidifica è
  in funzione o ferma.

> Se non vedi la nuova opzione nella pagina di configurazione, attiva il
> selettore **"Mostra le opzioni di configurazione facoltative non utilizzate"**
> in fondo alla pagina: essendo facoltativa e senza valore, Home Assistant la
> nasconde finché non le assegni un id.

### Correzioni

- Corretto un errore che impediva l'aggiornamento dalle versioni precedenti
  ("invalid options: expected int").

## 1.1.0

### Novità

- Gestione della scheda **deumidifica** (opzionale): vi crea il binary sensor
  `binary_sensor.templari_dehumidifier_state`, che riporta se la deumidifica è
  in funzione o ferma.

> Se non vedi la nuova opzione nella pagina di configurazione, attiva il
> selettore **"Mostra le opzioni di configurazione facoltative non utilizzate"**
> in fondo alla pagina: essendo facoltativa e senza valore, Home Assistant la
> nasconde finché non le assegni un id.

## 1.0.2

### Ottimizzazioni

- varie migliorie al codice per evitare disconnessioni e per occupare meno
  processore e memoria

## 1.0.1

- L'app non si blocca più, richiedendo un riavvio manuale, quando lo sniffer
  resta irraggiungibile per un certo tempo.

