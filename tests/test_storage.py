import json

import pytest

from designazione.domain import COMPETITION, Criticism
from designazione.storage import MAX_BYTES, export_notes, import_notes


def payload(**entry_changes):
    entry = {
        "group_id": "85582",
        "team": "SCUOLA BASKET ROMA",
        "points": 2,
        "note": "Criticità da verificare",
    }
    entry.update(entry_changes)
    return {"version": 1, "competition": COMPETITION.identity, "entries": [entry]}


def test_roundtrip_preserves_exact_teams_notes_and_group_identity():
    notes = {
        "85582": {"SCUOLA BASKET ROMA": Criticism(4, "Nota: più attenzione")},
        "85583": {"BASKET ROMA": Criticism(2, "Un altro girone")},
    }
    assert import_notes(export_notes(notes)) == notes
    assert import_notes(export_notes({})) == {}


@pytest.mark.parametrize(
    "changes",
    [
        {"points": True},
        {"points": 3},
        {"points": float("nan")},
        {"note": "x" * 2001},
        {"note": None},
        {"team": "  ROMA"},
        {"team": ""},
        {"group_id": "85584"},
    ],
)
def test_invalid_import_leaves_caller_state_untouched(changes):
    with pytest.raises(ValueError):
        import_notes(json.dumps(payload(**changes)).encode())


def test_duplicate_entries_rejected():
    data = payload()
    data["entries"] *= 2
    with pytest.raises(ValueError, match="duplicata"):
        import_notes(json.dumps(data).encode())


def test_wrong_competition_and_version_rejected():
    for field, value in (("competition", "altro"), ("version", 2)):
        data = payload()
        data[field] = value
        with pytest.raises(ValueError):
            import_notes(json.dumps(data).encode())


@pytest.mark.parametrize("data", [b"not json", b"[]", b"\xff", b" " * (MAX_BYTES + 1)])
def test_invalid_encoding_shape_or_size_rejected(data):
    with pytest.raises(ValueError):
        import_notes(data)
