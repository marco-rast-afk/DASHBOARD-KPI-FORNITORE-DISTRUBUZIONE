# core.py — Logica di calcolo estratta da dashboard_performance_SDA_v3.pyw
# Questo file NON ha interfaccia grafica: solo le funzioni pure di lettura e calcolo.

from datetime import datetime, date
import pandas as pd

# Fasce di default se non specificate diversamente per la filiale
FASCE_DEFAULT = [
    {"da": 0,       "a": 50000,  "prezzo": 3.190},
    {"da": 50000,   "a": 60000,  "prezzo": 3.050},
]

# Dizionario per gestire tariffe a 2 scaglioni personalizzate per ogni filiale
FASCE_PER_FILIALE = {
    "ROMA": [
        {"da": 0, "a": 45000, "prezzo": 3.250},
        {"da": 45000, "a": 90000, "prezzo": 3.100},
    ],
    "MILANO": [
        {"da": 0, "a": 55000, "prezzo": 3.150},
        {"da": 55000, "a": 100000, "prezzo": 2.950},
    ],
    # Aggiungere qui le altre filiali con i rispettivi 2 scaglioni
}


def ottieni_fasce_filiale(id_filiale):
    """
    Restituisce le fasce a 2 scaglioni specifiche per la filiale.
    Se la filiale non è censita in FASCE_PER_FILIALE, restituisce FASCE_DEFAULT.
    """
    filiale_pulita = str(id_filiale).strip()
    return FASCE_PER_FILIALE.get(filiale_pulita, FASCE_DEFAULT)


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
        # Corretto il bug originario in cui veniva cercato "lv_tot" anziché "ldv_tot"
        if dati["lv_af"] > 0:
            dati["prod"] = dati["ldv_tot"]

        risultato.setdefault(filiale, {})
        risultato[filiale].setdefault(data_key, {})
        risultato[filiale][data_key][giro] = dati

    return risultato


def aggrega_filiale(dati_filiale, date_da=None, date_a=None):
    """
    Aggrega i dati di una singola filiale nel periodo indicato.
    Calcola la produttività giornaliera e totale secondo le nuove specifiche.
    Restituisce (agg, giornate, per_giro).
    """
    giornate = {
        d: giri for d, giri in sorted(dati_filiale.items())
        if (date_da is None or d >= date_da) and (date_a is None or d <= date_a) and giri
    }

    if not giornate:
        return None, {}, {}

    n = len(giornate)

    # 1. Calcolo Produttività Giornaliera per ciascuna data: (Somma di LDV OK + LDV RITIRATE) / Numero dei corrieri
    prod_giornaliere = {}
    for d, giri in giornate.items():
        # Somma delle LDV OK + LDV RITIRATE di tutti i giri della giornata
        tot_ldv_giorno = sum(v.get("lv_ok", 0) + v.get("lv_rit", 0) for v in giri.values())
        n_corrieri = len(giri) # Il numero di giri attivi rappresenta il numero dei corrieri
        prod_giornaliere[d] = tot_ldv_giorno / n_corrieri if n_corrieri > 0 else 0.0
        
        # Iniettiamo la produttività giornaliera nei singoli giri per renderla disponibile a valle
        for g in giri:
            giri[g]["prod_giornaliera"] = prod_giornaliere[d]

    # 2. Calcolo Produttività Totale: Somma delle produttività giornaliere diviso il numero di giorni feriali (esclusi Sabato e Domenica)
    giorni_feriali = [d for d in giornate if d.weekday() < 5] # 0=Lunedì, ..., 4=Venerdì (5=Sabato, 6=Domenica)
    if giorni_feriali:
        produttivita_totale = sum(prod_giornaliere[d] for d in giorni_feriali) / len(giorni_feriali)
    else:
        produttivita_totale = 0.0

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
        "n_giorni":            n,
        "media_lv_af":         media_per_giro("lv_af"),
        "media_lv_ok":         media_per_giro("lv_ok"),
        "media_lv_rit":        media_per_giro("media_lv_rit"), # Backup in case someone uses it, but we use media_per_giro Below
        "media_prod":          produttivita_totale,            # Aggiornato con la produttività totale al netto di Sab/Dom
        "produttivita_totale": produttivita_totale,            # Chiave esplicita per chiarezza
        "tot_lv_af":           totale("lv_af"),
        "tot_lv_ok":           totale("lv_ok"),
        "tot_lv_rit":          totale("lv_rit"),               # Corretto il bug originario ("tot_lv_rit")
        "tot_stop_ok":         totale("stop_ok"),
        "tot_stop_rit":        totale("stop_rit"),
        "media_gg_lv_af":      media_giornaliera("lv_af"),
        "media_gg_lv_ok":      media_giornaliera("lv_ok"),
        "media_gg_lv_rit":     media_giornaliera("lv_rit"),
    }
    # Ripristiniamo la corretta chiamata a media_per_giro per la chiave "media_lv_rit"
    agg["media_lv_rit"] = media_per_giro("lv_rit")

    tutti_giri = sorted({g for day in giornate.values() for g in day})
    per_giro = {}
    for giro in tutti_giri:
        vals = [day[giro] for day in giornate.values() if giro in day]
        if not vals:
            continue
        n_g = len(vals)
        per_giro[giro] = {
            "n":                  n_g,
            "lv_af":              sum(v["lv_af"]    for v in vals) / n_g,
            "lv_ok":              sum(v["lv_ok"]    for v in vals) / n_g,
            "lv_rit":             sum(v["lv_rit"]   for v in vals) / n_g,
            "stop_ok":            sum(v["stop_ok"]  for v in vals) / n_g,
            "stop_rit":           sum(v["stop_rit"] for v in vals) / n_g,
            "prod_giornaliera":   sum(v.get("prod_giornaliera", 0) for v in vals) / n_g,
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
