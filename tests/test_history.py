import json
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from designazione.domain import Acquisition, Criticism, FipPage, Match, RoundKey, Standing
from designazione.history import (
    add_selection,
    capture_selection,
    export_history,
    import_history,
    record_feedback,
    remember_signal,
)
from designazione.scoring import ScoringSettings

NOW = datetime(2026, 10, 21, 10, tzinfo=timezone.utc)
SETTINGS = ScoringSettings()


def sample_page(key=RoundKey("85582", 1, 1)):
    ranking = tuple(Standing(i, f"Squadra {i}", 0, str(i)) for i in range(1, 12))
    matches = (
        Match(
            "000031",
            "Squadra 2",
            "Squadra 3",
            None,
            None,
            date(2026, 10, 22),
            "18:00",
            key,
            source_status="designata",
        ),
        Match(
            "000032",
            "Squadra 1",
            "Squadra 11",
            None,
            None,
            date(2026, 10, 23),
            "18:00",
            key,
            source_status="designata",
        ),
    )
    return FipPage(
        key, ranking, matches, (key,), NOW, "https://example.test", source_label="Backend FIP JSON"
    )


def automatic_history(page=None, **kwargs):
    page = page or sample_page()
    return remember_signal(
        {}, page.matches[0], Acquisition(page, NOW), {}, SETTINGS, now=NOW, **kwargs
    )


def test_first_automatic_signal_is_frozen_across_recalculation_and_feedback():
    page = sample_page()
    history = automatic_history(page)
    entry = next(iter(history.values()))
    assert entry.origin == "Sistema" and entry.score.total == 9.5
    assert entry.positions == (2, 3)
    assert "Sfida al vertice" in entry.reason and "Posizioni distanti" in entry.reason
    changed = replace(SETTINGS, top=0, nearby=0)
    again = remember_signal(
        history,
        page.matches[0],
        Acquisition(page, NOW),
        {"Squadra 2": Criticism(4)},
        changed,
        now=NOW,
    )
    assert again == history
    feedback = record_feedback(entry, "Tutor in campo", "Coerente", "Gara impegnativa")
    assert replace(feedback, feedback=entry.feedback) == entry
    restored = import_history(export_history({feedback.identity: feedback}))
    assert restored[entry.identity] == feedback


@pytest.mark.parametrize(
    "case", ["green", "failed", "incomplete", "stale", "past", "result", "undated"]
)
def test_only_current_verified_yellow_or_red_games_are_automatically_saved(case):
    page = sample_page()
    match = page.matches[1] if case == "green" else page.matches[0]
    if case == "past":
        match = replace(match, day=NOW.date() - timedelta(days=1))
    if case == "result":
        match = replace(match, home_points=63, away_points=73)
    if case == "undated":
        match = replace(match, day=None)
    page = replace(page, matches=(match,))
    if case == "incomplete":
        page = replace(page, issues=("Orario mancante",))
    if case == "stale":
        page = replace(page, fetched_at=NOW - timedelta(minutes=6))
    acquisition = Acquisition(page, NOW, "Errore fonte" if case == "failed" else None)
    assert not remember_signal({}, match, acquisition, {}, SETTINGS, now=NOW)


def test_yellow_threshold_is_included_and_manual_entry_cannot_hide_later_signal():
    page = sample_page()
    match = page.matches[0]
    settings = replace(SETTINGS, nearby=0)
    manual = capture_selection(
        match, Acquisition(page, NOW), {}, settings, reason="Osservazione umana", now=NOW
    )
    history = remember_signal(
        {manual.identity: manual}, match, Acquisition(page, NOW), {}, settings, now=NOW
    )
    assert len(history) == 2
    assert {e.origin for e in history.values()} == {"Manuale", "Sistema"}
    assert next(e for e in history.values() if e.origin == "Sistema").score.total == 6
    assert import_history(export_history(history)) == history


def test_retrospective_manual_report_does_not_invent_an_original_prediction():
    page = sample_page()
    match = replace(
        page.matches[1], day=NOW.date() - timedelta(days=1), home_points=70, away_points=69
    )
    page = replace(page, matches=(match,))
    entry = capture_selection(
        match,
        Acquisition(page, NOW),
        {},
        SETTINGS,
        reason="Difficoltà osservata sul campo",
        now=NOW,
    )
    assert entry.origin == "Manuale" and entry.score.total is None
    assert "a posteriori" in entry.score.blocked_reason
    history = add_selection({}, entry)
    assert import_history(export_history(history)) == history
    with pytest.raises(ValueError, match="già nello storico"):
        add_selection(history, entry)


@pytest.mark.parametrize(
    "mutation", ["duplicate", "total", "origin", "timezone", "nan", "competition"]
)
def test_invalid_history_backup_is_rejected(mutation):
    payload = json.loads(export_history(automatic_history()))
    entry = payload["entries"][0]
    if mutation == "duplicate":
        payload["entries"].append(entry)
    elif mutation == "total":
        entry["score"]["total"] = 1
    elif mutation == "origin":
        entry["origin"] = "Altro"
    elif mutation == "timezone":
        entry["selected_at"] = "2026-10-21T10:00:00"
    elif mutation == "nan":
        entry["settings"]["top"] = float("nan")
    else:
        payload["competition"] = "campionato errato"
    with pytest.raises(ValueError, match="Backup storico non valido"):
        import_history(json.dumps(payload).encode())
