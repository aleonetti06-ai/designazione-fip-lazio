import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup

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
# 2. INIZIALIZZAZIONE CRITICITÀ MANUALE
# ---------------------------------------------------------
if "criticita_societa" not in st.session_state:
    st.session_state["criticita_societa"] = {}

# Squadre Ufficiali estratte dai PDF FIP
SQUADRE_A = [
    "SCUOLA BASKET ROMA", "SUPERNOVA FIUMICINO", "ESQUILINO BASKETBALL", "STELLAEBK",
    "BASKET GUIDONIA", "BRACCIANO BASKET", "WILLIE BASKET RIETI", "DON BOSCO NUOVO SALARIO",
    "OLIMPIA ROMA", "BASKET ROMA", "VIS AURELIA BK"
]

SQUADRE_B = [
    "STELLE MARINE BASKET", "BASKET BEE", "CENTRI LAZIALI BASKET", "SMIT ROMA CENTRO",
    "CITTA FUTURA ROMA 1981", "BASKET CASSINO", "VIGNA PIA", "HSC ROMA BASKET",
    "BK FERENTINO", "AVENIA ACADEMY COLLEFERRO", "LATINA BASKET"
]

# ---------------------------------------------------------
# 3. CALENDARI UFFICIALI ESTRATTI DAI COMUNICATI FIP
# ---------------------------------------------------------
CALENDARIO_OFFICIAL_A = {
    1: [
        {"casa": "SCUOLA BASKET ROMA", "fuori": "SUPERNOVA FIUMICINO", "data": "18/10/2026", "ora": "16:30"},
        {"casa": "ESQUILINO BASKETBALL", "fuori": "STELLAEBK", "data": "21/10/2026", "ora": "20:00"},
        {"casa": "BASKET GUIDONIA", "fuori": "BRACCIANO BASKET", "data": "17/10/2026", "ora": "10:45"},
        {"casa": "WILLIE BASKET RIETI", "fuori": "DON BOSCO NUOVO SALARIO", "data": "17/10/2026", "ora": "15:30"},
        {"casa": "OLIMPIA ROMA", "fuori": "BASKET ROMA", "data": "18/10/2026", "ora": "15:30"}
    ],
    2: [
        {"casa": "DON BOSCO NUOVO SALARIO", "fuori": "STELLAEBK", "data": "24/10/2026", "ora": "18:30"},
        {"casa": "ESQUILINO BASKETBALL", "fuori": "BASKET ROMA", "data": "25/10/2026", "ora": "18:00"},
        {"casa": "OLIMPIA ROMA", "fuori": "VIS AURELIA BK", "data": "25/10/2026", "ora": "10:45"},
        {"casa": "WILLIE BASKET RIETI", "fuori": "BRACCIANO BASKET", "data": "25/10/2026", "ora": "11:00"},
        {"casa": "SUPERNOVA FIUMICINO", "fuori": "BASKET GUIDONIA", "data": "24/10/2026", "ora": "15:00"}
    ],
    3: [
        {"casa": "VIS AURELIA BK", "fuori": "BRACCIANO BASKET", "data": "01/11/2026", "ora": "16:30"},
        {"casa": "STELLAEBK", "fuori": "OLIMPIA ROMA", "data": "31/10/2026", "ora": "15:00"},
        {"casa": "BASKET GUIDONIA", "fuori": "SCUOLA BASKET ROMA", "data": "02/11/2026", "ora": "19:30"},
        {"casa": "SUPERNOVA FIUMICINO", "fuori": "WILLIE BASKET RIETI", "data": "31/10/2026", "ora": "18:30"},
        {"casa": "BASKET ROMA", "fuori": "DON BOSCO NUOVO SALARIO", "data": "01/11/2026", "ora": "15:00"}
    ]
}

CALENDARIO_OFFICIAL_B = {
    1: [
        {"casa": "STELLE MARINE BASKET", "fuori": "BASKET BEE", "data": "17/10/2026", "ora": "19:00"},
        {"casa": "CENTRI LAZIALI BASKET", "fuori": "SMIT ROMA CENTRO", "data": "19/10/2026", "ora": "17:45"},
        {"casa": "CITTA FUTURA ROMA 1981", "fuori": "BASKET CASSINO", "data": "18/10/2026", "ora": "10:00"},
        {"casa": "VIGNA PIA", "fuori": "HSC ROMA BASKET", "data": "18/10/2026", "ora": "11:30"},
        {"casa": "BK FERENTINO", "fuori": "AVENIA ACADEMY COLLEFERRO", "data": "21/10/2026", "ora": "17:45"}
    ],
    2: [
        {"casa": "CITTA FUTURA ROMA 1981", "fuori": "BASKET BEE", "data": "29/10/2026", "ora": "18:00"},
        {"casa": "CENTRI LAZIALI BASKET", "fuori": "AVENIA ACADEMY COLLEFERRO", "data": "26/10/2026", "ora": "19:00"},
        {"casa": "LATINA BASKET", "fuori": "SMIT ROMA CENTRO", "data": "24/10/2026", "ora": "18:00"},
        {"casa": "VIGNA PIA", "fuori": "BASKET CASSINO", "data": "25/10/2026", "ora": "11:00"},
        {"casa": "HSC ROMA BASKET", "fuori": "BK FERENTINO", "data": "25/10/2026", "ora": "12:00"}
    ],
    3: [
        {"casa": "VIGNA PIA", "fuori": "BASKET BEE", "data": "01/11/2026", "ora": "11:30"},
        {"casa": "CITTA FUTURA ROMA 1981", "fuori": "SMIT ROMA CENTRO", "data": "01/11/2026", "ora": "10:00"},
        {"casa": "CENTRI LAZIALI BASKET", "fuori": "HSC ROMA BASKET", "data": "22/10/2026", "ora": "19:15"},
        {"casa": "STELLE MARINE BASKET", "fuori": "BK FERENTINO", "data": "01/11/2026", "ora": "11:30"},
        {"casa": "AVENIA ACADEMY COLLEFERRO", "fuori": "LATINA BASKET", "data": "31/10/2026", "ora": "15:00"}
    ]
}

