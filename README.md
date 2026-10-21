# Designazione CIA · U15 Gold Lazio

Strumento interno di supporto ai designatori, con Python e Streamlit e interfaccia
italiana. Gestisce esclusivamente la fase di qualificazione U15 Gold maschile
Lazio: girone A `85582`, girone B `85583`, 11 squadre e 11 giornate per ciascuna
fase di andata/ritorno. Non effettua designazioni o invii alla FIP.

## Installazione e avvio

Richiede Python 3.11 o successivo, `venv` e accesso HTTPS a PyPI e alla fonte FIP.
Il setup non usa privilegi amministrativi ed è ripetibile:

```bash
bash scripts/setup.sh
```

Lo script crea `.venv` e installa le dipendenze runtime e di sviluppo dichiarate.
Su Streamlit Community Cloud il manifest runtime è `requirements.txt`;
`requirements-dev.txt` serve per sviluppo e verifiche. Non sono necessari browser
automatizzati, Playwright, Chromium o pacchetti di sistema.

Prima dell'avvio, creare la configurazione **privata** `.streamlit/secrets.toml`
usando `.streamlit/secrets.toml.example` come struttura e impostare `app_password`
a un valore scelto dal proprietario. Il file privato è escluso da Git. Poi:

```bash
.venv/bin/streamlit run app.py
```

In Community Cloud il proprietario deve configurare `app_password` in
**App settings → Secrets** prima di un futuro aggiornamento. Con chiave assente o
vuota l'accesso rimane chiuso: non esiste una password predefinita nel codice.
La password che era pubblica nel prototipo non viene riutilizzata o ruotata da
questa patch; il proprietario deve gestire separatamente la credenziale del
servizio. L'accesso resta quello di un piccolo strumento con password condivisa,
senza gestione di ruoli o account individuali.

Documentazione ufficiale:
[gestione segreti Streamlit](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management).

## Dove gira e quando si aggiorna

L'app pubblicata viene eseguita sui server di Streamlit Community Cloud. Il
browser visualizza l'interfaccia; le richieste FIP partono dal processo Python
del servizio. L'ambiente ChatGPT Work cloud viene usato per sviluppo e test e
non sostituisce l'hosting dell'app pubblicata. La piattaforma CIA Lazio in Apps
Script rimane separata e non viene modificata.

L'acquisizione è **a richiesta**: apertura della pagina e interazioni eseguono lo
script Streamlit. La cache condivisa tra sessioni evita nuovi download per
5 minuti per ciascun girone/fase/giornata. Non esiste un timer o un processo
periodico: la scadenza della cache provoca una richiesta solo alla successiva
esecuzione della pagina. Senza visite/interazioni non vengono avviati aggiornamenti.

Ogni nuova giornata richiede normalmente 2 GET (risultati e classifica), non una
scansione di tutti i turni. Il criterio ritorno, solo se attivato con peso > 0,
può leggere anche la corrispondente giornata d'andata, sempre con cache. In caso
di errore del backend viene tentata una sola lettura HTML della pagina pubblica.
Nessun retry automatico a raffica. Timeout espliciti: 10 secondi per connessione,
15 per lettura; errori e letture incomplete restano in cache 60 secondi. Il pulsante di aggiornamento
manuale rispetta almeno 30 secondi tra tentativi sulla stessa pagina.

Vengono mostrati ultimo tentativo e ultima acquisizione valida, in ora italiana.
Un errore o un aggiornamento incompleto conserva l'ultima pagina completa della
stessa selezione, quando disponibile, e sospende le raccomandazioni automatiche.
La cache pubblica è solo in memoria: riavvio o ibernazione possono cancellarla.
Se non esistono dati precedenti validi non viene mostrata una classifica a zero.

## Fonte FIP e significato dei dati

Gli endpoint sono stati osservati nel JavaScript pubblico FIP, che legge la base
`https://backend.fip.it/api/v1/` dall'elemento `#apibaseurl`, e verificati in lettura
il 21 ottobre 2026 per entrambi i gironi e per il ritorno:

- `risultati`: parametri `sesso`, `comitato_codice`, `codice_campionato`,
  `codice_fase`, `codice_girone`, `giornata`, `codice_andata_ritorno`.
- `classifica`: stessi filtri di campionato/girone, senza giornata e andata/ritorno.

`codice_andata_ritorno=1` significa andata; `0` ritorno. La risposta deve confermare
i filtri richiesti, anche per ciascuna gara. Il frontend HTML usa invece
`codice_ar`. Si tratta degli endpoint usati dal sito; non è stato verificato un
contratto pubblico di stabilità. I cambi di formato vengono segnalati, non ignorati.

La classifica conserva **posizioni e punti pubblicati da FIP**, anche in caso di
parità o penalizzazione. Non viene ricostruita sommando vittorie e non vengono
inventate colonne di partite giocate/vinte/perse. Le squadre sono verificate con
nome esatto e codice società, le gare con il numero FIP conservando gli zeri
iniziali. Doppioni identici sono deduplicati; doppioni discordanti sono un errore.

La fonte distingue `punti_casa/ospite` da `punti_casa/ospite_uff`. Il valore
sentinella `-1` significa punteggio assente. Si preferisce la coppia ufficiale
completa, altrimenti la coppia rilevata completa; non si mescolano origini.
Sono validi anche punteggi inferiori a 20 o superiori a 180. Un punteggio non
implica da solo omologazione: questa è dichiarata solo con `stato_gara=omologata`.
Gli stati osservati sono `calendario`, `designata`, `omologata`; valori nuovi
rimangono visibili e richiedono verifica prima di suggerire una designazione.

