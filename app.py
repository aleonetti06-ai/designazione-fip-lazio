import streamlit as st
import pandas as pd
import requests

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

# Inizializzazione della classifica modificabile in sessione
if "df_classifica_a" not in st.session_state:
    st.session_state["df_classifica_a"] = pd.DataFrame([
        {"Squadra": sq, "Punti": 0, "Gare": 0, "Vinte": 0, "Perse": 0} for sq in SQUADRE_GIRONE_A
    ])

if "df_classifica_b" not in st.session_state:
    st.session_state["df_classifica_b"] = pd.DataFrame([
        {"Squadra": sq, "Punti": 0, "Gare": 0, "Vinte": 0, "Perse": 0} for sq in SQUADRE_GIRONE_B
    ])

# ---------------------------------------------------------
# 3. CHIAMATA API DIRETTA PER DATI IN TEMPO REALE
# ---------------------------------------------------------
@st.cache_data(ttl=300)
def fetch_fip_api(codice_girone):
    """
    Tenta la lettura diretta dai server backend FIP
    """
    api_url = f"https://fip.it/api/v1/risultati?codice_girone={codice_girone}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Accept": "application/json"
    }
    try:
        res = requests.get(api_url, headers=headers, timeout=5)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return None

# ---------------------------------------------------------
# 4. SIDEBAR - REGOLAZIONI E CRITICITÀ
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
st.sidebar.header("⚠️ Criticità Manuali Società")
tutte_sq = sorted(list(set(SQUADRE_GIRONE_A + SQUADRE_GIRONE_B)))
nuova_societa = st.sidebar.selectbox("Seleziona Squadra:", tutte_sq)
livello_crit = st.sidebar.selectbox("Livello Criticità", ["Normale (+0)", "Media (+2.0)", "Alta (+4.0)"])
nota_crit = st.sidebar.text_input("Nota (es. Pubblico caldo):")

if st.sidebar.button("Salva Criticità"):
    valore = 0.0
    if "Media" in livello_crit: valore = 2.0
    elif "Alta" in livello_crit: valore = 4.0
    st.session_state["criticita_societa"][nuova_societa.upper()] = {"punti": valore, "nota": nota_crit}
    st.sidebar.success(f"Criticità salvata per {nuova_societa}")

# ---------------------------------------------------------
# 5. MAIN DASHBOARD & CALCOLO SCORE
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

def render_girone_ui(key_df, codice_girone):
    st.subheader("📊 Classifica Reale (Modificabile in tempo reale)")
    st.info("💡 Puoi fare doppio click sulle celle per aggiornare Punti/Vittorie/Sconfitte appena i pallini diventano omologati sul sito FIP.")
    
    # Editor interattivo di
