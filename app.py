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
# 2. INIZIALIZZAZIONE MEMORIA E SQUADRE REALI
# ---------------------------------------------------------
if "criticita_societa" not in st.session_state:
    st.session_state["criticita_societa"] = {}

# Elenco Ufficiale Squadre U15 Gold Lazio (estratto dal sito FIP)
SQUADRE_A = [
    "BASKET GUIDONIA",
    "OLIMPIA ROMA",
    "SUPERNOVA FIUMICINO",
    "BASKET ROMA",
    "SCUOLA BASKET ROMA",
    "STELLAEBK",
    "DON BOSCO NUOVO SALARIO",
    "WILLIE BASKET RIETI",
    "VIS AURELIA BK",
    "BRACCIANO BASKET"
]

SQUADRE_B = [
    "VIRTUS ROMA BASKET",
    "SMIT ROMA",
    "TIBER BASKET",
    "ALFA BASKET",
    "SAN PAOLO OSTIENSE",
    "ANZIO BASKET",
    "BASKET CASSINO",
    "LATINA BASKET",
    "PALESTRINA",
    "FORTITUDO ANAGNI"
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
tutte_le_squadre = sorted(list(set(SQUADRE_A + SQUADRE_B)))
nuova_societa = st.sidebar.selectbox("Seleziona Squadra:", tutte_le_squadre)
livello_crit = st.sidebar.selectbox("Livello Criticità", ["Normale (+0)", "Media (+2.0)", "Alta (+4.0)"])
nota_crit = st.sidebar.text_input("Nota (es. Pubblico caldo):")

if st.sidebar.button("Salva Criticità"):
    valore = 0.0
    if "Media" in livello_crit: valore = 2.0
    elif "Alta" in livello_crit: valore = 4.0
    st.session_state["criticita_societa"][nuova_societa.upper()] = {"punti": valore, "nota": nota_crit}
    st.sidebar.success(f"Salvata criticità per {nuova_societa}")

# ---------------------------------------------------------
# 4. CALCOLO E MAIN DASHBOARD
# ---------------------------------------------------------
st.title("🏀 Dashboard Designazione CIA - U15 Gold Lazio")
st.markdown("Valutazione criticità gare e supporto designazioni miniarbitri.")

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

def render_girone(squadre_list):
    classifica = {sq: i+1 for i, sq in enumerate(squadre_list)}

    st.subheader("Classifica Squadre")
    df_class = pd.DataFrame(list(classifica.items()), columns=["Squadra", "Posizione"])
    st.dataframe(df_class, use_container_width=True)

    st.subheader("Analisi Prossime Gare e Criticità")
    
    for i in range(0, len(squadre_list)-1, 2):
        casa, fuori = squadre_list[i], squadre_list[i+1]
        p_casa, p_fuori = classifica[casa], classifica[fuori]
        sc, dett = calcola_score(p_casa, p_fuori, casa, fuori)
        
        if sc >= soglia_rosso:
            st.error(f"🔴 **SCORE {sc:.1f} / 10** | **{casa} ({p_casa}ª)** vs **{fuori} ({p_fuori}ª)**\n\n"
                     f"👉 **AZIONI CONSIGLIATE:** FORMATORE AL TAVOLO\n\n*Motivazione:* {dett if dett else 'Scontro ad alta priorità'}")
        elif sc >= soglia_giallo:
            st.warning(f"🟡 **SCORE {sc:.1f} / 10** | **{casa} ({p_casa}ª)** vs **{fuori} ({p_fuori}ª)**\n\n"
                       f"👉 **AZIONI CONSIGLIATE:** TUTOR IN CAMPO CON IL MINIARBITRO\n\n*Motivazione:* {dett if dett else 'Gara equilibrata'}")
        else:
            st.success(f"🟢 **SCORE {sc:.1f} / 10** | **{casa} ({p_casa}ª)** vs **{fuori} ({p_fuori}ª)**\n\n"
                       f"👉 **AZIONI CONSIGLIATE:** MINIARBITRI IN AUTONOMIA\n\n*Motivazione:* {dett if dett else 'Partita ordinaria'}")

with tab1:
    render_girone(SQUADRE_A)

with tab2:
    render_girone(SQUADRE_B)
