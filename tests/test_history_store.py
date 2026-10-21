from copy import deepcopy
from dataclasses import replace
from unittest.mock import Mock

import pytest
import requests
from test_history import automatic_history

from designazione.history import record_feedback
from designazione.history_store import (
    HEADERS,
    GoogleSheetsHistoryStore,
    HistoryConflict,
    HistoryStoreError,
    configured_store,
    event_row,
    feedback_revision,
    replay,
)


class FakeSheets:
    def __init__(self):
        self.rows = [HEADERS[:]]
        self.requests = []
        self.fail_after_append = False
        self.status = 200

    def request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        if self.status != 200:
            return Mock(status_code=self.status)
        if method == "GET":
            return Mock(status_code=200, json=lambda: {"values": deepcopy(self.rows)})
        assert method == "POST" and url.endswith(":append")
        assert kwargs["params"] == {"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"}
        assert kwargs["timeout"] == (5, 15) and kwargs["allow_redirects"] is False
        rows = kwargs["json"]["values"]
        self.rows.extend(deepcopy(rows))
        if self.fail_after_append:
            self.fail_after_append = False
            raise requests.ReadTimeout("dettaglio privato da non esporre")
        return Mock(status_code=200, json=lambda: {"updates": {"updatedRows": len(rows)}})

    def store(self):
        return GoogleSheetsHistoryStore("test_spreadsheet", self)


def test_new_store_recovers_saved_history_and_never_overwrites_original():
    server = FakeSheets()
    history = automatic_history()
    assert server.store().add_new(history) == history
    assert server.store().load() == history  # Nuova istanza senza alcuna cache/sessione precedente.
    entry = next(iter(history.values()))
    changed = replace(entry, reason="Motivo successivo da non sostituire")
    assert server.store().add_new({entry.identity: changed}) == history
    assert len(server.rows) == 2
    assert sum(r[0] == "POST" for r in server.requests) == 1


def test_timeout_after_server_write_is_recoverable_without_duplicate():
    server = FakeSheets()
    store = server.store()
    history = automatic_history()
    server.fail_after_append = True
    with pytest.raises(HistoryStoreError, match="non confermato") as error:
        store.add_new(history)
    assert "dettaglio privato" not in str(error.value)
    assert store.add_new(history) == history
    assert len(server.rows) == 2


def test_concurrent_creates_preserve_first_snapshot_and_feedback_conflicts_preserve_both_events():
    entry = next(iter(automatic_history().values()))
    changed = replace(entry, reason="Altra lettura")
    first_feedback = record_feedback(entry, "Nessuno", "Coerente", "Primo operatore")
    second_feedback = record_feedback(entry, "Tutor in campo", "Sovrastimata", "Secondo operatore")
    first = event_row(first_feedback, "feedback", feedback_revision(entry))
    second = event_row(second_feedback, "feedback", feedback_revision(entry))
    rows = [HEADERS, event_row(entry), event_row(changed), first, second, first]
    history, seen, rejected = replay(rows)
    saved = history[entry.identity]
    assert replace(saved, feedback=entry.feedback) == entry
    assert saved.feedback == first_feedback.feedback
    assert rejected == {second[0]} and len(seen) == 3


def test_feedback_write_is_durable_and_stale_operator_gets_conflict():
    server = FakeSheets()
    history = automatic_history()
    original = next(iter(history.values()))
    store = server.store()
    store.add_new(history)
    revised = record_feedback(original, "Tutor in campo", "Coerente", "Riscontro")
    store.save_feedback(revised, feedback_revision(original))
    saved = server.store().load()[original.identity]
    assert saved == revised
    assert store.save_feedback(revised, feedback_revision(original))[original.identity] == revised
    other = record_feedback(original, "Nessuno", "Sottostimata", "Vecchia sessione")
    with pytest.raises(HistoryConflict, match="già modificato"):
        store.save_feedback(other, feedback_revision(original))
    assert server.store().load()[original.identity] == revised


@pytest.mark.parametrize("failure", ["header", "row", "403", "500"])
def test_store_errors_never_become_empty_success_or_overwrite(failure):
    server = FakeSheets()
    history = automatic_history()
    store = server.store()
    store.add_new(history)
    if failure == "header":
        server.rows[0] = ["Intestazione errata"]
    elif failure == "row":
        server.rows.append(["Riga corrotta"])
    else:
        server.status = int(failure)
    before = deepcopy(server.rows)
    with pytest.raises(HistoryStoreError):
        store.add_new(history)
    assert server.rows == before


def test_missing_or_invalid_credentials_do_not_attempt_network():
    assert configured_store({}) is None
    with pytest.raises(HistoryStoreError, match="Configurazione privata"):
        configured_store({"history_store": {"spreadsheet_id": "abc", "service_account": {}}})


def test_read_cache_reduces_widget_requests_but_force_reload_observes_other_writer():
    now = [0]
    server = FakeSheets()
    store = GoogleSheetsHistoryStore("test", server, clock=lambda: now[0])
    assert store.load() == {}
    other = server.store()
    history = automatic_history()
    other.add_new(history)
    calls = len(server.requests)
    assert store.load() == {} and len(server.requests) == calls
    assert store.load(force=True) == history
    now[0] = 16
    assert store.load() == history
