"""Archivio Google Sheets privato: eventi aggiunti, mai riscritture dell'intero storico."""

import hashlib
import json
import re
from dataclasses import asdict, replace
from threading import RLock
from time import monotonic
from urllib.parse import quote

import requests
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import AuthorizedSession
from google.oauth2.service_account import Credentials

from designazione.history import HistoryEntry, export_history, import_history

HEADERS = ["event_id", "operation", "entry_id", "payload_json"]
MAX_EVENTS = 10000
SCOPE = "https://www.googleapis.com/auth/spreadsheets"


class HistoryStoreError(ValueError):
    pass


class HistoryConflict(HistoryStoreError):
    pass


def _json(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=lambda item: item.isoformat(),
    )


def _digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def feedback_revision(entry):
    return _digest(_json(asdict(entry.feedback)))


def event_row(entry: HistoryEntry, operation="create", expected=None):
    payload = {"history": json.loads(export_history({entry.identity: entry})), "expected": expected}
    encoded = _json(payload)
    # Create identifica la gara, non il ricalcolo: la prima scrittura resta autorevole.
    event_id = _digest(f"create:{entry.identity}") if operation == "create" else _digest(encoded)
    if len(encoded) > 45000:
        raise HistoryStoreError("Segnalazione troppo grande per una cella dell’archivio.")
    return [event_id, operation, entry.identity, encoded]


def replay(rows):
    if not isinstance(rows, list) or not rows or rows[0] != HEADERS:
        raise HistoryStoreError(
            "Intestazioni dell’archivio non valide: nessun dato è stato sovrascritto."
        )
    if len(rows) > MAX_EVENTS + 1:
        raise HistoryStoreError(
            "Archivio oltre 10.000 eventi: occorre manutenzione prima di scrivere."
        )
    history, seen, rejected = {}, set(), set()
    for number, row in enumerate(rows[1:], 2):
        if not row:
            continue
        try:
            event_id, operation, identity, payload = row
            data = json.loads(payload)
            entries = import_history(_json(data["history"]).encode())
            if (
                len(entries) != 1
                or identity not in entries
                or operation not in ("create", "feedback")
            ):
                raise ValueError("Evento non valido")
            entry = entries[identity]
            if event_row(entry, operation, data["expected"])[0] != event_id:
                raise ValueError("Identificativo evento non coerente")
            if event_id in seen:
                continue  # Retry di una scrittura riuscita ma senza risposta ricevuta.
            seen.add(event_id)
            if operation == "create":
                history.setdefault(identity, entry)
            elif identity not in history:
                raise ValueError("Riscontro senza segnalazione originale")
            elif feedback_revision(history[identity]) != data["expected"]:
                rejected.add(event_id)  # Un altro operatore ha già modificato il riscontro.
            else:
                history[identity] = replace(history[identity], feedback=entry.feedback)
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            # Non esporre il contenuto privato della riga nell'interfaccia o nei log.
            raise HistoryStoreError(
                f"Archivio non leggibile alla riga {number}. Nessuna sovrascrittura."
            ) from exc
    try:
        export_history(history)
    except ValueError as exc:
        raise HistoryStoreError("Dimensione complessiva dello storico non supportata.") from exc
    return history, seen, rejected


