import streamlit as st
import pandas as pd

# ---------------------------------------------------------
# 1. AUTENTICAZIONE / ACCESSO PRIVATO
# ---------------------------------------------------------
st.set_page_config(page_title="Designatore CIA - U15 Gold Lazio", layout="wide", page_icon="🏀")

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.title("🏀 Accesso Riservato Designatore CIA")
        password = st.text_input("Inserisci la password per accedere:", type="password")
        if st.button("Accedi"):
            if password == "basket2026":  # Tua password
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Password errata.")
        return False
    return True

if not check_password():
    st.stop()

# ---------------------------------------------------------
# 2. INIZIALIZZAZIONE DATI REALI (GIRONE A - 11 SQUADRE)
# ---------------------------------------------------------
if "criticita_societa" not in st.session_state:
    st.session_state["criticita_societa"] = {}

# Classifica Reale Iniziale (Tutte a 0 punti)
SQUADRE_A_REALI = [
    "BASKET GUIDONIA",
    "OLIMPIA ROMA",
    "SUPERNOVA FIUMICINO",
    "BASKET ROMA",
    "SCUOLA BASKET ROMA",
    "STELLAEBK",
    "DON BOSCO NUOVO SALARIO",
    "WILLIE BASKET RIETI",
    "VIS AURELIA BK",
    "BRACCIANO BASKET",
    "ESQUILINO BASKETBALL"
]

if "classifica_a" not in st.session_state:
    st.session_state["classifica_a"] = {sq: {"Punti": 0, "G": 1, "V": 0, "P": 0} for sq in SQUADRE_A_REALI}

# Calendario Reale Turno 2 (24-25 Ottobre 2026)
GARE_GIRONE_A_TURNO_2 = [
    {"casa": "SUPERNOVA FIUMICINO", "fuori": "BASKET GUIDONIA", "data": "24/10/2026", "ora": "15:00"},
    {"casa": "ESQUILINO BASKETBALL", "fuori": "BASKET ROMA", "data": "25/10/2026", "ora": "18:00"},
    {"casa": "BRACCIANO BASKET", "fuori": "OLIMPIA ROMA", "data": "24/10/2026", "ora": "16:30"},
    {"casa": "DON BOSCO NUOVO SALARIO", "fuori": "SCUOLA BASKET ROMA", "data": "24/10/2026", "ora": "18:00"},
    {"casa": "WILLIE BASKET RIETI", "fuori": "STELLAEBK", "data": "25/10/2026", "ora": "11:00"},
]

# Calendario Reale Turno 3 (31/10 - 01/11 2026)
GARE_GIRONE_A_TURNO_3 = [
    {"casa": "BASKET GUIDONIA", "fuori": "ESQUILINO BASKETBALL", "data": "31/10/2026", "ora": "16:00"},
    {"casa": "BASKET ROMA", "fuori": "BRACCIANO BASKET", "data": "31/10/2026", "ora": "18:30"},
    {"casa": "OLIMPIA ROMA", "fuori": "DON BOSCO NUOVO SALARIO", "data": "01/11/2026", "ora": "11:30"},
    {"casa": "SCUOLA BASKET ROMA", "fuori": "WILLIE BASKET RIETI", "data": "01/11/2026", "ora": "16:00"},
    {"casa": "STELLAEBK", "fuori": "VIS AURELIA BK", "data": "01/11/2026", "ora": "18:00"},
]

# ---------------------------------------------------------
# 3. PANNELLO IMPOSTAZIONI (SIDEBAR)
# ---------------------------------------------------------
st.sidebar.header("⚙️ Impostazioni Algoritmo")

weight_vertice = st.sidebar.slider("Peso Scontro al Vertice (1ª-4ª)", 1.0, 8.0, 5.0)
weight_playoff = st.sidebar.slider("Peso Zona Taglio Playoff (6ª-10ª)", 1.0, 5.0, 2.5)
weight_pari = st.sidebar.slider("Peso Scontro Equilibrato (Δ pos ≤ 2)", 1.0, 5.0, 3.5)

st.sidebar.markdown("---")
st.sidebar.header("🔴 Soglie Designazione")
soglia_rosso = st.sidebar.slider("Soglia Formatore al Tavolo (Rosso)", 6.0, 10.0, 8.0)
soglia_giallo = st.sidebar.slider("Soglia Tutor in Campo (Giallo)", 4.0, 7.9, 6.0)

st.sidebar.markdown("---")
st.sidebar.header("📝 Aggiorna Punti Squadra")
sq_modifica = st.sidebar.selectbox("Squadra da Aggiornare:", SQUADRE_A_REALI)
punti_nuovi = st.sidebar.number_input("Punti in Classifica:", min_value=0, max_value=40, value=st.session_state["classifica_a"][sq_modifica]["Punti"])
if st.sidebar.button("Aggiorna Classifica"):
    st.session_state["classifica_a"][sq_modifica]["Punti"] = punti_nuovi
    st.sidebar.success(f"Aggiornati punti per {sq_modifica}")

st.sidebar.markdown("---")
st.sidebar.header("⚠️ Aggiungi Criticità Società")
nuova_societa = st.sidebar.selectbox("Seleziona Squadra per Criticità:", SQUADRE_A_REALI)
livello_crit = st.sidebar.selectbox("Livello Criticità", ["Normale (+0)", "Media (+2.0)", "Alta (+4.0)"])
nota_crit = st.sidebar.text_input("Nota (es. Pubblico caldo):")

