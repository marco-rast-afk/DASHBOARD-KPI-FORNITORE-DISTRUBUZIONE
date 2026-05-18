# app.py — Dashboard Performance SDA — versione Streamlit web
#
# Come avviare:
#   streamlit run app.py
#
# Struttura pagine:
#   1. Panoramica        → KPI globali + grafico confronto filiali
#   2. Dettaglio Filiale → KPI + tabella giri per filiale selezionata
#   3. Tutti i Giri      → tabella completa multi-filiale
#   4. Giornaliero       → dettaglio per singola giornata
#   5. Tariffa           → calcolo fatturato a scaglioni

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

# ─────────────────────────────────────────────────────────────
# CONFIG PAGINA
# ─────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────
# CSS PERSONALIZZATO  (dark minimal, simile all'originale)
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* KPI card custom */
    .kpi-box {
        background: #1e2330;
        border: 1px solid #2a3045;
        border-radius: 10px;
        padding: 16px 18px 12px;
        text-align: center;
    }
    .kpi-val  { font-size: 2rem; font-weight: 700; margin: 0; line-height: 1.1; }
    .kpi-lbl  { font-size: 0.78rem; color: #94a3b8; margin-top: 4px; }
    /* tabelle più compatte */
    div[data-testid="stDataFrame"] { font-size: 0.85rem; }
    /* sidebar */
    section[data-testid="stSidebar"] { background: #181c24; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────────
# SESSION STATE — dati caricati una volta sola
# ─────────────────────────────────────────────────────────────
# ── GOOGLE DRIVE — ID del file Excel condiviso ──────────────
GDRIVE_FILE_ID = "INCOLLA_QUI_IL_TUO_ID"   # ← sostituisci questo
GDRIVE_URL = f"https://docs.google.com/spreadsheets/d/151L_nfX6dhCgzlPJ9grl2j8ghLrdqHWO/edit?usp=drive_link&ouid=109021770760106017946&rtpof=true&sd=true"
if "dati"   not in st.session_state: st.session_state.dati   = None
if "fasce"  not in st.session_state: st.session_state.fasce  = [f.copy() for f in FASCE_DEFAULT]
if "date_da" not in st.session_state: st.session_state.date_da = None
if "date_a"  not in st.session_state: st.session_state.date_a  = None


# ─────────────────────────────────────────────────────────────
# SIDEBAR — CARICAMENTO FILE + FILTRI
# ─────────────────────────────────────────────────────────────
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
# ── NUOVO: carica automaticamente da Google Drive ──────────
    elif st.session_state.dati is None and GDRIVE_FILE_ID != "151L_nfX6dhCgzlPJ9grl2j8ghLrdqHWO":
        with st.spinner("Caricamento dati da Google Drive..."):
            try:
                import requests, io
                r = requests.get(GDRIVE_URL, timeout=30)
                r.raise_for_status()
                st.session_state.dati = leggi_file_corrieri(io.BytesIO(r.content),engine="openpyxl")
                st.success(f"✅ Dati aggiornati — {len(st.session_state.dati)} filiali")
            except Exception as e:
                st.error(f"Impossibile scaricare da Drive: {e}")


    st.markdown("---")

    # Filtro periodo
    if st.session_state.dati:
        tutte_date = sorted({
            d for fil in st.session_state.dati.values() for d in fil
        })
        if tutte_date:
            st.markdown("### 📅 Periodo")
            col1, col2 = st.columns(2)
            with col1:
                date_da = st.date_input("Dal", value=tutte_date[0],
                                        min_value=tutte_date[0], max_value=tutte_date[-1])
            with col2:
                date_a = st.date_input("Al",  value=tutte_date[-1],
                                       min_value=tutte_date[0], max_value=tutte_date[-1])
            st.session_state.date_da = date_da
            st.session_state.date_a  = date_a

            # Scorciatoie
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


# ─────────────────────────────────────────────────────────────
# GUARD — nessun file caricato
# ─────────────────────────────────────────────────────────────
if not st.session_state.dati:
    st.markdown("# 📦 Dashboard Performance SDA")
    st.info("👈  Carica il file **Performance_Corrieri.xlsx** dalla barra laterale per iniziare.")
    st.stop()

# Dati e filtri attivi
dati      = st.session_state.dati
filiali   = sorted(dati.keys())
date_da   = st.session_state.date_da
date_a    = st.session_state.date_a
fasce     = st.session_state.fasce


# ─────────────────────────────────────────────────────────────
# TABS PRINCIPALI
# ─────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Panoramica",
    "🏢 Dettaglio Filiale",
    "📋 Tutti i Giri",
    "📅 Giornaliero",
    "💶 Tariffa",
])


