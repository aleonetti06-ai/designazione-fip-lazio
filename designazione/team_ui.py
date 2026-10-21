"""Modifica dei pesi societari sui dati già acquisiti, senza richieste FIP."""

import streamlit as st

from designazione.domain import GROUPS, Acquisition, Criticism
from designazione.storage import export_notes


def team_weights_panel(acquisitions: dict[str, Acquisition], group_id: str | None = None) -> None:
    known = st.session_state.setdefault("team_sources", {})
    known.update(acquisitions)
    with st.expander("⚖️ Pesi squadre", expanded=False):
        st.caption(
            "Assegna la criticità di ciascuna squadra: normale +0, media +2, alta +4. "
            "I contributi delle due squadre si sommano al punteggio della gara, fino al tetto di 10."
        )
        if group_id is None:
            group_id = st.selectbox(
                "Girone per i pesi",
                list(GROUPS),
                format_func=lambda g: GROUPS[g],
                key="weights_group",
            )
        else:
            st.caption(f"Squadre del {GROUPS[group_id]}")
        acquisition = known.get(group_id)
        page = acquisition.page if acquisition else None
        if page is None or not page.ranking:
            st.info(
                "Carica il calendario nella Vista settimanale o apri la Dashboard "
                "sul girone scelto per impostare i pesi delle sue squadre."
            )
            return
        if not acquisition.usable_for_scores:
            st.warning(
                "Puoi modificare i pesi sulle squadre già acquisite. "
                "I pesi non rendono utilizzabili eventuali dati FIP incompleti o precedenti."
            )
        team = st.selectbox("Squadra", [r.team for r in page.ranking], key=f"note_team_{group_id}")
        notes = st.session_state["notes"].setdefault(group_id, {})
        item = notes.get(team, Criticism())
        suffix = f"{group_id}_{team}"
        with st.form(f"criticism_{suffix}"):
            points = st.selectbox(
                "Peso della squadra",
                [0, 2, 4],
                index=[0, 2, 4].index(item.points),
                format_func=lambda p: {0: "Normale (+0)", 2: "Media (+2)", 4: "Alta (+4)"}[p],
                key=f"critic_points_{suffix}",
            )
            note = st.text_area(
                "Nota", value=item.note, max_chars=2000, key=f"critic_note_{suffix}"
            )
            if st.form_submit_button("Applica peso e nota"):
                candidate = {
                    group: dict(items) for group, items in st.session_state["notes"].items()
                }
                candidate[group_id][team] = Criticism(float(points), note)
                try:
                    export_notes(candidate)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.session_state["notes"] = candidate
                    st.session_state["notes_saved"] = True
                    # Rigenera anche il backup dopo il salvataggio del modulo.
                    st.rerun()
        if st.session_state.pop("notes_saved", False):
            st.success("Peso e nota applicati alla sessione.")
        st.caption(
            "Pesi e note valgono nella vista settimanale e nella dashboard durante questa sessione. "
            "Per conservarli usa «Esporta / importa note» nel menu laterale. "
            "Le segnalazioni già nello storico mantengono la motivazione originale."
        )
        unknown = set(notes) - {r.team for r in page.ranking}
        if unknown:
            st.warning(
                f"{len(unknown)} note importate hanno nomi non presenti nella classifica "
                "corrente: restano nel backup ma non incidono sui punteggi."
            )
