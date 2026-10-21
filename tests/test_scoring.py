from dataclasses import replace

import pytest

from designazione.domain import Acquisition, Criticism, RoundKey
from designazione.scoring import ScoringSettings, assess_match, calculate_score


@pytest.mark.parametrize(
    "home,away,expected",
    [
        (2, 3, 9.5),
        (1, 4, 6),
        (6, 8, 7),
        (1, 11, 1),
        (4, 5, 4.5),
        (5, 6, 4.5),
        (8, 10, 7),
        (9, 11, 4.5),
    ],
)
def test_original_scoring_regressions(home, away, expected):
    assert calculate_score(home, away).total == expected
    assert calculate_score(away, home).total == expected


def test_criticisms_add_for_both_teams_and_cap_at_ten():
    score = calculate_score(
        1, 11, home_criticism=Criticism(2, "Casa"), away_criticism=Criticism(4, "Ospite")
    )
    assert score.total == 7 and len(score.contributions) == 3
    assert calculate_score(2, 3, home_criticism=Criticism(4)).total == 10


def test_missing_positions_do_not_default_to_fifth():
    score = calculate_score(None, 11)
    assert score.total is None and "nessuna raccomandazione" in score.advice(ScoringSettings())


@pytest.mark.parametrize(
    "kw", [{"yellow": 8, "red": 8}, {"yellow": 9, "red": 7}, {"top": float("nan")}, {"nearby": -1}]
)
def test_invalid_settings_rejected(kw):
    with pytest.raises(ValueError):
        ScoringSettings(**kw)


@pytest.mark.parametrize("margin,expected", [(4, 3), (5, 3), (6, 1)])
def test_return_rule_boundary_and_visible_contribution(margin, expected):
    settings = ScoringSettings(return_enabled=True, return_weight=2, close_margin=5)
    score = calculate_score(1, 11, settings=settings, is_return=True, first_leg_margin=margin)
    assert score.total == expected and f"Scarto andata {margin}" in score.explanation


def test_return_rule_disabled_by_default_or_zero_weight():
    assert calculate_score(1, 11, is_return=True).total == 1
    assert (
        calculate_score(1, 11, is_return=True, settings=ScoringSettings(return_enabled=True)).total
        == 1
    )


def test_missing_first_leg_blocks_when_rule_is_active():
    settings = ScoringSettings(return_enabled=True, return_weight=2)
    assert calculate_score(1, 11, settings=settings, is_return=True).total is None


def test_advice_thresholds_keep_original_meaning():
    settings = ScoringSettings()
    assert calculate_score(1, 4).advice(settings) == "Tutor in campo con il miniarbitro"
    assert calculate_score(2, 3).advice(settings) == "Formatore al tavolo"
    assert calculate_score(1, 11).advice(settings) == "Miniarbitri in autonomia"


def test_stale_or_incomplete_data_never_produces_green(page):
    match = next(m for m in page.matches if not m.has_result)
    for acquisition in (
        Acquisition(page, page.fetched_at, "Errore fonte"),
        Acquisition(None, page.fetched_at),
        Acquisition(replace(page, issues=("Data mancante",)), page.fetched_at),
    ):
        assert assess_match(match, acquisition, {}, ScoringSettings()).total is None


def test_return_requires_exact_reverse_pair_and_result(page):
    original = page.matches[0]
    returning = replace(
        original,
        match_id="009999",
        home=original.away,
        away=original.home,
        home_points=None,
        away_points=None,
        round=RoundKey("85582", 0, 1),
    )
    return_page = replace(page, round=returning.round, matches=(returning,))
    current = Acquisition(return_page, page.fetched_at)
    first = Acquisition(
        replace(
            page,
            matches=tuple(
                replace(m, source_status="omologata") if m.has_result else m for m in page.matches
            ),
        ),
        page.fetched_at,
    )
    settings = ScoringSettings(return_enabled=True, return_weight=2, close_margin=12)
    score = assess_match(returning, current, {}, settings, first)
    baseline = calculate_score(2, 10).total  # Posizioni ufficiali Bracciano/Guidonia.
    assert score.total == baseline + 2 and "Scarto andata 12" in score.explanation
    wrong_pair = replace(returning, home=original.home, away=original.away)
    wrong_page = replace(return_page, matches=(wrong_pair,))
    assert (
        assess_match(
            wrong_pair, Acquisition(wrong_page, page.fetched_at), {}, settings, first
        ).total
        is None
    )
    assert (
        assess_match(
            returning, current, {}, settings, replace(first, error="Fonte non aggiornata")
        ).total
        is None
    )
