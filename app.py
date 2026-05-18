# app.py — Dashboard Performance SDA — versione Streamlit web
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, timedelta
import io

from core import (
    leggi_file_corrieri,
    aggrega_filiale,
    calcola_tariffa,
    FASCE_DEFAULT,
    ottieni_fasce_filiale, # Importazione della nuova funzione di controllo tariffe
)

st.set_page_config(
    page_title="Dashboard Performance SDA",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

COLORI_FILIALI = ["#3b82f6", "#22c55e", "#a855f7", "#f59e0b", "#14b8a6", "#ef4444", "#ec4899", "#f97316"]

st.markdown("""
<style>
    .kpi-box {
        background: #1e2330;
        border: 1px solid #2a3045;
        border-radius: 10px;
        padding: 16px 18px 12px;
        text-align: center;
    }
    .kpi-val  { font-size: 2rem; font-weight: 700; margin: 0; line-height: 1.1; }
    .kpi-lbl  { font-size: 0.78rem; color: #94a3b8; margin-top: 4px; }
    div[data-testid="stDataFrame"] { font-size: 0.85rem; }
    section[data-testid="stSidebar"] { background: #181c24; }
</style>
""", unsafe_allow_html=True)

def kpi_card(label: str, value: str, color: str = "#3b82f6"):
    st.markdown(
        f'<div class="kpi-box">'
        f'<p class="kpi-val" style="color:{color}">{value}</p>'
        f'<p class="kpi-lbl">{label}</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

def fmt_eur(v: float) -> str:
    return f"€ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_n(v: float) -> str:
    return f"{int(v):,}".replace(",", ".")

def colore_filiale(filiali: list, nome: str) -> str:
    try:
        return COLORI_FILIALI[filiali.index(nome) % len(COLORI_FILIALI)]
    except ValueError:
        return "#3b82f6"

GDRIVE_FILE_ID = "151L_nfX6dhCgzlPJ9grl2j8ghLrdqHWO"
GDRIVE_URL = f"https://docs.google.com/spreadsheets/d/{GDRIVE_FILE_ID}/export?format=xlsx"

if "dati" not in st.session_state: st.session_state.dati = None
if "date_da" not in st.session_state: st.session_state.date_da = None
if "date_a" not in st.session_state: st.session_state.date_a = None

with st.sidebar:
    st.markdown("## 📦 Dashboard Performance")
    st.markdown("---")
    uploaded = st.file_uploader("Carica il file Excel", type=["xlsx", "xls"])
    if uploaded:
        with st.spinner("Lettura file..."):
            try:
                st.session_state.dati = leggi_file_corrieri(uploaded)
                st.success(f"✅ {len(st.session_state.dati)} filiali caricate")
            except Exception as e:
                st.error(f"Errore lettura file: {e}")
    elif st.session_state.dati is None:
        with st.spinner("Caricamento dati da Google Drive..."):
            try:
                import requests
                r = requests.get(GDRIVE_URL, timeout=30)
                r.raise_for_status()
                st.session_state.dati = leggi_file_corrieri(io.BytesIO(r.content), engine="openpyxl")
                st.success(f"✅ Dati caricati — {len(st.session_state.dati)} filiali")
            except Exception as e:
                st.error(f"Impossibile scaricare da Drive: {e}")

    st.markdown("---")
    if st.session_state.dati:
        tutte_date = sorted({d for fil in st.session_state.dati.values() for d in fil})
        if tutte_date:
            st.markdown("### 📅 Periodo")
            col1, col2 = st.columns(2)
            with col1:
                date_da = st.date_input("Dal", value=tutte_date[0], min_value=tutte_date[0], max_value=tutte_date[-1])
            with col2:
                date_a = st.date_input("Al", value=tutte_date[-1], min_value=tutte_date[0], max_value=tutte_date[-1])
            st.session_state.date_da = date_da
            st.session_state.date_a  = date_a

            c1, c2, c3 = st.columns(3)
            with c1:
                if st.button("Oggi"):
                    st.session_state.date_da = st.session_state.date_a = tutte_date[-1]
                    st.rerun()
            with c2:
                if st.button("7gg"):
                    st.session_state.date_a  = tutte_date[-1]
                    st.session_state.date_da = max(tutte_date[0], tutte_date[-1] - timedelta(days=6))
                    st.rerun()
            with c3:
                if st.button("Tutto"):
                    st.session_state.date_da = tutte_date[0]
                    st.session_state.date_a  = tutte_date[-1]
                    st.rerun()

if not st.session_state.dati:
    st.info("👈 Carica il file Performance_Corrieri.xlsx dalla barra laterale per iniziare.")
    st.stop()

dati = st.session_state.dati
filiali = sorted(dati.keys())
date_da = st.session_state.date_da
date_a = st.session_state.date_a

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Panoramica",
    "🏢 Dettaglio Filiale",
    "📋 Tutti i Giri",
    "📅 Giornaliero",
    "💶 Tariffa",
])

