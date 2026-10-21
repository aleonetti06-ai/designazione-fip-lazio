"""Interfaccia Streamlit italiana; dominio, fonte e backup sono moduli testabili."""

import hmac
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from designazione.domain import COMPETITION, GROUPS, Acquisition, RoundKey
from designazione.fip import SourceCache, source_url
from designazione.history import remember_signal
from designazione.history_ui import history_status, sync_history
from designazione.scoring import ScoringSettings, assess_match
from designazione.storage import export_notes, import_notes
from designazione.team_ui import team_weights_panel
from designazione.views import history_view, now_rome, weekly_view

ROME = ZoneInfo("Europe/Rome")


@st.cache_resource
def get_source() -> SourceCache:
    # Contiene solo dati pubblici FIP. Le note restano separate per sessione.
    return SourceCache()


def check_password() -> bool:
    try:
        expected = st.secrets.get("app_password", "")
    except FileNotFoundError:
        expected = ""
    if not isinstance(expected, str) or not expected.strip():
        st.error(
            "Accesso non configurato. Il proprietario deve impostare app_password "
            "nelle impostazioni private di Streamlit."
        )
        return False
    if st.session_state.get("authenticated", False):
        return True
    st.title("🏀 Accesso riservato Designatore CIA")
    with st.form("login"):
        entered = st.text_input("Password", type="password", key="login_password")
        submitted = st.form_submit_button("Accedi")
    if submitted:
        if hmac.compare_digest(entered.encode("utf-8"), expected.encode("utf-8")):
            st.session_state["authenticated"] = True
            del st.session_state["login_password"]
            st.rerun()
        else:
            st.error("Password errata.")
    return False


def settings_panel() -> ScoringSettings | None:
    with st.sidebar.expander("⚙️ Pesi e soglie", expanded=False):
        st.caption("Regole originali mantenute. Il punteggio è un supporto alla decisione.")
        top = st.slider("Scontro al vertice (1ª–4ª)", 1.0, 8.0, 5.0, step=0.5)
        playoff = st.slider("Zona taglio playoff (6ª–10ª)", 1.0, 5.0, 2.5, step=0.5)
        nearby = st.slider("Posizioni distanti al massimo 2", 1.0, 5.0, 3.5, step=0.5)
        red = st.slider("Soglia formatore al tavolo", 6.0, 10.0, 8.0, step=0.5)
        yellow = st.slider("Soglia tutor in campo", 4.0, 7.9, 6.0, step=0.1)
        enabled = st.checkbox("Considera il ritorno dopo andata equilibrata", value=False)
        st.caption(
            "Criterio aggiuntivo provvisorio: disattivato, peso iniziale 0. "
            "Scarto massimo proposto 5; parametri da validare con Andrea."
        )
        margin = st.number_input(
            "Scarto massimo andata (incluso)",
            min_value=0,
            max_value=100,
            value=5,
            step=1,
            disabled=not enabled,
        )
        bonus = st.slider(
            "Peso aggiuntivo ritorno (provvisorio)", 0.0, 5.0, 0.0, step=0.5, disabled=not enabled
        )
    try:
        return ScoringSettings(top, playoff, nearby, red, yellow, enabled, int(margin), bonus)
    except ValueError as exc:
        st.sidebar.error(str(exc))
        return None


def transfer_panel() -> None:
    with st.sidebar.expander("📁 Esporta / importa note", expanded=False):
        st.warning(
            "Le note sono solo in questa sessione. Scarica il backup per conservarle. "
            "Non sono condivise automaticamente con altri designatori."
        )
        st.download_button(
            "Scarica backup JSON",
            export_notes(st.session_state["notes"]),
            file_name="criticita-u15-lazio.json",
            mime="application/json",
        )
        uploaded = st.file_uploader("Carica un backup JSON", type=["json"])
        if uploaded is not None:
            try:
                imported = import_notes(uploaded.getvalue())
            except ValueError as exc:
                st.error(str(exc))
            else:
                count = sum(len(teams) for teams in imported.values())
                st.caption(
                    f"Backup valido: {count} voci. L'importazione sostituisce le note correnti."
                )
                if st.button("Importa e sostituisci le note della sessione"):
                    st.session_state["notes"] = imported
                    for key in list(st.session_state):
                        if key.startswith(("critic_points_", "critic_note_")):
                            del st.session_state[key]
                    st.rerun()