class GoogleSheetsHistoryStore:
    def __init__(self, spreadsheet_id, session, *, worksheet="Eventi", clock=monotonic):
        if not isinstance(spreadsheet_id, str) or not re.fullmatch(
            r"[A-Za-z0-9_-]+", spreadsheet_id
        ):
            raise HistoryStoreError("Identificativo del foglio non valido.")
        if not isinstance(worksheet, str) or not worksheet or len(worksheet) > 100:
            raise HistoryStoreError("Nome della scheda archivio non valido.")
        self.session = session
        escaped = worksheet.replace("'", "''")
        address = quote(f"'{escaped}'!A:D", safe="")
        self.url = (
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/{address}"
        )
        self.clock, self._loaded_at = clock, float("-inf")
        self._history, self._seen, self._rejected = {}, set(), set()
        self._rows = 0
        self._lock = RLock()

    def _request(self, method, suffix="", **kwargs):
        try:
            response = self.session.request(
                method, self.url + suffix, timeout=(5, 15), allow_redirects=False, **kwargs
            )
            if response.status_code != 200:
                status = response.status_code
                if status in (401, 403):
                    raise HistoryStoreError(
                        "Archivio non accessibile: verificare credenziale e permesso di modifica sul foglio."
                    )
                raise HistoryStoreError(f"Archivio Google Sheets non disponibile (HTTP {status}).")
            return response.json()
        except (requests.RequestException, GoogleAuthError) as exc:
            raise HistoryStoreError(
                "Collegamento all’archivio non riuscito: salvataggio non confermato."
            ) from exc
        except (ValueError, TypeError) as exc:
            if isinstance(exc, HistoryStoreError):
                raise
            raise HistoryStoreError(
                "Risposta dell’archivio non valida: salvataggio non confermato."
            ) from exc

    def load(self, *, force=False):
        with self._lock:
            if not force and self.clock() - self._loaded_at < 15:
                return dict(self._history)
            response = self._request("GET")
            rows = response.get("values", []) if isinstance(response, dict) else []
            history, seen, rejected = replay(rows)
            self._history, self._seen, self._rejected = history, seen, rejected
            self._rows, self._loaded_at = len(rows) - 1, self.clock()
            return dict(history)

    def _append(self, rows):
        if self._rows + len(rows) > MAX_EVENTS:
            raise HistoryStoreError("Archivio pieno: occorre manutenzione prima di scrivere.")
        # RAW impedisce che eventuali note testuali siano interpretate come formule.
        response = self._request(
            "POST",
            ":append",
            params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
            json={"majorDimension": "ROWS", "values": rows},
        )
        if not isinstance(response, dict) or response.get("updates", {}).get("updatedRows") != len(
            rows
        ):
            raise HistoryStoreError(
                "Scrittura senza conferma completa: riprovare la sincronizzazione."
            )
        self.load(force=True)
        if any(row[0] not in self._seen for row in rows):
            raise HistoryStoreError(
                "Scrittura non riletta nell’archivio: salvataggio non confermato."
            )

    def add_new(self, entries):
        with self._lock:
            current = self.load(force=True)
            try:
                export_history({**entries, **current})
            except ValueError as exc:
                raise HistoryStoreError(
                    "Importazione oltre i limiti dello storico: nessuna scrittura."
                ) from exc
            rows = [event_row(entry) for key, entry in entries.items() if key not in current]
            if rows:
                self._append(rows)
            return dict(self._history)

    def save_feedback(self, entry, expected):
        with self._lock:
            current = self.load(force=True)
            row = event_row(entry, "feedback", expected)
            if row[0] in self._seen and row[0] not in self._rejected:
                return current
            if (
                entry.identity not in current
                or feedback_revision(current[entry.identity]) != expected
            ):
                raise HistoryConflict(
                    "Riscontro già modificato nell’archivio. Aggiorna lo storico prima di salvare."
                )
            self._append([row])
            if row[0] in self._rejected:
                raise HistoryConflict(
                    "Un altro riscontro è stato salvato prima del tuo. Aggiorna lo storico e riesamina la modifica."
                )
            return dict(self._history)


def configured_store(secrets):
    config = secrets.get("history_store")
    if not config:
        return None
    try:
        account = dict(config["service_account"])
        if account.get("token_uri") != "https://oauth2.googleapis.com/token":
            raise ValueError("Endpoint credenziali non ammesso")
        credentials = Credentials.from_service_account_info(account, scopes=[SCOPE])
        session = AuthorizedSession(credentials, refresh_timeout=15, max_refresh_attempts=1)
        return GoogleSheetsHistoryStore(
            config["spreadsheet_id"], session, worksheet=config.get("worksheet", "Eventi")
        )
    except (KeyError, ValueError, TypeError, GoogleAuthError) as exc:
        raise HistoryStoreError(
            "Configurazione privata dell’archivio incompleta o non valida."
        ) from exc
