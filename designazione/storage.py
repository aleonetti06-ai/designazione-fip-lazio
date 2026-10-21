"""Backup esplicito JSON delle note; non simula un archivio condiviso durevole."""

import json
from typing import Mapping

from designazione.domain import COMPETITION, GROUPS, Criticism

MAX_BYTES = 256 * 1024


def export_notes(notes: Mapping[str, Mapping[str, Criticism]]) -> bytes:
    payload = {
        "version": 1,
        "competition": COMPETITION.identity,
        "entries": [
            {"group_id": group, "team": team, "points": item.points, "note": item.note}
            for group, teams in sorted(notes.items())
            for team, item in sorted(teams.items())
        ],
    }
    data = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    import_notes(data)  # Lo stesso contratto vale per scrittura e lettura.
    return data


def import_notes(data: bytes) -> dict[str, dict[str, Criticism]]:
    if len(data) > MAX_BYTES:
        raise ValueError("File troppo grande: massimo 256 KiB.")
    try:
        payload = json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise ValueError("Il file non contiene JSON UTF-8 valido.") from exc
    if (
        not isinstance(payload, dict)
        or type(payload.get("version")) is not int
        or payload.get("version") != 1
    ):
        raise ValueError("Versione del backup non supportata.")
    if payload.get("competition") != COMPETITION.identity:
        raise ValueError("Il backup appartiene a un altro campionato/fase.")
    entries = payload.get("entries")
    if not isinstance(entries, list) or len(entries) > 100:
        raise ValueError("Elenco note assente o troppo lungo.")
    result: dict[str, dict[str, Criticism]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("Voce del backup non valida.")
        group, team = entry.get("group_id"), entry.get("team")
        points, note = entry.get("points"), entry.get("note")
        if not isinstance(group, str) or group not in GROUPS:
            raise ValueError("Girone sconosciuto nel backup.")
        if not isinstance(team, str) or not team.strip() or len(team) > 160:
            raise ValueError("Nome squadra non valido nel backup.")
        if team != " ".join(team.split()):
            raise ValueError("Nome squadra non esatto: spazi non normalizzati.")
        if (
            isinstance(points, bool)
            or not isinstance(points, (int, float))
            or points not in (0, 2, 4)
        ):
            raise ValueError("Criticità nel backup ammessa: 0, 2 o 4.")
        if not isinstance(note, str) or len(note) > 2000:
            raise ValueError("Nota non valida: massimo 2000 caratteri.")
        group_notes = result.setdefault(group, {})
        if team in group_notes:
            raise ValueError("Squadra duplicata nel backup.")
        group_notes[team] = Criticism(float(points), note)
    return result
