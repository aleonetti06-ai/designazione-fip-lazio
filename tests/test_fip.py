from copy import deepcopy
from dataclasses import replace

import pytest
import requests
from bs4 import BeautifulSoup

from designazione.domain import Acquisition, RoundKey
from designazione.fip import FipError, SourceCache, fetch_page, parse_page


def soup_of(html):
    return BeautifulSoup(html, "html.parser")


def test_real_matches_no_ghost_results_and_exact_home_away(page):
    assert len(page.matches) == 5
    matches = {m.match_id: m for m in page.matches}
    assert (matches["002981"].home, matches["002981"].away, matches["002981"].result_label) == (
        "BASKET GUIDONIA",
        "BRACCIANO BASKET",
        "55 - 67",
    )
    assert (matches["002983"].home, matches["002983"].away, matches["002983"].result_label) == (
        "BASKET ROMA",
        "OLIMPIA ROMA",
        "44 - 66",
    )
    school = matches["002979"]
    assert school.home == "SCUOLA BASKET ROMA" and school.away == "SUPERNOVA FIUMICINO"
    assert not school.has_result and school.home_points is None and school.away_points is None
    assert str(school.day) == "2026-10-21" and school.time == "19:45"
    assert matches["002980"].home == "STELLAEBK"  # Il calendario statico era invertito.
    assert len(page.available_rounds) == 22
    assert RoundKey("85582", 0, 11) in page.available_rounds


def test_official_ranking_order_and_points_are_not_recomputed(page):
    assert [(r.position, r.team, r.points) for r in page.ranking[:5]] == [
        (1, "OLIMPIA ROMA", 2),
        (2, "BRACCIANO BASKET", 2),
        (3, "DON BOSCO NUOVO SALARIO", 2),
        (4, "SUPERNOVA FIUMICINO", 0),
        (5, "SCUOLA BASKET ROMA", 0),
    ]


def test_numbers_and_team_names_outside_match_do_not_create_results(html, key):
    trap = (
        "<div><li>SCUOLA BASKET ROMA</li><li>SUPERNOVA FIUMICINO</li><li>99</li><li>88</li></div>"
    )
    page = parse_page(html.replace("<body>", "<body>" + trap), key)
    assert sum(m.has_result for m in page.matches) == 3
    assert next(m for m in page.matches if m.match_id == "002979").home_points is None


def test_included_names_do_not_match_by_substring(html, key):
    # Esistono anche BASKET ROMA e SCUOLA BASKET ROMA nella stessa classifica.
    page = parse_page(html.replace("BRACCIANO BASKET", "BASKET ROMA JUNIOR"), key)
    m = next(m for m in page.matches if m.match_id == "002981")
    assert m.away == "BASKET ROMA JUNIOR" and m.away_points == 67
    assert next(m for m in page.matches if m.home == "BASKET ROMA").home_points == 44


@pytest.mark.parametrize("home,away", [(0, 20), (19, 181), (205, 3)])
def test_scores_have_no_artificial_20_180_bounds(html, key, home, away):
    soup = soup_of(html)
    points = soup.select_one(".results-matches__match").select(".team__points")
    points[0].string, points[1].string = str(home), str(away)
    match = parse_page(str(soup), key).matches[0]
    assert (match.home_points, match.away_points) == (home, away)


def test_exact_duplicate_id_is_deduplicated(html, key):
    soup = soup_of(html)
    soup.select_one(".results-matches").append(deepcopy(soup.select_one(".results-matches__match")))
    assert len(parse_page(str(soup), key).matches) == 5


def test_conflicting_duplicate_id_is_rejected(html, key):
    soup = soup_of(html)
    duplicate = deepcopy(soup.select_one(".results-matches__match"))
    duplicate.select_one(".team__points").string = "56"
    soup.select_one(".results-matches").append(duplicate)
    with pytest.raises(FipError, match="discordanti"):
        parse_page(str(soup), key)


@pytest.mark.parametrize("value", ["", "non disponibile", "-1", "44-66"])
def test_partial_or_unreadable_scores_are_rejected(html, key, value):
    soup = soup_of(html)
    soup.select_one(".team__points").string = value
    with pytest.raises(FipError):
        parse_page(str(soup), key)


def test_penalties_and_official_tie_order_survive(html, key):
    soup = soup_of(html)
    soup.select("table.ranking tbody tr")[-1].select("td")[-1].string = "-2"
    page = parse_page(str(soup), key)
    assert page.ranking[-1].team == "BASKET ROMA" and page.ranking[-1].points == -2


