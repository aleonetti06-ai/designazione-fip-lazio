import streamlit as st
import pandas as pd

# ---------------------------------------------------------
# 1. AUTENTICAZIONE E CONFIGURAZIONE
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
# 2. STRUTTURA DATI REALI SQUADRE (GIRONE A e B)
# ---------------------------------------------------------
if "criticita_societa" not in st.session_state:
    st.session_state["criticita_societa"] = {}

SQUADRE_GIRONE_A = [
    "BASKET GUIDONIA", "OLIMPIA ROMA", "SUPERNOVA FIUMICINO", "BASKET ROMA",
    "SCUOLA BASKET ROMA", "STELLAEBK", "DON BOSCO NUOVO SALARIO",
    "WILLIE BASKET RIETI", "VIS AURELIA BK", "BRACCIANO BASKET", "ESQUILINO BASKETBALL"
]

SQUADRE_GIRONE_B = [
    "VIRTUS ROMA BASKET", "SMIT ROMA", "TIBER BASKET", "ALFA BASKET",
    "SAN PAOLO OSTIENSE", "ANZIO BASKET", "BASKET CASSINO", "LATINA BASKET",
    "PALESTRINA", "FORTITUDO ANAGNI"
]

# Inizializzazione della classifica in sessione
if "classifica_data_a" not in st.session_state:
    st.session_state["classifica_data_a"] = {sq: {"Punti": 0, "Gare": 1, "Vinte": 0, "Perse": 1} for sq in SQUADRE_GIRONE_A}

if "classifica_data_b" not in st.session_state:
    st.session_state["classifica_data_b"] = {sq: {"Punti": 0, "Gare": 1, "Vinte": 0, "Perse": 1} for sq in SQUADRE_GIRONE_B}

# ---------------------------------------------------------
# 3. SIDEBAR - REGOLAZIONI, PUNTI E CRITICITÀ
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
st.sidebar.header("📝 Aggiorna Punti Classifica")
girone_sel = st.sidebar.radio("Seleziona Girone:", ["Girone A", "Girone B"])
squadre_opt = SQUADRE_GIRONE_A if girone_sel == "Girone A" else SQUADRE_GIRONE_B
sq_mod = st.sidebar.selectbox("Squadra:", squadre_opt)

pt_input = st.sidebar.number_input("Punti:", min_value=0, max_value=40, value=0)
v_input = st.sidebar.number_input("Vittorie:", min_value=0, max_value=20, value=0)
p_input = st.sidebar.number_input("Sconfitte:", min_value=0, max_value=20, value=0)

if st.sidebar.button("Aggiorna Squadra"):
    dict_target = st.session_state["classifica_data_a"] if girone_sel == "Girone A" else st.session_state["classifica_data_b"]
    dict_target[sq_mod]["Punti"] = pt_input
    dict_target[sq_mod]["Vinte"] = v_input
    dict_target[sq_mod]["Perse"] = p_input
    dict_target[sq_mod]["Gare"] = v_input + p_input
    st.sidebar.success(f"Aggiornata {sq_mod}!")

st.sidebar.markdown("---")
st.sidebar.header("⚠️ Criticità Manuali Società")
tutte_sq = sorted(list(set(SQUADRE_GIRONE_A + SQUADRE_GIRONE_B)))
nuova_societa = st.sidebar.selectbox("Seleziona Squadra per Criticità:", tutte_sq)
livello_crit = st.sidebar.selectbox("Livello Criticità", ["Normale (+0)", "Media (+2.0)", "Alta (+4.0)"])
nota_crit = st.sidebar.text_input("Nota (es. Pubblico caldo):")

if st.sidebar.button("Salva Criticità"):
    valore = 0.0
    if "Media" in livello_crit: valore = 2.0
    elif "Alta" in livello_crit: valore = 4.0
    st.session_state["criticita_societa"][nuova_societa.upper()] = {"punti": valore, "nota": nota_crit}
    st.sidebar.success(f"Criticità salvata per {nuova_societa}")

# ---------------------------------------------------------
# 4. MAIN DASHBOARD & CALCOLO SCORE
# ---------------------------------------------------------
st.title("🏀 Dashboard Designazione CIA - U15 Gold Lazio")
st.markdown("Analisi gare e valutazione criticità miniarbitri.")

