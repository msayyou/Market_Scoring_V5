# scoring_advanced.py — REIV Market Scorer v2.0
# Modules analytiques avancés :
# - Clustering K-means (familles de marchés)
# - Analyse de sensibilité (impact pondérations)
# - Monte Carlo (intervalle de confiance sur scores)
# - Momentum & cycle hôtelier
# - Spread cap rate / coût dette

import numpy as np
from scipy import stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
import warnings
warnings.filterwarnings("ignore")

from data import DIMS
from scoring import compute_scores, default_var_weights, SOURCE_RELIABILITY


# ── 1. CLUSTERING K-MEANS ────────────────────────────────────────────────────

CLUSTER_LABELS = {
    0: ("Core mature",        "#1fbd7e", "Marchés liquides, performants, faible risque"),
    1: ("Croissance émergente","#f0a030", "Pipeline fort, macro favorable, risque modéré"),
    2: ("Risqué / liquide",   "#d4537e", "Cap rates élevés, geopolitique, opportuniste"),
    3: ("Sous-performant",    "#555e78", "Faible performance, liquidité limitée"),
}


def cluster_markets(scores: list, n_clusters: int = None) -> dict:
    """
    Clustering K-means sur les 6 scores dimensionnels.

    Args:
        scores: output de compute_scores()
        n_clusters: si None, déterminé automatiquement par silhouette score

    Returns:
        dict {market_id: {cluster, label, color, description, silhouette_score}}
    """
    if len(scores) < 4:
        return {}

    # Matrice features : scores dimensionnels + risque
    feature_matrix = np.array([
        [s["dims"][d["id"]] for d in DIMS] + [s["risk_raw"]]
        for s in scores
    ], dtype=float)

    scaler = StandardScaler()
    X = scaler.fit_transform(feature_matrix)

    # Détermination automatique du nombre de clusters
    if n_clusters is None:
        best_k, best_sil = 2, -1
        for k in range(2, min(5, len(scores) - 1)):
            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(X)
            sil = silhouette_score(X, labels)
            if sil > best_sil:
                best_sil, best_k = sil, k
        n_clusters = best_k
    else:
        km_temp = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        labels_temp = km_temp.fit_predict(X)
        best_sil = silhouette_score(X, labels_temp) if len(scores) > n_clusters else 0

    km = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_labels = km.fit_predict(X)

    # Identifier le "type" de chaque cluster par ses centroïdes
    # Cluster avec le plus haut score total → Core mature, etc.
    cluster_means = {}
    for k in range(n_clusters):
        indices = [i for i, l in enumerate(cluster_labels) if l == k]
        cluster_means[k] = np.mean([scores[i]["total"] for i in indices])

    sorted_clusters = sorted(cluster_means.items(), key=lambda x: x[1], reverse=True)
    cluster_mapping = {orig: new for new, (orig, _) in enumerate(sorted_clusters)}

    result = {}
    for i, s in enumerate(scores):
        orig_cluster = int(cluster_labels[i])
        mapped = cluster_mapping.get(orig_cluster, orig_cluster)
        label_info = CLUSTER_LABELS.get(mapped, (f"Cluster {mapped}", "#888", ""))
        result[s["id"]] = {
            "cluster": mapped,
            "label": label_info[0],
            "color": label_info[1],
            "description": label_info[2],
            "silhouette": round(best_sil, 3),
            "n_clusters": n_clusters,
        }

    return result


# ── 2. ANALYSE DE SENSIBILITÉ ─────────────────────────────────────────────────

