# Verifica della patch — 21 ottobre 2026

Questo è un registro storico delle verifiche e dei limiti riscontrati durante
lo sviluppo. I blocchi di pubblicazione citati nelle prime fasi sono stati poi
risolti con i merge delle PR. Per lo stato funzionale attuale e le modifiche
pubblicate, consultare [README.md](README.md) e [CHANGELOG.md](CHANGELOG.md).

## Recupero e base

Recuperato il checkout cloud originale della precedente esecuzione, senza
ricostruire i file dai log. Nessun `AGENTS.md` presente nel checkout o nei suoi
antenati applicabili. Eseguito `bash scripts/setup.sh` come primo gate nel
repository: exit 0. L'unico Markdown preesistente era `README.md`, letto prima
della revisione del codice.

Base: `3fe23486d70e18602391b1cfa7177e388e2bf6ac`, ramo di lavoro
`fix/fip-data-integrity`. `git ls-remote` ha confermato la stessa base su `main`.
Le modifiche recuperate sono state conservate.

I 92 test, smoke test e fetch descritti nella consegna della precedente chat
erano risultati storici. I controlli qui sotto sono nuove esecuzioni sul codice
recuperato e completato.

## Correzioni ulteriori dopo il recupero

- **Cache inizialmente incompleta:** una prima acquisizione con anomalie o
  ripiego HTML era conservata per 300 secondi perché la scadenza considerava
  soltanto l'errore, non la qualità della pagina. Ora usa 60 secondi come gli
  altri fallimenti. Un test controlla conservazione entro il limite e recupero
  al successivo tentativo.
- **Gare con punteggio rilevato:** la UI escludeva queste gare dal calcolo, ma
  il dominio poteva ancora assegnare un suggerimento a una gara con risultato
  e stato `designata`. Ora anche `assess_match` sospende il suggerimento quando
  esiste un risultato pubblicato. Verificato sul caso 003090 del girone B.
- Aggiunte verifiche UI per password errata, cambio girone, ritorno, attivazione
  del criterio aggiuntivo, andata mancante e riuso della cache. Le transizioni
  A andata → A ritorno → A andata → B andata → A andata fanno 6 GET complessive
  simulate: tre acquisizioni, nessuna scansione di tutto il calendario.

## Verifiche offline nuove

`bash scripts/check.sh` sul codice del primo commit recuperato (`7994e59`):

- **95 test passati**, inclusi AppTest Streamlit, parser, cache, punteggi e backup.
- Ruff lint superato; 14 file Python con formattazione conforme.
- `pip check`: nessuna dipendenza incompatibile.
- `git diff --check`: superato.

Ambiente verificato: Python 3.12, Streamlit 1.66.0. Il manifest permette
Python 3.11 o successivo e intervalli di versioni; non è stata eseguita una
matrice su tutte le combinazioni ammesse.

Server Streamlit avviato nel cloud su loopback, porta 8517, e poi terminato:
`/_stcore/health` → **200, ok**; `/` → **200**, pagina Streamlit ricevuta.
Questo smoke test verifica l'avvio HTTP; accesso e interazioni applicative sono
coperti separatamente dagli AppTest. Nessun deploy pubblico.

## Verifiche live nuove

Acquisizioni reali con `designazione.fip.fetch_page`, iniziate il 21/10/2026
alle 11:56–11:57 CEST. Nessun mock e nessun dato personale arbitrale salvato.

| Selezione | Fonte effettiva | Squadre | Gare | Anomalie |
| --- | --- | ---: | ---: | ---: |
| A, andata, giornata 1 | Backend FIP JSON | 11 | 5 | 0 |
| A, andata, giornata 4 | Backend FIP JSON | 11 | 5 | 0 |
| B, andata, giornata 1 | Backend FIP JSON | 11 | 5 | 0 |
| A, ritorno, giornata 1 | Backend FIP JSON | 11 | 5 | 0 |

Confermati nella nuova lettura:

- 002983: BASKET ROMA–OLIMPIA ROMA, 44–66 ufficiale, stato `omologata`.
- 002981: BASKET GUIDONIA–BRACCIANO BASKET, 55–67 ufficiale, stato `omologata`.
- 002979: SCUOLA BASKET ROMA–SUPERNOVA FIUMICINO, 21/10/2026 ore 19:45,
  stato `designata`, senza risultato pubblicato.
- 003090: CENTRI LAZIALI BASKET–SMIT ROMA CENTRO, 63–73 **rilevato**,
  stato `designata`, non dichiarata omologata.