tab1, tab2 = st.tabs(["📌 Girone A (85582)", "📌 Girone B (85583)"])

def calcola_score(pos_casa, pos_fuori, casa_name, fuori_name):
    score = 1.0
    dettagli = []
    
    if pos_casa <= 4 and pos_fuori <= 4:
        score += weight_vertice
        dettagli.append("Sfida al vertice")
        
    if (6 <= pos_casa <= 10) and (6 <= pos_fuori <= 10):
        score += weight_playoff
        dettagli.append("Scontro Zona Taglio Playoff")
        
    if abs(pos_casa - pos_fuori) <= 2:
        score += weight_pari
        dettagli.append("Scontro equilibrato in classifica")
        
    crit_casa = st.session_state["criticita_societa"].get(casa_name.upper(), {"punti": 0, "nota": ""})
    crit_fuori = st.session_state["criticita_societa"].get(fuori_name.upper(), {"punti": 0, "nota": ""})
    
    extra = crit_casa["punti"] + crit_fuori["punti"]
    if extra > 0:
        score += extra
        note_str = f"{crit_casa['nota']} {crit_fuori['nota']}".strip()
        dettagli.append(f"Note società: {note_str}")
        
    return min(score, 10.0), ", ".join(dettagli)

def render_girone_ui(key_dict, squadre_lista):
    # Costruzione DataFrame Classifica
    data = []
    for sq, info in st.session_state[key_dict].items():
        data.append({"Squadra": sq, "Punti": info["Punti"], "G": info["Gare"], "V": info["Vinte"], "P": info["Perse"]})
        
    df = pd.DataFrame(data)
    df = df.sort_values(by=["Punti", "V", "Squadra"], ascending=[False, False, True]).reset_index(drop=True)
    df["Posizione"] = range(1, len(df) + 1)
    df = df[["Posizione", "Squadra", "Punti", "G", "V", "P"]]

    st.subheader("📊 Classifica Squadre")
    st.dataframe(df, use_container_width=True, hide_index=True)

    pos_dict = {row["Squadra"]: row["Posizione"] for _, row in df.iterrows()}
    punti_dict = {row["Squadra"]: row["Punti"] for _, row in df.iterrows()}

    st.markdown("---")
    st.subheader("📅 Analisi Partite e Assegnazione Formatori/Tutor")

    # Generazione accoppiamenti
    for i in range(0, len(squadre_lista)-1, 2):
        casa, fuori = squadre_lista[i], squadre_lista[i+1]
        p_casa, p_fuori = pos_dict.get(casa, 5), pos_dict.get(fuori, 5)
        pt_casa, pt_fuori = punti_dict.get(casa, 0), punti_dict.get(fuori, 0)
        
        sc, dett = calcola_score(p_casa, p_fuori, casa, fuori)
        
        match_info = f"**{casa} ({p_casa}ª - {pt_casa}pt)** vs **{fuori} ({p_fuori}ª - {pt_fuori}pt)**"
        
        if sc >= soglia_rosso:
            st.error(f"🔴 **SCORE {sc:.1f} / 10** | {match_info}\n\n"
                     f"👉 **AZIONI CONSIGLIATE:** FORMATORE AL TAVOLO\n\n*Motivazione:* {dett if dett else 'Scontro diretto ad alta criticità'}")
        elif sc >= soglia_giallo:
            st.warning(f"🟡 **SCORE {sc:.1f} / 10** | {match_info}\n\n"
                       f"👉 **AZIONI CONSIGLIATE:** TUTOR IN CAMPO CON IL MINIARBITRO\n\n*Motivazione:* {dett if dett else 'Gara equilibrata'}")
        else:
            st.success(f"🟢 **SCORE {sc:.1f} / 10** | {match_info}\n\n"
                       f"👉 **AZIONI CONSIGLIATE:** MINIARBITRI IN AUTONOMIA\n\n*Motivazione:* {dett if dett else 'Match ordinario'}")

with tab1:
    render_girone_ui("classifica_data_a", SQUADRE_GIRONE_A)

with tab2:
    render_girone_ui("classifica_data_b", SQUADRE_GIRONE_B)
