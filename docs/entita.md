# Entità dell'integrazione Pure VMC

Tutte le entità appartengono a un unico dispositivo, **Pure VMC**, e hanno quindi ID del tipo
`sensor.pure_vmc_<nome>`. I nomi qui sotto sono quelli inglesi che Home Assistant mostra di default;
tra parentesi la traduzione italiana, usata se la lingua dell'utente è l'italiano.

L'integrazione aggiorna tutto ogni **30 secondi**. Se l'unità risponde su **Modbus TCP** (porta 502) i
dati arrivano da lì con una sola breve connessione per ciclo; altrimenti dalle pagine web della
schermata principale (`ifspeed_sp.html`, `iftemp_*.html`, `ifalarms.html`, …), senza mai navigare i
menù, così il pannello a muro non viene disturbato. Per ogni entità è indicata la **sorgente**: la
pagina web oppure il registro Modbus del manuale del pannello EVO-PH (numero di registro del manuale;
sul filo l'indirizzo è il numero − 1).

Le entità segnate **Modbus** esistono solo se l'unità risponde su Modbus TCP: sono i dati che le
pagine web mostrano solo nelle schermate dei menù.

## Sommario

| Entità | Piattaforma | Sorgente | Scrivibile |
|---|---|---|---|
| Ventilation | `fan` | web / **Modbus** | sì |
| External / Return / Exhaust / Inlet Temperature | `sensor` | web / Modbus | — |
| Temperature Setpoint | `sensor` | web / Modbus | — (vedi il `number`) |
| Ventilation Speed | `sensor` | web / Modbus | — |
| Heat Recovery Efficiency | `sensor` | calcolata | — |
| Filter / Alarm / Bypass | `binary_sensor` | web / Modbus | — |
| Supply Fan Speed / Exhaust Fan Speed | `sensor` | **Modbus** | — |
| Fan Run Hours | `sensor` | **Modbus** | — |
| Operating Mode | `sensor` | **Modbus** | — |
| Boost Time Remaining | `sensor` | **Modbus** | — (vedi il `number`) |
| Filter Alarm Threshold | `sensor` | **Modbus** | — |
| Bypass Mode | `sensor` *oppure* `select` | **Modbus** | solo con bypass universale |
| Season | `select` | **Modbus** | sì |
| Temperature Setpoint | `number` | **Modbus** | sì |
| Boost Timer | `number` | **Modbus** | sì |
| Anti-Frost | `binary_sensor` | **Modbus** | — |
| Communication / Configuration / … Fault (8) | `binary_sensor` | **Modbus** | — |

---

## Ventola

### Ventilation (Ventilazione) — `fan.pure_vmc_ventilation`

Il comando principale dell'unità.

- **Stato:** `on` quando il set-point di velocità è diverso da 0.
- **Percentuale:** il set-point di velocità dei ventilatori, 20–100 %. L'unità non accetta valori tra 1 e
  19: sotto il 20 % si spegne, e un valore inferiore viene portato a 20. Nelle modalità *programma
  settimanale* e *automatica* (vedi sotto) la percentuale mostrata è 100, perché il valore reale
  (101/102) non è una percentuale; guardare *Operating Mode* per sapere in che modalità si è.
- **Preset:**
  - `normal` — velocità manuale. Sceglierlo esce dal booster o dal programma settimanale e torna
    all'ultima velocità manuale nota (senza Modbus: spegne e riaccende al 20 %);
  - `boost` — avvia il booster per 15 minuti (ventilatori alla massima velocità). Per una durata diversa
    usare *Boost Timer*;
  - `schedule` (*Programma settimanale*, solo Modbus) — affida la velocità al programma settimanale
    del pannello (quello che il pannello chiama *Orologio*).
- **Attributi:** `timer_mode` (vero nel programma settimanale), `raw_speed` (il valore grezzo, 0–100,
  101 = programma, 102 = automatico).
- **Come comanda:** con il Modbus attivo scrive direttamente il set-point (registro 51) e il booster
  (registro 53). Senza Modbus preme i tasti della pagina web (`ifspeed_sp.html`: +1/−1, +10/−10,
  on/off; `iftimer.html`: booster), con una rampa che rispetta il limite del 20 %. Se il pannello scarta
  una scrittura Modbus (vedi *Particolarità del pannello* più sotto) la ventola ripiega da sola sulla
  pagina web.

## Temperature

Quattro sonde dell'unità, tutte in °C con una cifra decimale. Sorgente: `iftemp_e|r|x|i.html` oppure i
registri 81–84 (valore ×0,1 °C, con segno).

| Entità | Sonda | Cosa misura |
|---|---|---|
| **External Temperature** (Temperatura Esterna) — `sensor.pure_vmc_external_temperature` | Te | aria esterna in ingresso, prima dello scambiatore |
| **Return Temperature** (Temperatura di Ripresa) — `sensor.pure_vmc_return_temperature` | Tr | aria ripresa dalla casa, prima dello scambiatore: è la migliore stima della temperatura media di casa |
| **Exhaust Temperature** (Temperatura di Espulsione) — `sensor.pure_vmc_exhaust_temperature` | Tx | aria espulsa all'esterno, dopo lo scambiatore |
| **Inlet Temperature** (Temperatura di Immissione) — `sensor.pure_vmc_inlet_temperature` | Ti | aria immessa in casa, dopo lo scambiatore |

Due avvertenze:

- **a ventilatori fermi le sonde misurano solo l'aria ferma nei condotti**, non l'esterno né la casa
  (Te può leggere 29 °C con 23 °C fuori). Usare questi valori in automazioni solo quando i
  ventilatori girano;
- con il Modbus, se l'unità segnala il guasto di una sonda (vedi le entità *… Probe Fault*) la
  temperatura corrispondente diventa `unknown` invece di mostrare un valore senza senso.

### Temperature Setpoint (Temperatura Impostata) — `sensor.pure_vmc_temperature_setpoint`

Il set-point di temperatura dell'unità, in °C. Sorgente: `iftemp_sp.html` oppure registro 52. Con il
Modbus, un valore ≤ 4,8 °C (che il pannello mostra come *OFF*) diventa `unknown`.

Che cosa fa il set-point dipende dall'unità: sulle unità con post-trattamento (batteria elettrica o ad
acqua) è la temperatura a cui punta la batteria; sulle altre entra nella logica del bypass (vedi
*Season*). **Il valore è memorizzato per stagione:** il registro mostra quello della stagione attiva, e
subito dopo un cambio di stagione può mostrare per un ciclo ancora quello vecchio.

