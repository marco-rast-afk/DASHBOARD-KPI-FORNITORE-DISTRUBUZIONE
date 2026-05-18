# core.py — Logica di calcolo Dashboard Performance SDA
#
# PRODUTTIVITÀ = LDV OK+RIT  (colonna R del file Excel)
#   Valore assoluto: somma LV OK + somma LV RIT per giro/giornata.
#   NON è un rapporto percentuale, non coinvolge LV AFF.

from datetime import datetime, date
import pandas as pd

# ─────────────────────────────────────────────────────────────
# SCAGLIONI TARIFFA DEFAULT (7 fasce, marginali per giorno)
# ─────────────────────────────────────────────────────────────
FASCE_DEFAULT = [
    {"da":      0, "a":  50000, "prezzo": 1.000},
    {"da":  50000, "a":  60000, "prezzo": 1.000},
 ]


# ─────────────────────────────────────────────────────────────
# LETTURA FILE EXCEL
# ─────────────────────────────────────────────────────────────
def leggi_file_corrieri(path_o_buffer, engine="openpyxl"):
    """
    Legge Performance_Corrieri.xlsx (header alla riga 6, indice 5).

    Colonne rilevanti:
      id_filiale   | data_presenza | giro
      LV AFF       | LV OK         | LV RIT
      LDV OK+RIT   ← produttività (col R, già calcolata alla fonte)
      STOP OK      | STOP RIT

    Restituisce:
        dict { filiale: { date: { giro(int): { ... } } } }
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
        elif isinstance(raw_data, date):
            data_key = raw_data
        elif isinstance(raw_data, (int, float)):
            try:
                data_key = datetime.fromordinal(
                    datetime(1899, 12, 30).toordinal() + int(raw_data)
                ).date()
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

        lv_ok  = _f(row.get("LV OK"))
        lv_rit = _f(row.get("LV RIT"))

        # Colonna R: usa il valore del file; se assente/zero ricalcola
        ldv_raw = _f(row.get("LDV OK+RIT"))
        ldv_tot = ldv_raw if ldv_raw > 0 else (lv_ok + lv_rit)

        dati = {
            "lv_af":    _f(row.get("LV AFF")),
            "lv_ok":    lv_ok,
            "lv_rit":   lv_rit,
            "ldv_tot":  ldv_tot,   # ← PRODUTTIVITÀ: LDV OK+RIT (colonna R)
            "stop_ok":  _f(row.get("STOP OK")),
            "stop_rit": _f(row.get("STOP RIT")),
        }

        risultato.setdefault(filiale, {})
        risultato[filiale].setdefault(data_key, {})
        risultato[filiale][data_key][giro] = dati

    return risultato


# ─────────────────────────────────────────────────────────────
# AGGREGAZIONE PER FILIALE
# ─────────────────────────────────────────────────────────────
def aggrega_filiale(dati_filiale, date_da=None, date_a=None):
    """
    Aggrega i dati di una singola filiale nel periodo indicato.

    Produttività (media_prod) = media giornaliera di LDV OK+RIT
        per ogni giorno: somma ldv_tot di tutti i giri
        poi: media di quei totali giornalieri sul periodo

    Restituisce (agg, giornate, per_giro).
    """
    giornate = {
        d: giri
        for d, giri in sorted(dati_filiale.items())
        if (date_da is None or d >= date_da)
        and (date_a  is None or d <= date_a)
        and giri
    }

    if not giornate:
        return None, {}, {}

    n = len(giornate)

    def _media_giornaliera(campo):
        """Somma il campo per tutti i giri del giorno, poi fa la media tra i giorni."""
        vals = [sum(r.get(campo, 0) for r in day.values()) for day in giornate.values()]
        return sum(vals) / len(vals) if vals else 0.0

    def _totale(campo):
        return sum(r.get(campo, 0) for day in giornate.values() for r in day.values())

    agg = {
        "n_giorni":        n,
        # Medie giornaliere (somma tutti i giri del giorno → media tra giorni)
        "media_gg_lv_af":  _media_giornaliera("lv_af"),
        "media_gg_lv_ok":  _media_giornaliera("lv_ok"),
        "media_gg_lv_rit": _media_giornaliera("lv_rit"),
        # Produttività = media giornaliera di LDV OK+RIT (valore assoluto)
        "media_prod":      _media_giornaliera("ldv_tot"),
        # Totali di periodo
        "tot_lv_af":       _totale("lv_af"),
        "tot_lv_ok":       _totale("lv_ok"),
        "tot_lv_rit":      _totale("lv_rit"),
        "tot_ldv":         _totale("ldv_tot"),
        "tot_stop_ok":     _totale("stop_ok"),
        "tot_stop_rit":    _totale("stop_rit"),
    }

    # Dettaglio per giro: medie sul numero di giorni in cui il giro è presente
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
            "ldv_tot":  sum(v["ldv_tot"]  for v in vals) / n_g,  # produttività media per giro
            "stop_ok":  sum(v["stop_ok"]  for v in vals) / n_g,
            "stop_rit": sum(v["stop_rit"] for v in vals) / n_g,
        }

    return agg, giornate, per_giro


# ─────────────────────────────────────────────────────────────
# CALCOLO TARIFFA A SCAGLIONI
# ─────────────────────────────────────────────────────────────
def calcola_tariffa(giornate_filiale, fasce):
    """
    Calcola fatturato con scaglioni marginali che si azzerano ogni giorno.
    Volume di riferimento = LDV OK+RIT (ldv_tot), colonna R.

    Restituisce (righe, tot_vol, tot_fatt, media_gg).
    """
    righe = []
    tot_vol = tot_fatt = n_giorni = 0

    for d in sorted(giornate_filiale):
        giri_day = giornate_filiale[d]

        # Volume giornaliero = somma ldv_tot di tutti i giri
        vol = sum(v.get("ldv_tot", 0) for v in giri_day.values())
        # Per il dettaglio mostriamo anche lv_ok e lv_rit separati
        lv_ok  = sum(v.get("lv_ok",  0) for v in giri_day.values())
        lv_rit = sum(v.get("lv_rit", 0) for v in giri_day.values())

        residuo     = float(vol)
        fatt_giorno = 0.0
        dettaglio_parti = []

        for idx, fascia in enumerate(fasce):
            da       = fascia["da"]
            a        = fascia["a"]
            prc      = fascia["prezzo"]
            capienza = max(0, a - da)
            if residuo > 0 and capienza > 0:
                quota        = min(residuo, capienza)
                parz         = quota * prc
                fatt_giorno += parz
                residuo     -= quota
                dettaglio_parti.append(
                    f"Sc.{idx+1}: {int(quota):,} × €{prc:.3f} = €{parz:,.2f}"
                )

        tot_vol   += vol
        tot_fatt  += fatt_giorno
        n_giorni  += 1

        righe.append({
            "data":      d,
            "lv_ok":     int(lv_ok),
            "lv_rit":    int(lv_rit),
            "volume":    int(vol),
            "fatturato": round(fatt_giorno, 2),
            "dettaglio": " | ".join(dettaglio_parti) if dettaglio_parti else "nessun LDV",
        })

    media_gg = tot_fatt / n_giorni if n_giorni else 0.0
    return righe, tot_vol, tot_fatt, media_gg
