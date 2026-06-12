# scoring.py — REIV Market Scorer v2.0
# Moteur de scoring enrichi :
# - Normalisation robuste (percentile rank + z-score)
# - Pondération par fiabilité source
# - Transformation non-linéaire (rendements décroissants)
# - Détection outliers (IQR)
# - Indice de confiance par marché
# - Vintage penalty
# - Déduplication corrélations (RevPAR / Occ / ADR)

import numpy as np
from scipy import stats
from data import DIMS

# ── Constantes ────────────────────────────────────────────────────────────────

# Fiabilité source par variable (0-1)
# 1.0 = STR certifié | 0.7 = rapport institutionnel | 0.4 = estimation proxy
SOURCE_RELIABILITY = {
    "revpar":    1.0,  # STR
    "occ":       1.0,  # STR
    "adr":       1.0,  # STR
    "revpar_g":  0.9,  # STR N vs N-1
    "pip_ratio": 0.8,  # STR pipeline
    "rooms_g":   0.8,  # STR
    "saturation":0.6,  # calcul proxy
    "vol_tx":    0.7,  # JLL/CBRE/Cushman
    "caprate":   0.7,  # JLL/CBRE/Cushman
    "nb_deals":  0.7,  # JLL/CBRE/Cushman
    # Macro hôteliers v3.4 — causalité directe RevPAR/EBITDA
    "revpar_elast":  0.65,  # proxy CBRE taxonomie + mix demande
    "spend_visitor": 0.70,  # UNWTO + Eurostat accommodation spend
    "connect":       0.50,  # estimation proxy
    "labour_cost":   0.80,  # CBRE/Eurostat — direct sur EBITDA
    "energy_cost":   0.65,  # Eurostat electricity prices + mix national
    # Risque
    "pol_risk":  0.60,  # Coface/subjectif
    "reg_stab":  0.50,  # subjectif 1-5
    "geo_exp":   0.50,  # subjectif 1-5
    # O'Neill 2023 — Cornell / CBRE, 3219 hôtels
    "goppar_rsd":       0.85,
    "hotel_class_risk": 0.80,
    "loc_type_risk":    0.75,
    # HVS 2025 European Hotel Valuation Index
    "hvi_index": 0.85,
    "hvi_cagr":  0.80,
    # ESG
    "cert_pct":  0.50,
    "reg_esg":   0.50,
    "tax_eu":    0.60,
    # Faisabilité
    "dev_cost":       0.65,
    "dev_revpar_idx": 0.70,
    "yield_on_cost":  0.65,
}

NONLINEAR = {
    "occ":            "diminishing",
    "revpar":         "sqrt",
    "adr":            "sqrt",
    "vol_tx":         "log",
    "nb_deals":       "log",
    "pip_ratio":      "sigmoid",
    "connect":        "linear",
    "revpar_g":       "linear",
    "rooms_g":        "linear",
    "saturation":     "linear",
    "caprate":        "linear",
    "pol_risk":       "linear",
    "reg_stab":       "linear",
    "geo_exp":        "linear",
    # Macro hôteliers v3.4
    "revpar_elast":   "linear",   # 0-1 → bornes naturelles
    "spend_visitor":  "sqrt",     # outliers haut (Paris/Dubaï) atténués
    "labour_cost":    "linear",
    "energy_cost":    "linear",
    # O'Neill 2023
    "goppar_rsd":       "linear",
    "hotel_class_risk": "linear",
    "loc_type_risk":    "linear",
    "cert_pct":         "sqrt",
    "reg_esg":          "linear",
    "tax_eu":           "linear",
    # HVS 2025
    "hvi_index":      "sqrt",
    "hvi_cagr":       "linear",
    # Faisabilité
    "dev_cost":       "log",
    "dev_revpar_idx": "sqrt",
    "yield_on_cost":  "linear",
}

# Variables corrélées — éviter double-comptage
# RevPAR ≈ Occ × ADR → on réduit le poids effectif si les trois sont présents
CORRELATED_GROUPS = [
    ["revpar", "occ", "adr"],  # RevPAR = Occ × ADR
]

# Vintage penalty : pénalité si données trop anciennes
# clé = nb mois max acceptable, valeur = pénalité multiplicative
VINTAGE_THRESHOLDS = {12: 1.0, 18: 0.92, 24: 0.82, 36: 0.65}


# ── Transformations non-linéaires ────────────────────────────────────────────

def apply_transform(values: list, transform: str) -> list:
    """Applique une transformation non-linéaire avant normalisation."""
    arr = np.array(values, dtype=float)
    mn = arr.min()

    # Shift pour valeurs négatives
    if mn < 0:
        arr = arr - mn + 1e-6

    if transform == "log":
        arr = np.log1p(arr)
    elif transform == "sqrt":
        arr = np.sqrt(arr)
    elif transform == "sigmoid":
        # Sigmoid centrée sur la médiane du panel
        med = np.median(arr)
        std = arr.std() + 1e-6
        arr = 1 / (1 + np.exp(-(arr - med) / std))
    elif transform == "diminishing":
        # Rendements décroissants : racine cubique
        arr = np.cbrt(arr)
    # "linear" : pas de transformation

    return list(arr)


