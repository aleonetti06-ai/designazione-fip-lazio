"""Dati pubblicati dalla fonte: nessuna classifica ricostruita o stato dedotto."""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class Competition:
    region: str = "LA"
    committee: str = "RLA"
    sex: str = "M"
    code: str = "U15G/M"
    phase: str = "1"
    teams_per_group: int = 11
    rounds_per_leg: int = 11

    @property
    def identity(self) -> str:
        return ":".join((self.region, self.committee, self.sex, self.code, self.phase))


COMPETITION = Competition()
GROUPS = {"85582": "Girone A", "85583": "Girone B"}


@dataclass(frozen=True)
class RoundKey:
    group_id: str
    leg: int  # FIP: 1 = andata, 0 = ritorno (verificato nei link del calendario).
    number: int

    def __post_init__(self):
        if self.group_id not in GROUPS or self.leg not in (0, 1):
            raise ValueError("Girone o fase andata/ritorno non supportati.")
        if not 1 <= self.number <= COMPETITION.rounds_per_leg:
            raise ValueError("Giornata non supportata.")

    @property
    def label(self) -> str:
        return f"{self.number}ª giornata · {'Andata' if self.leg == 1 else 'Ritorno'}"


@dataclass(frozen=True)
class Standing:
    position: int
    team: str
    points: int
    team_id: str | None = None


@dataclass(frozen=True)
class Match:
    match_id: str  # Numero gara FIP; conserva gli zeri iniziali.
    home: str
    away: str
    home_points: int | None
    away_points: int | None
    day: date | None
    time: str | None
    round: RoundKey
    home_id: str | None = None
    away_id: str | None = None
    source_status: str | None = None
    score_origin: str | None = None

    @property
    def has_result(self) -> bool:
        return self.home_points is not None and self.away_points is not None

    @property
    def result_label(self) -> str:
        if self.has_result:
            return f"{self.home_points} - {self.away_points}"
        return "Senza risultato pubblicato"

    @property
    def homologation_label(self) -> str:
        if self.source_status == "omologata":
            return "Omologata (stato FIP)"
        return "Non dichiarata omologata" if self.source_status else "Non esposta dalla fonte"


@dataclass(frozen=True)
class FipPage:
    round: RoundKey
    ranking: tuple[Standing, ...]
    matches: tuple[Match, ...]
    available_rounds: tuple[RoundKey, ...]
    fetched_at: datetime
    source_url: str
    issues: tuple[str, ...] = ()
    source_label: str = "HTML pubblico FIP"
    ranking_url: str | None = None


@dataclass(frozen=True)
class Acquisition:
    page: FipPage | None
    attempted_at: datetime
    error: str | None = None

    @property
    def usable_for_scores(self) -> bool:
        return self.page is not None and self.error is None and not self.page.issues


@dataclass(frozen=True)
class Criticism:
    points: float = 0.0
    note: str = ""
