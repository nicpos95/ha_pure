# Pure VMC

Integrazione Home Assistant per la ventilazione meccanica controllata (VMC) Pure.

Comunica direttamente con l'unità in rete locale — nessun cloud richiesto. Lo stato viene letto via
**Modbus TCP** quando il pannello lo offre (porta 502), altrimenti dalle pagine web. Con il Modbus
attivo anche i comandi passano da lì (con l'interfaccia web come riserva per la ventola).
Compatibile con Pure 250 e altri modelli della serie Pure il cui comando touch è dotato di porta ethernet RJ45.

## Funzionalità

- **Ventola** — Controlla velocità (0–100%), accensione/spegnimento, preset boost.
- **4 sensori di temperatura** — Esterna (Te), Ripresa (Tr), Espulsione (Tx), Immissione (Ti).
- **Sensore velocità** — Percentuale corrente + modalità timer (Orologio).
- **Efficienza recupero calore** — Calcolata automaticamente in %.
- **Allarmi e stato** — Filtri sporchi, allarme generico, bypass free-cooling, set-point temperatura.
- **Via Modbus TCP** — Velocità reale dei due ventilatori, ore di funzionamento, singoli allarmi
  (sonde, ventilatori, comunicazione, configurazione, antigelo), modalità di funzionamento, stagione,
  modalità bypass, soglia ore filtri, versione firmware.
- **Config flow** — Aggiungi tramite UI → "Pure VMC".

## Installazione

### Tramite HACS (consigliato)

1. Assicurati di avere [HACS](https://hacs.xyz) installato.
2. Vai su HACS → Integrazioni → menu (3 puntini) → **Repository personalizzati**.
3. Aggiungi: `https://github.com/nicpos95/ha_pure` — Categoria: **Integrazione**.
4. Cerca "Pure VMC" in HACS e clicca **Scarica**.
5. Riavvia Home Assistant.
6. Vai su Impostazioni → Dispositivi e servizi → **Aggiungi integrazione** → cerca "Pure VMC".
7. Inserisci l'indirizzo IP locale della tua unità Pure.

### Manuale

Copia la cartella `custom_components/pure/` nella tua directory `custom_components` di Home Assistant e riavvia.

## Configurazione

Dopo l'installazione, vai su:

**Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Pure VMC**

Inserisci l'indirizzo IP dell'unità (es. `192.168.1.243`). L'integrazione testerà automaticamente la connessione.

## Velocità e modalità

| Valore | Significato |
|--------|-------------|
| 0 | Spento |
| 20–100 | Velocità normale (regolabile con step 1 o 10) |
| 101 | Modalità timer (Orologio) — sola lettura |
| Boost | Attiva la modalità timer interna dell'unità |

**Nota**: le velocità 1–19 non sono valide — l'unità va in spegnimento automatico sotto il 20%. L'integrazione gestisce automaticamente la rampa di velocità rispettando questo vincolo hardware.

## Entity

| Platform | Nome | Descrizione |
|----------|------|-------------|
| `fan` | Pure Ventilation | Controllo ventola (velocità, preset) |
| `sensor` | External Temperature | Temperatura aria esterna (Te) |
| `sensor` | Return Temperature | Temperatura aria di ripresa (Tr) |
| `sensor` | Exhaust Temperature | Temperatura aria espulsa (Tx) |
| `sensor` | Inlet Temperature | Temperatura aria immessa (Ti) |
| `sensor` | Ventilation Speed | Velocità corrente % |
| `sensor` | Heat Recovery Efficiency | Efficienza recupero calore % |
| `sensor` | Temperature Setpoint | Temperatura impostata (logica bypass) |
| `binary_sensor` | Filter | Allarme filtri sporchi (`DirtyFilters`) — `problem` |
| `binary_sensor` | Alarm | Un qualsiasi allarme attivo — `problem` |
| `binary_sensor` | Bypass | Bypass free-cooling aperto |

Queste entità sono sempre disponibili. Senza Modbus vengono lette dalle pagine della schermata
principale, senza navigare i menu dell'unità (quindi il pannello a muro non viene disturbato).

### Entità aggiuntive via Modbus TCP

Create solo se l'unità risponde su Modbus TCP (porta 502).

| Platform | Nome | Descrizione |
|----------|------|-------------|
| `sensor` | Supply Fan Speed | Velocità reale ventilatore di immissione (RPM con segnale tachimetrico, altrimenti %) |
| `sensor` | Exhaust Fan Speed | Velocità reale ventilatore di ripresa |
| `sensor` | Fan Run Hours | Ore di funzionamento dell'unità |
| `sensor` | Boost Time Remaining | Secondi rimanenti del booster |
| `sensor` | Operating Mode | `off` / `manual` / `schedule` (Orologio) / `auto` / `boost` |
| `select` | Season | Stagione (`auto` / `winter` / `summer`) — **modificabile** |
| `select` | Bypass Mode | Gestione bypass (`auto` / `off` / `on`) — **modificabile** |
| `number` | Temperature Setpoint | Set-point temperatura, passi di 0,2 °C — **modificabile** |
| `number` | Boost Timer | Minuti di booster: impostarlo avvia il booster, 0 lo annulla |
| `sensor` | Filter Alarm Threshold | Soglia ore dell'allarme filtri — diagnostica |
| `binary_sensor` | Anti-Frost | Antigelo scambiatore attivo |
| `binary_sensor` | … Fault (×8) | Le singole voci della schermata Allarmi: comunicazione, configurazione, sonde Te/Tr/Tx/Ti, ventilatori, antigelo — `problem`, diagnostica |

## Modbus TCP

Il pannello touch con porta ethernet (EVO-PH / X511) espone tutto lo stato come *holding registers*.
Un'unica breve connessione per ciclo restituisce più dati di nove pagine web e non carica il piccolo
web server dell'unità. Il Modbus viene rilevato da solo all'avvio: se il pannello è impostato su RS485
(menu Installatore → Comunicazione → Modbus) o non risponde, l'integrazione continua a leggere le pagine
web come prima, e fa lo stesso per il singolo ciclo in cui il Modbus dovesse mancare. Si può disattivare
da **Configura** nella scheda dell'integrazione.

Dettagli: TCP 502, funzione 03, l'indirizzo sul filo è il numero di registro del manuale meno 1, e il
pannello chiude la connessione dopo 10 s senza accessi (per questo se ne apre una per ciclo). Nessuna
dipendenza esterna: il client è incluso (`modbus.py`).

### Comandi via Modbus

Con il Modbus attivo la ventola si comanda scrivendo direttamente il set-point di velocità (una sola
scrittura invece di una serie di pressioni sui tasti +/- della pagina web), e il preset **schedule**
rimette l'unità sul programma settimanale (Orologio). Il preset **boost** avvia 15 minuti di booster;
per una durata diversa usare *Boost Timer*.

Due particolarità del pannello, verificate su una Pure 250:

- **Conferma le scritture anche quando le scarta.** Per 60 secondi dopo ogni modifica fatta dalla pagina
  web (o dal touch) risponde "ok" e lascia il valore com'era. L'integrazione rilegge quindi ogni registro
  dopo averlo scritto: se il valore non si è mosso, la ventola ripiega sull'interfaccia web, mentre le
  altre entità segnalano l'errore (riprovare dopo un minuto).
- **Le scritture Modbus non sono salvate in memoria permanente**: secondo il manuale, allo spegnimento
  l'unità torna ai valori impostati da pannello o da web. Dopo un'interruzione di corrente Home Assistant
  mostrerà quindi lo stato reale dell'unità, non l'ultimo comando inviato.

## Test

```
pip install -r requirements_test.txt
pytest
```

## Crediti

Sviluppato da **Nicola Possamai** ([@nicpos95](https://github.com/nicpos95)).

Se utilizzi o distribuisci questo codice, ti chiedo gentilmente di mantenere i crediti e di citarmi come autore originale.

Si declina ogni responsabilità sull'uso del codice.
Non sono in nessun modo affiliato con produttori di VMC e/o installatori. Il codice è fornito in buona fede per facilitare l'integrazione al prossimo.

## Licenza

Apache 2.0 — Vedi file [LICENSE](LICENSE).
