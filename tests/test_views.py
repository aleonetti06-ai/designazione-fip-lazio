from dataclasses import replace
from datetime import timedelta
from io import BytesIO
from unittest.mock import Mock

import requests
import streamlit as st
from test_app import authenticated_app, element
from test_history import NOW, automatic_history, sample_page

from designazione import views
from designazione.calendar import ALL_ROUNDS, CalendarSnapshot
from designazione.domain import Acquisition, Criticism, RoundKey
from designazione.fip import SourceCache
from designazione.history import export_history, import_history


def weekly_app(monkeypatch, page=None):
    page = page or sample_page()
    snapshot = CalendarSnapshot({page.round: Acquisition(page, NOW)}, NOW)
    index = Mock()
    index.peek.return_value = None

    def load(**kw):
        index.peek.return_value = snapshot
        return snapshot

    index.load.side_effect = load
    monkeypatch.setattr(views, "get_calendar", lambda: index)
    monkeypatch.setattr(views, "now_rome", lambda: NOW)
    app = authenticated_app()
    app.session_state["page_view"] = "📅 Vista settimanale"
    return app, index


def test_coverage_after_reload_matches_games_and_keeps_real_errors(monkeypatch, reloaded_round_key):
    get = Mock(side_effect=AssertionError("Nessun accesso reale alla rete"))
    monkeypatch.setattr(requests, "get", get)
    app, index = weekly_app(monkeypatch)
    pages = [sample_page(reloaded_round_key(k.group_id, k.leg, k.number)) for k in ALL_ROUNDS]
    # Ogni gara compare in un solo turno, come nel calendario FIP.
    pages = [
        replace(p, matches=tuple(replace(m, match_id=f"{i:02}{m.match_id}") for m in p.matches))
        for i, p in enumerate(pages)
    ]
    snapshot = CalendarSnapshot({p.round: Acquisition(p, NOW) for p in pages}, NOW)
    index.load.side_effect = lambda **kw: setattr(index.peek, "return_value", snapshot)
    app.run()
    element(app.button, "Aggiorna calendario A e B").click().run()
    assert not app.exception and len(app.dataframe[0].value) == 88
    assert not any("turni non aggiornati" in w.value for w in app.warning)
    assert "Dettagli copertura calendario" not in [e.label for e in app.expander]
    assert any("44/44 turni aggiornati e verificabili" in c.value for c in app.caption)

    missing, failed, fallback = (p.round for p in pages[:3])
    del snapshot.entries[missing]
    snapshot.entries[failed] = replace(snapshot.entries[failed], error="Timeout fonte")
    item = snapshot.entries[fallback]
    snapshot.entries[fallback] = replace(item, page=replace(item.page, issues=("Ripiego HTML",)))
    element(app.checkbox, "Solo gialle, rosse e gare da verificare").check().run()
    assert not app.exception and index.load.call_count == 1 and not get.called
    assert any("3 turni non aggiornati" in w.value for w in app.warning)
    assert any("41/44 turni aggiornati e verificabili" in c.value for c in app.caption)
    details = element(app.expander, "Dettagli copertura calendario")
    assert len(details.markdown) == 3
    assert any("Dati assenti" in m.value for m in details.markdown)
    assert any("Timeout fonte" in m.value for m in details.markdown)
    assert any("Ripiego HTML" in m.value for m in details.markdown)
    table = app.dataframe[0].value
    assert set(
        table[table.Gara.isin([m.match_id for p in pages[1:3] for m in p.matches])].Priorità
    ) == {"Da verificare"}


