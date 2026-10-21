import json
from dataclasses import replace
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from secrets import token_urlsafe
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse

import pytest
import requests
import streamlit as st
from streamlit.testing.v1 import AppTest

from designazione import views
from designazione.domain import Acquisition, Criticism
from designazione.fip import SourceCache
from designazione.storage import export_notes, import_notes

APP = str(Path(__file__).parents[1] / "app.py")


@pytest.fixture(autouse=True)
def clean_resource_cache(monkeypatch):
    monkeypatch.setattr(views, "now_rome", lambda: datetime(2026, 10, 21, 10, tzinfo=timezone.utc))
    st.cache_resource.clear()
    yield
    st.cache_resource.clear()


def element(elements, label):
    return next(e for e in elements if e.label == label)


def authenticated_app():
    app = AppTest.from_file(APP, default_timeout=10)
    app.secrets["app_password"] = token_urlsafe(24)  # Solo credenziale effimera di test.
    app.session_state["authenticated"] = True
    app.session_state["page_view"] = "🏀 Dashboard designazione"
    return app


def test_unconfigured_access_is_closed_without_source_requests(monkeypatch):
    get = Mock()
    monkeypatch.setattr(requests, "get", get)
    app = AppTest.from_file(APP).run()
    assert not app.exception
    assert any("Accesso non configurato" in e.value for e in app.error)
    assert not app.dataframe and not get.called


def test_login_dashboard_verification_and_widgets_do_not_rescan_source(
    monkeypatch, api_results, api_ranking
):
    def response_for(url, **kwargs):
        payload = api_ranking if "classifica?" in url else api_results
        response = Mock(content=json.dumps(payload).encode())
        response.raise_for_status.return_value = None
        return response

    get = Mock(side_effect=response_for)
    monkeypatch.setattr(requests, "get", get)
    password = token_urlsafe(24)
    app = AppTest.from_file(APP, default_timeout=10)
    app.secrets["app_password"] = password
    app.session_state["page_view"] = "🏀 Dashboard designazione"
    app.run()
    assert not app.exception and not get.called
    element(app.text_input, "Password").input(password)
    element(app.button, "Accedi").click().run()
    assert not app.exception and get.call_count == 2
    assert app.dataframe[0].value.loc[3, "Squadra"] == "SUPERNOVA FIUMICINO"
    assert app.dataframe[0].value.loc[3, "Punti"] == 0
    element(app.slider, "Scontro al vertice (1ª–4ª)").set_value(6.0).run()
    assert not app.exception and get.call_count == 2
    assert not app.exception and len(app.dataframe) == 2 and get.call_count == 2
    assert "🔍 Verifica dati FIP" not in element(app.radio, "Pagina").options
    assert [tab.label for tab in app.tabs] == [
        "Gare e priorità",
        "Dati FIP: classifica e risultati",
    ]
    matches = app.dataframe[1].value.set_index("ID gara")
    assert matches.loc["002983", "Casa"] == "BASKET ROMA"
    assert matches.loc["002983", "Risultato"] == "44 - 66"
    assert matches.loc["002979", "Risultato"] == "Senza risultato pubblicato"
    assert matches.loc["002983", "Omologazione"] == "Omologata (stato FIP)"
    assert matches.loc["002979", "Stato FIP"] == "designata"
    element(app.button, "Esci").click().run()
    assert not app.exception and not app.session_state["authenticated"]
    assert element(app.text_input, "Password") and get.call_count == 2


def test_first_source_failure_has_no_zero_table_or_green(monkeypatch):
    monkeypatch.setattr(requests, "get", Mock(side_effect=requests.ReadTimeout))
    app = authenticated_app().run()
    assert not app.exception and not app.dataframe and not app.success
    assert any("ReadTimeout" in e.value for e in app.error)


def test_wrong_password_does_not_request_fip(monkeypatch):
    get = Mock()
    monkeypatch.setattr(requests, "get", get)
    app = AppTest.from_file(APP)
    app.secrets["app_password"] = token_urlsafe(24)
    app.run()
    element(app.text_input, "Password").input("valore errato per il test")
    element(app.button, "Accedi").click().run()
    assert not app.exception and not get.called and not app.dataframe
    assert any("Password errata" in e.value for e in app.error)