def sensitivity_analysis(
    markets: list,
    dim_weights: dict,
    var_weights: dict,
    delta: int = 10,
    norm_method: str = "absolute",
) -> dict:
    """
    Mesure l'impact d'une variation ±delta% sur chaque dimension
    sur le classement final.

    Returns:
        dict {dim_id: {
            "rank_changes": {market_id: delta_rank},
            "score_changes": {market_id: delta_score},
            "sensitivity_index": float  (volatilité moyenne du classement)
        }}
    """
    base_scores = compute_scores(markets, dim_weights, var_weights, norm_method=norm_method)
    base_ranks = {s["id"]: i for i, s in enumerate(base_scores)}

    results = {}

    for d in DIMS:
        dim_id = d["id"]
        original_w = dim_weights.get(dim_id, 0)

        # Variation +delta
        dw_up = dict(dim_weights)
        dw_up[dim_id] = min(original_w + delta, 100)
        scores_up = compute_scores(markets, dw_up, var_weights, norm_method=norm_method)
        ranks_up = {s["id"]: i for i, s in enumerate(scores_up)}

        # Variation -delta
        dw_down = dict(dim_weights)
        dw_down[dim_id] = max(original_w - delta, 0)
        scores_down = compute_scores(markets, dw_down, var_weights, norm_method=norm_method)
        ranks_down = {s["id"]: i for i, s in enumerate(scores_down)}

        rank_changes = {}
        score_changes = {}
        for s in base_scores:
            mid = s["id"]
            delta_rank_up = ranks_up.get(mid, 0) - base_ranks.get(mid, 0)
            delta_rank_down = ranks_down.get(mid, 0) - base_ranks.get(mid, 0)
            rank_changes[mid] = {
                "up": delta_rank_up,
                "down": delta_rank_down,
                "max_abs": max(abs(delta_rank_up), abs(delta_rank_down)),
            }

            score_up = next((x["total"] for x in scores_up if x["id"] == mid), 0)
            score_down = next((x["total"] for x in scores_down if x["id"] == mid), 0)
            score_changes[mid] = {
                "up": score_up - s["total"],
                "down": score_down - s["total"],
            }

        sensitivity_index = np.mean([v["max_abs"] for v in rank_changes.values()])

        results[dim_id] = {
            "rank_changes": rank_changes,
            "score_changes": score_changes,
            "sensitivity_index": round(float(sensitivity_index), 2),
            "dim_label": d["label"],
            "dim_color": d["color"],
        }

    return results


# ── 3. MONTE CARLO — INTERVALLES DE CONFIANCE ────────────────────────────────

def monte_carlo_scores(
    markets: list,
    dim_weights: dict,
    var_weights: dict,
    n_simulations: int = 1000,
    noise_level: float = 0.08,
    norm_method: str = "absolute",
    seed: int = 42,
) -> dict:
    """
    Simule N scénarios avec bruit gaussien sur les données brutes
    pour estimer l'intervalle de confiance sur chaque score.

    noise_level: écart-type du bruit en % de la valeur (défaut 8%)

    Returns:
        dict {market_id: {
            "mean": float,
            "std": float,
            "ci_low": float,   # P10
            "ci_high": float,  # P90
            "rank_mean": float,
            "rank_std": float,
        }}
    """
    rng = np.random.default_rng(seed)
    sim_scores = {m["id"]: [] for m in markets}
    sim_ranks = {m["id"]: [] for m in markets}

    for _ in range(n_simulations):
        # Perturbation aléatoire des données brutes
        noisy_markets = []
        for m in markets:
            nm = {"id": m["id"], "name": m["name"], "region": m["region"]}
            for d in DIMS:
                nm[d["id"]] = {}
                for v in d["vars"]:
                    raw = float(m[d["id"]][v["id"]])
                    reliability = SOURCE_RELIABILITY.get(v["id"], 0.5)
                    # Bruit inversement proportionnel à la fiabilité
                    effective_noise = noise_level * (1 + (1 - reliability))
                    noise = rng.normal(0, max(abs(raw) * effective_noise, 0.01))
                    nm[d["id"]][v["id"]] = max(raw + noise, 0)
            noisy_markets.append(nm)

        sim = compute_scores(noisy_markets, dim_weights, var_weights, norm_method=norm_method)
        for rank, s in enumerate(sim):
            sim_scores[s["id"]].append(s["total"])
            sim_ranks[s["id"]].append(rank + 1)

    results = {}
    for mid, scores_list in sim_scores.items():
        arr = np.array(scores_list)
        ranks_arr = np.array(sim_ranks[mid])
        results[mid] = {
            "mean": round(float(arr.mean()), 1),
            "std": round(float(arr.std()), 1),
            "ci_low": round(float(np.percentile(arr, 10)), 1),
            "ci_high": round(float(np.percentile(arr, 90)), 1),
            "rank_mean": round(float(ranks_arr.mean()), 1),
            "rank_std": round(float(ranks_arr.std()), 1),
        }

    return results


