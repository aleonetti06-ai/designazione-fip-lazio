import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import json

# ---------------------------------------------------------
# 1. AUTENTICAZIONE E CONFIGURAZIONE PRIVATA
# ---------------------------------------------------------
st.set_page_config(page_title="Designatore CIA - U15 Gold Lazio", layout="wide", page_icon="🏀")

def check_password():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False

    if not st.session_state["authenticated"]:
        st.title("🏀 Accesso Riservato Designatore CIA")
        password = st.text_input("Inserisci la password per accedere:", type="password")
        if st.button("Accedi"):
            if password == "basket2026":  # Password personale
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
# 3. SCRAPING DINAMICO DIRETTAMENTE DAL SITO FIP
# ---------------------------------------------------------
@st.cache_data(ttl=300)  # Sincronizza i dati ogni 5 minuti
def get_fip_live_data(codice_girone, giornata=1, codice_ar=1):
    url = f"https://fip.it/risultati/?group=campionati-regionali&regione_codice=LA&comitato_codice=RLA&sesso=M&codice_campionato=U15G/M&codice_fase=1&codice_girone={codice_girone}&codice_ar={codice_ar}&giornata={giornata}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    
    classifica = {}
    partite = []
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.content, "html.parser")
            
            # 1. Tenta di estrarre il JSON nascosto inviato dal server FIP
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string and "props" in script.string:
                    try:
                        data = json.loads(script.string)
                        # Parsing dati JSON nativi FIP se presenti
                        page_props = data.get("props", {}).get("pageProps", {})
                        if "classifica" in page_props:
                            for item in page_props["classifica"]:
                                classifica[item["squadra"].strip().upper()] = int(item.get("punti", 0))
                        if "partite" in page_props:
                            for p in page_props["partite"]:
                                partite.append({
                                    "casa": p.get("squadraCasa", "").upper(),
                                    "fuori": p.get("squadraOspite", "").upper(),
                                    "data": p.get("data", ""),
                                    "ora": p.get("ora", ""),
                                    "risultato": p.get("risultato", "Da disputare")
                                })
                    except:
                        pass
            
            # 2. Parsing di fallback se la struttura JSON varia
            if not partite or not classifica:
                for row in soup.find_all(["tr", "div"]):
                    txt = row.text.strip().upper()
                    lines = [l.strip() for l in txt.split("\n") if l.strip()]
                    
                    # Estrazione automatica della classifica
                    if len(lines) >= 2 and lines[1].isdigit():
                        sq_nome = lines[0]
                        if len(sq_nome) > 3 and not any(k in sq_nome for k in ["SPORTELLO", "RIFORMA", "GIRONE", "SQUADRA", "POS"]):
                            val = int(lines[1])
                            if val < 40 and sq_nome not in classifica:
                                classifica[sq_nome] = val

    except Exception:
        pass

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
nuova_societa = st.sidebar.text_input("Nome Squadra (es. BASKET ROMA):")
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
# 5. DASHBOARD PRINCIPALE E CALCOLO CRITICITÀ
# ---------------------------------------------------------
st.title("🏀 Dashboard Designazione CIA - U15 Gold Lazio")

top_col1, top_col2 = st.columns([3, 1])
with top_col1:
    st.markdown("Sincronizzazione **100% automatica** dal sito fip.it per classifica e calendari.")
with top_col2:
    if st.button("🔄 Sincronizza Dati FIP (Live Refresh)"):
        st.cache_data.clear()
        st.success("Sincronizzazione con fip.it completata!")
        st.rerun()

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
    c1, c2 = st.columns([1, 2])
    with c1:
        fase_sel = st.radio("Fase:", ["Andata", "Ritorno"], horizontal=True, key=f"fase_{codice_girone}")
        cod_ar = 1 if fase_sel == "Andata" else 2
    with c2:
        giornata_num = st.selectbox("Seleziona Giornata dal sito FIP:", list(range(1, 12)), index=0, key=f"g_{codice_girone}")

    with st.spinner(f"Scaricamento dati in tempo reale da fip.it per la {giornata_num}ª Giornata ({fase_sel})..."):
        classifica_dict, partite_fip = get_fip_live_data(codice_girone, giornata=giornata_num, codice_ar=cod_ar)

    # Classifica
    if classifica_dict:
        df_class = pd.DataFrame([{"Squadra": k, "Punti": v} for k, v in classifica_dict.items()])
        df_class = df_class.sort_values(by=["Punti", "Squadra"], ascending=[False, True]).reset_index(drop=True)
        df_class["Posizione"] = range(1, len(df_class) + 1)
        df_class = df_class[["Posizione", "Squadra", "Punti"]]

        st.subheader("Classifica Ufficiale Estratta da fip.it")
        st.dataframe(df_class, use_container_width=True, hide_index=True)

        pos_dict = {row["Squadra"]: row["Posizione"] for _, row in df_class.iterrows()}
        punti_dict = {row["Squadra"]: row["Punti"] for _, row in df_class.iterrows()}
    else:
        st.warning("Impossibile caricare la classifica automatica per questa giornata.")
        pos_dict, punti_dict = {}, {}

    st.subheader(f"Partite {giornata_num}ª Giornata d'{fase_sel} (da fip.it)")

    if partite_fip:
        for match in partite_fip:
            casa, fuori = match["casa"], match["fuori"]
            data_g, ora_g = match.get("data", ""), match.get("ora", "")
            ris = match.get("risultato", "")

            p_casa, p_fuori = pos_dict.get(casa, 5), pos_dict.get(fuori, 5)
            pt_casa, pt_fuori = punti_dict.get(casa, 0), punti_dict.get(fuori, 0)

            sc, dett = calcola_score(p_casa, p_fuori, casa, fuori)

            header_text = f"📅 **{data_g} {ora_g}** | **{casa} ({p_casa}ª - {pt_casa}pt)** vs **{fuori} ({p_fuori}ª - {pt_fuori}pt)** | *Stato:* `{ris}`"

            if sc >= soglia_rosso:
                st.error(f"🔴 **SCORE {sc:.1f} / 10** — {header_text}\n\n"
                         f"👉 **AZIONI CONSIGLIATE:** FORMATORE AL TAVOLO\n\n*Motivazione:* {dett if dett else 'Scontro ad alta priorità'}")
            elif sc >= soglia_giallo:
                st.warning(f"🟡 **SCORE {sc:.1f} / 10** — {header_text}\n\n"
                           f"👉 **AZIONI CONSIGLIATE:** TUTOR IN CAMPO CON IL MINIARBITRO\n\n*Motivazione:* {dett if dett else 'Gara equilibrata'}")
            else:
                st.success(f"🟢 **SCORE {sc:.1f} / 10** — {header_text}\n\n"
                           f"👉 **AZIONI CONSIGLIATE:** MINIARBITRI IN AUTONOMIA\n\n*Motivazione:* {dett if dett else 'Partita ordinaria'}")
    else:
        st.info("Nessuna partita estratta automaticamente. Clicca in alto su '🔄 Sincronizza Dati FIP' per tentare nuovamente la lettura dal sito.")

with tab1:
    render_girone_live("85582")

with tab2:
    render_girone_live("85583")