Con il Modbus esiste anche il `number` omonimo, che permette di modificarlo.

## Velocità ed efficienza

### Ventilation Speed (Velocità Ventilazione) — `sensor.pure_vmc_ventilation_speed`

Il set-point di velocità, in %: 0 = spento, 20–100 = manuale, 101 = programma settimanale, 102 =
automatico (sonda CO₂/umidità). Sorgente: `ifspeed_sp.html` oppure registro 51. Attributi:
`timer_mode`, `is_running` (vero se il set-point è > 0).

È il valore *impostato*, non quello misurato: per la velocità reale dei ventilatori vedere le due entità
seguenti.

### Supply Fan Speed / Exhaust Fan Speed (Velocità Ventilatore Immissione / Ripresa) — **Modbus**

`sensor.pure_vmc_supply_fan_speed`, `sensor.pure_vmc_exhaust_fan_speed`. La velocità misurata dei
due ventilatori, registri 87 e 88. In **giri al minuto** sulle unità con ventilatori a segnale
tachimetrico (indicativamente 1000 rpm al 30 %, 3400 al 100 % su una Pure 250), in **%** sulle unità
che il registro 7 dichiara senza tachimetrica. Salgono e scendono in una decina di secondi dopo un
comando: sono il modo giusto per sapere se l'aria si muove davvero.

