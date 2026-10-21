"""Vista settimanale, storico automatico delle priorità e segnalazioni manuali."""

from dataclasses import asdict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from designazione.calendar import ALL_ROUNDS, CalendarIndex, select_window
from designazione.domain import GROUPS, RoundKey
from designazione.history import (
    ASSESSMENTS,
    SUPPORTS,
    add_selection,
    capture_selection,
    export_history,
    import_history,
    record_feedback,
    remember_signal,
)
from designazione.history_ui import save_feedback, sync_history
from designazione.scoring import ScoringSettings, assess_match
from designazione.team_ui import team_weights_panel

ROME = ZoneInfo("Europe/Rome")


def now_rome():
    return datetime.now(ROME)


@st.cache_resource
def get_calendar() -> CalendarIndex:
    return CalendarIndex()


def weekly_view(settings: ScoringSettings | None, weights_container) -> None:
    st.header("📅 Vista settimanale · gironi A e B")
    now = now_rome()
    dates = st.date_input("Periodo", value=(now.date(), now.date() + timedelta(days=6)))
    groups = st.multiselect(
        "Gironi da mostrare", list(GROUPS), default=list(GROUPS), format_func=lambda g: GROUPS[g]
    )
    order = st.selectbox("Ordina gare per", ["Priorità", "Data e ora"])
    only_signals = st.checkbox("Solo gialle, rosse e gare da verificare")
    st.caption(
        "Il calendario viene caricato solo con il pulsante. Cambiare filtri o pesi non "
        "avvia richieste FIP. Sono inclusi recuperi e spostamenti di tutti i turni."
    )
    st.caption(
        "Le segnalazioni gialle e rosse nel periodo vengono registrate automaticamente nello storico, "
        "per entrambi i gironi, con la motivazione originale. Lo stato del salvataggio è indicato nel menu laterale."
    )
    index = get_calendar()
    refreshed = st.button("Carica / aggiorna calendario A e B")
    if refreshed:
        with st.spinner("Lettura dei due calendari completi; può richiedere alcuni minuti…"):
            index.load(force=True)
        now = now_rome()
    snapshot = index.peek()
    acquisitions = {}
    if snapshot is not None:
        for group in GROUPS:
            candidates = [
                item
                for key in snapshot.entries
                if key.group_id == group
                and (item := snapshot.acquisition(key, now)) is not None
                and item.page is not None
                and item.page.ranking
            ]
            if candidates:
                acquisitions[group] = max(candidates, key=lambda item: item.page.fetched_at)
    with weights_container:
        team_weights_panel(acquisitions)
    if snapshot is None:
        st.info(
            "Carica il calendario per vedere le gare. La prima lettura comprende 44 turni e 2 classifiche."
        )
        return
    st.caption(
        f"Ultimo aggiornamento dell'indice: {snapshot.updated_at.astimezone(ROME):%d/%m/%Y %H:%M:%S %Z}"
    )
    problems = []
    for key in ALL_ROUNDS:
        item = snapshot.acquisition(key, now)
        if item is None or not item.usable_for_scores:
            detail = (
                item.error
                if item and item.error
                else (" · ".join(item.page.issues) if item and item.page else "Dati assenti")
            )
            problems.append(f"{GROUPS[key.group_id]} · {key.label}: {detail}")
    if problems:
        st.warning(
            f"{len(problems)} turni non aggiornati o non verificabili. L'elenco può essere incompleto; nessuna assenza di gare viene interpretata come conferma."
        )
        with st.expander("Dettagli copertura calendario"):
            for problem in problems:
                st.write(problem)
    if not isinstance(dates, (tuple, list)) or len(dates) != 2:
        st.info("Seleziona anche la data finale del periodo.")
        return
    window = select_window(snapshot, dates[0], dates[1], now.date())
    for issue in window.conflicts:
        st.warning(issue)
    if window.anomalies:
        with st.expander(
            f"Da verificare: {len(window.anomalies)} gare senza data o con data trascorsa e senza risultato"
        ):
            for match in window.anomalies:
                st.write(
                    f"{GROUPS[match.round.group_id]} · {match.match_id} · {match.home}–{match.away} · {match.day or 'Data assente'}"
                )
    if settings is None:
        st.warning("Correggi pesi e soglie per valutare e selezionare le gare.")
        return
    history = st.session_state["history"]
    evaluated = []
    for match in window.games:
        current = snapshot.acquisition(match.round, now)
        first = snapshot.acquisition(RoundKey(match.round.group_id, 1, match.round.number), now)
        notes = st.session_state["notes"].get(match.round.group_id, {})
        score = assess_match(match, current, notes, settings, first)
        history = remember_signal(history, match, current, notes, settings, first, now=now)
        if match.round.group_id not in groups:
            continue
        if only_signals and score.total is not None and score.total < settings.yellow:
            continue
        evaluated.append((match, current, first, score))
    st.session_state["history"] = history
    sync_history()
    history = st.session_state["history"]
    if order == "Priorità":
        evaluated.sort(
            key=lambda row: (
                row[3].total is not None,
                -(row[3].total or 0),
                row[0].day,
                row[0].time or "99:99",
            )
        )
    if not evaluated:
        st.info("Nessuna gara da preparare trovata nei dati disponibili con questi filtri.")
    rows = []
    for match, _, _, score in evaluated:
        color = (
            "Da verificare"
            if score.total is None
            else (
                "🔴 Rosso"
                if score.total >= settings.red
                else "🟡 Giallo"
                if score.total >= settings.yellow
                else "🟢 Verde"
            )
        )
        rows.append(
            {
                "Gara": match.match_id,
                "Girone": GROUPS[match.round.group_id],
                "Data": match.day.strftime("%d/%m/%Y"),
                "Ora": match.time or "Da verificare",
                "Casa": match.home,
                "Ospite": match.away,
                "Punteggio": score.total,
                "Priorità": color,
                "Indicazione": score.advice(settings),
                "Motivazione": score.blocked_reason
                or " · ".join(f"{label}: +{value:g}" for label, value in score.contributions),
                "Storico": (
                    "Salvata"
                    if f"{match.round.group_id}:{match.match_id}:Sistema"
                    in st.session_state["history_confirmed"]
                    else "Da salvare"
                    if f"{match.round.group_id}:{match.match_id}:Sistema" in history
                    else "Non segnalata"
                ),
            }
        )
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.subheader("Segnala una gara sfuggita al sistema")
    st.caption(
        "Per una gara già trascorsa, seleziona il suo periodo in alto. "
        "La segnalazione manuale non ricostruisce un punteggio storico che non era stato salvato."
    )
    options = {
        f"{m.round.group_id}:{m.match_id}:Manuale": m
        for m in window.reportable
        if m.round.group_id in groups
    }
    if not options:
        st.info("Nessuna gara disponibile per una segnalazione manuale nel periodo scelto.")
        return
    choice = st.selectbox(
        "Gara da segnalare manualmente",
        list(options),
        format_func=lambda key: (
            f"{GROUPS[options[key].round.group_id]} · {options[key].match_id} · "
            f"{options[key].home}–{options[key].away}"
        ),
    )
    match = options[choice]
    if choice in history or f"{match.round.group_id}:{match.match_id}:Sistema" in history:
        st.info("Gara già nello storico: aggiungi il riscontro nella sezione Storico.")
        return
    current = snapshot.acquisition(match.round, now)
    first = snapshot.acquisition(RoundKey(match.round.group_id, 1, match.round.number), now)
    with st.form(f"track_{choice}"):
        reason = st.text_area("Motivo della segnalazione manuale", max_chars=2000)
        if st.form_submit_button("Salva segnalazione manuale"):
            try:
                entry = capture_selection(
                    match,
                    current,
                    st.session_state["notes"].get(match.round.group_id, {}),
                    settings,
                    reason=reason,
                    first_leg=first,
                    now=now,
                )
                st.session_state["history"] = add_selection(history, entry)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["history_saved"] = True
                st.rerun()


