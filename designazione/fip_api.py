"""Contratto JSON osservato nel JavaScript pubblico e verificato sul backend FIP.

Risultati e classifica sono endpoint letti dal sito FIP stesso, non API inventate.
I campi personali presenti nelle risposte non entrano nel modello o nelle fixture.
"""

import re
from datetime import date, datetime, timezone
from urllib.parse import urlencode

from designazione.domain import COMPETITION, FipPage, Match, RoundKey, Standing

API_BASE = "https://backend.fip.it/api/v1/"


def api_urls(key: RoundKey) -> tuple[str, str]:
    params = {
        "sesso": COMPETITION.sex,
        "comitato_codice": COMPETITION.committee,
        "codice_campionato": COMPETITION.code,
        "codice_fase": COMPETITION.phase,
        "codice_girone": key.group_id,
    }
    ranking = API_BASE + "classifica?" + urlencode(params)
    params.update(giornata=key.number, codice_andata_ritorno=key.leg)
    return API_BASE + "risultati?" + urlencode(params), ranking


def _number(value, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Backend FIP: {field} non è un intero.")
    return value


def _name(row: dict, key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Backend FIP: campo {key} assente.")
    return " ".join(value.split())


def _id(row: dict, key: str) -> str:
    value = _name(row, key)
    if not re.fullmatch(r"\d+", value):
        raise ValueError(f"Backend FIP: identificativo {key} non riconosciuto.")
    return value


def _context(row: dict, key: RoundKey) -> None:
    expected = {
        "sesso": COMPETITION.sex,
        "comitato_codice": COMPETITION.committee,
        "codice_campionato": COMPETITION.code,
        "codice_fase": COMPETITION.phase,
        "codice_girone": key.group_id,
        "giornata": str(key.number),
        "codice_andata_ritorno": str(key.leg),
    }
    for field, value in expected.items():
        if str(row.get(field)) != value:
            raise ValueError(f"Backend FIP: {field} non corrisponde alla richiesta.")


def _points(row: dict) -> tuple[int | None, int | None, str | None]:
    pairs = []
    for suffix in ("_uff", ""):
        pair = tuple(
            _number(row.get(f"punti_{side}{suffix}"), "punteggio") for side in ("casa", "ospite")
        )
        if any(p < -1 for p in pair):
            raise ValueError("Backend FIP: punteggio negativo non riconosciuto.")
        if (pair[0] == -1) != (pair[1] == -1):
            raise ValueError("Backend FIP: coppia di punteggi parziale.")
        pairs.append(pair)
    for pair, origin in zip(pairs, ("ufficiale", "rilevato")):
        if pair[0] >= 0:
            return pair[0], pair[1], origin
    return None, None, None  # -1 è il valore sentinella realmente osservato, non uno 0-0.


def parse_api_page(
    results, ranking, key: RoundKey, *, fetched_at: datetime | None = None
) -> FipPage:
    """Rifiuta dati ambigui; conserva ordine, punti e stati senza reinterpretarli."""
    if not isinstance(results, dict) or not isinstance(ranking, list):
        raise ValueError("Backend FIP: formato JSON non riconosciuto.")
    _context(results, key)
    rows = []
    for row in ranking:
        if not isinstance(row, dict):
            raise ValueError("Backend FIP: riga classifica non valida.")
        rows.append(
            Standing(
                _number(row.get("posizione"), "posizione"),
                _name(row, "nome_squadra"),
                _number(row.get("punti_classifica"), "punti classifica"),
                _id(row, "squadra_codice"),
            )
        )
    if (
        len(rows) != COMPETITION.teams_per_group
        or len({r.team_id for r in rows}) != len(rows)
        or len({r.team for r in rows}) != len(rows)
        or [r.position for r in rows] != list(range(1, len(rows) + 1))
    ):
        raise ValueError("Backend FIP: classifica incompleta, duplicata o fuori ordine.")
    roster = {r.team_id: r.team for r in rows}
    records = results.get("partite")
    if not isinstance(records, list) or not records:
        raise ValueError("Backend FIP: nessuna gara leggibile per la giornata.")
    matches: dict[str, Match] = {}
    issues = []
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("Backend FIP: scheda gara non valida.")
        _context(row, key)
        ref = _id(row, "numero_gara")
        if _id(row, "C01_GARA_PK") != ref:
            raise ValueError("Backend FIP: identificativi gara discordanti.")
        home, away = _name(row, "casa"), _name(row, "ospite")
        hid, aid = _id(row, "C01_B01_CASA_FK"), _id(row, "C01_B01_OSPITE_FK")
        if hid == aid or roster.get(hid) != home or roster.get(aid) != away:
            raise ValueError(
                f"Backend FIP: gara {ref}, nomi/codici società non coerenti con la classifica."
            )
        hp, ap, origin = _points(row)
        status = _name(row, "stato_gara")
        try:
            day = date.fromisoformat(_name(row, "data_partita"))
        except ValueError:
            day = None
        time = row.get("ora_partita")
        if not isinstance(time, str) or not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time):
            time = None
        if day is None or time is None:
            issues.append(f"Gara {ref}: data o ora non disponibili/leggibili.")
        if hp is not None and hp == ap:
            issues.append(f"Gara {ref}: punteggio pari pubblicato, stato da verificare.")
        if status == "omologata" and (hp is None or origin != "ufficiale"):
            raise ValueError(
                f"Backend FIP: gara {ref} omologata senza punteggio ufficiale completo."
            )
        match = Match(ref, home, away, hp, ap, day, time, key, hid, aid, status, origin)
        if ref in matches and matches[ref] != match:
            raise ValueError(f"Backend FIP: gara {ref}, duplicati discordanti.")
        matches[ref] = match
    teams = [team for m in matches.values() for team in (m.home_id, m.away_id)]
    if len(teams) != len(set(teams)):
        raise ValueError("Backend FIP: squadra presente in più gare della giornata.")
    if len(matches) != COMPETITION.teams_per_group // 2:
        issues.append(
            "Calendario incompleto: numero di gare diverso da quello atteso per il girone."
        )
    result_url, ranking_url = api_urls(key)
    return FipPage(
        key,
        tuple(rows),
        tuple(matches.values()),
        tuple(
            RoundKey(key.group_id, leg, n)
            for leg in (1, 0)
            for n in range(1, COMPETITION.rounds_per_leg + 1)
        ),
        fetched_at or datetime.now(timezone.utc),
        result_url,
        tuple(issues),
        "Backend FIP (JSON)",
        ranking_url,
    )
