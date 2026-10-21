"""HTML pubblico FIP, validazione circoscritta e cache delle acquisizioni.

Non vengono cercati numeri nel testo della pagina né letti nominativi arbitrali.
Un'acquisizione fallita non rimpiazza mai l'ultima pagina valida con dati vuoti.
"""

import json
import re
from dataclasses import replace
from datetime import date, datetime, timezone
from threading import Lock
from time import monotonic
from typing import Callable
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from designazione.domain import (
    COMPETITION,
    Acquisition,
    Competition,
    FipPage,
    Match,
    RoundKey,
    Standing,
)
from designazione.fip_api import api_urls, parse_api_page, parse_api_ranking

BASE_URL = "https://fip.it/risultati/"
MONTHS = {
    name: index
    for index, name in enumerate(
        (
            "gennaio",
            "febbraio",
            "marzo",
            "aprile",
            "maggio",
            "giugno",
            "luglio",
            "agosto",
            "settembre",
            "ottobre",
            "novembre",
            "dicembre",
        ),
        1,
    )
}


class FipError(ValueError):
    """Fonte non raggiungibile, incompleta o non conforme al formato verificato."""


def text(node: Tag | None) -> str:
    return " ".join(node.get_text(" ", strip=True).split()) if node else ""


def source_url(key: RoundKey, competition: Competition = COMPETITION) -> str:
    return (
        BASE_URL
        + "?"
        + urlencode(
            {
                "group": "campionati-regionali",
                "regione_codice": competition.region,
                "comitato_codice": competition.committee,
                "sesso": competition.sex,
                "codice_campionato": competition.code,
                "codice_fase": competition.phase,
                "codice_girone": key.group_id,
                "codice_ar": key.leg,
                "giornata": key.number,
            }
        )
    )


def _integer(value: str, field: str, signed: bool = False) -> int:
    if not re.fullmatch(r"-?\d+" if signed else r"\d+", value):
        raise FipError(f"{field}: valore non leggibile.")
    return int(value)


def _score(node: Tag | None) -> int | None:
    if node is None:
        raise FipError("Campo punteggio mancante nella gara.")
    value = text(node)
    if value in ("", "-", "–", "—"):
        return None
    return _integer(value, "Punteggio")


def _day(value: str) -> date | None:
    # Il sito pubblica, per esempio, "21 Ottobre 2026". Nessuna locale OS richiesta.
    parts = value.lower().split()
    if len(parts) == 3 and parts[1] in MONTHS:
        try:
            return date(int(parts[2]), MONTHS[parts[1]], int(parts[0]))
        except ValueError:
            return None
    return None


def _calendar(soup: BeautifulSoup, key: RoundKey) -> tuple[RoundKey, ...]:
    options = soup.select('select[name="calendar_mobile_select"] option')
    available = []
    selected = []
    for option in options:
        query = parse_qs(urlparse(option.get("value", "")).query)
        try:
            candidate = RoundKey(
                query["codice_girone"][0], int(query["codice_ar"][0]), int(query["giornata"][0])
            )
        except (KeyError, ValueError, IndexError) as exc:
            raise FipError("Collegamenti calendario FIP non riconosciuti.") from exc
        if candidate.group_id != key.group_id:
            raise FipError("Il calendario restituito appartiene a un altro girone.")
        if candidate not in available:
            available.append(candidate)
        if option.has_attr("selected"):
            selected.append(candidate)
    if key not in available or selected != [key]:
        raise FipError("La fonte non conferma la giornata e la fase richieste.")
    return tuple(available)


def _ranking(soup: BeautifulSoup, competition: Competition) -> tuple[Standing, ...]:
    tables = soup.select("table.ranking")
    if len(tables) != 1:
        raise FipError("Classifica ufficiale FIP assente o ambigua.")
    rows = []
    for row in tables[0].select("tbody > tr"):
        cells = row.find_all("td", recursive=False)
        if len(cells) != 3:
            raise FipError(
                "Formato della classifica FIP cambiato: attese posizione, squadra, punti."
            )
        name = text(cells[1].select_one(".team__name"))
        if not name:
            raise FipError("Nome squadra mancante in classifica.")
        rows.append(
            Standing(
                _integer(text(cells[0]), "Posizione"),
                name,
                _integer(text(cells[2]), "Punti classifica", signed=True),
            )
        )
    if len(rows) != competition.teams_per_group or len({r.team for r in rows}) != len(rows):
        raise FipError("Classifica incompleta o con squadre duplicate.")
    if [r.position for r in rows] != list(range(1, len(rows) + 1)):
        raise FipError("Posizioni FIP mancanti, duplicate o fuori ordine.")
    # Mantiene ordine e punti pubblicati, anche con penalizzazioni o parità.
    return tuple(rows)