def test_weekly_load_automatically_saves_reason_and_filters_do_not_redownload(monkeypatch):
    get = Mock(side_effect=AssertionError("Nessun accesso reale alla rete"))
    monkeypatch.setattr(requests, "get", get)
    app, index = weekly_app(monkeypatch)
    app.run()
    assert not app.exception and not index.load.called and not get.called
    assert [panel.label for panel in app.sidebar.expander][:3] == [
        "⚙️ Pesi e soglie",
        "⚖️ Pesi squadre",
        "📁 Esporta / importa note",
    ]
    assert not app.session_state["history"]
    element(app.button, "Aggiorna calendario A e B").click().run()
    assert not app.exception and index.load.call_count == 1
    history = dict(app.session_state["history"])
    assert len(history) == 1
    original = next(iter(history.values()))
    assert original.origin == "Sistema" and original.score.total == 9.5
    assert "Sfida al vertice" in original.reason
    element(app.multiselect, "Gironi da mostrare").set_value(["85583"]).run()
    element(app.slider, "Scontro al vertice (1ª–4ª)").set_value(0.0).run()
    assert not app.exception and index.load.call_count == 1 and not get.called
    assert app.session_state["history"] == history
    element(app.radio, "Pagina").set_value("📚 Storico gare attenzionate").run()
    assert not app.exception
    table = app.dataframe[0].value
    assert table.loc[0, "Origine"] == "Sistema"
    assert table.loc[0, "Punteggio salvato"] == 9.5
    assert "Sfida al vertice" in table.loc[0, "Perché segnalata"]
    assert any("sessione corrente" in w.value for w in app.warning)


def test_weekly_team_weights_recalculate_without_reload_and_follow_navigation(monkeypatch):
    get = Mock(side_effect=AssertionError("Nessun accesso reale alla rete"))
    monkeypatch.setattr(requests, "get", get)
    app, index = weekly_app(monkeypatch)
    app.run()
    element(app.button, "Aggiorna calendario A e B").click().run()
    page_b = sample_page(RoundKey("85583", 1, 1))
    index.peek.return_value.entries[page_b.round] = Acquisition(page_b, NOW)
    original = dict(app.session_state["history"])
    element(app.selectbox, "Squadra").set_value("Squadra 11").run()
    element(app.selectbox, "Peso della squadra").set_value(4)
    element(app.button, "Applica peso e nota").click().run()
    element(app.selectbox, "Squadra").set_value("Squadra 1").run()
    element(app.selectbox, "Peso della squadra").set_value(2)
    element(app.text_area, "Nota").input("Valutazione societaria")
    element(app.button, "Applica peso e nota").click().run()
    table = app.dataframe[0].value
    row = table[(table.Girone == "Girone A") & (table.Gara == "000032")].iloc[0]
    assert row.Punteggio == 7 and row.Priorità == "🟡 Giallo"
    assert app.session_state["history"]["85582:000032:Sistema"].score.total == 7
    assert all(app.session_state["history"][key] == entry for key, entry in original.items())
    element(app.selectbox, "Girone per i pesi").set_value("85583").run()
    element(app.selectbox, "Squadra").set_value("Squadra 1").run()
    assert element(app.selectbox, "Peso della squadra").value == 0
    assert app.session_state["notes"]["85582"]["Squadra 1"] == Criticism(
        2, "Valutazione societaria"
    )
    assert not app.exception and index.load.call_count == 1 and not get.called
    monkeypatch.setattr(SourceCache, "get", lambda self, key, **kw: index.peek().entries[key])
    element(app.radio, "Pagina").set_value("🏀 Dashboard designazione").run()
    element(app.selectbox, "Squadra").set_value("Squadra 1").run()
    assert not app.exception and element(app.selectbox, "Peso della squadra").value == 2
    assert any("SCORE 7.0" in item.value for item in app.warning)
    assert index.load.call_count == 1 and not get.called


def test_past_missed_game_can_be_reported_and_feedback_keeps_original_snapshot(monkeypatch):
    page = sample_page()
    match = replace(
        page.matches[1], day=NOW.date() - timedelta(days=1), home_points=60, away_points=59
    )
    page = replace(page, matches=(match,))
    app, index = weekly_app(monkeypatch, page)
    app.run()
    app.date_input[0].set_value((NOW.date() - timedelta(days=6), NOW.date()))
    element(app.button, "Aggiorna calendario A e B").click().run()
    assert not app.exception and not app.session_state["history"]
    element(app.text_area, "Motivo della segnalazione manuale").input("Difficoltà non prevista")
    element(app.button, "Salva segnalazione manuale").click().run()
    assert not app.exception
    original = next(iter(app.session_state["history"].values()))
    assert original.origin == "Manuale" and original.score.total is None
    element(app.radio, "Pagina").set_value("📚 Storico gare attenzionate").run()
    element(app.selectbox, "Supporto effettivamente presente").set_value("Nessuno")
    element(app.selectbox, "Valutazione della priorità iniziale").set_value("Non valutabile")
    element(app.text_area, "Osservazione dopo la gara").input("Da discutere con Andrea")
    element(app.button, "Salva riscontro").click().run()
    assert not app.exception and index.load.call_count == 1
    saved = next(iter(app.session_state["history"].values()))
    assert replace(saved, feedback=original.feedback) == original
    assert saved.feedback.note == "Da discutere con Andrea"
    assert import_history(export_history(app.session_state["history"]))[saved.identity] == saved