### Heat Recovery Efficiency (Efficienza Recupero Calore) — `sensor.pure_vmc_heat_recovery_efficiency`

Calcolata in Home Assistant, in %, dalle tre temperature Te, Tr e Ti:

- in riscaldamento (fuori più freddo che dentro): (Ti − Te) / (Tr − Te) × 100;
- in raffrescamento (fuori più caldo): (Te − Ti) / (Te − Tr) × 100;

limitata a 0–100. Vale `unknown` quando i ventilatori sono fermi (con il Modbus si guarda la velocità
misurata; dalle pagine web il set-point, e anche nel programma settimanale, perché lì la velocità
reale non è nota) o quando manca una temperatura. Con il bypass aperto l'aria non attraversa lo
scambiatore e il valore scende verso zero: è normale.

## Stato e allarmi (sempre disponibili)

### Filter (Filtro) — `binary_sensor.pure_vmc_filter`

Classe `problem`: `on` = allarme **filtri sporchi**. Sorgente: il banner rosso di `ifalarms.html`
(che contiene *DirtyFilters*) oppure il bit 4 del registro 90. Dalle pagine web ha l'attributo
`alarm_banner` con il testo grezzo del banner, così un allarme diverso dai filtri resta comunque
leggibile.

L'allarme può essere a **ore** (scatta al superamento della soglia *Ore filtri*, vedi *Filter Alarm
Threshold*) o a **pressostato**, secondo la configurazione di fabbrica. Il reset non è possibile da
Home Assistant: si fa dal pannello (con l'allarme a ore, impostando nel menù Fabbrica una nuova soglia
= ore di funzionamento attuali + ore al prossimo allarme).

### Alarm (Allarme) — `binary_sensor.pure_vmc_alarm`

Classe `problem`: `on` se l'unità ha **un qualsiasi allarme attivo**. Sorgente: l'icona di allarme della
schermata principale (`if7834.html`) oppure i registri 90 e 97 (qualunque bit, anche quelli che
l'integrazione non conosce per nome). Con il Modbus ha l'attributo `active_alarms`, la lista degli
allarmi attivi per nome (`filter`, `fans`, `temp_external`, …).

### Bypass — `binary_sensor.pure_vmc_bypass`

`on` = la serranda del **bypass è aperta**: l'aria esterna entra senza passare dallo scambiatore
(free cooling / free heating). Sorgente: l'icona `if5523.html` oppure il bit 0 del registro 86. È lo
stato reale della serranda, che si muove da uno a quattro minuti dopo che la logica dell'unità ha deciso
(vedi *Season*).

## Sensori solo Modbus

### Fan Run Hours (Ore Ventilatori) — `sensor.pure_vmc_fan_run_hours`

Ore di funzionamento dell'unità (registri 95 e 96: alto × 65536 + basso), classe `duration`, con
`state_class: total_increasing`, quindi utilizzabile nelle statistiche a lungo termine. Si confronta
con *Filter Alarm Threshold* per sapere quanto manca al prossimo allarme filtri.

### Operating Mode (Modalità di Funzionamento) — `sensor.pure_vmc_operating_mode`

Sensore enumerato, derivato dai registri 51 e 53:

| Valore | Significato |
|---|---|
| `off` | set-point di velocità 0 |
| `manual` | velocità fissa 20–100 % |
| `schedule` | programma settimanale del pannello (*Orologio*, set-point 101) |
| `auto` | velocità governata dalla sonda CO₂/umidità/segnale esterno (set-point 102) |
| `boost` | booster in corso (ha la precedenza su tutto il resto) |

### Boost Time Remaining (Tempo Booster Rimanente) — `sensor.pure_vmc_boost_time_remaining`

Secondi rimanenti del booster (registro 53), 0 se non attivo. Il pannello lo aggiorna a ogni ciclo.

### Filter Alarm Threshold (Soglia Allarme Filtri) — `sensor.pure_vmc_filter_alarm_threshold`

Diagnostica. La soglia in ore dell'allarme filtri a ore (registro 24, memorizzato a passi di 500 h; il
valore di fabbrica è 2000 h). Sulle unità con allarme a pressostato il numero è presente ma non conta.