def parse_page(
    html: str | bytes,
    key: RoundKey,
    *,
    fetched_at: datetime | None = None,
    competition: Competition = COMPETITION,
) -> FipPage:
    soup = BeautifulSoup(html, "html.parser")
    for name, expected in (
        ("sesso", competition.sex),
        ("campionati", competition.code),
        ("fasi", competition.phase),
        ("gironi", key.group_id),
    ):
        actual = soup.select(f'select[name="{name}"] option[selected]')
        if len(actual) != 1 or actual[0].get("value") != expected:
            raise FipError(f"La fonte non conferma il filtro {name} richiesto.")
    available = _calendar(soup, key)
    ranking = _ranking(soup, competition)
    roster = {r.team for r in ranking}
    matches: dict[str, Match] = {}
    issues = []
    for node in soup.select("div.results-matches__match"):
        ref = text(node.select_one(".results-matches__match__info .ref"))
        if not re.fullmatch(r"\d+", ref):
            raise FipError("Numero gara FIP assente o non riconosciuto.")
        teams = node.select(".teams > .team")
        if len(teams) != 2:
            raise FipError(f"Gara {ref}: attese esattamente due squadre.")
        home, away = (text(t.select_one(".team__name")) for t in teams)
        if home == away or home not in roster or away not in roster:
            raise FipError(f"Gara {ref}: nomi squadra non corrispondenti alla classifica FIP.")
        hp, ap = (_score(t.select_one(".team__points")) for t in teams)
        if (hp is None) != (ap is None):
            raise FipError(f"Gara {ref}: risultato parziale, manca un punteggio.")
        day = _day(text(node.select_one(".datetime .date")))
        time = text(node.select_one(".datetime .time"))
        if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", time):
            time = None
        if day is None or time is None:
            issues.append(f"Gara {ref}: data o ora non disponibili/leggibili.")
        if hp is not None and hp == ap:
            issues.append(f"Gara {ref}: punteggio pari pubblicato, stato da verificare.")
        match = Match(ref, home, away, hp, ap, day, time, key)
        if ref in matches and matches[ref] != match:
            raise FipError(f"Gara {ref}: duplicati con dati discordanti.")
        matches[ref] = match
    if not matches:
        raise FipError("Calendario senza gare leggibili: non viene interpretato come turno vuoto.")
    names = [team for m in matches.values() for team in (m.home, m.away)]
    if len(names) != len(set(names)):
        raise FipError("Una squadra compare in più gare della stessa giornata.")
    if len(matches) != competition.teams_per_group // 2:
        issues.append(
            "Calendario incompleto: numero di gare diverso da quello atteso per il girone."
        )
    return FipPage(
        key,
        ranking,
        tuple(matches.values()),
        available,
        fetched_at or datetime.now(timezone.utc),
        source_url(key, competition),
        tuple(dict.fromkeys(issues)),
    )


def _get(url: str) -> requests.Response:
    try:
        response = requests.get(
            url,
            timeout=(10, 15),
            headers={
                "User-Agent": "DesignazioneU15Lazio/1.0 (lettura calendario pubblico FIP)",
            },
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        code = exc.response.status_code if exc.response is not None else None
        detail = f"HTTP {code}" if code is not None else type(exc).__name__
        raise FipError(f"FIP non raggiungibile ({detail}); riprovare più tardi.") from exc
    return response


def fetch_ranking(group_id: str) -> list:
    """Una classifica validata da riusare nella scansione esplicita del calendario."""
    try:
        payload = json.loads(_get(api_urls(RoundKey(group_id, 1, 1))[1]).content)
        parse_api_ranking(payload)
        return payload
    except (ValueError, UnicodeError) as exc:
        raise FipError(str(exc)) from exc


def fetch_page(key: RoundKey, *, ranking: list | None = None) -> FipPage:
    # Endpoint e parametri osservati nel sito FIP, poi verificati per A/B e ritorno.
    try:
        result_url, ranking_url = api_urls(key)
        results = json.loads(_get(result_url).content)
        if ranking is None:
            ranking = json.loads(_get(ranking_url).content)
        return parse_api_page(results, ranking, key)
    except (ValueError, UnicodeError) as exc:
        api_error = str(exc)
    try:
        page = parse_page(_get(source_url(key)).content, key)
    except FipError as exc:
        raise FipError(f"Backend: {api_error} HTML pubblico: {exc}") from exc
    # Il ripiego conserva dati consultabili, ma non deve mascherare un errore con un verde.
    return replace(
        page,
        issues=page.issues
        + (
            f"Backend non verificabile ({api_error}). Ripiego su HTML pubblico: "
            "stati e omologazioni non disponibili; raccomandazioni sospese.",
        ),
    )


class SourceCache:
    """Cache pubblica in memoria, condivisibile fra sessioni e sicura fra thread.

    TTL 5 minuti; errori 60 secondi; aggiornamento manuale non prima di 30 secondi.
    Non è un archivio durevole e non contiene note degli utenti.
    """

    def __init__(
        self,
        fetcher: Callable[[RoundKey], FipPage] = fetch_page,
        clock: Callable[[], float] = monotonic,
        ttl: float = 300,
        error_ttl: float = 60,
        min_refresh: float = 30,
    ):
        self.fetcher, self.clock = fetcher, clock
        self.ttl, self.error_ttl, self.min_refresh = ttl, error_ttl, min_refresh
        self._entries: dict[RoundKey, tuple[float, Acquisition]] = {}
        self._lock = Lock()

    def get(self, key: RoundKey, *, force: bool = False) -> Acquisition:
        with self._lock:
            now = self.clock()
            previous = self._entries.get(key)
            if previous:
                previous_time, old = previous
                expiry = self.ttl if old.usable_for_scores else self.error_ttl
                if now - previous_time < (self.min_refresh if force else expiry):
                    return old
            attempt = datetime.now(timezone.utc)
            try:
                page = self.fetcher(key)
                if page.issues and previous and previous[1].page and not previous[1].page.issues:
                    result = replace(
                        previous[1],
                        attempted_at=attempt,
                        error="Acquisizione incompleta: " + " ".join(page.issues),
                    )
                else:
                    result = Acquisition(page, attempt)
            except FipError as exc:
                result = Acquisition(previous[1].page if previous else None, attempt, str(exc))
            self._entries[key] = (self.clock(), result)
            return result
