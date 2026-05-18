# core.py — Logica di calcolo estratta da dashboard_performance_SDA_v3.pyw
# Questo file NON ha interfaccia grafica: solo le funzioni pure di lettura e calcolo.

from datetime import datetime, date
import pandas as pd

FASCE_DEFAULT = [
    {"da": 0,       "a": 50000,  "prezzo": 3.190},
    {"da": 50000,   "a": 60000,  "prezzo": 3.050},
    {"da": 60000,   "a": 70000,  "prezzo": 2.950},
    {"da": 70000,   "a": 80000,  "prezzo": 2.850},
    {"da": 80000,   "a": 90000,  "prezzo": 2.750},
    {"da": 90000,   "a": 100000, "prezzo": 2.650},
    {"da": 100000,  "a": 999999, "prezzo": 2.550},
]


def leggi_file_corrieri(path_o_buffer, engine="openpyxl"):
    """
    Legge Performance_Corrieri.xlsx.
    Accetta sia un path su disco sia un buffer (es. file caricato da Streamlit).
    Restituisce dict: {filiale: {data: {giro: {...}}}}
    """
    df = pd.read_excel(path_o_buffer, header=5, engine=engine)
    df = df.dropna(subset=["id_filiale"])
    df["id_filiale"] = df["id_filiale"].astype(str).str.strip()
    df = df[df["id_filiale"].str.strip() != ""]
    df.columns = [str(c).strip() for c in df.columns]

    def _f(v):
        try:
            return float(v) if v is not None and str(v).strip() not in ("", "nan") else 0.0
        except (TypeError, ValueError):
            return 0.0

    risultato = {}

    for _, row in df.iterrows():
        filiale = str(row["id_filiale"]).strip()
        if not filiale or filiale == "nan":
            continue

        raw_data = row.get("data_presenza")
        if isinstance(raw_data, datetime):
            data_key = raw_data.date()
        elif isinstance(raw_data, (int, float)):
            try:
                data_key = datetime.fromordinal(
                    datetime(1899, 12, 30).toordinal() + int(raw_data)).date()
            except Exception:
                continue
        else:
            continue

        try:
            giro = int(_f(row.get("giro", 0)))
            if giro <= 0:
                continue
        except (TypeError, ValueError):
            continue

        dati = {
            "lv_af":    _f(row.get("LV AFF")),
            "lv_ok":    _f(row.get("LV OK")),
            "lv_rit":   _f(row.get("LV RIT")),
            "ldv_tot":  _f(row.get("LDV OK+RIT")),
            "stop_ok":  _f(row.get("STOP OK")),
            "stop_rit": _f(row.get("STOP RIT")),
            "prod":     0.0,
        }
        if dati["lv_af"] > 0:
            dati["prod"] = dati["lv_ok"] / dati["lv_af"]

        risultato.setdefault(filiale, {})
        risultato[filiale].setdefault(data_key, {})
        risultato[filiale][data_key][giro] = dati

    return risultato


def aggrega_filiale(dati_filiale, date_da=None, date_a=None):
    """
    Aggrega i dati di una singola filiale nel periodo indicato.
    Restituisce (agg, giornate, per_giro).
    """
    giornate = {
        d: giri for d, giri in sorted(dati_filiale.items())
        if (date_da is None or d >= date_da) and (date_a is None or d <= date_a) and giri
    }

    if not giornate:
        return None, {}, {}

    n = len(giornate)

    def media_per_giro(campo):
        vals = []
        for day in giornate.values():
            v = [r[campo] for r in day.values() if r.get(campo) is not None]
            if v:
                vals.append(sum(v) / len(v))
        return sum(vals) / len(vals) if vals else 0.0

    def media_giornaliera(campo):
        vals = [sum(r.get(campo, 0) for r in day.values()) for day in giornate.values()]
        return sum(vals) / len(vals) if vals else 0.0

    def totale(campo):
        return sum(r.get(campo, 0) for day in giornate.values() for r in day.values())

    agg = {
        "n_giorni":        n,
        "media_lv_af":     media_per_giro("lv_af"),
        "media_lv_ok":     media_per_giro("lv_ok"),
        "media_lv_rit":    media_per_giro("lv_rit"),
        "media_prod":      media_per_giro("prod"),
        "tot_lv_af":       totale("lv_af"),
        "tot_lv_ok":       totale("lv_ok"),
        "tot_lv_rit":      totale("lv_rit"),
        "tot_stop_ok":     totale("stop_ok"),
        "tot_stop_rit":    totale("stop_rit"),
        "media_gg_lv_af":  media_giornaliera("lv_af"),
        "media_gg_lv_ok":  media_giornaliera("lv_ok"),
        "media_gg_lv_rit": media_giornaliera("lv_rit"),
    }

    tutti_giri = sorted({g for day in giornate.values() for g in day})
    per_giro = {}
    for giro in tutti_giri:
        vals = [day[giro] for day in giornate.values() if giro in day]
        if not vals:
            continue
        n_g = len(vals)
        per_giro[giro] = {
            "n":        n_g,
            "lv_af":    sum(v["lv_af"]    for v in vals) / n_g,
            "lv_ok":    sum(v["lv_ok"]    for v in vals) / n_g,
            "lv_rit":   sum(v["lv_rit"]   for v in vals) / n_g,
            "stop_ok":  sum(v["stop_ok"]  for v in vals) / n_g,
            "stop_rit": sum(v["stop_rit"] for v in vals) / n_g,
            "prod":     sum(v["prod"]     for v in vals) / n_g,
        }

    return agg, giornate, per_giro


def calcola_tariffa(giornate_filiale, fasce):
    """
    Calcola fatturato giornaliero con logica a scaglioni progressivi.
    Restituisce lista di dict con dettaglio per giorno.
    """
    righe = []
    tot_vol = tot_fatt = n_giorni = 0

    for d in sorted(giornate_filiale):
        giri_day = giornate_filiale[d]
        lv_ok  = sum(v.get("lv_ok",  0) for v in giri_day.values())
        lv_rit = sum(v.get("lv_rit", 0) for v in giri_day.values())
        vol    = lv_ok + lv_rit

        residuo = float(vol)
        fatt_giorno = 0.0
        dettaglio_parti = []

        for idx, fascia in enumerate(fasce):
            da  = fascia["da"]
            a   = fascia["a"]
            prc = fascia["prezzo"]
            capienza = max(0, a - da)
            if residuo > 0 and capienza > 0:
                quota = min(residuo, capienza)
                parz  = quota * prc
                fatt_giorno += parz
                residuo     -= quota
                dettaglio_parti.append(f"Sc.{idx+1}: {int(quota):,} × €{prc:.3f} = €{parz:,.2f}")

        tot_vol   += vol
        tot_fatt  += fatt_giorno
        n_giorni  += 1

        righe.append({
            "data":         d.strftime("%d/%m/%Y"),
            "lv_ok":        int(lv_ok),
            "lv_rit":       int(lv_rit),
            "volume":       int(vol),
            "fatturato":    round(fatt_giorno, 2),
            "dettaglio":    " | ".join(dettaglio_parti) if dettaglio_parti else "nessun LDV",
        })

    return righe, tot_vol, tot_fatt, (tot_fatt / n_giorni if n_giorni else 0)
