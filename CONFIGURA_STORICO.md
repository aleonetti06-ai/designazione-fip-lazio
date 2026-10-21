# Attivazione dello storico permanente

Il codice salva automaticamente le segnalazioni in un foglio Google privato.
La pagina Streamlit resta l'interfaccia per consultarle e aggiungere i riscontri.
GitHub conserva il codice; non contiene note o dati dell'archivio.

## Configurazione una tantum del proprietario

1. Usare il foglio privato predisposto per questo progetto, oppure un foglio
   dedicato equivalente. La scheda deve chiamarsi `Eventi` e avere nella riga 1
   queste quattro intestazioni esatte, da A a D:
   `event_id`, `operation`, `entry_id`, `payload_json`.
   L'archivio predisposto è vuoto: non sono state inventate segnalazioni passate.
2. Nel progetto Google autorizzato per l'app abilitare Google Sheets API e
   predisporre una credenziale di account di servizio. Non occorrono ruoli
   amministrativi sull'intero progetto per leggere o modificare il foglio:
   l'accesso ai dati dipende dalla condivisione del singolo file.
3. Condividere **solo quel foglio** con l'indirizzo `client_email` dell'account
   di servizio, assegnandogli il ruolo **Editor**. Lasciare il file privato,
   senza accesso pubblico tramite link. Gli operatori usano l'accesso Streamlit.
4. Nelle impostazioni private dell'app Streamlit, sezione **Secrets**, mantenere
   `app_password` e aggiungere i blocchi `history_store` e
   `history_store.service_account` indicati in `.streamlit/secrets.toml.example`.
   Copiare i valori dal JSON della credenziale. `spreadsheet_id` è la parte
   dell'URL fra `/d/` e `/edit`. `private_key` va fra tre virgolette per
   conservare le interruzioni di riga della chiave.
5. Dopo aver pubblicato il codice e aggiornato i segreti, riavviare l'app per
   ricreare il collegamento. Aprire **Storico gare attenzionate** e premere
   **Aggiorna storico condiviso**. Il menu deve indicare il collegamento
   all'archivio permanente, senza errori di permessi o configurazione.
6. Consultare un periodo con una gara gialla/rossa. Verificare **Salvata** nella
   vista settimanale e **Confermato** nello storico, poi aprire una nuova
   sessione autenticata e verificare che la stessa segnalazione sia presente.

La credenziale resta nei segreti privati di Streamlit: non va inserita nel
repository pubblico, nel foglio stesso o nella chat. L'autorizzazione del
connettore Google Drive usato per predisporre il foglio non viene trasferita
automaticamente al processo Python su Streamlit.

Documentazione ufficiale:
- [Streamlit e fogli privati](https://docs.streamlit.io/develop/tutorials/databases/private-gsheet)
- [Configurazione dei segreti su Community Cloud](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
- [Aggiunta di righe tramite Sheets API](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/append)

## Comportamento verificabile

La prima segnalazione viene aggiunta senza riscrivere l'intero archivio.
L'identità comprende girone, numero gara e origine Sistema/Manuale. Due operatori
che segnalano contemporaneamente la stessa gara possono produrre due eventi
tecnici, ma nello storico rimane una sola prima segnalazione per identità.
I riscontri sono eventi separati: il punteggio e la motivazione originali non
vengono sostituiti. Se due riscontri partono dalla stessa versione, il primo
registrato viene applicato e il secondo richiede un riesame esplicito.

La conferma di salvataggio compare solo dopo la rilettura dal servizio. Se una
richiesta scade dopo che Google ha già scritto, la sincronizzazione successiva
riconosce la segnalazione esistente senza duplicarla. Durante un'interruzione
di rete le nuove segnalazioni restano **Da salvare** nella sessione: non è
possibile garantire una scrittura remota quando il servizio non è raggiungibile.
Gli aggiornamenti sono tentati alle successive interazioni. Il pulsante nello
storico forza la rilettura; non è un processo schedulato.

L'importazione JSON aggiunge solo segnalazioni mancanti. Non cancella né
sovrascrive quelle condivise. Il download resta una copia facoltativa quando
il collegamento è attivo. Le criticità societarie restano gestite separatamente
con il loro backup; questo intervento rende durevole lo storico delle gare.

## Manutenzione e limiti

Non ordinare, eliminare o modificare manualmente le righe della scheda `Eventi`:
l'ordine conserva la sequenza delle operazioni. I dati vengono consultati e
modificati attraverso Streamlit. La lettura condivisa ha cache di 15 secondi;
prima delle scritture viene riletta la fonte. Timeout espliciti, nessun ciclo
di retry senza limite. L'archivio ammette 10.000 eventi; il contenuto esportabile
mantiene i limiti di 440 segnalazioni e 2 MiB. Al superamento il sistema segnala
il problema e non tronca i dati.

Il foglio è durevole rispetto alla sessione Streamlit, ma il proprietario può
ancora cancellarlo o revocare l'accesso. Per una nuova stagione usare un archivio
dedicato e aggiornare esplicitamente il contesto del campionato.
