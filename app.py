# app.py — Dashboard Performance SDA — versione Streamlit web
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, timedelta
import json, io

from core import (
    leggi_file_corrieri,
    aggrega_filiale,
    calcola_tariffa,
    FASCE_DEFAULT,
)

st.set_page_config(
    page_title="Dashboard Performance SDA",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

COLORI_FILIALI = [
    "#3b82f6", "#22c55e", "#a855f7", "#f59e0b",
    "#14b8a6", "#ef4444", "#ec4899", "#f97316",
]

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

def prod_color(p: float) -> str:
    if p >= 0.95:   return "#22c55e"
    if p >= 0.85:   return "#f59e0b"
    return "#ef4444"

GDRIVE_FILE_ID = "151L_nfX6dhCgzlPJ9grl2j8ghLrdqHWO"
GDRIVE_URL = f"https://docs.google.com/spreadsheets/d/{GDRIVE_FILE_ID}/export?format=xlsx"
if "dati"   not in st.session_state: st.session_state.dati   = None
if "fasce"  not in st.session_state: st.session_state.fasce  = [f.copy() for f in FASCE_DEFAULT]
if "date_da" not in st.session_state: st.session_state.date_da = None
if "date_a"  not in st.session_state: st.session_state.date_a  = None

with st.sidebar:
    st.markdown("## 📦 Dashboard Performance")
    st.markdown("---")
    uploaded = st.file_uploader(
        "Carica il file Excel",
        type=["xlsx", "xls"],
        help="File Performance_Corrieri.xlsx — header alla riga 6",
    )
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
                st.success(f"✅ Dati aggiornati — {len(st.session_state.dati)} filiali")
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
                    st.session_state.date_da = st.session_state.date_a = date.today()
                    st.rerun()
            with c2:
                if st.button("7gg"):
                    st.session_state.date_a  = tutte_date[-1]
                    st.session_state.date_da = tutte_date[-1] - timedelta(days=6)
                    st.rerun()
            with c3:
                if st.button("Tutto"):
                    st.session_state.date_da = tutte_date[0]
                    st.session_state.date_a  = tutte_date[-1]
                    st.rerun()
    st.markdown("---")
    st.caption("Dashboard Performance SDA v3 · Streamlit")

if not st.session_state.dati:
    st.markdown("# 📦 Dashboard Performance SDA")
    st.info("👈  Carica il file **Performance_Corrieri.xlsx** dalla barra laterale per iniziare.")
    st.stop()

dati      = st.session_state.dati
filiali   = sorted(dati.keys())
date_da   = st.session_state.date_da
date_a    = st.session_state.date_a
fasce     = st.session_state.fasce

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Panoramica",
    "🏢 Dettaglio Filiale",
    "📋 Tutti i Giri",
    "📅 Giornaliero",
    "💶 Tariffa",
])

with tab1:
    st.markdown("### Panoramica Multi-Filiale")
    riepilogo = []
    for fil in filiali:
        agg, _, _ = aggrega_filiale(dati[fil], date_da, date_a)
        if agg:
            riepilogo.append({"filiale": fil, **agg})
    if not riepilogo:
        st.warning("Nessun dato nel periodo selezionato.")
        st.stop()

    tot_af  = sum(r["tot_lv_af"]  for r in riepilogo)
    tot_ok  = sum(r["tot_lv_ok"]  for r in riepilogo)
    tot_rit = sum(r["tot_lv_rit"] for r in riepilogo)
    prod_g  = (tot_ok + tot_rit) / tot_af if tot_af > 0 else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: kpi_card("Filiali attive",   str(len(riepilogo)),        "#3b82f6")
    with c2: kpi_card("Tot LV Affidate",  fmt_n(tot_af),              "#3b82f6")
    with c3: kpi_card("Tot LV Ok",        fmt_n(tot_ok),              "#22c55e")
    with c4: kpi_card("Tot LV Ritiro",    fmt_n(tot_rit),             "#a855f7")
    with c5: kpi_card("Produttività %",   f"{prod_g:.1%}",            prod_color(prod_g))

    st.markdown("---")
    st.markdown("#### Produttività per Filiale")
    df_riep = pd.DataFrame(riepilogo)
    df_riep["prod_pct"] = df_riep["media_prod"] * 100
    fig_prod = go.Figure()
    for i, row in df_riep.iterrows():
        col = colore_filiale(filiali, row["filiale"])
        fig_prod.add_trace(go.Bar(
            x=[row["filiale"]],
            y=[round(row["prod_pct"], 1)],
            marker_color=col,
            name=row["filiale"],
            text=[f"{row['prod_pct']:.1f}%"],
            textposition="outside",
            showlegend=False,
        ))
    fig_prod.add_hline(y=95, line_dash="dash", line_color="#22c55e", annotation_text="Target 95%", annotation_position="top right")
    fig_prod.update_layout(
        plot_bgcolor="#181c24", paper_bgcolor="#0f1117", font_color="#f1f5f9", height=320,
        yaxis=dict(range=[0, 110], ticksuffix="%", gridcolor="#2a3045"), xaxis=dict(gridcolor="#2a3045"),
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig_prod, use_container_width=True)

    st.markdown("#### Tabella Riepilogativa")
    df_tab = df_riep[["filiale", "n_giorni", "tot_lv_af", "tot_lv_ok", "tot_lv_rit", "media_gg_lv_ok", "media_prod"]].copy()
    df_tab.columns = ["Filiale", "Giorni", "Tot LV AF", "Tot LV Ok", "Tot LV Rit", "Media LV Ok/gg", "Prod %"]
    df_tab["Tot LV AF"]      = df_tab["Tot LV AF"].apply(fmt_n)
    df_tab["Tot LV Ok"]      = df_tab["Tot LV Ok"].apply(fmt_n)
    df_tab["Tot LV Rit"]     = df_tab["Tot LV Rit"].apply(fmt_n)
    df_tab["Media LV Ok/gg"] = df_tab["Media LV Ok/gg"].apply(lambda x: f"{x:.0f}")
    df_tab["Prod %"]         = df_tab["Prod %"].apply(lambda x: f"{x:.1%}")
    st.dataframe(df_tab, use_container_width=True, hide_index=True)