def test_group_and_return_navigation_fetches_only_selected_rounds(monkeypatch):
    fixtures = Path(__file__).parent / "fixtures"
    requested = []

    def response_for(url, **kwargs):
        query = parse_qs(urlparse(url).query)
        group = "a" if query["codice_girone"] == ["85582"] else "b"
        if "classifica?" in url:
            name = f"fip_api_ranking_{group}.json"
        else:
            assert query["giornata"] == ["1"]
            leg = "round" if query["codice_andata_ritorno"] == ["1"] else "return"
            name = f"fip_api_{group}_{leg}1.json"
        requested.append(name)
        response = Mock(content=(fixtures / name).read_bytes())
        response.raise_for_status.return_value = None
        return response

    monkeypatch.setattr(requests, "get", response_for)
    app = authenticated_app().run()
    element(app.selectbox, "Fase").set_value(0).run()
    assert not app.exception and len(requested) == 4
    assert any("16/01/2027" in e.value for e in app.caption)
    element(app.checkbox, "Considera il ritorno dopo andata equilibrata").check().run()
    assert not app.exception and len(requested) == 4  # Peso 0: nessuna altra richiesta.
    element(app.slider, "Peso aggiuntivo ritorno (provvisorio)").set_value(2.0).run()
    assert not app.exception and len(requested) == 4  # L'andata è già nella cache.
    assert any("Andata non verificabile" in e.value for e in app.warning)
    element(app.selectbox, "Fase").set_value(1).run()
    element(app.selectbox, "Girone").set_value("85583").run()
    assert not app.exception and len(requested) == 6
    assert any("63 - 73" in e.value and "Non dichiarata omologata" in e.value for e in app.info)
    element(app.selectbox, "Girone").set_value("85582").run()
    assert not app.exception and len(requested) == 6
    assert set(requested) == {
        "fip_api_a_round1.json",
        "fip_api_a_return1.json",
        "fip_api_b_round1.json",
        "fip_api_ranking_a.json",
        "fip_api_ranking_b.json",
    }


def test_stale_ranking_visible_but_recommendations_suspended(monkeypatch, page):
    stale = Acquisition(page, page.fetched_at, "Errore fonte di test")
    monkeypatch.setattr(SourceCache, "get", lambda *a, **kw: stale)
    app = authenticated_app().run()
    assert not app.exception and len(app.dataframe) == 2
    assert any("precedente acquisizione" in e.value for e in app.warning)
    assert any("Da verificare" in e.value for e in app.warning)
    assert not app.success
    assert app.dataframe[0].value.loc[0, "Punti"] == 2


def test_notes_form_affects_score_and_is_isolated_per_session(monkeypatch, page):
    downloads = []
    original_download = st.download_button

    def download(label, data, **kwargs):
        downloads.append(data)
        return original_download(label, data, **kwargs)

    monkeypatch.setattr(st, "download_button", download)
    acquisition = Acquisition(page, page.fetched_at)
    monkeypatch.setattr(SourceCache, "get", lambda *a, **kw: acquisition)
    app = authenticated_app().run()
    element(app.selectbox, "Squadra").set_value("SCUOLA BASKET ROMA").run()
    element(app.selectbox, "Peso della squadra").set_value(4)
    element(app.text_area, "Nota").input("Criticità da verificare")
    element(app.button, "Applica peso e nota").click().run()
    assert not app.exception
    assert app.session_state["notes"]["85582"]["SCUOLA BASKET ROMA"] == Criticism(
        4, "Criticità da verificare"
    )
    assert any("SCORE 8.5" in e.value for e in app.error)
    assert any(
        e.score.total == 8.5 and e.origin == "Sistema"
        for e in app.session_state["history"].values()
    )
    assert any("Criticità da verificare" in e.value for e in app.text)
    assert import_notes(downloads[-1]) == app.session_state["notes"]
    other = authenticated_app().run()
    assert not other.exception and not other.session_state["notes"]["85582"]


def test_import_preview_and_explicit_replace_updates_notes(monkeypatch, page):
    imported = {"85582": {"SCUOLA BASKET ROMA": Criticism(4, "Nota importata")}}
    monkeypatch.setattr(st, "file_uploader", lambda *a, **kw: BytesIO(export_notes(imported)))
    monkeypatch.setattr(SourceCache, "get", lambda *a, **kw: Acquisition(page, page.fetched_at))
    app = authenticated_app().run()
    assert not app.exception and app.session_state["notes"] == {"85582": {}}
    element(app.button, "Importa e sostituisci le note della sessione").click().run()
    assert not app.exception and app.session_state["notes"] == imported
    assert any("Nota importata" in e.value for e in app.text)


def test_invalid_import_keeps_existing_notes(monkeypatch, page):
    monkeypatch.setattr(st, "file_uploader", lambda *a, **kw: BytesIO(b"not json"))
    monkeypatch.setattr(SourceCache, "get", lambda *a, **kw: Acquisition(page, page.fetched_at))
    app = authenticated_app()
    notes = {"85582": {"SCUOLA BASKET ROMA": Criticism(2, "Da conservare")}}
    app.session_state["notes"] = notes
    app.run()
    assert not app.exception and app.session_state["notes"] == notes
    assert any("JSON UTF-8" in e.value for e in app.error)


def test_invalid_thresholds_block_recommendations(monkeypatch, page):
    acquisition = Acquisition(page, page.fetched_at)
    monkeypatch.setattr(SourceCache, "get", lambda *a, **kw: acquisition)
    app = authenticated_app().run()
    element(app.slider, "Soglia formatore al tavolo").set_value(6.0)
    element(app.slider, "Soglia tutor in campo").set_value(7.0).run()
    assert not app.exception and not app.success
    assert any("soglia gialla" in e.value for e in app.error)


def test_incomplete_page_blocks_recommendations(monkeypatch, page):
    incomplete = replace(page, issues=("Orario mancante",))
    monkeypatch.setattr(
        SourceCache, "get", lambda *a, **kw: Acquisition(incomplete, page.fetched_at)
    )
    app = authenticated_app().run()
    assert not app.exception and not app.success
    assert any("Orario mancante" in e.value for e in app.warning)