# TAB 1: PANORAMICA
with tab1:
    st.markdown("### Panoramica Multi-Filiale")
    riepilogo = []
    for fil in filiali:
        agg, _, _ = aggrega_filiale(dati[fil], date_da, date_a)
        if agg:
            riepilogo.append({"filiale": fil, **agg})
    
    if riepilogo:
        df_riep = pd.DataFrame(riepilogo)
        tot_af  = df_riep["tot_lv_af"].sum()
        tot_ok  = df_riep["tot_lv_ok"].sum()
        tot_rit = df_riep["tot_lv_rit"].sum()
        
        tot_giri_giorni = sum(sum(len(giri) for d, giri in dati[f].items() if (date_da is None or d >= date_da) and (date_a is None or d <= date_a)) for f in filiali)
        prod_complessiva_media = (tot_ok + tot_rit) / tot_giri_giorni if tot_giri_giorni > 0 else 0.0

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: kpi_card("Filiali attive",   str(len(riepilogo)),        "#3b82f6")
        with c2: kpi_card("Tot LV Affidate",  fmt_n(tot_af),              "#3b82f6")
        with c3: kpi_card("Tot LV Ok",        fmt_n(tot_ok),              "#22c55e")
        with c4: kpi_card("Tot LV Ritiro",    fmt_n(tot_rit),             "#a855f7")
        with c5: kpi_card("Prod. Media Corrieri", f"{prod_complessiva_media:.1f}", "#f59e0b")

        st.markdown("---")
        st.markdown("#### Produttività Media Corrieri per Filiale")
        fig_prod = go.Figure()
        for i, row in df_riep.iterrows():
            col = colore_filiale(filiali, row["filiale"])
            fig_prod.add_trace(go.Bar(
                x=[row["filiale"]],
                y=[round(row["media_prod"], 1)],
                marker_color=col,
                name=row["filiale"],
                text=[f"{row['media_prod']:.1f}"],
                textposition="outside",
                showlegend=False,
            ))
        fig_prod.update_layout(
            plot_bgcolor="#181c24", paper_bgcolor="#0f1117", font_color="#f1f5f9", height=300,
            yaxis=dict(gridcolor="#2a3045", title="Media Giornaliera Pezzi per Corriere"),
            margin=dict(l=0, r=0, t=20, b=0),
        )
        st.plotly_chart(fig_prod, use_container_width=True)

        st.markdown("#### Tabella Riepilogativa Filiali")
        df_tab = df_riep[["filiale", "n_giorni", "tot_lv_af", "tot_lv_ok", "tot_lv_rit", "media_prod"]].copy()
        df_tab.columns = ["Filiale", "Giorni Periodo", "Tot LV AF", "Tot LV Ok", "Tot LV Rit", "Prod. Media Corriere"]
        df_tab["Tot LV AF"]  = df_tab["Tot LV AF"].apply(fmt_n)
        df_tab["Tot LV Ok"]  = df_tab["Tot LV Ok"].apply(fmt_n)
        df_tab["Tot LV Rit"] = df_tab["Tot LV Rit"].apply(fmt_n)
        df_tab["Prod. Media Corriere"] = df_tab["Prod. Media Corriere"].apply(lambda x: f"{x:.1f}")
        st.dataframe(df_tab, use_container_width=True, hide_index=True)

# TAB 2: DETTAGLIO FILIALE
with tab2:
    st.markdown("### Dettaglio Singola Filiale")
    fil_sel = st.selectbox("Seleziona filiale", filiali, key="sel_fil")
    agg, giornate, per_giro = aggrega_filiale(dati[fil_sel], date_da, date_a)

    if agg:
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: kpi_card("Giorni Attivi",   str(agg["n_giorni"]),        "#94a3b8")
        with c2: kpi_card("Tot LV Affidate", fmt_n(agg["tot_lv_af"]),     "#3b82f6")
        with c3: kpi_card("Tot LV Ok",       fmt_n(agg["tot_lv_ok"]),     "#22c55e")
        with c4: kpi_card("Tot LV Rit",      fmt_n(agg["tot_lv_rit"]),    "#a855f7")
        with c5: kpi_card("Prod. Media Corrieri", f"{agg['media_prod']:.1f}", "#f59e0b")

        st.markdown("---")
        st.markdown("#### Rendimento dei singoli Giri (Medie Giornaliere del Periodo)")
        if per_giro:
            rows_giro = [{
                "Giro":      g,
                "Giorni Presenza": v["n"],
                "LV AF (Media)":  f"{v['lv_af']:.1f}",
                "LV Ok (Media)":  f"{v['lv_ok']:.1f}",
                "LV Rit (Media)": f"{v['lv_rit']:.1f}",
                "Stop Ok (Media)": f"{v['stop_ok']:.1f}",
                "Stop Rit (Media)": f"{v['stop_rit']:.1f}",
                "Prod Media Giorno (LV OK + RIT)": f"{v['prod_giro_corretta']:.1f}",
            } for g, v in sorted(per_giro.items())]
            st.dataframe(pd.DataFrame(rows_giro), use_container_width=True, hide_index=True)