# ── 4. MOMENTUM & CYCLE HÔTELIER ─────────────────────────────────────────────

# Phases du cycle (Choi 1999 adapté)
CYCLE_PHASES = {
    "expansion":    {"label": "Expansion",    "color": "#1fbd7e", "signal": +1},
    "peak":         {"label": "Peak",         "color": "#f0a030", "signal":  0},
    "contraction":  {"label": "Contraction",  "color": "#e2504a", "signal": -1},
    "trough":       {"label": "Creux",        "color": "#4f7fff", "signal": +1},
}


def compute_momentum(market: dict) -> dict:
    """
    Calcule des indicateurs de momentum à partir des données disponibles.
    Proxy du positionnement dans le cycle hôtelier.

    Returns:
        dict avec momentum_score, cycle_phase, signal
    """
    revpar = float(market["perf"].get("revpar", 0))
    revpar_g = float(market["perf"].get("revpar_g", 0))
    occ = float(market["perf"].get("occ", 0))
    pip_ratio = float(market["pipeline"].get("pip_ratio", 0))
    rooms_g = float(market["pipeline"].get("rooms_g", 0))
    caprate = float(market["liquidite"].get("caprate", 0))

    # Score momentum : croissance + occupation - pression supply
    momentum_score = (
        revpar_g * 2.5          # Croissance RevPAR = signal fort
        + (occ - 65) * 0.8      # Occupation > 65% = positif
        - pip_ratio * 0.6       # Pipeline fort = pression future
        + (8 - caprate) * 1.5   # Cap rate bas = confiance marché
    )

    # Phase cycle approximative
    if revpar_g > 8 and occ > 72:
        phase = "expansion"
    elif revpar_g > 4 and occ > 75:
        phase = "peak"
    elif revpar_g < 2 or occ < 60:
        phase = "trough"
    else:
        phase = "contraction"

    phase_info = CYCLE_PHASES[phase]

    return {
        "momentum_score": round(momentum_score, 1),
        "cycle_phase": phase,
        "cycle_label": phase_info["label"],
        "cycle_color": phase_info["color"],
        "signal": phase_info["signal"],
        "revpar_g": revpar_g,
        "occ": occ,
        "pip_ratio": pip_ratio,
    }


# ── 5. SPREAD CAP RATE / COÛT DETTE ──────────────────────────────────────────

def compute_caprate_spread(
    market: dict,
    debt_cost: float = 5.5,    # Coût moyen dette hôtelière EU 2025 (%)
    risk_free: float = 3.2,    # OAT 10 ans approx (%)
) -> dict:
    """
    Calcule le spread cap rate / coût dette et le rendement ajusté.
    Corgel 2004 : cap rate contre-cyclique → signal d'entrée.

    Returns:
        dict avec spread, yield_gap, entry_signal
    """
    caprate = float(market["liquidite"].get("caprate", 0))
    risk_premium = caprate - risk_free

    spread = caprate - debt_cost
    yield_gap = caprate - risk_free

    if spread > 1.5:
        entry_signal = "Achat attractif"
        signal_color = "#1fbd7e"
        signal_score = 85
    elif spread > 0.5:
        entry_signal = "Neutre"
        signal_color = "#f0a030"
        signal_score = 55
    elif spread > 0:
        entry_signal = "Vigilance"
        signal_color = "#f0a030"
        signal_score = 40
    else:
        entry_signal = "Spread négatif"
        signal_color = "#e2504a"
        signal_score = 20

    return {
        "caprate": caprate,
        "debt_cost": debt_cost,
        "risk_free": risk_free,
        "spread": round(spread, 2),
        "yield_gap": round(yield_gap, 2),
        "entry_signal": entry_signal,
        "signal_color": signal_color,
        "signal_score": signal_score,
        "risk_premium": round(risk_premium, 2),
    }