# ══════════════════════════════════════════════════════════════
# TAB 1 — PANORAMICA
# ══════════════════════════════════════════════════════════════
with tab1:
    st.markdown("### Panoramica Multi-Filiale")

    # Aggrega tutte le filiali
    riepilogo = []
    for fil in filiali:
        agg, _, _ = aggrega_filiale(dati[fil], date_da, date_a)
        if agg:
            riepilogo.append({"filiale": fil, **agg})

    if not riepilogo:
        st.warning("Nessun dato nel periodo selezionato.")
        st.stop()

    # KPI GLOBALI sommando tutte le filiali
    tot_af  = sum(r["tot_lv_af"]  for r in riepilogo)
    tot_ok  = sum(r["tot_lv_ok"]  for r in riepilogo)
    tot_rit = sum(r["tot_lv_rit"] for r in riepilogo)
    prod_g  = tot_ok / tot_af if tot_af > 0 else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1: kpi_card("Filiali attive",   str(len(riepilogo)),        "#3b82f6")
    with c2: kpi_card("Tot LV Affidate",  fmt_n(tot_af),              "#3b82f6")
    with c3: kpi_card("Tot LV Ok",        fmt_n(tot_ok),              "#22c55e")
    with c4: kpi_card("Tot LV Ritiro",    fmt_n(tot_rit),             "#a855f7")
    with c5: kpi_card("Produttività %",   f"{prod_g:.1%}",            prod_color(prod_g))

    st.markdown("---")

    # GRAFICO CONFRONTO FILIALI — produttività
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
    fig_prod.add_hline(y=95, line_dash="dash", line_color="#22c55e",
                       annotation_text="Target 95%", annotation_position="top right")
    fig_prod.update_layout(
        plot_bgcolor="#181c24", paper_bgcolor="#0f1117",
        font_color="#f1f5f9", height=320,
        yaxis=dict(range=[0, 110], ticksuffix="%", gridcolor="#2a3045"),
        xaxis=dict(gridcolor="#2a3045"),
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig_prod, use_container_width=True)

    # GRAFICO LV OK vs LV RIT
    st.markdown("#### LV Ok vs LV Ritiro per Filiale")
    fig_lv = go.Figure()
    fig_lv.add_trace(go.Bar(
        name="LV Ok",
        x=df_riep["filiale"], y=df_riep["tot_lv_ok"],
        marker_color="#22c55e",
    ))
    fig_lv.add_trace(go.Bar(
        name="LV Ritiro",
        x=df_riep["filiale"], y=df_riep["tot_lv_rit"],
        marker_color="#a855f7",
    ))
    fig_lv.update_layout(
        barmode="group",
        plot_bgcolor="#181c24", paper_bgcolor="#0f1117",
        font_color="#f1f5f9", height=300,
        yaxis=dict(gridcolor="#2a3045"),
        xaxis=dict(gridcolor="#2a3045"),
        legend=dict(bgcolor="#1e2330", bordercolor="#2a3045"),
        margin=dict(l=0, r=0, t=10, b=0),
    )
    st.plotly_chart(fig_lv, use_container_width=True)

    # TABELLA RIEPILOGATIVA
    st.markdown("#### Tabella Riepilogativa")
    df_tab = df_riep[[
        "filiale", "n_giorni", "tot_lv_af", "tot_lv_ok",
        "tot_lv_rit", "media_gg_lv_ok", "media_prod"
    ]].copy()
    df_tab.columns = [
        "Filiale", "Giorni", "Tot LV AF", "Tot LV Ok",
        "Tot LV Rit", "Media LV Ok/gg", "Prod %"
    ]
    df_tab["Tot LV AF"]      = df_tab["Tot LV AF"].apply(lambda x: fmt_n(x))
    df_tab["Tot LV Ok"]      = df_tab["Tot LV Ok"].apply(lambda x: fmt_n(x))
    df_tab["Tot LV Rit"]     = df_tab["Tot LV Rit"].apply(lambda x: fmt_n(x))
    df_tab["Media LV Ok/gg"] = df_tab["Media LV Ok/gg"].apply(lambda x: f"{x:.0f}")
    df_tab["Prod %"]         = df_tab["Prod %"].apply(lambda x: f"{x:.1%}")
    st.dataframe(df_tab, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════
# TAB 2 — DETTAGLIO FILIALE
# ══════════════════════════════════════════════════════════════
with tab2:
    st.markdown("### Dettaglio Filiale")

    fil_sel = st.selectbox("Seleziona filiale", filiali, key="sel_fil")
    agg, giornate, per_giro = aggrega_filiale(dati[fil_sel], date_da, date_a)

    if not agg:
        st.warning("Nessun dato per questa filiale nel periodo selezionato.")
    else:
        col = colore_filiale(filiali, fil_sel)

        # KPI FILIALE
        c1,c2,c3,c4,c5,c6 = st.columns(6)
        with c1: kpi_card("Giorni",         str(agg["n_giorni"]),              "#94a3b8")
        with c2: kpi_card("Media LV AF/gg", f"{agg['media_gg_lv_af']:.0f}",   "#3b82f6")
        with c3: kpi_card("Media LV Ok/gg", f"{agg['media_gg_lv_ok']:.0f}",   "#22c55e")
        with c4: kpi_card("Media LV Rit/gg",f"{agg['media_gg_lv_rit']:.0f}",  "#a855f7")
        with c5: kpi_card("Tot LV AF",      fmt_n(agg["tot_lv_af"]),           "#3b82f6")
        with c6: kpi_card("Produttività",   f"{agg['media_prod']:.1%}",        prod_color(agg["media_prod"]))

        st.markdown("---")

        # GRAFICO ANDAMENTO GIORNALIERO
        st.markdown("#### Andamento giornaliero LV Ok")
        giorni_data = []
        for d in sorted(giornate):
            lv_ok_d  = sum(v["lv_ok"]  for v in giornate[d].values())
            lv_rit_d = sum(v["lv_rit"] for v in giornate[d].values())
            prod_d   = sum(v["lv_ok"] for v in giornate[d].values()) / \
                       max(sum(v["lv_af"] for v in giornate[d].values()), 1)
            giorni_data.append({"data": d, "lv_ok": lv_ok_d,
                                "lv_rit": lv_rit_d, "prod": prod_d})
        df_giorni = pd.DataFrame(giorni_data)

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=df_giorni["data"], y=df_giorni["lv_ok"],
            name="LV Ok", line=dict(color="#22c55e", width=2),
            fill="tozeroy", fillcolor="rgba(34,197,94,0.1)",
        ))
        fig_trend.add_trace(go.Scatter(
            x=df_giorni["data"], y=df_giorni["lv_rit"],
            name="LV Rit", line=dict(color="#a855f7", width=2),
        ))
        fig_trend.update_layout(
            plot_bgcolor="#181c24", paper_bgcolor="#0f1117",
            font_color="#f1f5f9", height=280,
            yaxis=dict(gridcolor="#2a3045"),
            xaxis=dict(gridcolor="#2a3045"),
            legend=dict(bgcolor="#1e2330"),
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig_trend, use_container_width=True)

        # TABELLA PER GIRO
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
                "Prod %":    f"{v['prod']:.1%}",
            } for g, v in sorted(per_giro.items())]
            st.dataframe(pd.DataFrame(rows_giro),
                         use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════
# TAB 3 — TUTTI I GIRI
# ══════════════════════════════════════════════════════════════
with tab3:
    st.markdown("### Tutti i Giri — Multi-Filiale")

    righe_tutti = []
    for fil in filiali:
        _, _, pg = aggrega_filiale(dati[fil], date_da, date_a)
        for giro, v in sorted(pg.items()):
            righe_tutti.append({
                "Filiale":   fil,
                "Giro":      giro,
                "Giorni":    v["n"],
                "LV AF":     round(v["lv_af"],   1),
                "LV Ok":     round(v["lv_ok"],   1),
                "LV Rit":    round(v["lv_rit"],  1),
                "Stop Ok":   round(v["stop_ok"], 1),
                "Stop Rit":  round(v["stop_rit"],1),
                "Prod %":    f"{v['prod']:.1%}",
            })

    if righe_tutti:
        df_tutti = pd.DataFrame(righe_tutti)

        # Filtro per filiale
        fil_filter = st.multiselect(
            "Filtra per filiale", filiali, default=filiali, key="filter_tutti"
        )
        df_tutti = df_tutti[df_tutti["Filiale"].isin(fil_filter)]
        st.dataframe(df_tutti, use_container_width=True, hide_index=True)

        # Download CSV
        csv = df_tutti.to_csv(index=False, sep=";").encode("utf-8-sig")
        st.download_button(
            "⬇ Scarica CSV",
            data=csv,
            file_name="tutti_giri.csv",
            mime="text/csv",
        )
    else:
        st.warning("Nessun dato nel periodo selezionato.")


# ══════════════════════════════════════════════════════════════
# TAB 4 — GIORNALIERO
# ══════════════════════════════════════════════════════════════
with tab4:
    st.markdown("### Dettaglio Giornata")

    col_a, col_b = st.columns(2)
    with col_a:
        fil_g = st.selectbox("Filiale", filiali, key="sel_fil_giorno")
    with col_b:
        date_disponibili = sorted(dati[fil_g].keys()) if fil_g in dati else []
        if date_disponibili:
            giorno_sel = st.selectbox(
                "Data",
                options=date_disponibili,
                index=len(date_disponibili) - 1,
                format_func=lambda d: d.strftime("%d/%m/%Y"),
                key="sel_data_giorno",
            )
        else:
            giorno_sel = None
            st.info("Nessuna data disponibile per questa filiale.")

    if giorno_sel and giorno_sel in dati.get(fil_g, {}):
        giri_giorno = dati[fil_g][giorno_sel]

        st.markdown(f"#### {fil_g} — {giorno_sel.strftime('%d/%m/%Y')}")

        # KPI giornata
        lv_af_g  = sum(v["lv_af"]    for v in giri_giorno.values())
        lv_ok_g  = sum(v["lv_ok"]    for v in giri_giorno.values())
        lv_rit_g = sum(v["lv_rit"]   for v in giri_giorno.values())
        stop_ok  = sum(v["stop_ok"]  for v in giri_giorno.values())
        stop_rit = sum(v["stop_rit"] for v in giri_giorno.values())
        prod_g2  = lv_ok_g / lv_af_g if lv_af_g > 0 else 0

        c1,c2,c3,c4,c5 = st.columns(5)
        with c1: kpi_card("LV Affidate", fmt_n(lv_af_g),   "#3b82f6")
        with c2: kpi_card("LV Ok",       fmt_n(lv_ok_g),   "#22c55e")
        with c3: kpi_card("LV Ritiro",   fmt_n(lv_rit_g),  "#a855f7")
        with c4: kpi_card("Stop Ok",     fmt_n(stop_ok),   "#14b8a6")
        with c5: kpi_card("Prod %",      f"{prod_g2:.1%}", prod_color(prod_g2))

        st.markdown("---")

        rows_g = [{
            "Giro":     giro,
            "LV AF":    int(v["lv_af"]),
            "LV Ok":    int(v["lv_ok"]),
            "LV Rit":   int(v["lv_rit"]),
            "Stop Ok":  int(v["stop_ok"]),
            "Stop Rit": int(v["stop_rit"]),
            "Prod %":   f"{v['prod']:.1%}",
        } for giro, v in sorted(giri_giorno.items())]
        st.dataframe(pd.DataFrame(rows_g),
                     use_container_width=True, hide_index=True)

        # Grafico a barre orizzontale per giro
        df_bar = pd.DataFrame(rows_g)
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            y=[f"Giro {r['Giro']}" for r in rows_g],
            x=[r["LV Ok"] for r in rows_g],
            name="LV Ok", orientation="h", marker_color="#22c55e",
        ))
        fig_bar.add_trace(go.Bar(
            y=[f"Giro {r['Giro']}" for r in rows_g],
            x=[r["LV Rit"] for r in rows_g],
            name="LV Rit", orientation="h", marker_color="#a855f7",
        ))
        fig_bar.update_layout(
            barmode="stack",
            plot_bgcolor="#181c24", paper_bgcolor="#0f1117",
            font_color="#f1f5f9", height=max(200, len(rows_g) * 40),
            xaxis=dict(gridcolor="#2a3045"),
            yaxis=dict(gridcolor="#2a3045"),
            legend=dict(bgcolor="#1e2330"),
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig_bar, use_container_width=True)


