import streamlit as st
import requests
from bs4 import BeautifulSoup
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
# 2. INIZIALIZZAZIONE MEMORIA CRITICITÀ
# ---------------------------------------------------------
if "criticita_societa" not in st.session_state:
    st.session_state["criticita_societa"] = {}

# ---------------------------------------------------------
# 3. SCRAPER SITO FIP LAZIO MIGLIORATO
# ---------------------------------------------------------
@st.cache_data(ttl=1800)  # Aggiorna ogni 30 minuti
def get_fip_data(codice_girone):
    url = f"https://fip.it/risultati/?group=campionati-regionali&regione_codice=LA&comitato_codice=RLA&sesso=M&codice_campionato=U15G/M&codice_fase=1&codice_girone={codice_girone}"
    
    # Headers per bypassare blocchi anti-scraping della FIP
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None, None
            
        soup = BeautifulSoup(response.content, "html.parser")
        classifica = {}
        
        # Cerca tutte le tabelle presenti nella pagina
        tables = soup.find_all("table")
        for table in tables:
            rows = table.find_all("tr")
            pos = 1
            for row in rows:
                cols = row.find_all(["td", "th"])
                # Estrazione nome squadra
                if len(cols) >= 2:
                    testo = cols[0].text.strip()
                    # Rimuove righe d'intestazione ed estrae il nome pulito
                    if testo and not testo.lower().startswith(("pos", "squadra", "p", "g", "v")):
                        if len(testo) > 2:
                            classifica[testo] = pos
                            pos += 1
                            
        return classifica, soup
    except Exception as e:
        return None, None

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
# 5. MAIN DASHBOARD
# ---------------------------------------------------------
st.title("🏀 Dashboard Designazione CIA - U15 Gold Lazio")
st.markdown("Analisi automatica e valutazione criticità gare basata su dati FIP Lazio.")

tab1, tab2 = st.tabs(["📌 Girone A (85582)", "📌 Girone B (85583)"])

def calcola_score(pos_casa, pos_fuori, casa_name, fuori_name):
    score = 1.0
    dettagli = []
    
    if pos_casa <= 4 and pos_fuori <= 4:
        score += weight_vertice
        dettagli.append("Sfida al vertice")
        
    if (6 <= pos_casa <= 10) and (6 <= pos_fuori <= 10):
        score += weight_playoff
        dettagli.append("Scontro diretto Zona Taglio Playoff")
        
    if abs(pos_casa - pos_fuori) <= 2:
        score += weight_pari
        dettagli.append("Scontro equilibrato in classifica")
        
    crit_casa = st.session_state["criticita_societa"].get(casa_name.upper(), {"punti": 0, "nota": ""})
    crit_fuori = st.session_state["criticita_societa"].get(fuori_name.upper(), {"punti": 0, "nota": ""})
    
    extra = crit_casa["punti"] + crit_fuori["punti"]
    if extra > 0:
        score += extra
        note = f"Criticità segnalata: {crit_casa['nota']} {crit_fuori['nota']}".strip()
        dettagli.append(note)
        
    return min(score, 10.0), ", ".join(dettagli)

def render_girone(codice):
    classifica, _ = get_fip_data(codice)
    
    if not classifica:
        st.warning("Impossibile leggere la classifica FIP in automatico. Verifica che il campionato sia iniziato e con gare a calendario.")
        return

    st.subheader("Classifica Attuale")
    df_class = pd.DataFrame(list(classifica.items()), columns=["Squadra", "Posizione"])
    st.dataframe(df_class, use_container_width=True)

    st.subheader("Analisi Prossime Gare")
    squadre = list(classifica.keys())
    if len(squadre) >= 2:
        # Genera gli accoppiamenti di test basati sulle squadre lette
        for i in range(0, len(squadre)-1, 2):
            casa, fuori = squadre[i], squadre[i+1]
            p_casa, p_fuori = classifica[casa], classifica[fuori]
            sc, dett = calcola_score(p_casa, p_fuori, casa, fuori)
            
            if sc >= soglia_rosso:
                st.error(f"🔴 **SCORE {sc:.1f} / 10** | **{casa} ({p_casa}ª)** vs **{fuori} ({p_fuori}ª)**\n\n"
                         f"👉 **AZIONE:** FORMATORE AL TAVOLO\n\n*Note:* {dett}")
            elif sc >= soglia_giallo:
                st.warning(f"🟡 **SCORE {sc:.1f} / 10** | **{casa} ({p_casa}ª)** vs **{fuori} ({p_fuori}ª)**\n\n"
                           f"👉 **AZIONE:** TUTOR IN CAMPO CON IL MINIARBITRO\n\n*Note:* {dett}")
            else:
                st.success(f"🟢 **SCORE {sc:.1f} / 10** | **{casa} ({p_casa}ª)** vs **{fuori} ({p_fuori}ª)**\n\n"
                           f"👉 **AZIONE:** MINIARBITRI IN AUTONOMIA\n\n*Note:* {dett}")

with tab1:
    render_girone("85582")

with tab2:
    render_girone("85583")
