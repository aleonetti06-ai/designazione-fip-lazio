"""Prime segnalazioni automatiche e manuali, con motivazioni immutabili."""

import json
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
from math import isfinite
from zoneinfo import ZoneInfo

from designazione.domain import COMPETITION, Acquisition, Criticism, Match, RoundKey
from designazione.scoring import Score, ScoringSettings, assess_match

SUPPORTS = ("Non registrato", "Nessuno", "Tutor in campo", "Formatore al tavolo")
ASSESSMENTS = ("Da valutare", "Sottostimata", "Coerente", "Sovrastimata", "Non valutabile")
MAX_HISTORY_BYTES = 2 * 1024 * 1024
ORIGINS = ("Sistema", "Manuale")
ROME = ZoneInfo("Europe/Rome")


@dataclass(frozen=True)
class Feedback:
    support: str = "Non registrato"
    assessment: str = "Da valutare"
    note: str = ""
    updated_at: datetime | None = None

    def __post_init__(self):
        if self.support not in SUPPORTS or self.assessment not in ASSESSMENTS:
            raise ValueError("Supporto o riscontro non riconosciuto.")
        _text(self.note, "Nota riscontro", 2000)


@dataclass(frozen=True)
class HistoryEntry:
    match: Match
    origin: str
    selected_at: datetime
    source_at: datetime
    source_label: str
    source_issues: tuple[str, ...]
    positions: tuple[int | None, int | None]
    criticisms: tuple[float, float]
    settings: ScoringSettings
    score: Score
    reason: str
    feedback: Feedback

    @property
    def identity(self) -> str:
        return f"{self.match.round.group_id}:{self.match.match_id}:{self.origin}"


def capture_selection(
    match: Match,
    acquisition: Acquisition,
    notes: dict[str, Criticism],
    settings: ScoringSettings,
    *,
    reason: str,
    first_leg: Acquisition | None = None,
    origin: str = "Manuale",
    now: datetime | None = None,
) -> HistoryEntry:
    now = now or datetime.now(timezone.utc)
    page = acquisition.page
    if page is None or match not in page.matches or match.round != page.round:
        raise ValueError("Selezionare una gara presente nei dati acquisiti.")
    if origin not in ORIGINS:
        raise ValueError("Origine della segnalazione non valida.")
    _text(reason, "Motivo della scelta", 2000)
    if not reason.strip():
        raise ValueError("Indicare brevemente il motivo della scelta.")
    positions = {r.team: r.position for r in page.ranking}
    score = assess_match(match, acquisition, notes, settings, first_leg)
    if match.has_result or (match.day and match.day < now.astimezone(ROME).date()):
        score = Score(
            None,
            blocked_reason="Segnalazione a posteriori: valutazione originaria non disponibile.",
        )
    if origin == "Sistema" and (
        score.total is None
        or score.total < settings.yellow
        or match.day is None
        or (now - page.fetched_at).total_seconds() > 300
    ):
        raise ValueError("La gara non ha una segnalazione automatica corrente e verificabile.")
    return HistoryEntry(
        match,
        origin,
        now,
        page.fetched_at,
        page.source_label,
        page.issues + ((acquisition.error,) if acquisition.error else ()),
        (positions.get(match.home), positions.get(match.away)),
        (notes.get(match.home, Criticism()).points, notes.get(match.away, Criticism()).points),
        settings,
        score,
        reason.strip(),
        Feedback(),
    )


def remember_signal(
    history: dict[str, HistoryEntry],
    match: Match,
    acquisition: Acquisition,
    notes: dict[str, Criticism],
    settings: ScoringSettings,
    first_leg: Acquisition | None = None,
    *,
    now: datetime | None = None,
) -> dict[str, HistoryEntry]:
    """Conserva la prima segnalazione gialla/rossa, senza riscriverla ai rerun."""
    identity = f"{match.round.group_id}:{match.match_id}:Sistema"
    if identity in history:
        return history
    score = assess_match(match, acquisition, notes, settings, first_leg)
    if score.total is None or score.total < settings.yellow:
        return history
    reason = (
        score.advice(settings)
        + " · "
        + " · ".join(f"{label}: +{value:g}" for label, value in score.contributions)
        + " · Tetto: 10"
    )
    if score.explanation:
        reason += " · " + score.explanation
    try:
        entry = capture_selection(
            match,
            acquisition,
            notes,
            settings,
            reason=reason,
            first_leg=first_leg,
            origin="Sistema",
            now=now,
        )
    except ValueError:
        return history
    return add_selection(history, entry)


def add_selection(history: dict[str, HistoryEntry], entry: HistoryEntry) -> dict[str, HistoryEntry]:
    if entry.identity in history:
        raise ValueError("Gara già nello storico: la valutazione iniziale viene conservata.")
    candidate = {**history, entry.identity: entry}
    export_history(candidate)
    return candidate


def record_feedback(entry: HistoryEntry, support: str, assessment: str, note: str) -> HistoryEntry:
    return replace(entry, feedback=Feedback(support, assessment, note, datetime.now(timezone.utc)))


def _text(value, label, limit=160):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f"{label}: testo non valido o troppo lungo.")
    return value


def _number(value, label, maximum=10):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label}: numero non valido.")
    if not isfinite(value) or not 0 <= value <= maximum:
        raise ValueError(f"{label}: valore fuori intervallo.")
    return value


def _timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Il timestamp deve contenere il fuso orario.")
    return result