# ── 6. RISK PENETRATION INDEX (O'Neill 2023 — Table 21) ──────────────────────

def risk_penetration_index(scores: list, markets: list) -> dict:
    """
    Calcule le Risk Penetration Index par marché selon O'Neill 2023.
    Indice 100 = moyenne du panel.

    Trois dimensions :
    - GOP Profit Margin index (proxy : occ × adr / revpar × 0.38)
    - GOPPAR index (proxy : revpar × 0.38 annualisé / 365)
    - GOPPAR RSD index (O'Neill proxy — plus bas = moins risqué)

    Returns:
        dict {market_id: {
            gop_margin_raw, gop_margin_idx,
            goppar_raw, goppar_idx,
            goppar_rsd_raw, goppar_rsd_idx,
            verdict, verdict_color
        }}
    """
    from data import MARKET_PROFILES_ONEILL, goppar_rsd_proxy

    # Calcul des valeurs brutes par marché
    raw = {}
    for s in scores:
        m = next((mm for mm in markets if mm["id"] == s["id"]), None)
        if not m:
            continue
        revpar = float(m["perf"].get("revpar", 0))
        occ    = float(m["perf"].get("occ", 0)) / 100
        adr    = float(m["perf"].get("adr", 0))

        # GOP Margin proxy : GOP/RevPAR ≈ 38% (O'Neill 2023 moyenne upscale)
        # Ajustement selon occupation : meilleure occ → meilleure margin
        gop_margin = min(0.38 + (occ - 0.70) * 0.5, 0.65)
        gop_margin = max(gop_margin, 0.10)

        # GOPPAR proxy = RevPAR × GOP margin
        goppar = round(revpar * gop_margin, 2)

        # GOPPAR RSD depuis O'Neill benchmarks
        goppar_rsd = goppar_rsd_proxy(s["id"])

        raw[s["id"]] = {
            "gop_margin": round(gop_margin * 100, 2),
            "goppar": goppar,
            "goppar_rsd": goppar_rsd,
        }

    if not raw:
        return {}

    # Moyennes panel (= base 100)
    avg_margin = np.mean([v["gop_margin"] for v in raw.values()])
    avg_goppar = np.mean([v["goppar"] for v in raw.values()])
    avg_rsd    = np.mean([v["goppar_rsd"] for v in raw.values()])

    result = {}
    for mid, vals in raw.items():
        margin_idx = round(vals["gop_margin"] / avg_margin * 100, 1) if avg_margin else 100
        goppar_idx = round(vals["goppar"] / avg_goppar * 100, 1) if avg_goppar else 100
        rsd_idx    = round(vals["goppar_rsd"] / avg_rsd * 100, 1) if avg_rsd else 100

        # Verdict : bon investissement = margin > 100 + GOPPAR > 100 + RSD < 100
        score_verdict = (margin_idx > 100) + (goppar_idx > 100) + (rsd_idx < 100)
        if score_verdict == 3:
            verdict, verdict_color = "★ Attractif", "#1fbd7e"
        elif score_verdict == 2:
            verdict, verdict_color = "◎ Correct", "#4f7fff"
        elif score_verdict == 1:
            verdict, verdict_color = "△ Mitigé", "#f0a030"
        else:
            verdict, verdict_color = "✗ Défavorable", "#e2504a"

        result[mid] = {
            "gop_margin_raw": vals["gop_margin"],
            "gop_margin_idx": margin_idx,
            "goppar_raw": vals["goppar"],
            "goppar_idx": goppar_idx,
            "goppar_rsd_raw": vals["goppar_rsd"],
            "goppar_rsd_idx": rsd_idx,
            "verdict": verdict,
            "verdict_color": verdict_color,
        }

    return result


# ── 7. SCORING COMPOSITE ENRICHI ─────────────────────────────────────────────