### Bypass Mode (Modalità Bypass) — `sensor.pure_vmc_bypass_mode` *oppure* `select.pure_vmc_bypass_mode`

Il parametro *Bypass* del menù Parametri (registro 20, bit 2-3): `auto`, `off` (serranda sempre chiusa),
`on` (sempre aperta). **Ha effetto solo sulle unità con bypass configurato come "universale"** nel menù
Fabbrica: lì è un `select` e si può cambiare. Sulle unità con bypass **stagionale** l'unità ignora il
parametro (scrive "ok" e non cambia nulla), quindi viene esposto come sensore diagnostico e la serranda
si governa attraverso la stagione. L'integrazione distingue i due casi dal registro 7 (bit 10-11).

## Controlli solo Modbus

### Season (Stagione) — `select.pure_vmc_season`

Il parametro *Stagione* del menù Parametri (registro 20, bit 0-1). Governa la logica del bypass.

| Opzione | Sul pannello | Comportamento del bypass (stagionale) |
|---|---|---|
| `winter` (Inverno) | Inverno | si apre quando fuori è più caldo che dentro (free heating). Su una Pure 250 è stato osservato che si apre anche quando fuori è più fresco ma la casa è **sopra il set-point invernale** (raffrescamento libero limitato al set-point) |
| `summer` (Estate) | Estate | si apre quando fuori è più fresco che dentro (free cooling), fino alla temperatura minima *Bypass Tmin* del menù installatore; il set-point non conta |
| `auto` (Automatica) | *Stagione non def.* | il bypass è gestito come nella modalità automatica del bypass universale: chiuso finché la temperatura di ripresa sta nella fascia di comfort *Bypass Tmin*–*Tmax* del menù installatore, aperto quando la casa è fuori dalla fascia e l'aria esterna dentro. Il manuale la dichiara disponibile solo sulle unità senza batteria ad acqua per il post-raffrescamento |

Il valore è quello dell'unità stessa, non un'astrazione dell'integrazione: cambiarlo qui equivale a
cambiarlo sul pannello, e viene salvato in memoria permanente. La serranda reagisce da uno a quattro
minuti dopo. Con il pannello configurato per il cambio di stagione automatico da ingresso digitale, il
parametro non è modificabile neanche dal pannello.

### Temperature Setpoint (Temperatura Impostata) — `number.pure_vmc_temperature_setpoint`

Modifica il set-point di temperatura (registro 52) tra 5 e 30 °C, a passi di 0,2 °C (l'unità arrotonda:
26,5 diventa 26,6). Vale per la **stagione attiva** (il set-point è memorizzato per stagione) e viene
salvato in memoria permanente. Il sensore omonimo ne mostra il valore letto dall'unità.

### Boost Timer (Timer Booster) — `number.pure_vmc_boost_timer`

Minuti di booster rimanenti (registro 53, in secondi, arrotondati per eccesso al minuto). **Impostare un
valore avvia il booster** per quella durata (1–240 minuti, il pannello va da 1 minuto a 4 ore),
**impostare 0 lo annulla.** È l'unico valore che l'integrazione non salva in memoria permanente,
essendo un conto alla rovescia.

## Binary sensor solo Modbus

### Anti-Frost (Antigelo) — `binary_sensor.pure_vmc_anti_frost`

`on` = la **procedura antigelo** dello scambiatore è in corso (bit 4 del registro 86): l'unità sta
riducendo l'immissione o modulando i ventilatori perché la temperatura di espulsione Tx è scesa vicino
allo zero. Non è un allarme.

### Le otto voci della schermata Allarmi

Tutti di classe `problem` e categoria diagnostica; sono le stesse righe della schermata *Allarmi* del
pannello (Ok/Ko).