def _decode_entry(raw) -> HistoryEntry:
    match_data = raw.pop("match")
    round_data = match_data.pop("round")
    if type(round_data["leg"]) is not int or type(round_data["number"]) is not int:
        raise ValueError("Turno non valido nello storico.")
    key = RoundKey(**round_data)
    for field in ("home", "away", "match_id"):
        if not _text(match_data[field], field).strip():
            raise ValueError("Identità della gara incompleta.")
    if not match_data["match_id"].isascii() or not match_data["match_id"].isdigit():
        raise ValueError("Numero gara non valido.")
    if match_data["home"] == match_data["away"]:
        raise ValueError("Squadre coincidenti nello storico.")
    for field in ("home_id", "away_id", "source_status", "score_origin", "time"):
        if match_data[field] is not None:
            _text(match_data[field], field)
    points = (match_data["home_points"], match_data["away_points"])
    if (points[0] is None) != (points[1] is None):
        raise ValueError("Risultato incompleto nello storico.")
    for value in points:
        if value is not None and (type(value) is not int or value < 0):
            raise ValueError("Risultato non valido nello storico.")
    match_data["day"] = date.fromisoformat(match_data["day"]) if match_data["day"] else None
    match = Match(**match_data, round=key)
    positions, criticisms = raw["positions"], raw["criticisms"]
    if len(positions) != 2 or len(criticisms) != 2:
        raise ValueError("Posizioni o criticità incomplete.")
    for position in positions:
        if position is not None and (type(position) is not int or not 1 <= position <= 11):
            raise ValueError("Posizione ufficiale non valida.")
    for value in criticisms:
        if _number(value, "Criticità") not in (0, 2, 4):
            raise ValueError("Criticità non valida.")
    weights = raw["settings"]
    for name in ("top", "playoff", "nearby", "red", "yellow", "return_weight"):
        _number(weights[name], name)
    if type(weights["return_enabled"]) is not bool:
        raise ValueError("Impostazione ritorno non valida.")
    settings = ScoringSettings(**weights)
    score_data = raw["score"]
    contributions = score_data["contributions"]
    if not isinstance(contributions, list) or len(contributions) > 10:
        raise ValueError("Contributi non validi.")
    for label, value in contributions:
        _text(label, "Contributo", 200)
        _number(value, "Contributo")
    score_data["contributions"] = tuple(tuple(c) for c in contributions)
    _text(score_data["explanation"], "Spiegazione", 2000)
    if score_data["blocked_reason"] is not None:
        _text(score_data["blocked_reason"], "Motivo blocco", 2000)
    total = score_data["total"]
    if total is not None:
        _number(total, "Punteggio")
        if abs(total - min(sum(c[1] for c in contributions), 10)) > 1e-8:
            raise ValueError("Punteggio incoerente con i contributi salvati.")
    score = Score(**score_data)
    origin = raw["origin"]
    if origin not in ORIGINS:
        raise ValueError("Origine della segnalazione non valida.")
    if origin == "Sistema" and (total is None or total < settings.yellow or match.has_result):
        raise ValueError("Segnalazione automatica priva di priorità verificabile.")
    issues = raw["source_issues"]
    if not isinstance(issues, list) or len(issues) > 50:
        raise ValueError("Anomalie fonte non valide.")
    for issue in issues:
        _text(issue, "Anomalia", 4000)
    _text(raw["source_label"], "Fonte", 300)
    _text(raw["reason"], "Motivo della scelta", 2000)
    feedback = raw["feedback"]
    feedback["updated_at"] = _timestamp(feedback["updated_at"]) if feedback["updated_at"] else None
    return HistoryEntry(
        match,
        origin,
        _timestamp(raw["selected_at"]),
        _timestamp(raw["source_at"]),
        raw["source_label"],
        tuple(issues),
        tuple(positions),
        tuple(criticisms),
        settings,
        score,
        raw["reason"],
        Feedback(**feedback),
    )


def import_history(data: bytes) -> dict[str, HistoryEntry]:
    if len(data) > MAX_HISTORY_BYTES:
        raise ValueError("Backup storico troppo grande: massimo 2 MiB.")
    try:
        payload = json.loads(data.decode("utf-8"))
        if (
            type(payload["version"]) is not int
            or payload["version"] != 1
            or payload["kind"] != "gare-attenzionate"
            or payload["competition"] != COMPETITION.identity
            or payload["scoring_rules"] != "u15-gold-v1"
        ):
            raise ValueError("Versione, tipo o campionato dello storico non riconosciuto.")
        entries = payload["entries"]
        if not isinstance(entries, list) or len(entries) > 440:
            raise ValueError("Elenco storico non valido: massimo 440 segnalazioni.")
        result = {}
        for raw in entries:
            entry = _decode_entry(raw)
            if entry.identity in result:
                raise ValueError("Gara duplicata nel backup storico.")
            result[entry.identity] = entry
        return result
    except (KeyError, TypeError, AttributeError, ValueError, UnicodeError, OverflowError) as exc:
        raise ValueError(f"Backup storico non valido: {exc}") from exc


def export_history(history: dict[str, HistoryEntry]) -> bytes:
    payload = {
        "version": 1,
        "kind": "gare-attenzionate",
        "competition": COMPETITION.identity,
        "scoring_rules": "u15-gold-v1",
        "entries": [asdict(item) for _, item in sorted(history.items())],
    }
    data = json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
        allow_nan=False,
        default=lambda value: value.isoformat(),
    ).encode("utf-8")
    import_history(data)
    return data