def test_history_import_requires_explicit_replacement_and_does_not_touch_notes(monkeypatch):
    candidate = automatic_history()
    data = export_history(candidate)
    monkeypatch.setattr(
        st,
        "file_uploader",
        lambda label, **kw: BytesIO(data) if label == "Backup storico JSON" else None,
    )
    app = authenticated_app()
    app.session_state["page_view"] = "📚 Storico gare attenzionate"
    app.run()
    assert not app.exception and not app.session_state["history"]
    element(app.button, "Importa le segnalazioni mancanti").click().run()
    assert not app.exception and app.session_state["history"] == candidate
    assert app.session_state["notes"] == {}
    monkeypatch.setattr(
        st,
        "file_uploader",
        lambda label, **kw: BytesIO(b"{}") if label == "Backup storico JSON" else None,
    )
    app.run()
    assert not app.exception and app.session_state["history"] == candidate
    assert any("Backup storico non valido" in e.value for e in app.error)


def test_automatic_history_survives_a_new_streamlit_session(monkeypatch):
    from test_history_store import FakeSheets

    from designazione import history_ui

    server = FakeSheets()
    first_store = server.store()
    monkeypatch.setattr(history_ui, "get_history_store", lambda: first_store)
    app, _ = weekly_app(monkeypatch)
    app.run()
    element(app.button, "Aggiorna calendario A e B").click().run()
    assert not app.exception
    first = dict(app.session_state["history"])
    assert len(first) == 1 and app.session_state["history_confirmed"] == set(first)
    assert app.dataframe[0].value.loc[0, "Storico"] == "Salvata"

    # Nuova sessione e nuova istanza del client: nessun dato deriva dalla precedente.
    monkeypatch.setattr(history_ui, "get_history_store", lambda: server.store())
    other = authenticated_app()
    other.session_state["page_view"] = "📚 Storico gare attenzionate"
    other.run()
    assert not other.exception and other.session_state["history"] == first
    assert other.dataframe[0].value.loc[0, "Salvataggio"] == "Confermato"
    assert not any("solo nella sessione" in e.value for e in other.warning)


def test_failed_automatic_write_stays_pending_and_retry_recovers_without_duplicates(monkeypatch):
    from test_history_store import FakeSheets

    from designazione import history_ui

    server = FakeSheets()
    store = server.store()
    monkeypatch.setattr(history_ui, "get_history_store", lambda: store)
    app, _ = weekly_app(monkeypatch)
    app.run()
    server.status = 403
    element(app.button, "Aggiorna calendario A e B").click().run()
    assert not app.exception and len(app.session_state["history"]) == 1
    assert not app.session_state["history_confirmed"]
    assert any("Archivio non accessibile" in e.value for e in app.error)
    assert app.dataframe[0].value.loc[0, "Storico"] == "Da salvare"
    server.status = 200
    app.run()
    assert not app.exception
    assert app.session_state["history_confirmed"] == set(app.session_state["history"])
    assert len(server.rows) == 2


def test_import_keeps_shared_original_and_feedback(monkeypatch):
    from test_history_store import FakeSheets

    from designazione import history_ui

    server = FakeSheets()
    store = server.store()
    original = automatic_history()
    entry = next(iter(original.values()))
    store.add_new(original)
    candidate = {entry.identity: replace(entry, reason="Non deve sovrascrivere la motivazione")}
    data = export_history(candidate)
    monkeypatch.setattr(history_ui, "get_history_store", lambda: store)
    monkeypatch.setattr(
        st,
        "file_uploader",
        lambda label, **kw: BytesIO(data) if label == "Backup storico JSON" else None,
    )
    app = authenticated_app()
    app.session_state["page_view"] = "📚 Storico gare attenzionate"
    app.run()
    element(app.button, "Importa le segnalazioni mancanti").click().run()
    assert not app.exception and app.session_state["history"] == original
    assert server.store().load() == original and len(server.rows) == 2