if st.sidebar.button("Salva Criticità"):
    valore = 0.0
    if "Media" in livello_crit: valore = 2.0
    elif "Alta" in livello_crit: valore = 4.0
    st.session_state["criticita_societa"][nuova_societa.upper()] = {"punti": valore, "nota": nota_crit}
    st.sidebar.success(f"Salvata criticità per {nuova_societa}")

# ---------------------------------------------------------
# 4. DASHBOARD E VALUTAZIONE
# ---------------------------------------------------------
st.title("🏀 Dashboard Designazione CIA - U15 Gold Lazio")
st.markdown("Analisi e valutazione criticità gare basata su dati e calendari reali.")

tab1, tab2 = st.tabs(["📌 Girone A (85582)", "📌 Girone B (85583)"])

def calcola_score(pos_casa, pos_fuori, casa_name, fuori_name):
    score = 1.0
    dettagli = []
    
    if pos_casa <= 4 and pos_fuori <= 4:
        score += weight_vertice
        dettagli.append("Sfida al vertice (1ª-4ª pos)")
        
    if (6 <= pos_casa <= 10) and (6 <= pos_fuori <= 10):
        score += weight_playoff
        dettagli.append("Scontro diretto Zona Taglio Playoff (6ª-10ª pos)")
        
    if abs(pos_casa - pos_fuori) <= 2:
        score += weight_pari
        dettagli.append("Scontro equilibrato in classifica")
        
    crit_casa = st.session_state["criticita_societa"].get(casa_name.upper(), {"punti": 0, "nota": ""})
    crit_fuori = st.session_state["criticita_societa"].get(fuori_name.upper(), {"punti": 0, "nota": ""})
    
    extra = crit_casa["punti"] + crit_fuori["punti"]
    if extra > 0:
        score += extra
        note_str = f"{crit_casa['nota']} {crit_fuori['nota']}".strip()
        dettagli.append(f"Criticità societaria: {note_str}")
        
    return min(score, 10.0), ", ".join(dettagli)

def render_schedule(gare_list, posizioni_dict):
    for gara in gare_list:
        casa, fuori = gara["casa"], gara["fuori"]
        data_g, ora_g = gara["data"], gara["ora"]
        
        p_casa = posizioni_dict.get(casa, 5)
        p_fuori = posizioni_dict.get(fuori, 5)
        pt_casa = st.session_state["classifica_a"][casa]["Punti"]
        pt_fuori = st.session_state["classifica_a"][fuori]["Punti"]
        
        sc, dett = calcola_score(p_casa, p_fuori, casa, fuori)
        
        header_text = f"📅 **{data_g} ore {ora_g}** | **{casa} ({p_casa}ª - {pt_casa} pt)** vs **{fuori} ({p_fuori}ª - {pt_fuori} pt)**"
        
        if sc >= soglia_rosso:
            st.error(f"🔴 **SCORE {sc:.1f} / 10** — {header_text}\n\n"
                     f"👉 **AZIONI CONSIGLIATE:** FORMATORE AL TAVOLO\n\n*Motivazione:* {dett if dett else 'Scontro ad alta priorità'}")
        elif sc >= soglia_giallo:
            st.warning(f"🟡 **SCORE {sc:.1f} / 10** — {header_text}\n\n"
                       f"👉 **AZIONI CONSIGLIATE:** TUTOR IN CAMPO CON IL MINIARBITRO\n\n*Motivazione:* {dett if dett else 'Gara equilibrata'}")
        else:
            st.success(f"🟢 **SCORE {sc:.1f} / 10** — {header_text}\n\n"
                       f"👉 **AZIONI CONSIGLIATE:** MINIARBITRI IN AUTONOMIA\n\n*Motivazione:* {dett if dett else 'Partita ordinaria'}")

with tab1:
    # Costruzione Classifica Reale
    df_data = []
    for sq in SQUADRE_A_REALI:
        info = st.session_state["classifica_a"][sq]
        df_data.append({"Squadra": sq, "Punti": info["Punti"], "G": info["G"], "V": info["V"], "P": info["P"]})
        
    df_class = pd.DataFrame(df_data)
    # Ordina per Punti e poi per nome
    df_class = df_class.sort_values(by=["Punti", "Squadra"], ascending=[False, True]).reset_index(drop=True)
    df_class["Posizione"] = range(1, len(df_class) + 1)
    df_class = df_class[["Posizione", "Squadra", "Punti", "G", "V", "P"]]

    st.subheader("Classifica Ufficiale (Girone A)")
    st.dataframe(df_class, use_container_width=True, hide_index=True)

    posizioni_dict = {row["Squadra"]: row["Posizione"] for _, row in df_class.iterrows()}

    tab_t1, tab_t2 = st.tabs(["📅 Prossimo Turno (24-25 Ottobre)", "🔮 Turno Successivo (31 Ott-01 Nov)"])
    
    with tab_t1:
        st.subheader("Gare della Settimana")
        render_schedule(GARE_GIRONE_A_TURNO_2, posizioni_dict)
        
    with tab_t2:
        st.subheader("Anteprima Gare Giornata Dopo")
        render_schedule(GARE_GIRONE_A_TURNO_3, posizioni_dict)

with tab2:
    st.info("I Dati e Calendario del Girone B verranno caricati con la stessa struttura non appena disponibili.")