# TAB 3: TUTTI I GIRI
with tab3:
    st.markdown("### Elenco Completo Multi-Filiale di tutti i Giri")
    righe_tutti = []
    for fil in filiali:
        _, _, pg = aggrega_filiale(dati[fil], date_da, date_a)
        if pg:
            for giro, v in sorted(pg.items()):
                righe_tutti.append({
                    "Filiale":   fil,
                    "Giro":      giro,
                    "Giorni":    v["n"],
                    "LV AF (Media)":     round(v["lv_af"], 1),
                    "LV Ok (Media)":     round(v["lv_ok"], 1),
                    "LV Rit (Media)":    round(v["lv_rit"], 1),
                    "Stop Ok (Media)":   round(v["stop_ok"], 1),
                    "Stop Rit (Media)":  round(v["stop_rit"], 1),
                    "Prod Media Giorno (LV OK + RIT)": round(v["prod_giro_corretta"], 1),
                })
    if righe_tutti:
        df_tutti = pd.DataFrame(righe_tutti)
        fil_filter = st.multiselect("Filtra per filiale", filiali, default=filiali, key="filter_tutti")
        df_tutti = df_tutti[df_tutti["Filiale"].isin(fil_filter)]
        st.dataframe(df_tutti, use_container_width=True, hide_index=True)

# TAB 4: GIORNALIERO
with tab4:
    st.markdown("### Dettaglio Giornaliero per Filiale")
    fil_giorno = st.selectbox("Seleziona filiale", filiali, key="fil_giorno")
    _, giornate_g, _ = aggrega_filiale(dati[fil_giorno], date_da, date_a)
    
    if giornate_g:
        date_sel = st.selectbox("Seleziona data", sorted(giornate_g.keys(), reverse=True))
        giri_day = giornate_g[date_sel]
        
        righe_giorno = []
        for g, v in sorted(giri_day.items()):
            righe_giorno.append({
                "Giro": g,
                "LV AFF": int(v.get("lv_af", 0)),
                "LV OK": int(v.get("lv_ok", 0)),
                "LV RIT": int(v.get("lv_rit", 0)),
                "STOP OK": int(v.get("stop_ok", 0)),
                "STOP RIT": int(v.get("stop_rit", 0)),
                "Produttività (LV OK + RIT)": int(v.get("prod_specifica_giro", 0)),
            })
        st.dataframe(pd.DataFrame(righe_giorno), use_container_width=True, hide_index=True)
    else:
        st.warning("Nessun dato disponibile nel periodo selezionato.")

# TAB 5: TARIFFA
with tab5:
    st.markdown("### Calcolo Fatturato a Scaglioni Progressivi")
    fil_tar = st.selectbox("Seleziona filiale per tariffazione", filiali, key="fil_tar")
    _, giornate_t, _ = aggrega_filiale(dati[fil_tar], date_da, date_a)
    
    if giornate_t:
        # Recupera dinamicamente dal file core i 2 scaglioni specifici di QUESTA filiale
        fasce_attive = ottieni_fasce_filiale(fil_tar)
        
        # Mostra le tariffe applicate correnti dentro un piccolo menu informativo espandibile
        with st.expander(f"Ispeziona scaglioni attivi per la filiale: {fil_tar}", expanded=False):
            for idx, f in enumerate(fasce_attive):
                st.write(f"Scaglione {idx+1} ➔ Da: {f['da']} a {f['a']} LDV | Tariffa: € {f['prezzo']:.3f}")
        
        righe_tar, tot_v, tot_f, med_f = calcola_tariffa(giornate_t, fasce_attive)
        
        c1, c2, c3 = st.columns(3)
        with c1: kpi_card("Volume Totale (LV OK + RIT)", fmt_n(tot_v), "#3b82f6")
        with c2: kpi_card("Fatturato Totale Stimato", fmt_eur(tot_f), "#22c55e")
        with c3: kpi_card("Fatturato Medio / Giorno", fmt_eur(med_f), "#a855f7")
        
        st.markdown("---")
        st.markdown("#### Dettaglio giornaliero scaglioni")
        st.dataframe(pd.DataFrame(righe_tar), use_container_width=True, hide_index=True)
    else:
        st.warning("Nessun dato disponibile nel periodo selezionato.")