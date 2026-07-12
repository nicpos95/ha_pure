# Pure VMC

Integrazione Home Assistant per la ventilazione meccanica controllata (VMC) Pure.

Comunica direttamente con l'interfaccia web dell'unità tramite HTTP locale — nessun cloud richiesto.
Compatibile con Pure 250 e altri modelli della serie Pure il cui comando touch è dotato di porta ethernet RJ45.

## Funzionalità

- **Ventola** — Controlla velocità (0–100%), accensione/spegnimento, preset boost.
- **4 sensori di temperatura** — Esterna (Te), Ripresa (Tr), Espulsione (Tx), Immissione (Ti).
- **Sensore velocità** — Percentuale corrente + modalità timer (Orologio).
- **Efficienza recupero calore** — Calcolata automaticamente in %.
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

## Crediti

Sviluppato da **Nicola Possamai** ([@nicpos95](https://github.com/nicpos95)).

Se utilizzi o distribuisci questo codice, ti chiedo gentilmente di mantenere i crediti e di citarmi come autore originale.

Si declina ogni responsabilità sull'uso del codice.
Non sono in nessun modo affiliato con produttori di VMC e/o installatori. Il codice è fornito in buona fede per facilitare l'integrazione al prossimo.

## Licenza

Apache 2.0 — Vedi file [LICENSE](LICENSE).