@pytest.mark.parametrize(
    "selector", ["table.ranking", "table.ranking tbody tr", "select[name=gironi]"]
)
def test_missing_source_data_is_not_a_zero_ranking(html, key, selector):
    soup = soup_of(html)
    soup.select_one(selector).decompose()
    with pytest.raises(FipError):
        parse_page(str(soup), key)


def test_wrong_group_or_round_response_is_rejected(html):
    for wrong in (RoundKey("85583", 1, 1), RoundKey("85582", 0, 1), RoundKey("85582", 1, 2)):
        with pytest.raises(FipError):
            parse_page(html, wrong)


def test_no_match_nodes_is_a_source_error(html, key):
    soup = soup_of(html)
    soup.select_one(".results-matches").decompose()
    with pytest.raises(FipError, match="senza gare"):
        parse_page(str(soup), key)


def test_missing_time_or_partial_calendar_disables_recommendations(html, key):
    soup = soup_of(html)
    soup.select_one(".datetime .time").decompose()
    soup.select(".results-matches__match")[-1].decompose()
    page = parse_page(str(soup), key)
    assert len(page.issues) == 2
    assert not Acquisition(page, page.fetched_at).usable_for_scores


def test_tied_published_score_is_not_assumed_a_final_result(html, key):
    soup = soup_of(html)
    soup.select_one(".results-matches__match").select(".team__points")[1].string = "55"
    page = parse_page(str(soup), key)
    assert any("punteggio pari" in issue for issue in page.issues)


def test_cache_avoids_requests_on_widget_reruns_and_limits_manual_refresh(page, key):
    now, calls = [0], []

    def fetch(k):
        calls.append(k)
        return page

    cache = SourceCache(fetch, clock=lambda: now[0])
    first = cache.get(key)
    for _ in range(10):
        assert cache.get(key) is first
    now[0] = 29
    cache.get(key, force=True)
    assert len(calls) == 1
    now[0] = 30
    cache.get(key, force=True)
    assert len(calls) == 2
    now[0] = 331
    cache.get(key)
    assert len(calls) == 3


def test_failed_refresh_preserves_last_valid_ranking_and_recovery(page, key):
    now, calls = [0], []

    def fetch(k):
        calls.append(k)
        if len(calls) == 2:
            raise FipError("FIP non raggiungibile (ReadTimeout)")
        return page

    cache = SourceCache(fetch, clock=lambda: now[0])
    good = cache.get(key)
    now[0] = 301
    bad = cache.get(key)
    assert bad.page is good.page and bad.error and not bad.usable_for_scores
    assert bad.page.ranking[0].points == 2
    now[0] = 350
    assert cache.get(key) is bad and len(calls) == 2
    now[0] = 362
    recovered = cache.get(key)
    assert recovered.usable_for_scores and recovered.error is None and len(calls) == 3


def test_first_fetch_failure_has_no_fabricated_data(key):
    def fetch(k):
        raise FipError("Formato sorgente cambiato")

    result = SourceCache(fetch).get(key)
    assert result.page is None and result.error and not result.usable_for_scores


def test_first_incomplete_read_uses_short_cache_then_recovers(page, key):
    now, calls = [0], []

    def fetch(k):
        calls.append(k)
        return replace(page, issues=("Ripiego HTML",)) if len(calls) == 1 else page

    cache = SourceCache(fetch, clock=lambda: now[0])
    incomplete = cache.get(key)
    assert incomplete.page and not incomplete.usable_for_scores
    now[0] = 59
    assert cache.get(key) is incomplete and len(calls) == 1
    now[0] = 60
    assert cache.get(key).usable_for_scores and len(calls) == 2


def test_incomplete_refresh_keeps_complete_previous_page(page, key):
    now, calls = [0], []

    def fetch(k):
        calls.append(k)
        return (
            page
            if len(calls) == 1
            else replace(page, matches=page.matches[:3], issues=("Incompleto",))
        )

    cache = SourceCache(fetch, clock=lambda: now[0])
    cache.get(key)
    now[0] = 301
    result = cache.get(key)
    assert result.page is page and result.error and not result.usable_for_scores


def test_http_error_checked_and_timeout_is_explicit(monkeypatch, key):
    captured = {}

    def get(url, **kwargs):
        captured.update(kwargs)
        response = requests.Response()
        response.status_code = 503
        raise requests.HTTPError(response=response)

    monkeypatch.setattr(requests, "get", get)
    with pytest.raises(FipError, match="HTTP 503"):
        fetch_page(key)
    assert captured["timeout"] == (10, 15)


def test_network_timeout_is_not_swallowed(monkeypatch, key):
    def get(*args, **kwargs):
        raise requests.ReadTimeout()

    monkeypatch.setattr(requests, "get", get)
    with pytest.raises(FipError, match="ReadTimeout"):
        fetch_page(key)