Il calendario usa `data_partita`, `ora_partita`, `casa` e `ospite` attuali. Una gara
senza risultato non viene dichiarata giocata solo perché la data è trascorsa.
Esempi di regressione reali: Basket Roma–Olimpia 44–66; Guidonia–Bracciano 55–67;
Scuola Basket Roma–Supernova il 21/10 alle 19:45 senza risultato; nel girone B,
Centri Laziali–Smit con 63–73 rilevato e stato ancora `designata`.

Il parser HTML circoscritto a `table.ranking` e `div.results-matches__match`
rimane un ripiego e un riscontro indipendente per le regressioni. Se il backend
fallisce, i dati HTML sono consultabili con avviso, **senza raccomandazioni
automatiche**: quell'HTML non espone stati e omologazioni. Non vengono letti o
conservati nominativi arbitrali nel modello dell'app o nelle fixture.

## Punteggio di supporto alla designazione

| Contributo | Valore iniziale |
| --- | ---: |
| Base | 1 |
| Entrambe nelle prime 4 | +5 |
| Entrambe nelle posizioni 6–10 | +2,5 |
| Differenza posizioni ≤ 2 | +3,5 |
| Criticità per ciascuna società | +0 / +2 / +4 |
| Tetto finale | 10 |

Soglie originali: rosso ≥ 8, formatore al tavolo; giallo ≥ 6, tutor in campo;
sotto 6, miniarbitri in autonomia. I pesi e le soglie sono modificabili, ma la
soglia gialla deve rimanere strettamente inferiore alla rossa. Esempi conservati:
2ª contro 3ª → 9,5; 1ª contro 4ª → 6; 6ª contro 8ª → 7; 1ª contro 11ª → 1.
Ogni contributo è mostrato separatamente. Il punteggio viene proposto per le
gare senza risultato, non per quelle già concluse/con punteggio pubblicato.

Il criterio aggiuntivo **ritorno dopo andata equilibrata** è disattivato e ha
peso iniziale **0**. Il limite iniziale di scarto **5** è una proposta provvisoria,
esplicitata nell'interfaccia e configurabile, da validare con Andrea insieme al
peso. Se attivo con peso > 0, si cerca nella stessa giornata d'andata la coppia
esatta con casa/ospite e codici invertiti, numero gara differente, punteggio e
omologazione verificabili. Con scarto ≤ limite viene aggiunto il peso scelto.
Lo scarto e il contributo sono spiegati nell'interfaccia. In assenza dell'andata
verificabile il punteggio resta non valutabile; non si interpreta l'assenza come
scarto elevato o bonus zero. Un calendario che non abbia il ritorno nello stesso
numero di giornata richiede un adattamento documentato, non una scansione occulta.

Le posizioni iniziali, specie quando molte squadre hanno zero punti, sono ancora
poco informative: i pesi richiedono validazione operativa. La scelta arbitrale
rimane una decisione del designatore.

## Criticità, note e conservazione

Le note sono distinte per girone e nome esatto della squadra e restano **nella
sessione corrente**. «Applica in questa sessione» aggiorna i punteggi, ma non
significa salvataggio condiviso o durevole. Per conservarle:

1. Scaricare il backup JSON dopo le modifiche.
2. Conservarlo in una destinazione privata appropriata.
3. In una nuova sessione caricarlo, controllare il numero di voci e premere
   «Importa e sostituisci le note della sessione».

L'importazione valida versione, campionato, gironi, duplicati, livelli 0/2/4,
dimensione massima 256 KiB e note di massimo 2000 caratteri. Un file non valido
non modifica lo stato. Nomi non presenti nella classifica corrente vengono
segnalati e non incidono sui punteggi; rimangono nel backup per non perderli.
Non commettere in Git backup con note reali.

Nella repository di partenza non risultava una configurazione di archivio
persistente. Le impostazioni private di produzione non sono accessibili con
l'accesso in sola lettura alla repository e non sono state ispezionate. Per un
archivio **condiviso e durevole** serve una destinazione esterna scelta dal
proprietario, per esempio un foglio Google privato con accesso server autorizzato
o un database gestito, più credenziali private, controllo degli accessi e gestione
delle modifiche concorrenti. Nessun servizio/account è stato creato da questa
patch. File locali o SQLite sul filesystem di Community Cloud non risolvono
questo requisito.

## Verifiche

```bash
bash scripts/check.sh
```

Esegue test pytest, lint Ruff, controllo formattazione e controllo compatibilità
delle dipendenze installate. È possibile eseguire separatamente:

```bash
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/python -m pip check
```

I test sono **offline**: fixture HTML/JSON minimali della fonte, senza arbitri o
altri dati personali non necessari; rete simulata per errori e cache; AppTest per
accesso, navigazione, modifiche dei widget, note e assenza di raccomandazioni con
dati falliti/precedenti. Il confronto HTML/JSON protegge i casi reali del parser
originario. I controlli live sono separati e dipendono dalla disponibilità FIP.
Gli esiti della ripresa del lavoro, distinti dai log precedenti, sono in
[VERIFICA.md](VERIFICA.md).

Il futuro deploy, la configurazione privata della password, l'eventuale archivio
condiviso e la validazione dei pesi con Andrea rimangono passaggi distinti.
Questa patch non modifica `main`, l'app pubblica o la piattaforma Apps Script.
