import json
from copy import deepcopy
from pathlib import Path

import pytest
import requests

from designazione.domain import Acquisition, RoundKey
from designazione.fip import fetch_page
from designazione.fip_api import parse_api_page
from designazione.scoring import ScoringSettings, assess_match

FIXTURES = Path(__file__).parent / "fixtures"


def test_backend_agrees_with_public_html_without_ghost_results(api_results, api_ranking, key, page):
    parsed = parse_api_page(api_results, api_ranking, key)

    def fields(m):
        return (m.match_id, m.home, m.away, m.home_points, m.away_points, m.day, m.time)

    assert [fields(m) for m in parsed.matches] == [fields(m) for m in page.matches]
    assert [(r.position, r.team, r.points) for r in parsed.ranking] == [
        (r.position, r.team, r.points) for r in page.ranking
    ]
    assert parsed.source_label == "Backend FIP (JSON)"
    assert parsed.ranking[3].team_id == "056236" and parsed.ranking[3].points == 0
    assert parsed.matches[2].home == "BASKET ROMA" and parsed.matches[2].home_points == 44
    assert parsed.matches[0].source_status == "omologata"
    assert parsed.matches[3].source_status == "designata" and not parsed.matches[3].has_result


def test_b_has_unconfirmed_score_and_changed_november_date():
    results = json.loads((FIXTURES / "fip_api_b_round1.json").read_text())
    ranking = json.loads((FIXTURES / "fip_api_ranking_b.json").read_text())
    page = parse_api_page(results, ranking, RoundKey("85583", 1, 1))
    unconfirmed = next(m for m in page.matches if m.match_id == "003090")
    assert unconfirmed.result_label == "63 - 73" and unconfirmed.score_origin == "rilevato"
    assert (
        unconfirmed.source_status == "designata"
        and "Non dichiarata" in unconfirmed.homologation_label
    )
    score = assess_match(unconfirmed, Acquisition(page, page.fetched_at), {}, ScoringSettings())
    assert score.total is None and "risultato già pubblicato" in score.blocked_reason
    future = next(m for m in page.matches if m.match_id == "003093")
    assert str(future.day) == "2026-11-21" and future.time == "18:00" and not future.has_result
    assert future.source_status == "calendario"


@pytest.mark.parametrize("home,away", [(0, 20), (19, 181), (205, 3)])
def test_backend_accepts_real_scores_outside_old_bounds(api_results, api_ranking, key, home, away):
    row = api_results["partite"][0]
    row.update(punti_casa=home, punti_casa_uff=home, punti_ospite=away, punti_ospite_uff=away)
    match = parse_api_page(api_results, api_ranking, key).matches[0]
    assert (match.home_points, match.away_points) == (home, away)


def test_official_score_takes_precedence_without_inferring_status(api_results, api_ranking, key):
    api_results["partite"][0]["punti_casa"] = 99
    page = parse_api_page(api_results, api_ranking, key)
    assert page.matches[0].home_points == 55 and page.matches[0].score_origin == "ufficiale"
    row = api_results["partite"][0]
    row.update(punti_casa_uff=-1, punti_ospite_uff=-1, stato_gara="designata")
    match = parse_api_page(api_results, api_ranking, key).matches[0]
    assert match.home_points == 99 and match.score_origin == "rilevato"
    assert "Non dichiarata" in match.homologation_label


def test_unknown_state_is_displayed_but_cannot_produce_green(api_results, api_ranking, key):
    api_results["partite"][3]["stato_gara"] = "stato non riconosciuto"
    page = parse_api_page(api_results, api_ranking, key)
    match = page.matches[3]
    assert match.source_status == "stato non riconosciuto"
    assert (
        assess_match(match, Acquisition(page, page.fetched_at), {}, ScoringSettings()).total is None
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("punti_casa_uff", -1),
        ("punti_casa", -2),
        ("punti_casa", True),
        ("numero_gara", "x"),
        ("C01_B01_CASA_FK", "999999"),
        ("casa", "BASKET ROMA"),
        ("codice_girone", "85583"),
        ("giornata", 2),
    ],
)
def test_inconsistent_backend_record_is_rejected(api_results, api_ranking, key, field, value):
    api_results["partite"][0][field] = value
    with pytest.raises(ValueError):
        parse_api_page(api_results, api_ranking, key)


def test_backend_duplicate_id_deduplication_and_conflict(api_results, api_ranking, key):
    duplicate = deepcopy(api_results["partite"][0])
    api_results["partite"].append(duplicate)
    assert len(parse_api_page(api_results, api_ranking, key).matches) == 5
    duplicate["punti_casa_uff"] += 1
    with pytest.raises(ValueError, match="duplicati discordanti"):
        parse_api_page(api_results, api_ranking, key)


def test_backend_official_ranking_not_reordered_or_reconstructed(api_results, api_ranking, key):
    api_ranking[-1]["punti_classifica"] = -2
    page = parse_api_page(api_results, api_ranking, key)
    assert page.ranking[-1].points == -2
    assert page.ranking[3].team == "SUPERNOVA FIUMICINO" and page.ranking[3].points == 0
    with pytest.raises(ValueError, match="classifica incompleta"):
        parse_api_page(api_results, api_ranking[:-1], key)


def test_backend_return_leg_verified_from_echoed_context(api_ranking):
    data = json.loads((FIXTURES / "fip_api_a_return1.json").read_text())
    page = parse_api_page(data, api_ranking, RoundKey("85582", 0, 1))
    assert len(page.matches) == 5 and page.matches[0].home == "SUPERNOVA FIUMICINO"
    assert str(page.matches[0].day) == "2027-01-16" and not page.matches[0].has_result
    with pytest.raises(ValueError, match="codice_andata_ritorno"):
        parse_api_page(data, api_ranking, RoundKey("85582", 1, 1))


def test_backend_failure_html_fallback_is_explicit_and_blocks_recommendations(
    monkeypatch, html, key
):
    class Response:
        content = html.encode()

        def raise_for_status(self):
            pass

    def get(url, **kwargs):
        if "backend.fip.it" in url:
            raise requests.ReadTimeout()
        return Response()

    monkeypatch.setattr(requests, "get", get)
    page = fetch_page(key)
    acquisition = Acquisition(page, page.fetched_at)
    assert page.source_label == "HTML pubblico FIP" and not acquisition.usable_for_scores
    assert any("Ripiego su HTML" in issue for issue in page.issues)


def test_calendar_fetch_reuses_ranking_without_requesting_it_again(
    monkeypatch, api_results, api_ranking, key
):
    requested = []

    def get(url, **kwargs):
        requested.append(url)
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(api_results).encode()
        return response

    monkeypatch.setattr(requests, "get", get)
    page = fetch_page(key, ranking=api_ranking)
    assert len(requested) == 1 and "/risultati?" in requested[0]
    assert len(page.ranking) == 11 and len(page.matches) == 5 and not page.issues