- A ritorno giornata 1: cinque gare del 16–17 gennaio 2027, senza risultato.

Il codice effettivamente recuperato usa timeout `(10, 15)`, come README e test,
diversamente dal `(10, 20)` citato nella consegna. Le quattro letture nuove
sono riuscite con `(10, 15)`, senza ripiego. Il ripiego HTML è verificato offline;
non è stata forzata una nuova indisponibilità della fonte pubblica. Questi esiti
non dimostrano disponibilità continua né coprono tutte le 44 selezioni.

## Consegna e limiti

Il connettore GitHub conferma `pull=true`, `push=false` sulla repository originale;
nessuna PR risulta presente. Il fork `filospinato/designazione-fip-lazio` non
risulta accessibile (404); non è disponibile un'operazione fork nel connettore
e il browser cloud mostra GitHub senza autenticazione. Nessuna PR creata,
nessun merge e nessuna modifica a `main`, al sito pubblico o ad Apps Script.

Il primo lavoro è committato nel checkout cloud (`7994e59`). La preparazione
di un archivio alternativo è stata interrotta su indicazione dell’utente:
nessun archivio è stato pubblicato o caricato. L’utente ha poi autorizzato
il merge, che rimane bloccato dai permessi GitHub, non da una conferma mancante.

Prima di un futuro deploy il proprietario deve configurare `app_password` nei
segreti privati Streamlit. La credenziale precedente non è stata riutilizzata
o ruotata. Note e criticità hanno export/import JSON verificato; non esiste
ancora un archivio condiviso durevole. Il criterio ritorno resta disattivato,
con peso 0 e parametri da validare con Andrea.

L'app rimane a richiesta sui server Streamlit: cache 5 minuti, nessun processo
schedulato e nessun aggiornamento periodico quando non ci sono interazioni.


## Estensione: vista settimanale e storico automatico

Implementazione successiva richiesta dall’utente, nello stesso checkout cloud.
Prima di procedere è stato ripetuto `bash scripts/setup.sh`: exit 0.

- Vista iniziale settimanale A/B, periodo e ordine modificabili; caricamento
  esplicito di tutti i turni per includere recuperi e spostamenti. I widget non
  riscaricano il calendario. Classifica condivisa tra i turni dello stesso
  girone, cache degli errori, arresto dopo tre turni consecutivi non verificabili.
- Prima segnalazione gialla/rossa conservata automaticamente nella sessione,
  con origine Sistema, punteggio, motivazione, contributi, impostazioni, posizioni,
  criticità e timestamp. Cambi successivi non sovrascrivono la fotografia.
- Segnalazioni Manuali distinte per gare sfuggite al sistema, anche concluse;
  nessuna previsione originaria inventata a posteriori. Riscontro separato e
  backup JSON con importazione esplicita e validata.
- Date mancanti o trascorse senza risultato sono da verificare anche nella
  Dashboard per giornata. Non si producono nuovi suggerimenti su gare passate.
- Pesi e soglie iniziali invariati; nessun flusso di assegnazione persone,
  conferma presenze o revisione automatica delle criticità.

### Verifica offline dell’estensione

Nuova esecuzione completa `bash scripts/check.sh`: **120 test passati**,
Ruff lint e formattazione conformi, dipendenze coerenti. `git diff --check`
superato. Tra i casi aggiunti: scansione con due sole classifiche, riuso senza
richieste dai filtri, conservazione dei dati precedenti, duplicati discordanti,
gare recuperate da altri turni, soglie giallo/rosso, nessuna registrazione con
dati incompleti o vecchi, fotografia immutabile, segnalazioni a posteriori,
navigazione Streamlit, riscontro e backup.

### Verifica live dell’estensione

Nuova lettura reale il **21 ottobre 2026 dalle 12:19:09 CEST**, durata **123,1 s**,
con `CalendarIndex.load()` e codice dell’estensione. Risultati:

| Controllo | Esito |
| --- | ---: |
| Turni acquisiti | 44 su 44 |
| Turni verificabili e con dati entro 5 minuti al termine | 44 |
| Gare complessive | 220 |
| Gare da preparare nel periodo 21–27 ottobre | 12 |
| Gare senza data / trascorse senza risultato | 0 |
| Doppioni discordanti fra turni | 0 |