def full_analysis(
    markets: list,
    dim_weights: dict,
    var_weights: dict,
    norm_method: str = "absolute",
    debt_cost: float = 5.5,
    risk_free: float = 3.2,
    run_monte_carlo: bool = True,
    n_simulations: int = 500,
) -> dict:
    """
    Analyse complète : scoring + momentum + spread + clustering + MC + RPI.

    Returns:
        dict complet par marché avec tous les indicateurs
    """
    from data import MARKET_PROFILES_ONEILL, ONEILL_RSD_CLASS, ONEILL_RSD_PROPTYPE, ONEILL_RSD_LOCTYPE

    scores = compute_scores(markets, dim_weights, var_weights, norm_method=norm_method)

    # Clustering
    clusters = cluster_markets(scores)

    # Monte Carlo
    mc = monte_carlo_scores(
        markets, dim_weights, var_weights,
        n_simulations=n_simulations, norm_method=norm_method
    ) if run_monte_carlo else {}

    # Sensibilité
    sensitivity = sensitivity_analysis(markets, dim_weights, var_weights, norm_method=norm_method)

    # Risk Penetration Index (O'Neill 2023)
    rpi = risk_penetration_index(scores, markets)

    # Momentum + spread + RPI + O'Neill profile par marché
    enriched = []
    for s in scores:
        m = next((mm for mm in markets if mm["id"] == s["id"]), None)
        if not m:
            continue

        momentum  = compute_momentum(m)
        spread    = compute_caprate_spread(m, debt_cost=debt_cost, risk_free=risk_free)
        cluster   = clusters.get(s["id"], {})
        mc_data   = mc.get(s["id"], {})
        rpi_data  = rpi.get(s["id"], {})

        # Profil O'Neill enrichi
        oneill_profile = MARKET_PROFILES_ONEILL.get(s["id"], {})
        oneill_detail = {}
        if oneill_profile:
            oneill_detail = {
                "class":      oneill_profile.get("class", "—"),
                "proptype":   oneill_profile.get("proptype", "—"),
                "loctype":    oneill_profile.get("loctype", "—"),
                "rsd_class":  ONEILL_RSD_CLASS.get(oneill_profile.get("class", ""), 0),
                "rsd_prop":   ONEILL_RSD_PROPTYPE.get(oneill_profile.get("proptype", ""), 0),
                "rsd_loc":    ONEILL_RSD_LOCTYPE.get(oneill_profile.get("loctype", ""), 0),
            }

        enriched.append({
            **s,
            "momentum":      momentum,
            "spread":        spread,
            "cluster":       cluster,
            "mc":            mc_data,
            "rpi":           rpi_data,
            "oneill":        oneill_detail,
        })

    return {
        "scores":      enriched,
        "sensitivity": sensitivity,
        "n_markets":   len(markets),
        "norm_method": norm_method,
    }


# ── v3.1 — Stress test marché ─────────────────────────────────────────────────

def market_vulnerability(market: dict, rsd_reference: float = 40.0) -> float:
    """
    Facteur de vulnérabilité au stress — O'Neill 2023.

    Le GOPPAR RSD mesure la volatilité opérationnelle structurelle d'un marché
    selon son profil (classe dominante, type de propriété, localisation).
    La volatilité étant symétrique, un marché à RSD élevé amplifie les chocs
    dans les deux sens (downside ET upside).

    Référence 40% ≈ moyenne pondérée du panel O'Neill (3 219 hôtels US).
    Borné [0.75, 1.35] : un marché economy/extended-stay (RSD ~20%) encaisse
    25% de choc en moins, un marché luxury urbain (RSD ~54%) en prend 35% de plus.

    Returns:
        float — multiplicateur d'amplitude de choc
    """
    rsd = float(market.get("risque", {}).get("goppar_rsd", rsd_reference))
    vuln = rsd / rsd_reference
    return float(np.clip(vuln, 0.75, 1.35))