# ---------------------------------------------------------
# 4. SCRAPING RISULTATI SOLO SE CONFERMATI SUL SITO FIP
# ---------------------------------------------------------
@st.cache_data(ttl=300)
def fetch_fip_confirmed_results(codice_girone, squadre_lista):
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    results = []
    stats = {sq: {"Punti": 0, "G": 0, "V": 0, "P": 0} for sq in squadre_lista}

    for g in range(1, 12):
        url = f"https://fip.it/risultati/?group=campionati-regionali&regione_codice=LA&comitato_codice=RLA&sesso=M&codice_campionato=U15G/M&codice_fase=1&codice_girone={codice_girone}&codice_ar=1&giornata={g}"
        try:
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                soup = BeautifulSoup(res.content, "html.parser")
                
                for el in soup.find_all(["div", "tr", "li"]):
                    txt = el.text.strip().upper()
                    lines = [l.strip() for l in txt.split("\n") if l.strip()]
                    
                    if len(lines) >= 3:
                        nums = [int(s) for s in lines if s.isdigit() and 20 <= int(s) <= 180]
                        if len(nums) >= 2:
                            c_p, f_p = nums[0], nums[1]
                            
                            sq_trovate = [s for s in squadre_lista if s in txt]
                            if len(sq_trovate) >= 2:
                                casa, fuori = sq_trovate[0], sq_trovate[1]
                                match_id = f"G{g}_{casa}_{fuori}"
                                
                                if not any(r["id"] == match_id for r in results):
                                    vincitore = casa if c_p > f_p else fuori
                                    perdente = fuori if c_p > f_p else casa
                                    
                                    stats[vincitore]["Punti"] += 2
                                    stats[vincitore]["V"] += 1
                                    stats[vincitore]["G"] += 1
                                    
                                    stats[perdente]["P"] += 1
                                    stats[perdente]["G"] += 1
                                    
                                    results.append({
                                        "id": match_id,
                                        "Giornata": f"{g}ª Giornata",
                                        "Casa": casa,
                                        "Punti Casa": c_p,
                                        "Fuori": fuori,
                                        "Punti Fuori": f_p,
                                        "Risultato": f"{c_p} - {f_p}",
                                        "Vincitore": vincitore
                                    })
        except Exception:
            pass

    return results, stats

# ---------------------------------------------------------
# 5. NAVIGATION BAR & IMPOSTAZIONI
# ---------------------------------------------------------
st.sidebar.title("📌 Menu Navigazione")
pagina = st.sidebar.radio("Vai a:", ["🏀 Dashboard Designazione", "🔍 Verifica & Sync Dati FIP"])

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Impostazioni Algoritmo")

weight_vertice = st.sidebar.slider("Peso Scontro al Vertice (1ª-4ª)", 1.0, 8.0, 5.0)
weight_playoff = st.sidebar.slider("Peso Zona Taglio Playoff (6ª-10ª)", 1.0, 5.0, 2.5)
weight_pari = st.sidebar.slider("Peso Scontro Equilibrato (Δ pos ≤ 2)", 1.0, 5.0, 3.5)

st.sidebar.markdown("---")
st.sidebar.header("🔴 Soglie Designazione")
soglia_rosso = st.sidebar.slider("Soglia Formatore al Tavolo (Rosso)", 6.0, 10.0, 8.0)
soglia_giallo = st.sidebar.slider("Soglia Tutor in Campo (Giallo)", 4.0, 7.9, 6.0)

st.sidebar.markdown("---")
st.sidebar.header("⚠️ Criticità Società")
tutte_sq = sorted(list(set(SQUADRE_A + SQUADRE_B)))
nuova_societa = st.sidebar.selectbox("Squadra:", tutte_sq)
livello_crit = st.sidebar.selectbox("Livello Criticità", ["Normale (+0)", "Media (+2.0)", "Alta (+4.0)"])
nota_crit = st.sidebar.text_input("Nota:")

