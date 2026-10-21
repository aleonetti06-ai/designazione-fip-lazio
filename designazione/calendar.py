"""Indice esplicito dei due gironi: include recuperi in qualsiasi giornata."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from threading import Lock
from time import monotonic

from designazione.domain import COMPETITION, GROUPS, Acquisition, Match, RoundKey
from designazione.fip import FipError, fetch_page, fetch_ranking

ALL_ROUNDS = tuple(
    RoundKey(group, leg, number)
    for group in GROUPS
    for leg in (1, 0)
    for number in range(1, COMPETITION.rounds_per_leg + 1)
)


@dataclass(frozen=True)
class CalendarSnapshot:
    entries: dict[RoundKey, Acquisition]
    updated_at: datetime

    def acquisition(self, key: RoundKey, now: datetime) -> Acquisition | None:
        item = self.entries.get(key)
        # Un cambio filtro non scarica dati. Dopo 5 minuti i vecchi dati restano
        # consultabili, ma serve un aggiornamento esplicito per i suggerimenti.
        if item and item.page and (now - item.page.fetched_at).total_seconds() > 300:
            return replace(
                item, error=item.error or "Dati oltre 5 minuti: aggiornare il calendario."
            )
        return item


class CalendarIndex:
    """Carica solo su comando; 44 risultati + 2 classifiche, al massimo 2 GET simultanee.

    Nessuna richiesta quando si legge peek() o si cambiano date, filtri e pesi.
    Riutilizza per 5 minuti un indice completo, per 60 secondi uno incompleto.
    Dopo 3 turni falliti consecutivi interrompe il girone, marcando i rimanenti.
    """

    def __init__(self, page_fetcher=fetch_page, ranking_fetcher=fetch_ranking, clock=monotonic):
        self.page_fetcher, self.ranking_fetcher, self.clock = page_fetcher, ranking_fetcher, clock
        self._snapshot: CalendarSnapshot | None = None
        self._loaded_at = float("-inf")
        self._lock = Lock()

    def peek(self) -> CalendarSnapshot | None:
        return self._snapshot

    def load(self, *, force=False) -> CalendarSnapshot:
        with self._lock:
            previous = self._snapshot
            complete = previous and all(a.usable_for_scores for a in previous.entries.values())
            ttl = 300 if complete else 60
            if previous and self.clock() - self._loaded_at < (60 if force else ttl):
                return previous
            old = previous.entries if previous else {}

            def load_group(group):
                entries = {}
                failure = None
                failures = 0
                try:
                    ranking = self.ranking_fetcher(group)
                    ranked_at = datetime.now(timezone.utc)
                except FipError as exc:
                    failure = str(exc)
                for key in (k for k in ALL_ROUNDS if k.group_id == group):
                    attempt = datetime.now(timezone.utc)
                    prior = old.get(key)
                    try:
                        if failure:
                            raise FipError(failure)
                        page = self.page_fetcher(key, ranking=ranking)
                        page = replace(page, fetched_at=min(page.fetched_at, ranked_at))
                        if page.round != key:
                            raise FipError(
                                "Calendario: turno restituito diverso da quello richiesto."
                            )
                        if page.issues and prior and prior.page and not prior.page.issues:
                            raise FipError("Acquisizione incompleta: " + " ".join(page.issues))
                        item = Acquisition(page, attempt)
                    except FipError as exc:
                        item = Acquisition(prior.page if prior else None, attempt, str(exc))
                    entries[key] = item
                    failures = 0 if item.usable_for_scores else failures + 1
                    if failures >= 3 and failure is None:
                        failure = (
                            "Scansione interrotta dopo tre turni consecutivi non verificabili."
                        )
                return entries

            # I worker non accedono mai allo stato Streamlit o alle note private.
            with ThreadPoolExecutor(max_workers=2) as pool:
                entries = {}
                for group_entries in pool.map(load_group, GROUPS):
                    entries.update(group_entries)
            self._snapshot = CalendarSnapshot(entries, datetime.now(timezone.utc))
            self._loaded_at = self.clock()
            return self._snapshot


@dataclass(frozen=True)
class CalendarWindow:
    games: tuple[Match, ...]
    reportable: tuple[Match, ...]
    anomalies: tuple[Match, ...]
    conflicts: tuple[str, ...]


def select_window(
    snapshot: CalendarSnapshot, start: date, end: date, today: date
) -> CalendarWindow:
    if end < start:
        raise ValueError("La data finale deve essere successiva o uguale a quella iniziale.")
    matches, conflicts = {}, set()
    for item in snapshot.entries.values():
        if item.page is None:
            continue
        for match in item.page.matches:
            identity = (match.round.group_id, match.match_id)
            if identity in matches and matches[identity] != match:
                conflicts.add(identity)
            matches[identity] = match
    games, reportable, anomalies = [], [], []
    for identity, match in matches.items():
        if identity in conflicts:
            continue
        if match.day and start <= match.day <= end:
            reportable.append(match)
        if match.has_result:
            continue
        if match.day is None or match.day < today:
            anomalies.append(match)
        elif start <= match.day <= end:
            games.append(match)
    games.sort(key=lambda m: (m.day, m.time or "99:99", m.round.group_id, m.match_id))
    return CalendarWindow(
        tuple(games),
        tuple(sorted(reportable, key=lambda m: (m.day, m.time or "99:99", m.match_id))),
        tuple(anomalies),
        tuple(
            f"{GROUPS[group]} · gara {ref}: presente in turni discordanti, esclusa."
            for group, ref in sorted(conflicts)
        ),
    )