| Entità | Pannello | Sorgente | Significato |
|---|---|---|---|
| **Communication Fault** (Guasto Comunicazione) — `binary_sensor.pure_vmc_communication_fault` | Communication | reg. 90 bit 0 o bit 8 | il pannello non comunica con la scheda X540 o X531 dell'unità |
| **Configuration Fault** (Errore di Configurazione) — `binary_sensor.pure_vmc_configuration_fault` | Configuration | reg. 97 bit 0 | configurazione incoerente (es. ingressi digitali) |
| **External Temperature Probe Fault** (Guasto Sonda Esterna) — `…_external_temperature_probe_fault` | Te | reg. 90 bit 1 | sonda Te guasta o scollegata |
| **Return Temperature Probe Fault** (Guasto Sonda Ripresa) — `…_return_temperature_probe_fault` | Tr | reg. 90 bit 2 | sonda Tr |
| **Exhaust Temperature Probe Fault** (Guasto Sonda Espulsione) — `…_exhaust_temperature_probe_fault` | Tx | reg. 90 bit 3 | sonda Tx |
| **Inlet Temperature Probe Fault** (Guasto Sonda Immissione) — `…_inlet_temperature_probe_fault` | Ti | reg. 90 bit 7 | sonda Ti |
| **Fan Fault** (Guasto Ventilatori) — `binary_sensor.pure_vmc_fan_fault` | Fans | reg. 90 bit 5 | ventilatore guasto (da pressostato o segnale tachimetrico) |
| **Anti-Frost Alarm** (Allarme Antigelo) — `binary_sensor.pure_vmc_anti_frost_alarm` | Anti-Frost | reg. 97 bit 1 | la procedura antigelo non riesce a proteggere lo scambiatore |

Quando una sonda è in guasto, la temperatura corrispondente diventa `unknown`.

## Dispositivo, opzioni, diagnostica

- Con il Modbus il dispositivo mostra la **versione firmware** del pannello (registri 3-4, formato
  `AA.MM.GG.PP`).
- **Configura** nella scheda dell'integrazione: *Leggi l'unità tramite Modbus TCP* (attivo di default).
  Disattivandolo si torna alle sole pagine web e le entità Modbus spariscono.
- **Scarica diagnostica**: lo stato decodificato più i registri grezzi (1–27, 32–38, 51–54, 81–99), con
  l'indirizzo IP oscurato. Da allegare a una segnalazione: le varianti di queste unità differiscono
  nella configurazione e il file mostra cosa riporta la propria.

## Particolarità del pannello di cui tener conto

- **Scritture scartate per 60 secondi.** Dopo ogni modifica fatta dalla pagina web o dal touch, per circa
  un minuto il pannello risponde "ok" alle scritture Modbus e le ignora. L'integrazione rilegge ogni
  registro dopo averlo scritto: la ventola ripiega sulla pagina web, gli altri controlli mettono il
  comando in coda e lo riprovano ogni 15 secondi per al massimo 3 minuti. Nel frattempo l'entità mostra
  il valore reale, non quello richiesto.
- **Valori temporanei senza salvataggio.** Una scrittura Modbus da sola torna al valore salvato dopo
  circa un minuto senza accessi ai registri (basta un riavvio di Home Assistant). Per questo
  l'integrazione, dopo ogni scrittura riuscita, chiede all'unità di salvarla in memoria permanente
  (registro 5, bit 14 per la configurazione, bit 15 per i set-point), come fa la sua pagina web.
  Ogni comando è quindi una scrittura sulla memoria non volatile dell'unità: normale per l'uso
  quotidiano, da evitare in automazioni che cambiano velocità ogni minuto.
- **Registro di configurazione a zero.** Su alcuni pannelli (una Pure 250 con firmware 25.01) il
  registro 7, che descrive la configurazione dell'unità, legge sempre 0. In quel caso l'integrazione
  presume ventilatori con tachimetrica (RPM) e bypass stagionale.
