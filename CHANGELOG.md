# Changelog

Registro sintetico delle modifiche, dalla più recente.

## 21 ottobre 2026

- Aggiunta la pagina **Info**; sintetizzato il README e introdotto questo registro.
- Rinominato il pulsante in **Aggiorna calendario A e B** ([PR #3](https://github.com/aleonetti06-ai/designazione-fip-lazio/pull/3)).
- Riunite dashboard e verifica FIP in due schede della stessa pagina; aggiunto
  **Pesi squadre** come pannello richiudibile sotto **Pesi e soglie**, disponibile
  anche nella vista settimanale ([PR #2](https://github.com/aleonetti06-ai/designazione-fip-lazio/pull/2)).
- Corretta l’acquisizione FIP: backend JSON primario, classifica pubblicata,
  casa/ospite e ID verificati, risultati rilevati distinti dagli ufficiali e
  dall’omologazione, calendario dinamico e ripiego HTML segnalato.
- Aggiunte vista settimanale, gestione degli errori senza falsi verdi e
  storico automatico delle gare gialle/rosse con motivazione originale,
  segnalazioni manuali, riscontri e archivio Google Sheets configurabile.
- Spostata la password nei Secrets privati; introdotti backup JSON, moduli
  separati, test e script di setup/verifica ([PR #1](https://github.com/aleonetti06-ai/designazione-fip-lazio/pull/1)).

Il collegamento dello storico a Google richiede configurazione privata;
i pesi societari e le note restano nella sessione con backup JSON.
