# Verifica della patch — 21 ottobre 2026

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

`bash scripts/check.sh` sul codice finale:

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

Consegna alternativa: archivio completo del codice finale, fixture, test,
istruzioni e applicatore, senza cronologia Git, credenziali o note reali. La
pubblicazione richiede un successivo accesso GitHub abilitato.

Prima di un futuro deploy il proprietario deve configurare `app_password` nei
segreti privati Streamlit. La credenziale precedente non è stata riutilizzata
o ruotata. Note e criticità hanno export/import JSON verificato; non esiste
ancora un archivio condiviso durevole. Il criterio ritorno resta disattivato,
con peso 0 e parametri da validare con Andrea.

L'app rimane a richiesta sui server Streamlit: cache 5 minuti, nessun processo
schedulato e nessun aggiornamento periodico quando non ci sono interazioni.
