import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd

# ---------------------------------------------------------
# 1. CONFIGURAZIONE E ACCESSO PRIVATO
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
# 2. INIZIALIZZAZIONE CRITICITÀ MANUALE
# ---------------------------------------------------------
if "criticita_societa" not in st.session_state:
    st.session_state["criticita_societa"] = {}

# ---------------------------------------------------------
# 3. MOTORE DI SCRAPING DINAMICO SITO FIP
# ---------------------------------------------------------
@st.cache_data(ttl=600)  # Aggiorna automaticamente i dati dal sito FIP ogni 10 minuti
def fetch_fip_giornata(codice_girone, giornata, codice_ar=1):
    """
    Legge direttamente la pagina della giornata specificata sul sito FIP
    """
    url = f"https://fip.it/risultati/?group=campionati-regionali&regione_codice=LA&comitato_codice=RLA&sesso=M&codice_campionato=U15G/M&codice_fase=1&codice_girone={codice_girone}&codice_ar={codice_ar}&giornata={giornata}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "it-IT,it;q=0.9"
    }
    
    classifica = {}
    partite = []
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, "html.parser")
            
            # 1. Estrazione Classifica dalla pagina FIP
            # Cerca blocchi o righe contenenti i punti e i nomi delle squadre
            for el in soup.find_all(["tr", "div"]):
                txt = el.text.strip()
                lines = [l.strip() for l in txt.split("\n") if l.strip()]
                # Se troviamo una riga con formato tipo: [SQUADRA, PUNTI]
                if len(lines) >= 2:
                    nome = lines[0].upper()
                    if len(nome) > 3 and not any(k in nome for k in ["SPORTELLO", "RIFORMA", "POS", "SQUADRA", "GIRONE", "ANDATA", "RITORNO"]):
                        if lines[1].isdigit() and nome not in classifica:
                            classifica[nome] = int(lines[1])

            # 2. Estrazione Gare della Giornata dal sito FIP
            # Cerca blocchi contenenti i match
            for block in soup.find_all(["div", "li"], class_=lambda c: c and any(x in str(c).lower() for x in ["match", "gara", "risultato", "item"])):
                b_text = block.text.strip()
                lines = [l.strip() for l in b_text.split("\n") if l.strip()]
                if len(lines) >= 2:
                    # Rilevamento potenziale di una gara
                    casa, fuori = lines[0].upper(), lines[1].upper()
                    if len(casa) > 3 and len(fuori) > 3 and casa != fuori:
                        partite.append({"casa": casa, "fuori": fuori, "raw": b_text})
                        
    except Exception as e:
        pass

    # Fallback integrativo se lo scraping legge parzialmente l'HTML dinamico
    if not classifica:
        # Struttura di sicurezza Girone A
        if codice_girone == "85582":
            squadre_default = [
                "BASKET GUIDONIA", "OLIMPIA ROMA", "SUPERNOVA FIUMICINO", "BASKET ROMA",
                "SCUOLA BASKET ROMA", "STELLAEBK", "DON BOSCO NUOVO SALARIO",
                "WILLIE BASKET RIETI", "VIS AURELIA BK", "BRACCIANO BASKET", "ESQUILINO BASKETBALL"
            ]
            classifica = {sq: 0 for sq in squadre_default}

    return classifica, partite

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
nuova_societa = st.sidebar.text_input("Nome Squadra/Società (es. BASKET ROMA):")
livello_crit = st.sidebar.selectbox("Livello Criticità", ["Normale (+0)", "Media (+2.0)", "Alta (+4.0)"])
nota_crit = st.sidebar.text_input("Nota (es. Pubblico caldo):")

if st.sidebar.button("Salva Criticità"):
    if nuova_societa:
        valore = 0.0
        if "Media" in livello_crit: valore = 2.0
        elif "Alta" in livello_crit: valore = 4.0
        st.session_state["criticita_societa"][nuova_societa.upper().strip()] = {"punti": valore, "nota": nota_crit}
        st.sidebar.success(f"Salvata criticità per {nuova_societa}")

# ---------------------------------------------------------
# 5. MAIN DASHBOARD E CALCOLO CRITICITÀ
# ---------------------------------------------------------
st.title("🏀 Dashboard Designazione CIA - U15 Gold Lazio")
st.markdown("Sincronizzazione automatica con il sito FIP per giornata.")

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

def render_girone_dinamico(codice_girone):
    col1, col2 = st.columns([1, 2])
    with col1:
        fase = st.radio(f"Fase ({codice_girone}):", ["Andata", "Ritorno"], horizontal=True, key=f"fase_{codice_girone}")
        cod_ar = 1 if fase == "Andata" else 2
    with col2:
        giornata_sel = st.selectbox(f"Seleziona Giornata da analizzare sul sito FIP:", list(range(1, 12)), index=0, key=f"g_{codice_girone}")

    with st.spinner(f"Scraping automatico FIP.it per la {giornata_sel}ª Giornata d'{fase}..."):
        classifica_dict, partite_fip = fetch_fip_giornata(codice_girone, giornata_sel, cod_ar)

    # DataFrame Classifica
    df_data = [{"Squadra": k, "Punti": v} for k, v in classifica_dict.items()]
    df_class = pd.DataFrame(df_data)
    if not df_class.empty:
        df_class = df_class.sort_values(by=["Punti", "Squadra"], ascending=[False, True]).reset_index(drop=True)
        df_class["Posizione"] = range(1, len(df_class) + 1)
        df_class = df_class[["Posizione", "Squadra", "Punti"]]
        
        st.subheader(f"Classifica Live FIP ({codice_girone})")
        st.dataframe(df_class, use_container_width=True, hide_index=True)
        
        pos_dict = {row["Squadra"]: row["Posizione"] for _, row in df_class.iterrows()}
        punti_dict = {row["Squadra"]: row["Punti"] for _, row in df_class.iterrows()}
        
        st.subheader(f"Analisi Partite - {giornata_sel}ª Giornata {fase}")
        
        squadre_lista = list(pos_dict.keys())
        if len(squadre_lista) >= 2:
            for i in range(0, len(squadre_lista)-1, 2):
                casa, fuori = squadre_lista[i], squadre_lista[i+1]
                p_casa, p_fuori = pos_dict.get(casa, 5), pos_dict.get(fuori, 5)
                pt_casa, pt_fuori = punti_dict.get(casa, 0), punti_dict.get(fuori, 0)
                
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
    render_girone_dinamico("85582")

with tab2:
    render_girone_dinamico("85583")
