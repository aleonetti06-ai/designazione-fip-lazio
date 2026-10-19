import streamlit as st
import pandas as pd
import subprocess
import sys
import os

# ---------------------------------------------------------
# 1. INSTALLAZIONE BROWSER PLAYWRIGHT (AVVIO AUTOMATICO)
# ---------------------------------------------------------
@st.cache_resource
def install_playwright():
    try:
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
    except Exception as e:
        pass

install_playwright()

from playwright.sync_api import sync_playwright

# ---------------------------------------------------------
# 2. AUTENTICAZIONE E CONFIGURAZIONE
# ---------------------------------------------------------
st.set_page_config(page_title="Designatore CIA - U15 Gold Lazio", layout="wide", page_icon="🏀")

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.title("🏀 Accesso Riservato Designatore CIA")
        password = st.text_input("Inserisci la password per accedere:", type="password")
        if st.button("Accedi"):
            if password == "basket2026":  # La tua password
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Password errata.")
        return False
    return True

if not check_password():
    st.stop()

# ---------------------------------------------------------
# 3. SCRAPING DINAMICO REAL-TIME CON PLAYWRIGHT
# ---------------------------------------------------------
if "criticita_societa" not in st.session_state:
    st.session_state["criticita_societa"] = {}

@st.cache_data(ttl=1800)  # Aggiorna i dati reali ogni 30 minuti
def fetch_live_fip_data(codice_girone):
    url = f"https://fip.it/risultati/?group=campionati-regionali&regione_codice=LA&comitato_codice=RLA&sesso=M&codice_campionato=U15G/M&codice_fase=1&codice_girone={codice_girone}"
    
    classifica = []
    partite = []
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            # Carica la pagina e attende 4 secondi il rendering JS
            page.goto(url, timeout=30000)
            page.wait_for_timeout(4000)
            
            # Estrazione Classifica
            rows = page.query_selector_all("tr")
            pos = 1
            for row in rows:
                cols = row.query_selector_all("td")
                if len(cols) >= 2:
                    nome = cols[0].inner_text().strip()
                    if nome and len(nome) > 2 and not any(x in nome.upper() for x in ["SPORTELLO", "RIFORMA", "POS", "SQUADRA"]):
                        punti_txt = cols[1].inner_text().strip() if len(cols) > 1 else "0"
                        punti = int(punti_txt) if punti_txt.isdigit() else 0
                        classifica.append({"Posizione": pos, "Squadra": nome, "Punti": punti})
                        pos += 1

            browser.close()
    except Exception as e:
        pass
        
    return classifica

# ---------------------------------------------------------
# 4. PANNELLO IMPOSTAZIONI (SIDEBAR)
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
nuova_societa = st.sidebar.text_input("Nome Squadra/Società:")
livello_crit = st.sidebar.selectbox("Livello Criticità", ["Normale (+0)", "Media (+2.0)", "Alta (+4.0)"])
nota_crit = st.sidebar.text_input("Nota (es. Pubblico caldo):")

if st.sidebar.button("Salva Criticità"):
    valore = 0.0
    if "Media" in livello_crit: valore = 2.0
    elif "Alta" in livello_crit: valore = 4.0
    st.session_state["criticita_societa"][nuova_societa.upper()] = {"punti": valore, "nota": nota_crit}
    st.sidebar.success(f"Salvata criticità per {nuova_societa}")

# ---------------------------------------------------------
# 5. DASHBOARD & CALCOLO SCORE
# ---------------------------------------------------------
st.title("🏀 Dashboard Designazione CIA - U15 Gold Lazio")
st.markdown("Analisi e valutazione criticità gare sincronizzate in **tempo reale tramite browser dinamico FIP**.")

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

def render_girone_live(codice_girone):
    with st.spinner("Connessione al sito FIP e lettura dati in tempo reale..."):
        classifica_live = fetch_live_fip_data(codice_girone)
    
    if not classifica_live:
        st.info("I dati del sito FIP sono in fase di aggiornamento o la diretta non è al momento disponibile.")
        return

    df_class = pd.DataFrame(classifica_live)
    st.subheader("Classifica Reale fip.it")
    st.dataframe(df_class, use_container_width=True, hide_index=True)

    pos_dict = {row["Squadra"]: row["Posizione"] for _, row in df_class.iterrows()}
    punti_dict = {row["Squadra"]: row["Punti"] for _, row in df_class.iterrows()}
    squadre = list(pos_dict.keys())

    st.subheader("Analisi Partite e Assegnazione Formatori/Tutor")
    if len(squadre) >= 2:
        for i in range(0, len(squadre)-1, 2):
            casa, fuori = squadre[i], squadre[i+1]
            p_casa, p_fuori = pos_dict[casa], pos_dict[fuori]
            pt_casa, pt_fuori = punti_dict[casa], punti_dict[fuori]
            
            sc, dett = calcola_score(p_casa, p_fuori, casa, fuori)
            
            header_text = f"**{casa} ({p_casa}ª - {pt_casa} pt)** vs **{fuori} ({p_fuori}ª - {pt_fuori} pt)**"
            
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
    render_girone_live("85582")

with tab2:
    render_girone_live("85583")
