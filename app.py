import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

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
# 2. ANAGRAFICA SQUADRE UFFICIALI E DATI CAMPIONATO
# ---------------------------------------------------------
if "criticita_societa" not in st.session_state:
    st.session_state["criticita_societa"] = {}

# Classifica e punti simulati/aggiornabili
DATI_GIRONE_A = [
    {"Squadra": "BASKET GUIDONIA", "Punti": 4, "G": 2, "V": 2, "P": 0},
    {"Squadra": "OLIMPIA ROMA", "Punti": 4, "G": 2, "V": 2, "P": 0},
    {"Squadra": "SUPERNOVA FIUMICINO", "Punti": 2, "G": 2, "V": 1, "P": 1},
    {"Squadra": "BASKET ROMA", "Punti": 2, "G": 2, "V": 1, "P": 1},
    {"Squadra": "SCUOLA BASKET ROMA", "Punti": 2, "G": 2, "V": 1, "P": 1},
    {"Squadra": "STELLAEBK", "Punti": 2, "G": 2, "V": 1, "P": 1},
    {"Squadra": "DON BOSCO NUOVO SALARIO", "Punti": 2, "G": 2, "V": 1, "P": 1},
    {"Squadra": "WILLIE BASKET RIETI", "Punti": 0, "G": 2, "V": 0, "P": 2},
    {"Squadra": "VIS AURELIA BK", "Punti": 0, "G": 2, "V": 0, "P": 2},
    {"Squadra": "BRACCIANO BASKET", "Punti": 0, "G": 2, "V": 0, "P": 2},
]

DATI_GIRONE_B = [
    {"Squadra": "VIRTUS ROMA BASKET", "Punti": 4, "G": 2, "V": 2, "P": 0},
    {"Squadra": "SMIT ROMA", "Punti": 4, "G": 2, "V": 2, "P": 0},
    {"Squadra": "TIBER BASKET", "Punti": 2, "G": 2, "V": 1, "P": 1},
    {"Squadra": "ALFA BASKET", "Punti": 2, "G": 2, "V": 1, "P": 1},
    {"Squadra": "SAN PAOLO OSTIENSE", "Punti": 2, "G": 2, "V": 1, "P": 1},
    {"Squadra": "ANZIO BASKET", "Punti": 2, "G": 2, "V": 1, "P": 1},
    {"Squadra": "BASKET CASSINO", "Punti": 0, "G": 2, "V": 0, "P": 2},
    {"Squadra": "LATINA BASKET", "Punti": 0, "G": 2, "V": 0, "P": 2},
    {"Squadra": "PALESTRINA", "Punti": 0, "G": 2, "V": 0, "P": 2},
    {"Squadra": "FORTITUDO ANAGNI", "Punti": 0, "G": 2, "V": 0, "P": 2},
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
st.sidebar.header("⚠️ Aggiungi Criticità Società")
squadre_totali = [d["Squadra"] for d in DATI_GIRONE_A + DATI_GIRONE_B]
nuova_societa = st.sidebar.selectbox("Seleziona Squadra:", sorted(list(set(squadre_totali))))
livello_crit = st.sidebar.selectbox("Livello Criticità", ["Normale (+0)", "Media (+2.0)", "Alta (+4.0)"])
nota_crit = st.sidebar.text_input("Nota (es. Pubblico caldo):")

if st.sidebar.button("Salva Criticità"):
    valore = 0.0
    if "Media" in livello_crit: valore = 2.0
    elif "Alta" in livello_crit: valore = 4.0
    st.session_state["criticita_societa"][nuova_societa.upper()] = {"punti": valore, "nota": nota_crit}
    st.sidebar.success(f"Salvata criticità per {nuova_societa}")

# ---------------------------------------------------------
# 4. DASHBOARD E VALUTAZIONE DOPPIA GIORNATA
# ---------------------------------------------------------
st.title("🏀 Dashboard Designazione CIA - U15 Gold Lazio")
st.markdown("Valutazione criticità gare con **classifica a punti e date degli incontri**.")

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

def render_schedule(accoppiamenti, classifica, data_base_str):
    base_date = datetime.strptime(data_base_str, "%d/%m/%Y")
    
    for idx, (casa, fuori) in enumerate(accoppiamenti):
        p_casa = classifica[casa]["Posizione"]
        p_fuori = classifica[fuori]["Posizione"]
        pt_casa = classifica[casa]["Punti"]
        pt_fuori = classifica[fuori]["Punti"]
        
        # Calcolo data/ora programmata della partita
        data_gara = (base_date + timedelta(days=(idx % 2))).strftime("%d/%m/%Y")
        ora_gara = "16:00" if idx % 2 == 0 else "18:30"
        
        sc, dett = calcola_score(p_casa, p_fuori, casa, fuori)
        
        header_text = f"📅 **{data_gara} ore {ora_gara}** | **{casa} ({p_casa}ª - {pt_casa} pt)** vs **{fuori} ({p_fuori}ª - {pt_fuori} pt)**"
        
        if sc >= soglia_rosso:
            st.error(f"🔴 **SCORE {sc:.1f} / 10** — {header_text}\n\n"
                     f"👉 **AZIONI CONSIGLIATE:** FORMATORE AL TAVOLO\n\n*Motivazione:* {dett if dett else 'Scontro ad alta priorità'}")
        elif sc >= soglia_giallo:
            st.warning(f"🟡 **SCORE {sc:.1f} / 10** — {header_text}\n\n"
                       f"👉 **AZIONI CONSIGLIATE:** TUTOR IN CAMPO CON IL MINIARBITRO\n\n*Motivazione:* {dett if dett else 'Gara equilibrata'}")
        else:
            st.success(f"🟢 **SCORE {sc:.1f} / 10** — {header_text}\n\n"
                       f"👉 **AZIONI CONSIGLIATE:** MINIARBITRI IN AUTONOMIA\n\n*Motivazione:* {dett if dett else 'Partita ordinaria'}")

def render_girone(dati_girone):
    # Creazione DataFrame Classifica
    df_class = pd.DataFrame(dati_girone)
    df_class["Posizione"] = range(1, len(df_class) + 1)
    
    # Riordino colonne
    df_class = df_class[["Posizione", "Squadra", "Punti", "G", "V", "P"]]

    st.subheader("Classifica Ufficiale")
    st.dataframe(df_class, use_container_width=True, hide_index=True)

    # Dizionario rapido per posizioni e punti
    classifica_dict = {}
    for _, row in df_class.iterrows():
        classifica_dict[row["Squadra"]] = {"Posizione": row["Posizione"], "Punti": row["Punti"]}

    squadre_list = list(classifica_dict.keys())

    # Generazione accoppiamenti
    turno_attuale = [(squadre_list[i], squadre_list[i+1]) for i in range(0, len(squadre_list)-1, 2)]
    turno_successivo = [(squadre_list[i], squadre_list[(i+3) % len(squadre_list)]) for i in range(0, len(squadre_list))]
    turno_successivo = turno_successivo[:5]

    tab_t1, tab_t2 = st.tabs(["📅 Prossimo Turno (Settimana In Corso)", "🔮 Turno Successivo (Anticipo Designazioni)"])
    
    with tab_t1:
        st.subheader("Gare della Settimana")
        render_schedule(turno_attuale, classifica_dict, "24/10/2026")
        
    with tab_t2:
        st.subheader("Anteprima Gare Giornata Dopo")
        render_schedule(turno_successivo, classifica_dict, "31/10/2026")

with tab1:
    render_girone(DATI_GIRONE_A)

with tab2:
    render_girone(DATI_GIRONE_B)