# ══════════════════════════════════════════════════════════════
# TAB 5 — TARIFFA
# ══════════════════════════════════════════════════════════════
with tab5:
    st.markdown("### Calcolo Tariffa a Scaglioni")

    col_fil, col_void = st.columns([2, 5])
    with col_fil:
        fil_tar = st.selectbox("Filiale", filiali, key="sel_fil_tar")

    # EDITOR SCAGLIONI
    with st.expander("⚙ Modifica scaglioni tariffa", expanded=False):
        st.caption("Modifica i valori e premi **Applica** per ricalcolare.")
        fasce_edit = []
        cols_head = st.columns([2, 2, 2, 1])
        cols_head[0].markdown("**Da (LDV)**")
        cols_head[1].markdown("**A (LDV)**")
        cols_head[2].markdown("**Prezzo €/LDV**")

        for i, fascia in enumerate(fasce):
            c1, c2, c3, _ = st.columns([2, 2, 2, 1])
            da  = c1.number_input("", value=int(fascia["da"]),   step=1000,
                                   key=f"da_{i}",  label_visibility="collapsed")
            a   = c2.number_input("", value=int(fascia["a"]),    step=1000,
                                   key=f"a_{i}",   label_visibility="collapsed")
            prc = c3.number_input("", value=float(fascia["prezzo"]), step=0.001,
                                   format="%.3f", key=f"prc_{i}",
                                   label_visibility="collapsed")
            fasce_edit.append({"da": int(da), "a": int(a), "prezzo": float(prc)})

        if st.button("✅ Applica scaglioni"):
            st.session_state.fasce = fasce_edit
            fasce = fasce_edit
            st.success("Scaglioni aggiornati.")
            st.rerun()

    st.markdown("---")

    # CALCOLO
    if fil_tar in dati:
        _, giornate_tar, _ = aggrega_filiale(dati[fil_tar], date_da, date_a)
        if giornate_tar:
            righe_tar, tot_vol, tot_fatt, media_gg = calcola_tariffa(
                giornate_tar, st.session_state.fasce
            )

            # KPI TARIFFA
            c1, c2, c3, c4 = st.columns(4)
            with c1: kpi_card("Giorni",       str(len(righe_tar)),   "#94a3b8")
            with c2: kpi_card("Volume LDV",   fmt_n(tot_vol),        "#3b82f6")
            with c3: kpi_card("Fatturato",    fmt_eur(tot_fatt),     "#22c55e")
            with c4: kpi_card("Media/giorno", fmt_eur(media_gg),     "#f59e0b")

            st.markdown("---")

            # GRAFICO FATTURATO GIORNALIERO
            st.markdown("#### Fatturato giornaliero")
            df_tar = pd.DataFrame(righe_tar)
            fig_tar = go.Figure(go.Bar(
                x=df_tar["data"], y=df_tar["fatturato"],
                marker_color="#22c55e",
                text=[fmt_eur(v) for v in df_tar["fatturato"]],
                textposition="outside",
            ))
            fig_tar.update_layout(
                plot_bgcolor="#181c24", paper_bgcolor="#0f1117",
                font_color="#f1f5f9", height=280,
                yaxis=dict(gridcolor="#2a3045", tickprefix="€ "),
                xaxis=dict(gridcolor="#2a3045"),
                margin=dict(l=0, r=0, t=30, b=0),
            )
            st.plotly_chart(fig_tar, use_container_width=True)

            # TABELLA DETTAGLIO
            st.markdown("#### Dettaglio per giorno")
            df_tar_show = df_tar[["data", "lv_ok", "lv_rit",
                                  "volume", "fatturato", "dettaglio"]].copy()
            df_tar_show.columns = ["Data", "LV Ok", "LV Rit",
                                   "Volume", "Fatturato €", "Dettaglio scaglioni"]
            df_tar_show["Fatturato €"] = df_tar_show["Fatturato €"].apply(fmt_eur)
            st.dataframe(df_tar_show, use_container_width=True, hide_index=True)

            # Download
            csv_tar = df_tar_show.to_csv(index=False, sep=";").encode("utf-8-sig")
            st.download_button(
                "⬇ Scarica CSV tariffa",
                data=csv_tar,
                file_name=f"tariffa_{fil_tar}.csv",
                mime="text/csv",
            )
        else:
            st.warning("Nessun dato per questa filiale nel periodo selezionato.")