def history_view() -> None:
    st.header("📚 Storico gare attenzionate")
    if st.button("Aggiorna storico condiviso"):
        sync_history(force=True)
    if st.session_state.get("history_store_status") == "connected":
        st.caption(
            "Le segnalazioni confermate sono conservate nell’archivio permanente e disponibili nelle nuove sessioni. La copia JSON è facoltativa."
        )
    else:
        st.warning(
            "Salvataggio permanente non attivo o non raggiungibile. Le nuove segnalazioni restano nella sessione corrente finché la sincronizzazione non riesce."
        )
    st.caption(
        "Per le segnalazioni del sistema vengono conservati il primo punteggio giallo/rosso, "
        "la motivazione, i pesi, le posizioni e le criticità di quel momento. Il riscontro non li modifica. "
        "Le gare sfuggite al sistema si aggiungono manualmente; questo campione non rappresenta tutte le gare. "
        "Considera anche il supporto effettivamente presente."
    )
    history = st.session_state["history"]
    st.download_button(
        "Scarica backup storico JSON",
        export_history(history),
        file_name="storico-gare-u15-lazio.json",
        mime="application/json",
    )
    with st.expander("Importa storico"):
        uploaded = st.file_uploader("Backup storico JSON", type=["json"], key="history_upload")
        if uploaded is not None:
            try:
                candidate = import_history(uploaded.getvalue())
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.caption(
                    f"Backup valido: {len(candidate)} segnalazioni. Aggiunge soltanto quelle assenti, conservando motivazioni e riscontri già registrati."
                )
                if st.button("Importa le segnalazioni mancanti"):
                    st.session_state["history"] = {**candidate, **history}
                    for key in list(st.session_state):
                        if key.startswith("feedback_"):
                            del st.session_state[key]
                    st.rerun()
    if not history:
        if st.session_state.get("history_store_status") == "error":
            st.info(
                "Lo storico condiviso non è consultabile al momento. Nessun dato remoto è stato cancellato."
            )
            return
        st.info(
            "Nessuna segnalazione registrata. Le priorità gialle e rosse vengono salvate quando consulti le gare; puoi anche aggiungere segnalazioni manuali."
        )
        return
    entries = sorted(history.values(), key=lambda e: e.selected_at, reverse=True)
    st.caption(
        f"{len(entries)} segnalazioni · {sum(e.feedback.assessment != 'Da valutare' for e in entries)} con riscontro registrato"
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Gara": e.match.match_id,
                    "Girone": GROUPS[e.match.round.group_id],
                    "Origine": e.origin,
                    "Salvataggio": "Confermato"
                    if e.identity in st.session_state["history_confirmed"]
                    else "Da salvare",
                    "Prima segnalazione": e.selected_at.astimezone(ROME).strftime("%d/%m/%Y %H:%M"),
                    "Data gara salvata": str(e.match.day or "Da verificare"),
                    "Casa": e.match.home,
                    "Ospite": e.match.away,
                    "Punteggio salvato": e.score.total,
                    "Indicazione salvata": e.score.advice(e.settings),
                    "Perché segnalata": e.reason,
                    "Supporto effettivo": e.feedback.support,
                    "Riscontro": e.feedback.assessment,
                }
                for e in entries
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )
    identity = st.selectbox(
        "Gara nello storico",
        [e.identity for e in entries],
        format_func=lambda key: (
            f"{history[key].origin} · {history[key].match.match_id} · {history[key].match.home}–{history[key].match.away}"
        ),
    )
    entry = history[identity]
    with st.expander("Valutazione originale e pesi salvati", expanded=True):
        st.caption(
            f"{entry.origin} · prima segnalazione: {entry.selected_at.astimezone(ROME):%d/%m/%Y %H:%M %Z} · dati FIP: {entry.source_at.astimezone(ROME):%d/%m/%Y %H:%M %Z}"
        )
        st.write(f"Posizioni casa/ospite: {entry.positions} · criticità: {entry.criticisms}")
        st.write(entry.reason)
        st.write(entry.score.blocked_reason or entry.score.advice(entry.settings))
        for label, value in entry.score.contributions:
            st.write(f"{label}: +{value:g}")
        if entry.score.explanation:
            st.write(entry.score.explanation)
        for issue in entry.source_issues:
            st.warning(issue)
        st.json(asdict(entry.settings), expanded=False)
    st.subheader("Riscontro dopo la gara")
    future = entry.match.day is not None and entry.match.day > now_rome().date()
    if future:
        st.info("Il riscontro si compila dalla data della gara salvata nello storico.")
    with st.form(f"feedback_form_{identity}"):
        support = st.selectbox(
            "Supporto effettivamente presente",
            SUPPORTS,
            index=SUPPORTS.index(entry.feedback.support),
            key=f"feedback_support_{identity}",
        )
        assessment = st.selectbox(
            "Valutazione della priorità iniziale",
            ASSESSMENTS,
            index=ASSESSMENTS.index(entry.feedback.assessment),
            key=f"feedback_assessment_{identity}",
        )
        note = st.text_area(
            "Osservazione dopo la gara",
            value=entry.feedback.note,
            max_chars=2000,
            key=f"feedback_note_{identity}",
        )
        if st.form_submit_button("Salva riscontro", disabled=future):
            updated = record_feedback(entry, support, assessment, note)
            try:
                export_history({identity: updated})
                save_feedback(updated, entry)
            except ValueError as exc:
                st.error(str(exc))
            else:
                st.session_state["history_saved"] = True
                st.rerun()
