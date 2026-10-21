# Designazione CIA · U15 Gold Lazio

App Python e Streamlit per individuare le gare che richiedono supporto ai
miniarbitri nei gironi A e B dell’U15 Gold maschile Lazio. Propone priorità e
motivazioni; la decisione resta al designatore. Non invia designazioni alla FIP.

[Apri l’app](https://gare-da-attenzionare15g.streamlit.app/)

## Uso

- **Vista settimanale:** premi «Aggiorna calendario A e B», scegli periodo e
  filtri. Il calendario comprende andata, ritorno e recuperi.
- **Dashboard designazione:** consulta una giornata, i suggerimenti e la
  scheda «Dati FIP: classifica e risultati».
- **Storico gare attenzionate:** conserva le prime segnalazioni gialle/rosse
  con motivazione e permette di aggiungere il riscontro. Le gare sfuggite al
  sistema si segnalano manualmente dalla vista settimanale.
- **Info:** istruzioni su punteggi, fonti, aggiornamenti e salvataggi.

Nel menu laterale, **Pesi e soglie** modifica le regole generali;
**Pesi squadre** assegna criticità +0/+2/+4 e note alle singole società.
Valori iniziali: base 1; entrambe top 4 +5; entrambe nelle posizioni 6–10 +2,5;
distanza ≤2 posti +3,5; tetto 10. Rosso ≥8: formatore al tavolo; giallo ≥6:
tutor in campo; sotto 6: miniarbitri in autonomia. Il criterio aggiuntivo sul
ritorno è provvisorio e disattivato. I pesi richiedono validazione operativa.

## Dati e salvataggi

La fonte primaria è il backend JSON FIP, con classifica pubblicata, ID gara e
casa/ospite verificati. Risultato rilevato, ufficiale e omologazione restano
distinti. Errori, dati precedenti/incompleti e ripiego HTML sono segnalati e
sospendono le raccomandazioni; non generano semafori verdi automatici.

L’app gira sui server Streamlit e lavora **a richiesta**. La vista settimanale
si aggiorna con il pulsante; la dashboard legge il turno consultato con cache
di 5 minuti. Non esiste un aggiornamento schedulato a pagina chiusa.

- **Storico:** permanente e condiviso solo con Google Sheets configurato e
  scritture confermate. Altrimenti serve il backup JSON della sessione.
- **Pesi squadre e note:** restano nella sessione; conservarli e ripristinarli
  tramite «Esporta / importa note». Il collegamento dello storico non li salva.

## Avvio e configurazione

Richiede Python 3.11 o successivo e accesso HTTPS a PyPI e FIP. Dalla radice:

```bash
bash scripts/setup.sh
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Imposta `app_password` nel file privato, poi avvia:

```bash
.venv/bin/streamlit run app.py
```

Su **Streamlit Community Cloud** usa **Settings → Secrets**. Senza password
configurata l’accesso resta chiuso. Non pubblicare credenziali o backup reali
nella repository. Per l’archivio Google segui [CONFIGURA_STORICO.md](CONFIGURA_STORICO.md).

## Sviluppo e verifiche

```bash
bash scripts/check.sh
```

Esegue test offline, lint, formattazione e controllo dipendenze. Le prove live
su FIP e sul salvataggio Google sono separate. `app.py` e le viste gestiscono
l’interfaccia; `designazione/` separa dominio, acquisizione, calcolo e archivi;
`tests/` contiene fixture ridotte e regressioni. La piattaforma Apps Script
CIA Lazio resta separata.

Modifiche: [CHANGELOG.md](CHANGELOG.md). Verifiche storiche: [VERIFICA.md](VERIFICA.md).
