"""Regole esplicite di supporto alla designazione, senza dipendenze Streamlit."""

from dataclasses import dataclass
from math import isfinite
from typing import Mapping

from designazione.domain import Acquisition, Criticism, Match


@dataclass(frozen=True)
class ScoringSettings:
    top: float = 5.0
    playoff: float = 2.5
    nearby: float = 3.5
    red: float = 8.0
    yellow: float = 6.0
    return_enabled: bool = False
    close_margin: int = 5  # Proposta provvisoria, non concordata con l'autore.
    return_weight: float = 0.0  # Nessun contributo aggiuntivo finché non configurato.

    def __post_init__(self):
        for value in (self.top, self.playoff, self.nearby, self.return_weight):
            if not isfinite(value) or not 0 <= value <= 10:
                raise ValueError("I pesi devono essere finiti e compresi tra 0 e 10.")
        if not 0 <= self.yellow < self.red <= 10:
            raise ValueError("Occorre 0 ≤ soglia gialla < soglia rossa ≤ 10.")
        if isinstance(self.close_margin, bool) or not isinstance(self.close_margin, int):
            raise ValueError("Lo scarto massimo deve essere un intero.")
        if self.close_margin < 0:
            raise ValueError("Lo scarto massimo non può essere negativo.")


@dataclass(frozen=True)
class Score:
    total: float | None
    contributions: tuple[tuple[str, float], ...] = ()
    explanation: str = ""
    blocked_reason: str | None = None

    def advice(self, settings: ScoringSettings) -> str:
        if self.total is None:
            return "Da verificare: nessuna raccomandazione automatica"
        if self.total >= settings.red:
            return "Formatore al tavolo"
        if self.total >= settings.yellow:
            return "Tutor in campo con il miniarbitro"
        return "Miniarbitri in autonomia"


def calculate_score(
    home_position: int | None,
    away_position: int | None,
    *,
    home_criticism: Criticism = Criticism(),
    away_criticism: Criticism = Criticism(),
    settings: ScoringSettings = ScoringSettings(),
    is_return: bool = False,
    first_leg_margin: int | None = None,
) -> Score:
    if home_position is None or away_position is None:
        return Score(None, blocked_reason="Posizione ufficiale di una squadra mancante.")
    if home_position < 1 or away_position < 1:
        raise ValueError("Le posizioni devono essere positive.")
    contributions = [("Base", 1.0)]
    if home_position <= 4 and away_position <= 4:
        contributions.append(("Sfida al vertice (1ª–4ª)", settings.top))
    if 6 <= home_position <= 10 and 6 <= away_position <= 10:
        contributions.append(("Zona taglio playoff (6ª–10ª)", settings.playoff))
    if abs(home_position - away_position) <= 2:
        contributions.append(("Posizioni distanti al massimo 2", settings.nearby))
    for label, criticism in (
        ("Criticità casa", home_criticism),
        ("Criticità ospite", away_criticism),
    ):
        if criticism.points not in (0, 2, 4):
            raise ValueError("Criticità ammessa: 0, 2 o 4 punti.")
        if criticism.points:
            contributions.append((label, criticism.points))
    explanation = ""
    if is_return and settings.return_enabled and settings.return_weight > 0:
        if first_leg_margin is None:
            return Score(
                None,
                tuple(contributions),
                blocked_reason="Andata non verificabile: criterio ritorno incompleto.",
            )
        if first_leg_margin < 0:
            raise ValueError("Lo scarto dell'andata non può essere negativo.")
        explanation = (
            f"Scarto andata {first_leg_margin}; limite configurato "
            f"≤ {settings.close_margin} (parametri provvisori)."
        )
        if first_leg_margin <= settings.close_margin:
            contributions.append(("Ritorno dopo andata equilibrata", settings.return_weight))
    return Score(
        min(sum(value for _, value in contributions), 10.0), tuple(contributions), explanation
    )


def assess_match(
    match: Match,
    acquisition: Acquisition,
    notes: Mapping[str, Criticism],
    settings: ScoringSettings,
    first_leg: Acquisition | None = None,
) -> Score:
    if not acquisition.usable_for_scores:
        return Score(None, blocked_reason="Dati FIP precedenti, mancanti o incompleti.")
    page = acquisition.page
    if page is None or match.round != page.round or match not in page.matches:
        return Score(None, blocked_reason="Gara non verificata nell'acquisizione corrente.")
    if match.has_result:
        return Score(None, blocked_reason="Gara con risultato già pubblicato.")
    if match.source_status is not None and match.source_status not in ("designata", "calendario"):
        return Score(None, blocked_reason=f"Stato FIP da verificare: {match.source_status}.")
    positions = {row.team: row.position for row in page.ranking}
    margin = None
    if match.round.leg == 0 and settings.return_enabled and settings.return_weight > 0:
        if first_leg and first_leg.usable_for_scores and first_leg.page:
            candidates = [
                m
                for m in first_leg.page.matches
                if m.round.group_id == match.round.group_id
                and m.round.leg == 1
                and m.match_id != match.match_id
                and m.home == match.away
                and m.away == match.home
                and m.has_result
                and m.home_points != m.away_points
                and m.source_status == "omologata"
                and (match.home_id is None or m.away_id == match.home_id)
                and (match.away_id is None or m.home_id == match.away_id)
            ]
            if len(candidates) == 1:
                margin = abs(candidates[0].home_points - candidates[0].away_points)
    return calculate_score(
        positions.get(match.home),
        positions.get(match.away),
        home_criticism=notes.get(match.home, Criticism()),
        away_criticism=notes.get(match.away, Criticism()),
        settings=settings,
        is_return=match.round.leg == 0,
        first_leg_margin=margin,
    )