# ── Détection outliers ────────────────────────────────────────────────────────

def detect_outliers_iqr(values: list) -> list:
    """
    Détecte les outliers par méthode IQR (Tukey).
    Retourne les indices outliers.
    """
    arr = np.array(values, dtype=float)
    q1, q3 = np.percentile(arr, 25), np.percentile(arr, 75)
    iqr = q3 - q1
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return [i for i, v in enumerate(values) if v < lower or v > upper]


def winsorize(values: list, limits=(0.05, 0.05)) -> list:
    """Winsorisation : plafonne les extrêmes aux percentiles 5-95."""
    arr = np.array(values, dtype=float)
    p_low = np.percentile(arr, limits[0] * 100)
    p_high = np.percentile(arr, (1 - limits[1]) * 100)
    return list(np.clip(arr, p_low, p_high))


# ── Normalisation robuste ─────────────────────────────────────────────────────

def normalize_percentile(values: list, direction: int) -> list:
    """
    Normalisation par rang percentile (0-100).
    Plus robuste que min-max face aux outliers.
    """
    arr = np.array(values, dtype=float)
    n = len(arr)
    if n < 2:
        return [50.0] * n

    ranks = stats.rankdata(arr, method="average")
    percentiles = (ranks - 1) / (n - 1) * 100

    if direction == -1:
        percentiles = 100 - percentiles

    return list(np.round(percentiles, 1))


def normalize_zscore(values: list, direction: int) -> list:
    """
    Normalisation z-score → rescalé 0-100.
    Utile pour variables avec distribution normale.
    """
    arr = np.array(values, dtype=float)
    if arr.std() == 0:
        return [50.0] * len(values)
    z = (arr - arr.mean()) / arr.std()
    if direction == -1:
        z = -z
    # Rescale z-score (-3,+3) → (0,100)
    scaled = (z + 3) / 6 * 100
    return list(np.clip(np.round(scaled, 1), 0, 100))


def normalize_minmax(values: list, direction: int) -> list:
    """Min-max classique — conservé comme option."""
    arr = np.array(values, dtype=float)
    mn, mx = arr.min(), arr.max()
    if mx == mn:
        return [50.0] * len(values)
    if direction == 1:
        return list(((arr - mn) / (mx - mn) * 100).round(1))
    return list(((mx - arr) / (mx - mn) * 100).round(1))


# ── Ajustement corrélations ───────────────────────────────────────────────────

def adjust_correlated_weights(dim_id: str, var_weights: dict) -> dict:
    """
    Réduit le poids effectif des variables corrélées pour éviter
    le double-comptage. Ex: si RevPAR + Occ + ADR présents → réduction.
    """
    adjusted = dict(var_weights.get(dim_id, {}))
    for group in CORRELATED_GROUPS:
        present = [v for v in group if v in adjusted]
        if len(present) >= 3:
            # Réduction proportionnelle : groupe de 3 corrélées → poids /1.4
            for v in present:
                adjusted[v] = adjusted[v] / 1.4
        elif len(present) == 2:
            for v in present:
                adjusted[v] = adjusted[v] / 1.2
    return adjusted


# ── Vintage penalty ───────────────────────────────────────────────────────────

def vintage_penalty(data_age_months: int) -> float:
    """Retourne le multiplicateur de pénalité selon l'âge des données."""
    for threshold in sorted(VINTAGE_THRESHOLDS.keys()):
        if data_age_months <= threshold:
            return VINTAGE_THRESHOLDS[threshold]
    return 0.50  # données > 36 mois : forte pénalité


# ── Indice de confiance ───────────────────────────────────────────────────────

def confidence_index(market: dict) -> float:
    """
    Calcule un indice de confiance 0-1 pour un marché.
    Basé sur la fiabilité des sources des variables renseignées.
    """
    reliabilities = []
    for d in DIMS:
        for v in d["vars"]:
            val = market[d["id"]].get(v["id"], 0)
            rel = SOURCE_RELIABILITY.get(v["id"], 0.5)
            # Pénalité si valeur = 0 (non renseignée)
            if val == 0:
                rel *= 0.3
            reliabilities.append(rel)
    return round(np.mean(reliabilities), 3)


# ── Score couleur / risque ────────────────────────────────────────────────────

def score_color(s: int) -> str:
    if s >= 75: return "#1fbd7e"
    if s >= 58: return "#4f7fff"
    if s >= 42: return "#f0a030"
    return "#e2504a"


