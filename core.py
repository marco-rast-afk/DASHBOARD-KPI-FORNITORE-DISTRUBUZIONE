# core.py — Logica di calcolo per Dashboard Performance SDA
#
# PRODUTTIVITÀ GIORNALIERA:
#   = somma(LDV OK+RIT colonna R di tutti i giri del giorno) / numero giri presenti
# MEDIA PRODUTTIVITÀ FILIALE:
#   = somma(prod_giornaliera) / giorni lavorativi  [SABATI ESCLUSI, weekday != 5]

from datetime import datetime, date
import pandas as pd

# Fasce di ripiego se la filiale non è censita nel dizionario personalizzato
FASCE_DEFAULT = [
    {"da": 0,       "a": 50000,  "prezzo": 3.190},
    {"da": 50000,   "a": 60000,  "prezzo": 3.050},
]

# DIZIONARIO PERSONALIZZATO: 2 scaglioni per filiale.
# Usa lo stesso identico nome/ID che compare nel file Excel (es. "AP", "ROMA", ecc.)
FASCE_PER_FILIALE = {
    "AP": [
        {"da": 0,    "a": 6142,   "prezzo": 3.190},
        {"da": 6143, "a": 10000,  "prezzo": 3.040},
    ],
    "AV": [
        {"da": 0,     "a": 45000,  "prezzo": 3.300},
        {"da": 45000, "a": 90000,  "prezzo": 3.150},
    ],
    "FG": [
        {"da": 0,     "a": 55000,  "prezzo": 3.150},
        {"da": 55000, "a": 100000, "prezzo": 2.950},
    ],
}

def ottieni_fasce_filiale(id_filiale):
    """Restituisce le fasce specifiche per filiale, o FASCE_DEFAULT se non censita."""
    return FASCE_PER_FILIALE.get(str(id_filiale).strip(), FASCE_DEFAULT)

def _is_lavorativo(d: date) -> bool:
    """True se il giorno NON è sabato (weekday 5)."""
    return d.weekday() != 5


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

        lv_ok  = _f(row.get("LV OK"))
        lv_rit = _f(row.get("LV RIT"))
        # Colonna R: usa il valore del file; se zero/assente ricalcola
        ldv_raw = _f(row.get("LDV OK+RIT"))
        ldv_tot = ldv_raw if ldv_raw > 0 else (lv_ok + lv_rit)

        risultato.setdefault(filiale, {})
        risultato[filiale].setdefault(data_key, {})
        risultato[filiale][data_key][giro] = {
            "lv_af":    _f(row.get("LV AFF")),
            "lv_ok":    lv_ok,
            "lv_rit":   lv_rit,
            "ldv_tot":  ldv_tot,   # LDV OK+RIT colonna R — base produttività
            "stop_ok":  _f(row.get("STOP OK")),
            "stop_rit": _f(row.get("STOP RIT")),
        }

    return risultato


def aggrega_filiale(dati_filiale, date_da=None, date_a=None):
    giornate = {
        d: giri for d, giri in sorted(dati_filiale.items())
        if (date_da is None or d >= date_da) and (date_a is None or d <= date_a) and giri
    }
    if not giornate:
        return None, {}, {}

    # ── Produttività giornaliera ──────────────────────────────
    # = somma(ldv_tot tutti i giri del giorno) / numero giri presenti
    def _prod_giorno(giri):
        n = len(giri)
        return sum(v.get("ldv_tot", 0) for v in giri.values()) / n if n > 0 else 0.0

    prod_per_giorno = {d: _prod_giorno(giri) for d, giri in giornate.items()}

    # ── Media produttività: solo giorni lavorativi (sabati esclusi) ──
    giorni_lav = [d for d in giornate if _is_lavorativo(d)]
    n_lav = len(giorni_lav)
    if n_lav > 0:
        media_prod = sum(prod_per_giorno[d] for d in giorni_lav) / n_lav
    else:
        media_prod = sum(prod_per_giorno.values()) / len(giornate)

    n_tot = len(giornate)

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
        "n_giorni":            n_lav,          # giorni lavorativi (sabati esclusi)
        "n_giorni_tot":        n_tot,           # tutti i giorni con dati
        "media_prod":          media_prod,      # LDV/corriere su gg lavorativi
        "produttivita_totale": media_prod,      # alias per compatibilità app.py
        "prod_per_giorno":     prod_per_giorno, # dict data→float per grafici
        "media_lv_af":         media_per_giro("lv_af"),
        "media_lv_ok":         media_per_giro("lv_ok"),
        "media_lv_rit":        media_per_giro("lv_rit"),
        "tot_lv_af":           totale("lv_af"),
        "tot_lv_ok":           totale("lv_ok"),
        "tot_lv_rit":          totale("lv_rit"),
        "tot_ldv":             totale("ldv_tot"),  # tot LDV OK+RIT del periodo
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
            "ldv_tot":            sum(v["ldv_tot"]  for v in vals) / n_g,
            "stop_ok":            sum(v["stop_ok"]  for v in vals) / n_g,
            "stop_rit":           sum(v["stop_rit"] for v in vals) / n_g,
            # alias mantenuto per compatibilità con eventuali riferimenti residui
            "prod_giro_corretta": sum(v["ldv_tot"]  for v in vals) / n_g,
        }

    return agg, giornate, per_giro


def calcola_tariffa(giornate_filiale, fasce):
    righe = []
    tot_vol = tot_fatt = n_giorni = 0

    for d in sorted(giornate_filiale):
        giri_day = giornate_filiale[d]
        # Volume = ldv_tot (colonna R); fallback lv_ok+lv_rit
        vol    = sum(v.get("ldv_tot", v.get("lv_ok", 0) + v.get("lv_rit", 0))
                     for v in giri_day.values())
        lv_ok  = sum(v.get("lv_ok",  0) for v in giri_day.values())
        lv_rit = sum(v.get("lv_rit", 0) for v in giri_day.values())

        residuo = float(vol)
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
                    f"Sc.{idx+1}: {int(quota):,} x EUR{prc:.3f} = EUR{parz:,.2f}")

        tot_vol   += vol
        tot_fatt  += fatt_giorno
        n_giorni  += 1

        righe.append({
            "data":      d.strftime("%d/%m/%Y"),
            "lv_ok":     int(lv_ok),
            "lv_rit":    int(lv_rit),
            "volume":    int(vol),
            "fatturato": round(fatt_giorno, 2),
            "dettaglio": " | ".join(dettaglio_parti) if dettaglio_parti else "nessun LDV",
        })

    return righe, tot_vol, tot_fatt, (tot_fatt / n_giorni if n_giorni else 0)
