"""Sincronizzazione dello storico condiviso, separata dal calcolo delle priorità."""

import streamlit as st

from designazione.history_store import HistoryStoreError, configured_store, feedback_revision


@st.cache_resource
def get_history_store():
    return configured_store(st.secrets)


def sync_history(*, force=False):
    st.session_state.setdefault("history", {})
    st.session_state.setdefault("history_confirmed", set())
    try:
        store = get_history_store()
        if store is None:
            st.session_state["history_store_status"] = "missing"
            return
        remote = store.load(force=force)
        local = st.session_state["history"]
        pending = {key: entry for key, entry in local.items() if key not in remote}
        st.session_state["history"] = {**pending, **remote}
        st.session_state["history_confirmed"] = set(remote)
        if pending:
            remote = store.add_new(pending)
            st.session_state["history"] = remote
            st.session_state["history_confirmed"] = set(remote)
        st.session_state["history_store_status"] = "connected"
        st.session_state.pop("history_store_error", None)
    except HistoryStoreError as exc:
        st.session_state["history_store_status"] = "error"
        st.session_state["history_store_error"] = str(exc)


def history_status():
    status = st.session_state.get("history_store_status", "missing")
    if status == "missing":
        st.sidebar.warning(
            "Archivio permanente non configurato. Le segnalazioni sono solo nella sessione corrente; esporta una copia per non perderle."
        )
    elif status == "error":
        st.sidebar.error(st.session_state["history_store_error"])
    else:
        st.sidebar.caption("Storico collegato all’archivio permanente privato.")
    pending = set(st.session_state["history"]) - st.session_state["history_confirmed"]
    if pending:
        st.sidebar.warning(
            f"{len(pending)} segnalazioni da salvare nell’archivio permanente. Non chiudere la sessione prima della conferma o scarica una copia JSON."
        )


def save_feedback(entry, original):
    store = get_history_store()
    if store is None:
        st.session_state["history"][entry.identity] = entry
        return
    remote = store.save_feedback(entry, feedback_revision(original))
    # Conserva eventuali segnalazioni locali ancora in attesa di invio.
    st.session_state["history"] = {**st.session_state["history"], **remote}
    st.session_state["history_confirmed"] = set(remote)