def acquisition_status(acquisition: Acquisition, key: RoundKey, label: str = "Dati FIP") -> None:
    st.link_button(f"Apri fonte · {label}", source_url(key))
    st.caption(
        f"Ultimo tentativo: {acquisition.attempted_at.astimezone(ROME):%d/%m/%Y %H:%M:%S %Z}"
    )
    if acquisition.error:
        st.error(acquisition.error)
    if acquisition.page:
        page = acquisition.page
        st.caption(f"Fonte acquisizione: {page.source_label}")
        if page.ranking_url:
            st.link_button("Dati classifica FIP (JSON)", page.ranking_url)
        freshness_label = (
            "Ultima lettura incompleta" if page.issues else "Ultima acquisizione valida"
        )
        st.caption(
            f"{freshness_label} · {label}: {page.fetched_at.astimezone(ROME):%d/%m/%Y %H:%M:%S %Z}"
        )
        if acquisition.error:
            st.warning(
                "Mostro dati di una precedente acquisizione. "
                "Le raccomandazioni automatiche sono sospese."
            )
        for issue in page.issues:
            st.warning(issue)
    else:
        st.warning("Nessun dato valido disponibile. Classifica e punteggi non vengono inventati.")


def render_matches(
    acquisition: Acquisition, settings: ScoringSettings | None, first_leg: Acquisition | None
) -> None:
    page = acquisition.page
    if page is None:
        return
    st.subheader(page.round.label)
    st.caption(
        "Risultati, stato gara e omologazione sono distinti. "
        "L'omologazione viene indicata solo se lo stato FIP è «omologata»."
    )
    st.caption(
        "Le priorità gialle e rosse vengono aggiunte automaticamente allo storico. "
        "Lo stato del salvataggio è indicato nel menu laterale."
    )
    for match in page.matches:
        day = match.day.strftime("%d/%m/%Y") if match.day else "Data non disponibile"
        st.markdown(f"**{match.home} — {match.away}**")
        st.caption(f"Gara {match.match_id} · {day} · {match.time or 'Ora non disponibile'}")
        st.caption(
            f"Stato FIP: {match.source_status or 'Non esposto'} · {match.homologation_label}"
        )
        if match.has_result:
            st.info(
                f"Risultato {match.score_origin or 'pubblicato'}: {match.result_label}. "
                f"{match.homologation_label}."
            )
        else:
            st.write(match.result_label)
            if settings is None:
                st.warning("Correggere pesi e soglie prima della valutazione.")
                continue
            if match.day is None or match.day < now_rome().date():
                st.warning("Da verificare: data assente o trascorsa senza risultato pubblicato.")
                continue
            score = assess_match(
                match,
                acquisition,
                st.session_state["notes"].get(page.round.group_id, {}),
                settings,
                first_leg,
            )
            st.session_state["history"] = remember_signal(
                st.session_state["history"],
                match,
                acquisition,
                st.session_state["notes"].get(page.round.group_id, {}),
                settings,
                first_leg,
                now=now_rome(),
            )
            if score.total is None:
                st.warning(f"Da verificare · {score.blocked_reason}")
            else:
                message = f"SCORE {score.total:.1f} / 10 · {score.advice(settings)}"
                if score.total >= settings.red:
                    st.error("🔴 " + message)
                elif score.total >= settings.yellow:
                    st.warning("🟡 " + message)
                else:
                    st.success("🟢 " + message)
                st.caption(
                    " · ".join(f"{label}: +{points:g}" for label, points in score.contributions)
                    + " · Tetto: 10"
                )
                if score.explanation:
                    st.caption(score.explanation)
        for name in (match.home, match.away):
            criticism = st.session_state["notes"].get(page.round.group_id, {}).get(name)
            if criticism and criticism.note:
                st.text(f"Nota {name}: {criticism.note}")


