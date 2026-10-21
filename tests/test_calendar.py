from dataclasses import replace
from datetime import timedelta
from unittest.mock import Mock

from test_history import NOW, sample_page

from designazione.calendar import ALL_ROUNDS, CalendarIndex, CalendarSnapshot, select_window
from designazione.domain import Acquisition, RoundKey
from designazione.fip import FipError


def test_round_lookup_survives_module_reload_without_mixing_contexts(reloaded_round_key):
    page = sample_page()
    original = Acquisition(page, NOW)
    snapshot = CalendarSnapshot({page.round: original}, NOW)
    key = reloaded_round_key(page.round.group_id, page.round.leg, page.round.number)
    assert key != page.round  # Campi uguali, classi Python di generazioni diverse.
    assert snapshot.acquisition(key, NOW) is original
    assert not snapshot.acquisition(key, NOW + timedelta(minutes=6)).usable_for_scores
    for different in (
        reloaded_round_key("85583", 1, 1),
        reloaded_round_key("85582", 0, 1),
        reloaded_round_key("85582", 1, 2),
    ):
        assert snapshot.acquisition(different, NOW) is None


def test_failed_refresh_after_reload_preserves_last_valid_pages(reloaded_round_key, monkeypatch):
    from designazione import calendar

    clock = [0]
    fetch = Mock(side_effect=lambda key, **kw: sample_page(key))
    index = CalendarIndex(fetch, lambda group: [], clock=lambda: clock[0])
    original = index.load()
    monkeypatch.setattr(
        calendar,
        "ALL_ROUNDS",
        tuple(reloaded_round_key(k.group_id, k.leg, k.number) for k in ALL_ROUNDS),
    )
    fetch.side_effect = FipError("Timeout fonte")
    clock[0] = 301
    failed = index.load()
    for key, item in failed.entries.items():
        assert item.page is original.acquisition(key, NOW).page
        assert item.error and not item.usable_for_scores


def test_explicit_calendar_load_reuses_two_rankings_and_never_fetches_on_filters():
    clock = [0]
    ranking = Mock(return_value=["public ranking"])
    fetch = Mock(side_effect=lambda key, **kw: sample_page(key))
    index = CalendarIndex(fetch, ranking, clock=lambda: clock[0])
    assert index.peek() is None and not fetch.called
    snapshot = index.load()
    assert len(snapshot.entries) == 44 and fetch.call_count == 44 and ranking.call_count == 2
    assert all(c.kwargs["ranking"] == ["public ranking"] for c in fetch.call_args_list)
    select_window(index.peek(), NOW.date(), NOW.date() + timedelta(days=6), NOW.date())
    clock[0] = 59
    assert index.load(force=True) is snapshot
    clock[0] = 299
    assert index.load() is snapshot
    assert fetch.call_count == 44


def test_failed_reload_preserves_old_pages_and_stops_after_three_consecutive_errors():
    clock = [0]
    fetch = Mock(side_effect=lambda key, **kw: sample_page(key))
    index = CalendarIndex(fetch, lambda group: [], clock=lambda: clock[0])
    old = index.load()
    fetch.reset_mock(side_effect=True)
    fetch.side_effect = FipError("Timeout fonte")
    clock[0] = 301
    failed = index.load()
    assert fetch.call_count == 6
    assert len(failed.entries) == 44
    for key in ALL_ROUNDS:
        assert failed.entries[key].page == old.entries[key].page
        assert not failed.entries[key].usable_for_scores
    clock[0] = 360
    assert index.load() is failed


def test_ranking_failure_prevents_result_scan_and_marks_missing_group():
    ranking = Mock(side_effect=FipError("Classifica non disponibile"))
    fetch = Mock()
    snapshot = CalendarIndex(fetch, ranking).load()
    assert not fetch.called and ranking.call_count == 2
    assert all(a.page is None and a.error for a in snapshot.entries.values())


def test_window_includes_rescheduled_games_across_rounds_and_retrospective_reports():
    first = sample_page()
    key = RoundKey("85583", 0, 11)
    second = sample_page(key)
    result = replace(
        first.matches[1], day=NOW.date() - timedelta(days=1), home_points=2, away_points=190
    )
    overdue = replace(first.matches[0], match_id="000040", day=NOW.date() - timedelta(days=2))
    first = replace(first, matches=first.matches[:1] + (result, overdue))
    entries = {p.round: Acquisition(p, NOW) for p in (first, second)}
    window = select_window(
        CalendarSnapshot(entries, NOW),
        NOW.date() - timedelta(days=2),
        NOW.date() + timedelta(days=6),
        NOW.date(),
    )
    assert len(window.games) == 3 and len(window.reportable) == 5
    assert window.anomalies == (overdue,) and not window.conflicts
    assert any(m.round.number == 11 for m in window.games)
    snapshot = CalendarSnapshot(entries, NOW)
    assert not snapshot.acquisition(first.round, NOW + timedelta(minutes=6)).usable_for_scores


def test_conflicting_game_id_across_rounds_is_excluded():
    first = sample_page()
    second = sample_page(RoundKey("85582", 1, 2))
    snapshot = CalendarSnapshot({p.round: Acquisition(p, NOW) for p in (first, second)}, NOW)
    window = select_window(snapshot, NOW.date(), NOW.date() + timedelta(days=6), NOW.date())
    assert len(window.conflicts) == 2 and not window.games and not window.reportable