with tab2:
    st.markdown("### Dettaglio Filiale")
    fil_sel = st.selectbox("Seleziona filiale", filiali, key="sel_fil")
    agg, giornate, per_giro = aggrega_filiale(dati[fil_sel], date_da, date_a)

    if not agg:
        st.warning("Nessun dato per questa filiale nel periodo selezionato.")
    else:
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        with c1: kpi_card("Giorni",         str(agg["n_giorni"]),              "#94a3b8")
        with c2: kpi_card("Media LV AF/gg", f"{agg['media_gg_lv_af']:.0f}",   "#3b82f6")
        with c3: kpi_card("Media LV Ok/gg", f"{agg['media_gg_lv_ok']:.0f}",   "#22c55e")
        with c4: kpi_card("Media LV Rit/gg",f"{agg['media_gg_lv_rit']:.0f}",  "#a855f7")
        with c5: kpi_card("Tot LV AF",      fmt_n(agg["tot_lv_af"]),           "#3b82f6")
        with c6: kpi_card("Produttività",   f"{agg['media_prod']:.1%}",        prod_color(agg["media_prod"]))

        st.markdown("---")
        st.markdown("#### Dettaglio per Giro (medie periodo)")
        if per_giro:
            rows_giro = [{
                "Giro":      g,
                "Giorni":    v["n"],
                "LV AF":     f"{v['lv_af']:.0f}",
                "LV Ok":     f"{v['lv_ok']:.0f}",
                "LV Rit":    f"{v['lv_rit']:.0f}",
                "Stop Ok":   f"{v['stop_ok']:.0f}",
                "Stop Rit":  f"{v['stop_rit']:.0f}",
                "Prod Media Giorno": f"{v.get('prod_giro_corretta', 0.0):.1f}",
            } for g, v in sorted(per_giro.items())]
            st.dataframe(pd.DataFrame(rows_giro), use_container_width=True, hide_index=True)

with tab3:
    st.markdown("### Tutti i Giri — Multi-Filiale")
    righe_tutti = []
    for fil in filiali:
        _, _, pg = aggrega_filiale(dati[fil], date_da, date_a)
        if pg:
            for giro, v in sorted(pg.items()):
                righe_tutti.append({
                    "Filiale":   fil,
                    "Giro":      giro,
                    "Giorni":    v["n"],
                    "LV AF":     round(v["lv_af"],   1),
                    "LV Ok":     round(v["lv_ok"],   1),
                    "LV Rit":    round(v["lv_rit"],  1),
                    "Stop Ok":   round(v["stop_ok"], 1),
                    "Stop Rit":  round(v["stop_rit"], 1),
                    "Prod Media Giorno": round(v.get("prod_giro_corretta", 0.0), 1),
                })
    if righe_tutti:
        df_tutti = pd.DataFrame(righe_tutti)
        fil_filter = st.multiselect("Filtra per filiale", filiali, default=filiali, key="filter_tutti")
        df_tutti = df_tutti[df_tutti["Filiale"].isin(fil_filter)]
        st.dataframe(df_tutti, use_container_width=True, hide_index=True)
    else:
        st.warning("Nessun dato nel periodo selezionato.")