def risk_color(r: int) -> str:
    if r > 60: return "#e2504a"
    if r > 35: return "#f0a030"
    return "#1fbd7e"


def confidence_color(c: float) -> str:
    if c >= 0.75: return "#1fbd7e"
    if c >= 0.55: return "#f0a030"
    return "#e2504a"


# ── Moteur principal ──────────────────────────────────────────────────────────

def normalize_absolute(value: float, var_id: str, direction: int,
                        transform: str = "linear") -> float:
    """
    Normalisation sur bornes absolues (VARIABLE_BOUNDS).
    Résultat stable quel que soit le panel actif — scores comparables dans le temps.

    Étapes :
    1. Clip sur [min_abs, max_abs]
    2. Transformation non-linéaire optionnelle
    3. Min-max sur les bornes transformées → 0-100
    """
    from data import VARIABLE_BOUNDS

    bounds = VARIABLE_BOUNDS.get(var_id)
    if bounds is None:
        # Fallback : normalisation relative si variable inconnue
        return 50.0

    mn, mx = float(bounds[0]), float(bounds[1])
    v = float(np.clip(value, mn, mx))

    # Shift pour transformation (toutes valeurs >= 1e-6)
    shift = max(0, -mn) + 1e-6

    def _transform(x):
        x = x + shift
        if transform == "log":
            return float(np.log1p(x))
        elif transform == "sqrt":
            return float(np.sqrt(x))
        elif transform == "diminishing":
            return float(np.cbrt(x))
        elif transform == "sigmoid":
            return x  # sigmoid reste relative
        return x

    v_t  = _transform(v)
    mn_t = _transform(mn)
    mx_t = _transform(mx)

    if mx_t == mn_t:
        score = 50.0
    else:
        score = (v_t - mn_t) / (mx_t - mn_t) * 100

    score = float(np.clip(score, 0, 100))
    return 100 - score if direction == -1 else score


def compute_scores(
    markets: list,
    dim_weights: dict,
    var_weights: dict,
    norm_method: str = "absolute",   # "absolute" (défaut) | "percentile" | "zscore" | "minmax"
    use_nonlinear: bool = True,
    use_reliability: bool = True,
    use_corr_adjust: bool = True,
    use_winsorize: bool = True,
) -> list:
    """
    Moteur de scoring v3.0 — normalisation absolue par défaut.

    norm_method="absolute" : bornes fixes VARIABLE_BOUNDS → scores stables et comparables
    norm_method="percentile" : rang dans le panel actif (ancien comportement)

    Returns:
        liste triée de dicts {id, name, region, total, dims, risk_raw,
                               confidence, outlier_flags}
    """
    # Fonctions de normalisation relative (fallback)
    rel_norm_fn = {
        "percentile": normalize_percentile,
        "zscore":     normalize_zscore,
        "minmax":     normalize_minmax,
    }.get(norm_method, normalize_percentile)

    use_absolute = (norm_method == "absolute")

    results = []

    for m in markets:
        total = 0.0
        dim_scores = {}
        outlier_flags = {}
        idx = markets.index(m)

        for d in DIMS:
            dim_id    = d["id"]
            vw        = adjust_correlated_weights(dim_id, var_weights) if use_corr_adjust \
                        else dict(var_weights.get(dim_id, {}))
            dim_score        = 0.0
            dim_reliability_sum = 0.0

            for v in d["vars"]:
                var_id    = v["id"]
                direction = v["dir"]
                transform = NONLINEAR.get(var_id, "linear") if use_nonlinear else "linear"
                raw_val   = float(m[dim_id][var_id])

                if use_absolute:
                    score_var = normalize_absolute(raw_val, var_id, direction, transform)
                else:
                    # Normalisation relative (mode comparaison panel)
                    raw_vals = [float(mm[dim_id][var_id]) for mm in markets]

                    # Détection outliers
                    if idx in detect_outliers_iqr(raw_vals):
                        outlier_flags[var_id] = True

                    vals = winsorize(raw_vals) if use_winsorize else raw_vals
                    if use_nonlinear:
                        vals = apply_transform(vals, transform)
                    score_var = rel_norm_fn(vals, direction)[idx]

                # Fiabilité source
                reliability = SOURCE_RELIABILITY.get(var_id, 0.5) if use_reliability else 1.0
                w           = vw.get(var_id, 100 / len(d["vars"]))

                dim_score           += score_var * (w / 100) * reliability
                dim_reliability_sum += reliability

            # Correction fiabilité
            if dim_reliability_sum > 0 and use_reliability:
                avg_rel   = dim_reliability_sum / len(d["vars"])
                dim_score = dim_score / avg_rel

            dim_scores[dim_id] = round(min(max(dim_score, 0), 100))
            dw    = dim_weights.get(dim_id, 0)
            total += dim_scores[dim_id] * (dw / 100)

        # Risque brut composite — pondération : pol 40%, geo 40%, reg_stab 20%
        pol      = float(m["risque"]["pol_risk"])
        geo      = float(m["risque"]["geo_exp"])
        reg      = float(m["risque"].get("reg_stab", 3))
        pr       = normalize_absolute(pol, "pol_risk", -1)   # inversé : 1=safe=100
        gr       = normalize_absolute(geo, "geo_exp",  -1)
        rr       = normalize_absolute(reg, "reg_stab",  1)   # 5=stable=100
        risk_raw = round(100 - (pr * 0.4 + gr * 0.4 + rr * 0.2))

        results.append({
            "id":            m["id"],
            "name":          m["name"],
            "region":        m["region"],
            "total":         round(min(max(total, 0), 100)),
            "dims":          dim_scores,
            "risk_raw":      risk_raw,
            "confidence":    confidence_index(m),
            "outlier_flags": outlier_flags,
        })

    return sorted(results, key=lambda x: x["total"], reverse=True)