def _apply_shocks(market: dict, shocks: dict, vuln: float = 1.0) -> dict:
    """
    Applique les chocs d'un scénario à une copie du marché,
    modulés par le facteur de vulnérabilité O'Neill du marché.

    - Choc multiplicatif : l'écart à 1 est amplifié → 1 + (val−1)×vuln
      Ex : ×0.85 avec vuln 1.3 → ×0.805 ; avec vuln 0.8 → ×0.88
    - Choc additif : directement mis à l'échelle → val×vuln

    Les valeurs choquées sont reclampées dans VARIABLE_BOUNDS par
    normalize_absolute, donc pas besoin de clipper ici.
    """
    import copy as _copy
    m = _copy.deepcopy(market)

    for d in DIMS:
        dim_id = d["id"]
        for v in d["vars"]:
            var_id = v["id"]
            if var_id not in shocks:
                continue
            mode, val = shocks[var_id]
            cur = float(m[dim_id][var_id])
            if mode == "mult":
                effective = 1.0 + (val - 1.0) * vuln
                m[dim_id][var_id] = cur * effective
            elif mode == "add":
                m[dim_id][var_id] = cur + val * vuln
    return m


def stress_test_markets(
    markets: list,
    dim_weights: dict,
    var_weights: dict,
    profile_name: str = "Value-add",
    norm_method: str = "absolute",
) -> dict:
    """
    Stress test complet : recalcule le score sous chaque scénario
    (base / upside / downside), applique le haircut politique,
    et mesure la dégradation de notation.

    IMPORTANT : nécessite norm_method="absolute" pour que les scores
    soient comparables entre scénarios (le mode relatif re-normaliserait
    sur le panel choqué et masquerait l'effet du choc).

    Returns:
        dict {market_id: {
            "name", "gate0": {passed, reasons},
            "scenarios": {scen_id: {score_raw, score_final, rating, color, label}},
            "delta_downside": int (crans perdus base→downside),
            "resilience": str ("Résilient"|"Sensible"|"Fragile"),
            "resilience_color": str,
            "forbidden": bool,
        }}
    """
    from data import STRESS_SCENARIOS
    from scoring import (
        apply_gate0, political_haircut, score_to_rating,
        rating_delta, in_forbidden_zone,
    )

    # Force le mode absolu pour comparabilité inter-scénarios
    effective_norm = "absolute"

    results = {}

    # Scores par scénario — panel entier recalculé à chaque fois
    scenario_scores = {}
    for scen_id, scen in STRESS_SCENARIOS.items():
        shocked_markets = [
            _apply_shocks(m, scen["shocks"], vuln=market_vulnerability(m))
            for m in markets
        ]
        scores = compute_scores(
            shocked_markets, dim_weights, var_weights,
            norm_method=effective_norm,
        )
        scenario_scores[scen_id] = {s["id"]: s for s in scores}

    for m in markets:
        mid = m["id"]
        gate0 = apply_gate0(m, profile_name)

        scenarios_out = {}
        for scen_id, scen in STRESS_SCENARIOS.items():
            s = scenario_scores[scen_id].get(mid)
            if s is None:
                continue
            raw = s["total"]
            hc = political_haircut(raw, m)
            final = hc["score_adjusted"]
            rt = score_to_rating(final)
            scenarios_out[scen_id] = {
                "score_raw":   raw,
                "score_final": final,
                "haircut_pct": hc["haircut_pct"],
                "rating":      rt["rating"],
                "color":       rt["color"],
                "label":       scen["label"],
                "scen_color":  scen["color"],
                "risk_raw":    s["risk_raw"],
            }

        # Dégradation base → downside en crans de notation
        delta = 0
        if "base" in scenarios_out and "downside" in scenarios_out:
            delta = rating_delta(
                scenarios_out["base"]["rating"],
                scenarios_out["downside"]["rating"],
            )

        if delta <= 0:
            resilience, res_color = "Résilient", "#1fbd7e"
        elif delta == 1:
            resilience, res_color = "Sensible", "#f0a030"
        else:
            resilience, res_color = "Fragile", "#e2504a"

        base_s = scenarios_out.get("base", {})
        forbidden = in_forbidden_zone(
            base_s.get("score_final", 50), base_s.get("risk_raw", 50)
        )

        results[mid] = {
            "name":             m["name"],
            "gate0":            gate0,
            "scenarios":        scenarios_out,
            "delta_downside":   delta,
            "resilience":       resilience,
            "resilience_color": res_color,
            "forbidden":        forbidden,
        }

    return results
