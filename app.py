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
# 2. SQUADRE E CALENDARIO DETTAGLIATO (GIRONE A E B)
# ---------------------------------------------------------
if "criticita_societa" not in st.session_state:
    st.session_state["criticita_societa"] = {}

SQUADRE_A = [
    "BASKET GUIDONIA", "OLIMPIA ROMA", "SUPERNOVA FIUMICINO", "BASKET ROMA",
    "SCUOLA BASKET ROMA", "STELLAEBK", "DON BOSCO NUOVO SALARIO",
    "WILLIE BASKET RIETI", "VIS AURELIA BK", "BRACCIANO BASKET", "ESQUILINO BASKETBALL"
]

SQUADRE_B = [
    "VIRTUS ROMA BASKET", "SMIT ROMA", "TIBER BASKET", "ALFA BASKET",
    "SAN PAOLO OSTIENSE", "ANZIO BASKET", "BASKET CASSINO", "LATINA BASKET",
    "PALESTRINA", "FORTITUDO ANAGNI"
]

if "classifica_a" not in st.session_state:
    st.session_state["classifica_a"] = {sq: {"Punti": 0, "G": 1, "V": 0, "P": 1} for sq in SQUADRE_A}

if "classifica_b" not in st.session_state:
    st.session_state["classifica_b"] = {sq: {"Punti": 0, "G": 1, "V": 0, "P": 1} for sq in SQUADRE_B}

# 1ª Giornata Girone A (In Corso / In attesa di omologazione)
GARE_A_G1 = [
    {"casa": "BASKET GUIDONIA", "fuori": "BRACCIANO BASKET", "data": "17/10/2026", "ora": "10:45", "note": "55 - 67 (In attesa omologazione)"},
    {"casa": "WILLIE BASKET RIETI", "fuori": "DON BOSCO NUOVO SALARIO", "data": "17/10/2026", "ora": "19:30", "note": "64 - 70 (In attesa omologazione)"},
    {"casa": "ESQUILINO BASKETBALL", "fuori": "BASKET ROMA", "data": "18/10/2026", "ora": "18:00", "note": "Gara disputata"},
    {"casa": "STELLAEBK", "fuori": "SUPERNOVA FIUMICINO", "data": "18/10/2026", "ora": "11:00", "note": "Gara disputata"},
    {"casa": "VIS AURELIA BK", "fuori": "SCUOLA BASKET ROMA", "data": "18/10/2026", "ora": "16:00", "note": "Gara disputata"},
]

# 2ª Giornata Girone A (Prossimo Turno 24-25 Ottobre)
GARE_A_G2 = [
    {"casa": "SUPERNOVA FIUMICINO", "fuori": "BASKET GUIDONIA", "data": "24/10/2026", "ora": "15:00", "note": "Prossima Gara"},
    {"casa": "ESQUILINO BASKETBALL", "fuori": "BASKET ROMA", "data": "25/10/2026", "ora": "18:00", "note": "Prossima Gara"},
    {"casa": "BRACCIANO BASKET", "fuori": "OLIMPIA ROMA", "data": "24/10/2026", "ora": "16:30", "note": "Prossima Gara"},
    {"casa": "DON BOSCO NUOVO SALARIO", "fuori": "SCUOLA BASKET ROMA", "data": "24/10/2026", "ora": "18:00", "note": "Prossima Gara"},
    {"casa": "WILLIE BASKET RIETI", "fuori": "STELLAEBK", "data": "25/10/2026", "ora": "11:00", "note": "Prossima Gara"},
]