# ── Pondérations par défaut ───────────────────────────────────────────────────

def default_var_weights() -> dict:
    """Pondérations égales par défaut pour toutes les variables."""
    vw = {}
    for d in DIMS:
        vw[d["id"]] = {}
        n = len(d["vars"])
        for i, v in enumerate(d["vars"]):
            vw[d["id"]][v["id"]] = round(100 / n) if i < n - 1 else 100 - round(100 / n) * (n - 1)
    return vw


# ── v3.1 — Gate 0 · Haircut politique · Notation AAA-CCC ─────────────────────

def apply_gate0(market: dict, profile_name: str) -> dict:
    """
    Gate 0 — filtre éliminatoire de stabilité politique AVANT scoring.
    Aucune pondération ne peut compenser un risque pays rédhibitoire.

    Returns:
        {"passed": bool, "reasons": [str]}
    """
    from data import GATE0_THRESHOLDS

    thresholds = GATE0_THRESHOLDS.get(profile_name, GATE0_THRESHOLDS["Value-add"])
    pol = float(market["risque"].get("pol_risk", 3))
    geo = float(market["risque"].get("geo_exp", 3))

    reasons = []
    if pol > thresholds["pol_risk_max"]:
        reasons.append(
            f"Risque politique {pol:.0f}/5 > seuil {profile_name} ({thresholds['pol_risk_max']}/5)"
        )
    if geo > thresholds["geo_exp_max"]:
        reasons.append(
            f"Exposition géopolitique {geo:.0f}/5 > seuil {profile_name} ({thresholds['geo_exp_max']}/5)"
        )

    return {"passed": len(reasons) == 0, "reasons": reasons}


def political_haircut(score: float, market: dict) -> dict:
    """
    Haircut politique post-scoring — correction multiplicative selon pol_risk.
    Pour les marchés qui passent Gate 0 mais restent fragiles.

    Returns:
        {"score_adjusted": int, "haircut_pct": float, "multiplier": float}
    """
    from data import POLITICAL_HAIRCUT

    pol = int(round(float(market["risque"].get("pol_risk", 3))))
    pol = max(1, min(5, pol))
    mult = POLITICAL_HAIRCUT.get(pol, 1.0)
    adjusted = round(score * mult)

    return {
        "score_adjusted": adjusted,
        "haircut_pct": round((1 - mult) * 100, 1),
        "multiplier": mult,
    }


def score_to_rating(score: float) -> dict:
    """
    Convertit un score 0-100 en notation type agence (AAA → CCC).

    Returns:
        {"rating": str, "label": str, "color": str}
    """
    from data import RATING_SCALE

    for threshold, rating, label, color in RATING_SCALE:
        if score >= threshold:
            return {"rating": rating, "label": label, "color": color}
    # Fallback (ne devrait jamais arriver, dernier seuil = 0)
    _, rating, label, color = RATING_SCALE[-1]
    return {"rating": rating, "label": label, "color": color}


def rating_delta(rating_a: str, rating_b: str) -> int:
    """
    Nombre de crans entre deux notations (a → b).
    Positif = dégradation. Ex: AA → BBB = +2 crans.
    """
    from data import RATING_SCALE
    order = [r[1] for r in RATING_SCALE]  # ["AAA","AA","A","BBB","BB","B","CCC"]
    try:
        return order.index(rating_b) - order.index(rating_a)
    except ValueError:
        return 0


def in_forbidden_zone(score: float, risk_raw: float) -> bool:
    """
    Règle d'or risque/rendement : risque élevé + attractivité faible = zone interdite.
    """
    from data import FORBIDDEN_ZONE
    return risk_raw >= FORBIDDEN_ZONE["risk_min"] and score <= FORBIDDEN_ZONE["score_max"]