Fonte di tutte le pagine: **Backend FIP (JSON)**. Nessuna anomalia e nessun
ripiego HTML. Non sono stati salvati payload live, nominativi arbitrali o note
reali. Una scansione riuscita non garantisce disponibilità continua della fonte.

### Stato di pubblicazione e conservazione

Rivalidati `main = 3fe23486d70e18602391b1cfa7177e388e2bf6ac` e permessi del
connettore `pull=true`, `push=false`. Nessuna pubblicazione o modifica dell’app
Streamlit, nessun merge. Per pubblicare occorre accesso GitHub con scrittura.
Lo storico automatico è ancora limitato alla sessione: il backup JSON consente
conservazione e ripristino espliciti, ma la conservazione automatica durevole
richiede una destinazione esterna autorizzata e configurata. Nessun servizio
è stato creato. Questa limitazione è visibile nell’interfaccia e nel README.

## Estensione: archivio permanente delle segnalazioni

Richiesta successiva dell'utente: conservare automaticamente lo storico oltre
la sessione Streamlit. Primo gate `bash scripts/setup.sh` superato, istruzioni
Markdown lette; aggiunta `google-auth` per il collegamento privato Google Sheets.
Setup ripetuto con la nuova dipendenza: exit 0, google-auth 2.62.0 nell'ambiente
verificato. Nessun nuovo account, servizio a pagamento o modifica ad Apps Script.

### Codice e comportamento

- Aggiunti `history_store.py` (lettura/scrittura del foglio privato) e
  `history_ui.py` (sincronizzazione con l'interfaccia). La nuova sessione legge
  lo storico condiviso prima di mostrare o valutare le gare.
- Ogni segnalazione viene aggiunta automaticamente; la conferma compare solo
  dopo rilettura dal servizio. Errore o configurazione assente mantengono le
  nuove voci nella sessione con stato **Da salvare**, senza falsi successi.
- La sequenza di eventi conserva la prima fotografia per ID gara e origine,
  deduplica i retry e separa i riscontri. Due modifiche del riscontro partite
  dalla stessa versione non si sovrascrivono: una richiede riesame.
- Importazione JSON limitata alle segnalazioni assenti; nessuna sostituzione
  dell'archivio condiviso. Letture con cache di 15 secondi, scritture precedute
  da rilettura, timeout espliciti e valori RAW per evitare formule nelle note.
- Configurazione privata documentata in `CONFIGURA_STORICO.md` e nel file
  `secrets.toml.example`, verificato anche con il parser TOML. Nessuna credenziale
  reale inserita nel repository.

### Verifiche offline

**133 test passati** nella suite completa, inclusi gli AppTest Streamlit.
Lint, formattazione, dipendenze e `git diff --check` superati. Nuovi casi:
nuovo client e nuova sessione recuperano lo storico; la prima motivazione non
cambia; timeout dopo una scrittura riuscita non duplica; riscontri concorrenti
non si sovrascrivono; importazione preserva gli originali; HTTP 403/500, righe
corrotte e intestazioni errate non diventano un archivio vuoto o una conferma.
Questi controlli usano un servizio Sheets simulato, non credenziali Google reali.

### Risorsa cloud predisposta e limiti di attivazione

Creato tramite il connettore Google Drive un foglio nativo privato dedicato,
con scheda `Eventi` e intestazioni rilette dopo l'importazione. Metadati verificati:
`shared=false`, unica autorizzazione restituita di tipo proprietario. Nessuna
condivisione pubblica e nessuna segnalazione reale o fittizia inserita.
Il collegamento al file è consegnato nella chat, non incorporato nel codice pubblico.
Anteprima locale controllata; formattazione e struttura native rilette via API.

**Non è una prova di scrittura dall'app pubblicata.** Il connettore autorizzato
in questa chat non fornisce una credenziale trasferibile al processo Streamlit.
Occorre configurare l'account di servizio con accesso Editor al singolo foglio
nei segreti privati dell'app e poi eseguire la verifica fra sessioni descritta
nella guida. Non sono disponibili qui accesso alle impostazioni private o una
credenziale runtime. L'ultima verifica GitHub conferma ancora `push=false`:
nessuna PR, merge, pubblicazione o deploy eseguiti.

Non sono stati cambiati pesi, soglie o fonte FIP in questa estensione. Per il
dubbio di Andrea resta valida la correzione già preparata: dati JSON separati
per gare e classifica, risultati rilevati distinti da quelli ufficiali e stato
di omologazione non dedotto. Nessuna classifica provvisoria ricostruita.