# 3ª Giornata Girone A (Turno Successivo 31 Ott-01 Nov)
GARE_A_G3 = [
    {"casa": "BASKET GUIDONIA", "fuori": "ESQUILINO BASKETBALL", "data": "31/10/2026", "ora": "16:00", "note": "Turno Successivo"},
    {"casa": "BASKET ROMA", "fuori": "BRACCIANO BASKET", "data": "31/10/2026", "ora": "18:30", "note": "Turno Successivo"},
    {"casa": "OLIMPIA ROMA", "fuori": "DON BOSCO NUOVO SALARIO", "data": "01/11/2026", "ora": "11:30", "note": "Turno Successivo"},
    {"casa": "SCUOLA BASKET ROMA", "fuori": "WILLIE BASKET RIETI", "data": "01/11/2026", "ora": "16:00", "note": "Turno Successivo"},
    {"casa": "STELLAEBK", "fuori": "VIS AURELIA BK", "data": "01/11/2026", "ora": "18:00", "note": "Turno Successivo"},
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
st.sidebar.header("📝 Aggiorna Punti Omologati")
girone_sel = st.sidebar.radio("Seleziona Girone:", ["Girone A", "Girone B"])
lista_sq_sel = SQUADRE_A if girone_sel == "Girone A" else SQUADRE_B
dict_class_sel = st.session_state["classifica_a"] if girone_sel == "Girone A" else st.session_state["classifica_b"]

sq_modifica = st.sidebar.selectbox("Squadra:", lista_sq_sel)
punti_nuovi = st.sidebar.number_input("Punti:", min_value=0, max_value=40, value=dict_class_sel[sq_modifica]["Punti"])
vinte_nuove = st.sidebar.number_input("Vittorie:", min_value=0, max_value=20, value=dict_class_sel[sq_modifica]["V"])
perse_nuove = st.sidebar.number_input("Sconfitte:", min_value=0, max_value=20, value=dict_class_sel[sq_modifica]["P"])

if st.sidebar.button("Aggiorna Classifica"):
    dict_class_sel[sq_modifica]["Punti"] = punti_nuovi
    dict_class_sel[sq_modifica]["V"] = vinte_nuove
    dict_class_sel[sq_modifica]["P"] = perse_nuove
    dict_class_sel[sq_modifica]["G"] = vinte_nuove + perse_nuove
    st.sidebar.success(f"Aggiornati punti per {sq_modifica}")

st.sidebar.markdown("---")
st.sidebar.header("⚠️ Aggiungi Criticità Società")
tutte_sq = sorted(list(set(SQUADRE_A + SQUADRE_B)))
nuova_societa = st.sidebar.selectbox("Seleziona Squadra per Criticità:", tutte_sq)
livello_crit = st.sidebar.selectbox("Livello Criticità", ["Normale (+0)", "Media (+2.0)", "Alta (+4.0)"])
nota_crit = st.sidebar.text_input("Nota (es. Pubblico caldo):")

if st.sidebar.button("Salva Criticità"):
    valore = 0.0
    if "Media" in livello_crit: valore = 2.0
    elif "Alta" in livello_crit: valore = 4.0
    st.session_state["criticita_societa"][nuova_societa.upper()] = {"punti": valore, "nota": nota_crit}
    st.sidebar.success(f"Salvata criticità per {nuova_societa}")

# ---------------------------------------------------------
# 4. DASHBOARD E VALUTAZIONE GARE
# ---------------------------------------------------------
st.title("🏀 Dashboard Designazione CIA - U15 Gold Lazio")
st.markdown("Analisi gare e valutazione criticità miniarbitri per le giornate di campionato.")

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

def render_schedule(gare_list, posizioni_dict, dict_classifica):
    for gara in gare_list:
        casa, fuori = gara["casa"], gara["fuori"]
        data_g, ora_g = gara["data"], gara["ora"]
        info_extra = gara.get("note", "")
        
        p_casa = posizioni_dict.get(casa, 5)
        p_fuori = posizioni_dict.get(fuori, 5)
        pt_casa = dict_classifica[casa]["Punti"]
        pt_fuori = dict_classifica[fuori]["Punti"]
        
        sc, dett = calcola_score(p_casa, p_fuori, casa, fuori)
        
        header_text = f"📅 **{data_g} ore {ora_g}** | **{casa} ({p_casa}ª - {pt_casa} pt)** vs **{fuori} ({p_fuori}ª - {pt_fuori} pt)** | *{info_extra}*"
        
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
    df_data = []
    for sq in SQUADRE_A:
        info = st.session_state["classifica_a"][sq]
        df_data.append({"Squadra": sq, "Punti": info["Punti"], "G": info["G"], "V": info["V"], "P": info["P"]})
        
    df_class = pd.DataFrame(df_data)
    df_class = df_class.sort_values(by=["Punti", "V", "Squadra"], ascending=[False, False, True]).reset_index(drop=True)
    df_class["Posizione"] = range(1, len(df_class) + 1)
    df_class = df_class[["Posizione", "Squadra", "Punti", "G", "V", "P"]]

    st.subheader("Classifica Ufficiale (Girone A)")
    st.dataframe(df_class, use_container_width=True, hide_index=True)

    posizioni_dict = {row["Squadra"]: row["Posizione"] for _, row in df_class.iterrows()}

    tab_g1, tab_g2, tab_g3 = st.tabs(["🟡 1ª Giornata (In corso)", "📅 2ª Giornata (24-25 Ott)", "🔮 3ª Giornata (31 Ott-01 Nov)"])
    
    with tab_g1:
        st.subheader("Risultati e Gare 1ª Giornata")
        render_schedule(GARE_A_G1, posizioni_dict, st.session_state["classifica_a"])
        
    with tab_g2:
        st.subheader("Gare Prossimo Turno")
        render_schedule(GARE_A_G2, posizioni_dict, st.session_state["classifica_a"])
        
    with tab_g3:
        st.subheader("Anteprima Turno Successivo")
        render_schedule(GARE_A_G3, posizioni_dict, st.session_state["classifica_a"])

with tab2:
    st.info("Configurazione per il Girone B pronta e integrabile con i calendari delle giornate.")