def main() -> None:
    st.set_page_config(page_title="Designatore CIA · U15 Gold Lazio", page_icon="🏀", layout="wide")
    if not check_password():
        st.stop()
    if "notes" not in st.session_state:
        st.session_state["notes"] = {}
    if "history" not in st.session_state:
        st.session_state["history"] = {}
    st.sidebar.title("📌 Designazione CIA")
    if st.session_state.get("page_view") == "🔍 Verifica dati FIP":
        st.session_state["page_view"] = "🏀 Dashboard designazione"
    view = st.sidebar.radio(
        "Pagina",
        [
            "📅 Vista settimanale",
            "🏀 Dashboard designazione",
            "📚 Storico gare attenzionate",
        ],
        key="page_view",
    )
    settings = settings_panel()
    weights_container = st.sidebar.container()
    transfer_panel()
    if st.sidebar.button("Esci"):
        st.session_state["authenticated"] = False
        st.rerun()
    sync_history()
    if st.session_state.pop("history_saved", False):
        st.info("Storico aggiornato. Verifica lo stato del salvataggio nel menu laterale.")
    if view == "📅 Vista settimanale":
        weekly_view(settings, weights_container)
        history_status()
        return
    if view == "📚 Storico gare attenzionate":
        with weights_container:
            team_weights_panel({})
        history_view()
        history_status()
        return
    group = st.sidebar.selectbox("Girone", list(GROUPS), format_func=lambda g: f"{GROUPS[g]} ({g})")
    leg = st.sidebar.selectbox("Fase", [1, 0], format_func=lambda v: "Andata" if v else "Ritorno")
    number = st.sidebar.selectbox("Giornata", list(range(1, COMPETITION.rounds_per_leg + 1)))
    key = RoundKey(group, leg, number)
    force = st.sidebar.button("Aggiorna dati FIP")
    st.sidebar.caption(
        "Cache 5 minuti; dopo un errore 60 secondi. "
        "Il pulsante rispetta un intervallo minimo di 30 secondi per pagina."
    )
    with st.spinner("Acquisizione FIP della giornata selezionata…"):
        acquisition = get_source().get(key, force=force)
    with weights_container:
        team_weights_panel({group: acquisition}, group)
    st.title("🏀 Designazione CIA · U15 Gold Lazio")
    st.caption(
        "Supporto ai designatori. La scelta della coppia arbitrale resta una valutazione umana."
    )
    acquisition_status(acquisition, key)
    page = acquisition.page
    if page is None:
        history_status()
        return
    recommendations, verification = st.tabs(["Gare e priorità", "Dati FIP: classifica e risultati"])
    with verification:
        st.subheader("Classifica pubblicata da FIP")
        st.dataframe(
            pd.DataFrame(
                [
                    {"Posizione": r.position, "Squadra": r.team, "Punti": r.points}
                    for r in page.ranking
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
        st.subheader("Gare della giornata selezionata")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "ID gara": m.match_id,
                        "Casa": m.home,
                        "Ospite": m.away,
                        "Data": m.day.strftime("%d/%m/%Y") if m.day else "Non disponibile",
                        "Ora": m.time or "Non disponibile",
                        "Risultato": m.result_label,
                        "Stato": "Con risultato pubblicato"
                        if m.has_result
                        else "Senza risultato pubblicato",
                        "Stato FIP": m.source_status or "Non esposto dalla fonte",
                        "Origine punteggio": m.score_origin or "Non disponibile",
                        "Omologazione": m.homologation_label,
                    }
                    for m in page.matches
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
    with recommendations:
        first_leg = None
        if (
            settings
            and settings.return_enabled
            and settings.return_weight > 0
            and leg == 0
            and acquisition.usable_for_scores
            and any(not m.has_result for m in page.matches)
        ):
            # Un solo turno aggiuntivo, mai una scansione automatica di tutto il campionato.
            first_key = RoundKey(group, 1, number)
            with st.spinner("Verifica dell'andata corrispondente…"):
                first_leg = get_source().get(first_key, force=force)
            with st.expander("Fonte per il criterio ritorno"):
                acquisition_status(first_leg, first_key, "Andata")
                st.caption(
                    "Confronto per nomi esatti e casa/ospite invertite. "
                    "Se l'abbinamento non esiste in questo turno, il criterio resta non valutabile."
                )
        render_matches(acquisition, settings, first_leg)
    sync_history()
    history_status()


if __name__ == "__main__":
    main()
