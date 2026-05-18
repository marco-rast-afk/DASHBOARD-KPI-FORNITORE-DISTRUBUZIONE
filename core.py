# core.py — Logica di calcolo per Dashboard Performance SDA
from datetime import datetime, date
import pandas as pd

# Fasce di ripiego se la filiale non è censita nel dizionario personalizzato
FASCE_DEFAULT = [
    {"da": 0,       "a": 50000,  "prezzo": 3.190},
    {"da": 50000,   "a": 60000,  "prezzo": 3.050},
]

# DIZIONARIO PERSONALIZZATO: Configura qui i 2 scaglioni per ogni filiale.
# IMPORTANTE: Usa lo stesso identico nome/ID che compare nel file Excel (es. "AP", "ROMA", ecc.)
FASCE_PER_FILIALE = {
    "AP": [
        {"da": 0,     "a": 40000,  "prezzo": 3.250},
        {"da": 40000, "a": 80000,  "prezzo": 3.100},
    ],
    "AV": [
        {"da": 0,     "a": 45000,  "prezzo": 3.300},
        {"da": 45000, "a": 90000,  "prezzo": 3.150},
    ],
    "FG": [
        {"da": 0,     "a": 55000,  "prezzo": 3.150},
        {"da": 55000, "a": 100000, "prezzo": 2.950},
    ],
    # Puoi aggiungere tutte le filiali che desideri seguendo questa struttura...
}

def ottieni_fasce_filiale(id_filiale):
    """
    Restituisce le fasce a 2 scaglioni specifiche per la filiale indicata.
    Se la filiale non è presente nel dizionario personalizzato, restituisce le FASCE_DEFAULT.
    """
    filiale_pulita = str(id_filiale).strip()
    return FASCE_PER_FILIALE.get(filiale_pulita, FASCE_DEFAULT)


def leggi_file_corrieri(path_o_buffer, engine="openpyxl"):
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
                data_key = datetime.fromordinal(datetime(1899, 12, 30).toordinal() + int(raw_data)).date()
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
            "stop_ok":  _f(row.get("STOP OK")),
            "stop_rit": _f(row.get("STOP RIT")),
        }
        risultato.setdefault(filiale, {})
        risultato[filiale].setdefault(data_key, {})
        risultato[filiale][data_key][giro] = dati

    return risultato

def aggrega_filiale(dati_filiale, date_da=None, date_a=None):
    giornate = {
        d: giri for d, giri in sorted(dati_filiale.items())
        if (date_da is None or d >= date_da) and (date_a is None or d <= date_a) and giri
    }
    if not giornate:
        return None, {}, {}

    n = len(giornate)
    
    # Calcolo produttività specifica giorno per giorno per ogni singolo giro
    for d, giri in giornate.items():
        for g in giri:
            giri[g]["prod_specifica_giro"] = giri[g].get("lv_ok", 0.0) + giri[g].get("lv_rit", 0.0)

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

    tot_corrieri_giorno = sum(len(day) for day in giornate.values())
    tot_ok_rit = totale("lv_ok") + totale("lv_rit")
    media_produttivita_corrieri = tot_ok_rit / tot_corrieri_giorno if tot_corrieri_giorno > 0 else 0.0

    agg = {
        "n_giorni":            n,
        "media_lv_af":         media_per_giro("lv_af"),
        "media_lv_ok":         media_per_giro("lv_ok"),
        "media_lv_rit":        media_per_giro("lv_rit"),
        "media_prod":          media_produttivita_corrieri,  
        "produttivita_totale": media_produttivita_corrieri,  
        "tot_lv_af":           totale("lv_af"),
        "tot_lv_ok":           totale("lv_ok"), 
        "tot_lv_rit":          totale("lv_rit"),     
        "tot_stop_ok":         totale("stop_ok"),
        "tot_stop_rit":        totale("stop_rit"),
        "media_gg_lv_af":      media_giornaliera("lv_af"),
        "media_gg_lv_ok":      media_giornaliera("lv_ok"),
        "media_gg_lv_rit":     media_giornaliera("lv_rit"),
    }

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
            "prod_giro_corretta": sum(v.get("prod_specifica_giro", 0.0) for v in vals) / n_g,
        }

    return agg, giornate, per_giro

def calcola_tariffa(giornate_filiale, fasce):
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
                dettaglio_parti.append(f"Sc.{idx+1}: {int(quota):,} x EUR{prc:.3f} = EUR{parz:,.2f}")

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