if st.sidebar.button("Salva Criticità"):
    valore = 0.0
    if "Media" in livello_crit: valore = 2.0
    elif "Alta" in livello_crit: valore = 4.0
    st.session_state["criticita_societa"][nuova_societa.upper()] = {"punti": valore, "nota": nota_crit}
    st.sidebar.success(f"Salvata criticità per {nuova_societa}")

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

# =========================================================
# PAGINA 1: DASHBOARD
# =========================================================
if pagina == "🏀 Dashboard Designazione":
    st.title("🏀 Dashboard Designazione CIA - U15 Gold Lazio")
    st.markdown("Valutazione criticità basata sui calendari FIP ufficiali e risultati omologati.")

    tab1, tab2 = st.tabs(["📌 Girone A (85582)", "📌 Girone B (85583)"])

    def render_schedule(gare_list, posizioni_dict, stats_dict):
        for gara in gare_list:
            casa, fuori = gara["casa"], gara["fuori"]
            data_g, ora_g = gara["data"], gara["ora"]
            
            p_casa = posizioni_dict.get(casa, 5)
            p_fuori = posizioni_dict.get(fuori, 5)
            pt_casa = stats_dict.get(casa, {}).get("Punti", 0)
            pt_fuori = stats_dict.get(fuori, {}).get("Punti", 0)
            
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

    def render_girone(codice_girone, squadre_lista, calendario_dict):
        with st.spinner("Scansione risultati FIP in corso..."):
            _, stats_dict = fetch_fip_confirmed_results(codice_girone, squadre_lista)
            
        df_data = []
        for sq in squadre_lista:
            info = stats_dict.get(sq, {"Punti": 0, "G": 0, "V": 0, "P": 0})
            df_data.append({"Squadra": sq, "Punti": info["Punti"], "G": info["G"], "V": info["V"], "P": info["P"]})
            
        df_class = pd.DataFrame(df_data)
        df_class = df_class.sort_values(by=["Punti", "V", "Squadra"], ascending=[False, False, True]).reset_index(drop=True)
        df_class["Posizione"] = range(1, len(df_class) + 1)
        df_class = df_class[["Posizione", "Squadra", "Punti", "G", "V", "P"]]

        st.subheader("Classifica Ufficiale")
        st.dataframe(df_class, use_container_width=True, hide_index=True)

        posizioni_dict = {row["Squadra"]: row["Posizione"] for _, row in df_class.iterrows()}

        tab_g1, tab_g2, tab_g3 = st.tabs(["🟡 1ª Giornata (17-21 Ott)", "📅 2ª Giornata (24-25 Ott)", "🔮 3ª Giornata (31 Ott-02 Nov)"])
        
        with tab_g1:
            st.subheader("Gare 1ª Giornata")
            render_schedule(calendario_dict.get(1, []), posizioni_dict, stats_dict)
            
        with tab_g2:
            st.subheader("Gare 2ª Giornata (Prossimo Turno)")
            render_schedule(calendario_dict.get(2, []), posizioni_dict, stats_dict)
            
        with tab_g3:
            st.subheader("Gare 3ª Giornata (Turno Successivo)")
            render_schedule(calendario_dict.get(3, []), posizioni_dict, stats_dict)

    with tab1:
        render_girone("85582", SQUADRE_A, CALENDARIO_OFFICIAL_A)

    with tab2:
        render_girone("85583", SQUADRE_B, CALENDARIO_OFFICIAL_B)

# =========================================================
# PAGINA 2: VERIFICA & SYNC DATI FIP
# =========================================================
elif pagina == "🔍 Verifica & Sync Dati FIP":
    st.title("🔍 Pannello Controllo e Verifica Risultati FIP")
    st.markdown("Visualizzazione **esclusiva delle gare giocate** estratte dal sito FIP.")

    if st.button("🔄 Forza Sincronizzazione Live con fip.it"):
        st.cache_data.clear()
        st.success("Sincronizzazione live effettuata!")
        st.rerun()

    tab_v1, tab_v2 = st.tabs(["🔍 Verifica Girone A (85582)", "🔍 Verifica Girone B (85583)"])

    def render_verifica(codice_girone, squadre_lista):
        with st.spinner("Estrazione gare con risultato dal portale FIP..."):
            results_list, _ = fetch_fip_confirmed_results(codice_girone, squadre_lista)
            
        if results_list:
            df_res = pd.DataFrame(results_list)
            df_res = df_res[["Giornata", "Casa", "Punti Casa", "Fuori", "Punti Fuori", "Risultato", "Vincitore"]]
            st.subheader(f"Gare con Risultato Rilevate ({len(df_res)} match disputati)")
            st.dataframe(df_res, use_container_width=True, hide_index=True)
        else:
            st.info("Nessun risultato omologato/definitivo ancora scaricato dal portale FIP per questo girone.")

    with tab_v1:
        render_verifica("85582", SQUADRE_A)

    with tab_v2:
        render_verifica("85583", SQUADRE_B)
