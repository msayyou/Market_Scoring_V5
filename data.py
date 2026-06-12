# data.py — REIV Market Scorer v3.0
# Sources : O'Neill et al. 2023 (Cornell) · HVS 2025 European HVI · CBRE Destination Index 2025
# v3.0 : bornes absolues par variable (scoring indépendant du panel)
#         + données recalibrées sur sources HVS/CBRE/STR

# ── Dimensions & variables ────────────────────────────────────────────────────

DIMS = [
    {
        "id": "perf", "label": "Performance hôtelière", "color": "#4f7fff",
        "vars": [
            {"id": "revpar",   "label": "RevPAR (€)",                  "unit": "€",  "dir": 1},
            {"id": "occ",      "label": "Occupation (%)",               "unit": "%",  "dir": 1},
            {"id": "adr",      "label": "ADR (€)",                      "unit": "€",  "dir": 1},
            {"id": "revpar_g", "label": "Croissance RevPAR (%)",        "unit": "%",  "dir": 1},
        ]
    },
    {
        "id": "pipeline", "label": "Pipeline & croissance", "color": "#1fbd7e",
        "vars": [
            {"id": "pip_ratio",  "label": "Pipeline/parc (%)",           "unit": "%",  "dir": 1},
            {"id": "rooms_g",    "label": "Croissance rooms 3a (%)",      "unit": "%",  "dir": 1},
            {"id": "saturation", "label": "Saturation (inverse)",         "unit": "",   "dir": -1},
        ]
    },
    {
        "id": "liquidite", "label": "Liquidité transactionnelle", "color": "#f0a030",
        "vars": [
            {"id": "vol_tx",    "label": "Volume deals (M€)",             "unit": "M€", "dir": 1},
            {"id": "caprate",   "label": "Cap rate (%)",                   "unit": "%",  "dir": 1},
            {"id": "nb_deals",  "label": "Nombre de deals",                "unit": "",   "dir": 1},
            {"id": "hvi_index", "label": "HVI HVS 2024 (indice valeur)",   "unit": "",   "dir": 1},
            {"id": "hvi_cagr",  "label": "HVI CAGR 2015-24 (%)",           "unit": "%",  "dir": 1},
        ]
    },
    {
        "id": "macro", "label": "Fondamentaux macro hôteliers", "color": "#7f6fff",
        "vars": [
            # Remplacements v3.4 — seules variables à causalité directe démontrée sur RevPAR
            {"id": "revpar_elast",  "label": "Élasticité RevPAR/PIB (0-1)",      "unit": "",  "dir": 1},
            # Dépense/visiteur > volume d'arrivées : capte la valeur, pas le comptage
            {"id": "spend_visitor", "label": "Dépense/visiteur (€/nuit)",         "unit": "€", "dir": 1},
            {"id": "connect",       "label": "Connectivité aérienne (1-5)",        "unit": "",  "dir": 1},
            # Labour cost : 30-35% du CA hôtelier — causalité directe EBITDA
            {"id": "labour_cost",   "label": "Coût travail — inv (CBRE 1-10)",    "unit": "",  "dir": -1},
            # Énergie : 6-8% du CA — post-2022 devenu critère de screening
            {"id": "energy_cost",   "label": "Coût énergie relatif (1-10 inv)",   "unit": "",  "dir": -1},
        ]
    },
    {
        "id": "risque", "label": "Risque opérationnel & pays", "color": "#e2504a",
        "vars": [
            {"id": "pol_risk",        "label": "Risque politique (1-5 inv)",        "unit": "", "dir": -1},
            {"id": "reg_stab",        "label": "Stabilité réglementaire (1-5)",     "unit": "", "dir": 1},
            {"id": "geo_exp",         "label": "Exposition géopolitique (1-5 inv)", "unit": "", "dir": -1},
            {"id": "goppar_rsd",      "label": "GOPPAR RSD proxy % (O'Neill 2023)", "unit": "%","dir": -1},
            {"id": "hotel_class_risk","label": "Classe dominante risque (1-5)",     "unit": "", "dir": -1},
            {"id": "loc_type_risk",   "label": "Type localisation risque (1-5)",    "unit": "", "dir": -1},
        ]
    },
    {
        "id": "esg", "label": "ESG & durabilité", "color": "#d4537e",
        "vars": [
            {"id": "cert_pct", "label": "Parc certifié (%)",               "unit": "%", "dir": 1},
            {"id": "reg_esg",  "label": "Conformité réglementaire (1-5)",  "unit": "",  "dir": 1},
            {"id": "tax_eu",   "label": "Score Taxonomie EU (1-5)",         "unit": "",  "dir": 1},
        ]
    },
    {
        "id": "faisabilite", "label": "Faisabilité développement", "color": "#20c4c8",
        "vars": [
            {"id": "dev_cost",      "label": "Coût développement (k€/ch)", "unit": "k€", "dir": -1},
            {"id": "dev_revpar_idx","label": "Development/RevPAR Index",   "unit": "",   "dir": 1},
            {"id": "yield_on_cost", "label": "Yield on cost (%)",          "unit": "%",  "dir": 1},
        ]
    },
]

# ── Bornes absolues par variable ──────────────────────────────────────────────
# Indépendantes du panel — permettent un scoring stable et comparable dans le temps.
# Sources : STR Global, HVS London, CBRE Research, Eurostat, JLL Hotels 2024-2025
# Format : {var_id: (min_absolu, max_absolu)}
# min = marché le plus faible en Europe/MENA plausible
# max = marché de référence mondiale (Londres/Paris/Dubai pour les top)

VARIABLE_BOUNDS = {
    # Performance hôtelière — STR Global, HVS 2025
    "revpar":    (20,   250),   # 20 = marché émergent low-cost / 250 = Londres upscale
    "occ":       (45,   88),    # 45 = marché creux / 88 = Amsterdam high-season
    "adr":       (40,   320),   # 40 = budget MENA / 320 = Paris luxury
    "revpar_g":  (-5,   20),    # -5 = contraction / +20 = hypercroissance type Riyad Vision 2030

    # Pipeline & croissance — STR Pipeline Report 2024
    "pip_ratio":  (0,   25),    # 0 = marché fermé / 25 = Riyad/Dubai hyperexpansion
    "rooms_g":    (0,   25),    # idem
    "saturation": (1,    5),    # 1 = capacité d'absorption forte / 5 = saturé

    # Liquidité — HVS 2025, JLL Hotels 2024, CBRE 2025
    "vol_tx":    (5,  1500),    # 5 = marché illiquide / 1500 = Londres
    "caprate":   (3.5,  11),    # 3.5 = prime core EU / 11 = marché spéculatif AN
    "nb_deals":  (0,    35),    # 0 = pas de transactions / 35 = Londres
    "hvi_index": (0.3,  4.5),   # HVS base 1993=1 / Paris 4.29 = max panel EU
    "hvi_cagr":  (-5,   8),     # -5 = déclin prolongé / +8 = Athènes type

    # Macro hôteliers — variables à causalité directe démontrée sur RevPAR
    # Sources : STR/HVS études d'élasticité, Eurostat énergie, UNWTO spend/visitor
    "revpar_elast":  (0.1,  0.9),  # 0.1 = leisure pur (Marrakech) / 0.9 = corporate fort (Londres)
    "spend_visitor": (40,   280),  # 40 = marché budget / 280 = Paris/Zurich haut de gamme
    "connect":       (1,    5),    # inchangé
    "labour_cost":   (1,    10),   # CBRE 1-10 — inchangé
    "energy_cost":   (1,    10),   # 1 = gaz/charbon dominant coûteux / 10 = renouvelables favorables

    # Risque — Coface, Euler Hermes, O'Neill 2023
    "pol_risk":        (1, 5),
    "reg_stab":        (1, 5),
    "geo_exp":         (1, 5),
    "goppar_rsd":      (15, 65),  # O'Neill 2023 : economy 18% / luxury 54% (max ~65 avec ajustements)
    "hotel_class_risk":(1, 5),
    "loc_type_risk":   (1, 5),

    # ESG — BREEAM, HQE, EU Taxonomy
    "cert_pct":  (0,   55),    # 0 = aucune certification / 55 = Amsterdam/Nordics
    "reg_esg":   (1,    5),
    "tax_eu":    (1,    5),

    # Faisabilité — HVS, Hospitality Finance 2024
    "dev_cost":      (50,  500),  # 50 = construction Afrique du Nord / 500 = Londres luxury
    "dev_revpar_idx":(5,   30),   # calculé RevPAR annuel / dev_cost
    "yield_on_cost": (2,   12),   # 2 = barely viable / 12 = Tunis/Casablanca low-cost
}


# ── Profils investisseur ──────────────────────────────────────────────────────

REGION_LABELS = {"EU": "Europe", "MED": "Méditerranée", "AN": "Afrique du Nord", "MO": "Moyen-Orient"}
REGION_COLORS = {"EU": "#4f7fff", "MED": "#1fbd7e", "AN": "#f0a030", "MO": "#d4537e"}

PROFILES = {
    "Core":        {"perf": 28, "pipeline":  8, "liquidite": 28, "macro": 18, "risque": 10, "esg": 5, "faisabilite":  3},
    "Value-add":   {"perf": 22, "pipeline": 20, "liquidite": 18, "macro": 13, "risque":  9, "esg": 5, "faisabilite": 13},
    "Opportuniste":{"perf": 16, "pipeline": 28, "liquidite":  8, "macro": 16, "risque":  8, "esg": 4, "faisabilite": 20}}


# ── O'Neill 2023 — Benchmarks GOPPAR RSD ─────────────────────────────────────
# Source : Cornell Hospitality Quarterly — Tables 6, 7, 9

ONEILL_RSD_CLASS = {
    "luxury":         54.34,
    "upper_upscale":  50.69,
    "upscale":        37.18,
    "upper_midscale": 38.29,
    "midscale":       34.96,
    "economy":        18.47}

ONEILL_RSD_PROPTYPE = {
    "full_service":   47.88,
    "limited_service":37.45,
    "convention":     57.21,
    "all_suites":     41.09,
    "extended_stay":  23.71,
    "resort":         40.37}

ONEILL_RSD_LOCTYPE = {
    "large_metro_urban":    49.55,
    "large_metro_suburban": 34.46,
    "large_metro_airport":  38.16,
    "midsized_urban":       36.54,
    "midsized_suburban":    35.79,
    "small_city":           33.31,
    "highway":              34.69,
    "resort_destination":   32.43}

MARKET_PROFILES_ONEILL = {
    "paris":      {"class": "upper_upscale", "proptype": "full_service",    "loctype": "large_metro_urban"},
    "london":     {"class": "upper_upscale", "proptype": "full_service",    "loctype": "large_metro_urban"},
    "madrid":     {"class": "upscale",       "proptype": "full_service",    "loctype": "large_metro_urban"},
    "lisbon":     {"class": "upscale",       "proptype": "limited_service", "loctype": "large_metro_urban"},
    "barcelona":  {"class": "upscale",       "proptype": "full_service",    "loctype": "large_metro_urban"},
    "athens":     {"class": "upscale",       "proptype": "limited_service", "loctype": "large_metro_suburban"},
    "milan":      {"class": "upper_upscale", "proptype": "full_service",    "loctype": "large_metro_urban"},
    "amsterdam":  {"class": "upscale",       "proptype": "full_service",    "loctype": "large_metro_urban"},
    "casablanca": {"class": "upscale",       "proptype": "full_service",    "loctype": "large_metro_urban"},
    "marrakech":  {"class": "upscale",       "proptype": "resort",          "loctype": "resort_destination"},
    "dubai":      {"class": "luxury",        "proptype": "full_service",    "loctype": "large_metro_urban"},
    "riyadh":     {"class": "upper_upscale", "proptype": "full_service",    "loctype": "large_metro_urban"},
    "abu_dhabi":  {"class": "upper_upscale", "proptype": "full_service",    "loctype": "large_metro_urban"},
    "cairo":      {"class": "upscale",       "proptype": "full_service",    "loctype": "large_metro_urban"},
    "tunis":      {"class": "midscale",      "proptype": "limited_service", "loctype": "large_metro_urban"}}

CLASS_RISK_SCORE = {
    "luxury": 5, "upper_upscale": 4, "upscale": 3,
    "upper_midscale": 3, "midscale": 2, "economy": 1}

LOCTYPE_RISK_SCORE = {
    "large_metro_urban": 5, "large_metro_airport": 4, "large_metro_suburban": 3,
    "midsized_urban": 3, "midsized_suburban": 2, "small_city": 2,
    "highway": 3, "resort_destination": 2}


# ── HVS 2025 European Hotel Valuation Index ───────────────────────────────────
# Source : HVS London Office, March 2025 — Tableau pages 4 et 6

HVS_HVI = {
    "paris":      {"hvi": 4.29, "cagr":  0.7, "delta_2024":  0.0},
    "london":     {"hvi": 3.34, "cagr": -2.0, "delta_2024":  0.0},
    "amsterdam":  {"hvi": 2.35, "cagr":  1.8, "delta_2024": -1.1},
    "barcelona":  {"hvi": 2.10, "cagr":  2.7, "delta_2024":  3.7},
    "milan":      {"hvi": 2.06, "cagr":  0.9, "delta_2024":  1.3},
    "madrid":     {"hvi": 2.03, "cagr":  4.3, "delta_2024":  6.8},
    "lisbon":     {"hvi": 1.40, "cagr":  4.7, "delta_2024":  7.8},
    "athens":     {"hvi": 1.31, "cagr":  6.1, "delta_2024": 11.8},
    # Marchés hors panel HVS — estimation par analogie
    "dubai":      {"hvi": 2.80, "cagr":  3.5, "delta_2024":  3.0},
    "riyadh":     {"hvi": 1.80, "cagr":  4.0, "delta_2024":  5.0},
    "abu_dhabi":  {"hvi": 2.00, "cagr":  3.0, "delta_2024":  3.5},
    "casablanca": {"hvi": 0.60, "cagr":  1.5, "delta_2024":  2.0},
    "marrakech":  {"hvi": 0.55, "cagr":  2.0, "delta_2024":  3.0},
    "cairo":      {"hvi": 0.35, "cagr": -1.0, "delta_2024": -2.0},
    "tunis":      {"hvi": 0.30, "cagr": -0.5, "delta_2024":  1.0}}


# ── CBRE European Hotels Destination Index 2025 ───────────────────────────────
# Source : CBRE Research, December 2025

CBRE_MARKET_DATA = {
    "paris":      {"loc_type_cbre": "IG", "labour_cost_score": 3, "hwe": 3, "revpar_g_ytd25":  0.5},
    "london":     {"loc_type_cbre": "IG", "labour_cost_score": 4, "hwe": 3, "revpar_g_ytd25": -2.0},
    "madrid":     {"loc_type_cbre": "IG", "labour_cost_score": 6, "hwe": 3, "revpar_g_ytd25":  5.5},
    "barcelona":  {"loc_type_cbre": "IG", "labour_cost_score": 6, "hwe": 3, "revpar_g_ytd25": -1.5},
    "lisbon":     {"loc_type_cbre": "IG", "labour_cost_score": 7, "hwe": 3, "revpar_g_ytd25":  1.0},
    "athens":     {"loc_type_cbre": "IG", "labour_cost_score": 8, "hwe": 5, "revpar_g_ytd25":  4.5},
    "milan":      {"loc_type_cbre": "IG", "labour_cost_score": 5, "hwe": 2, "revpar_g_ytd25":  4.0},
    "amsterdam":  {"loc_type_cbre": "IG", "labour_cost_score": 3, "hwe": 2, "revpar_g_ytd25": -0.5},
    "dubai":      {"loc_type_cbre": "IG", "labour_cost_score": 7, "hwe": 4, "revpar_g_ytd25":  3.0},
    "riyadh":     {"loc_type_cbre": "IG", "labour_cost_score": 6, "hwe": 3, "revpar_g_ytd25":  6.0},
    "abu_dhabi":  {"loc_type_cbre": "IG", "labour_cost_score": 6, "hwe": 3, "revpar_g_ytd25":  3.5},
    "casablanca": {"loc_type_cbre": "MH", "labour_cost_score": 9, "hwe": 4, "revpar_g_ytd25":  3.0},
    "marrakech":  {"loc_type_cbre": "SL", "labour_cost_score": 9, "hwe": 5, "revpar_g_ytd25":  4.0},
    "cairo":      {"loc_type_cbre": "IG", "labour_cost_score": 9, "hwe": 4, "revpar_g_ytd25": -3.0},
    "tunis":      {"loc_type_cbre": "MH", "labour_cost_score": 8, "hwe": 3, "revpar_g_ytd25":  1.0}}


# ── Fonctions utilitaires ─────────────────────────────────────────────────────

def goppar_rsd_proxy(market_id: str) -> float:
    """GOPPAR RSD proxy — O'Neill 2023 : 50% classe + 30% type + 20% localisation."""
    p = MARKET_PROFILES_ONEILL.get(market_id)
    if not p:
        return 40.0
    return round(
        ONEILL_RSD_CLASS.get(p["class"], 37.0) * 0.50
        + ONEILL_RSD_PROPTYPE.get(p["proptype"], 40.0) * 0.30
        + ONEILL_RSD_LOCTYPE.get(p["loctype"], 37.0) * 0.20,
        1,
    )

def build_oneill_vars(market_id: str) -> dict:
    p = MARKET_PROFILES_ONEILL.get(market_id, {})
    return {
        "goppar_rsd":       goppar_rsd_proxy(market_id),
        "hotel_class_risk": CLASS_RISK_SCORE.get(p.get("class", "upscale"), 3),
        "loc_type_risk":    LOCTYPE_RISK_SCORE.get(p.get("loctype", "large_metro_urban"), 3)}

def build_hvs_vars(market_id: str) -> dict:
    h = HVS_HVI.get(market_id, {"hvi": 1.0, "cagr": 0.5})
    return {"hvi_index": h["hvi"], "hvi_cagr": h["cagr"]}

def build_cbre_vars(market_id: str) -> dict:
    """Variables CBRE conservées : labour_cost uniquement (HWE supprimé)."""
    c = CBRE_MARKET_DATA.get(market_id, {"labour_cost_score": 5})
    return {"labour_cost": c["labour_cost_score"]}


# ── Macro hôtelière v3.4 — variables à causalité directe ─────────────────────
# Sources :
#   revpar_elast  : proxy calculé depuis CBRE taxonomie IG/SL + DEMAND_PROFILE mix
#                   Études STR/HVS élasticité corporate vs leisure (ratio 0.8 vs 0.3)
#   spend_visitor : UNWTO Tourism Expenditure 2024 + Eurostat accommodation spend
#                   Proxy : ADR × occ_coefficient × séjour_moyen estimé
#   energy_cost   : Eurostat Electricity Prices for Non-Household 2024 (H1)
#                   + mix énergétique national (renouvelables %)
#                   Scale 1-10 : 10 = coût très favorable (faible + mix vert)

MACRO_HOTEL_DATA = {
    # Format : {revpar_elast, spend_visitor, energy_cost}
    # revpar_elast : plus le marché est corporate/MICE, plus l'élasticité est haute
    # spend_visitor : €/nuit/visiteur — dépense totale hébergement + extras
    # energy_cost : 1=très coûteux/dépendant fossiles, 10=favorable/renouvelables

    # Europe
    "paris":      {"revpar_elast": 0.72, "spend_visitor": 220, "energy_cost": 5},
    # Paris : fort corporate (0.72) · spend élevé · énergie nucléaire (mi-coût)
    "london":     {"revpar_elast": 0.78, "spend_visitor": 240, "energy_cost": 4},
    # Londres : corporate dominant · spend le plus élevé · énergie chère UK
    "madrid":     {"revpar_elast": 0.62, "spend_visitor": 160, "energy_cost": 7},
    # Madrid : mixte · spend moyen · Spain bon mix renouvelables (wind/solar)
    "barcelona":  {"revpar_elast": 0.48, "spend_visitor": 155, "energy_cost": 7},
    # Barcelone : leisure majority · énergie comparable à Madrid
    "milan":      {"revpar_elast": 0.70, "spend_visitor": 175, "energy_cost": 4},
    # Milan : corporate/MICE fort · énergie Italie chère (dépendance gaz)
    "amsterdam":  {"revpar_elast": 0.58, "spend_visitor": 180, "energy_cost": 6},
    # Amsterdam : mixte · NL bon mix renouvelables
    # Méditerranée
    "lisbon":     {"revpar_elast": 0.42, "spend_visitor": 130, "energy_cost": 8},
    # Lisbonne : leisure orienté · Portugal excellent mix solaire/éolien
    "athens":     {"revpar_elast": 0.35, "spend_visitor": 110, "energy_cost": 6},
    # Athènes : leisure dominant · énergie modérée · solaire en développement
    # Afrique du Nord
    "casablanca": {"revpar_elast": 0.55, "spend_visitor": 85,  "energy_cost": 7},
    # Casablanca : corporate local fort · Maroc programme solaire Noor
    "marrakech":  {"revpar_elast": 0.28, "spend_visitor": 95,  "energy_cost": 7},
    # Marrakech : leisure très dominant (82%) · faible élasticité PIB
    "cairo":      {"revpar_elast": 0.45, "spend_visitor": 65,  "energy_cost": 3},
    # Le Caire : mixte · Égypte forte dépendance gaz/pétrole · énergie coûteuse
    "tunis":      {"revpar_elast": 0.38, "spend_visitor": 55,  "energy_cost": 4},
    # Tunis : leisure · dépendance fossiles · spend faible
    # Moyen-Orient
    "dubai":      {"revpar_elast": 0.65, "spend_visitor": 245, "energy_cost": 6},
    # Dubaï : mixte corporate/MICE · spend très élevé · énergie subventionnée
    "riyadh":     {"revpar_elast": 0.62, "spend_visitor": 175, "energy_cost": 7},
    # Riyad : corporate dominant · énergie locale bon marché (pétrole national)
    "abu_dhabi":  {"revpar_elast": 0.60, "spend_visitor": 200, "energy_cost": 7},
    # Abu Dhabi : corporate/MICE · Masdar → transition renouvelables avancée
}


def build_macro_vars(market_id: str) -> dict:
    """
    Variables macro hôtelières v3.4 — causalité directe sur RevPAR/EBITDA.
    Remplace gdp_g (faible prédictivité CT) et hwe_score (opérationnel, pas macro).
    """
    d = MACRO_HOTEL_DATA.get(market_id, {
        "revpar_elast": 0.5, "spend_visitor": 120, "energy_cost": 5})
    cbre = CBRE_MARKET_DATA.get(market_id, {"labour_cost_score": 5})
    return {
        "revpar_elast":  d["revpar_elast"],
        "spend_visitor": d["spend_visitor"],
        "connect":       5 if market_id in ("paris", "london", "dubai") else
                         4 if market_id in ("madrid", "barcelona", "milan",
                                            "amsterdam", "lisbon", "riyadh", "abu_dhabi") else 3,
        "labour_cost":   cbre["labour_cost_score"],
        "energy_cost":   d["energy_cost"]}

def dev_revpar_index(revpar: float, dev_cost_k: float) -> float:
    if dev_cost_k <= 0:
        return 0.0
    return round((revpar * 365 / (dev_cost_k * 1000)) * 100, 2)

def yield_on_cost(revpar: float, dev_cost_k: float, goppar_margin: float = 0.38) -> float:
    if dev_cost_k <= 0:
        return 0.0
    return round((revpar * 365 * goppar_margin / (dev_cost_k * 1000)) * 100, 2)


# ── Données marchés — recalibrées v3.0 ───────────────────────────────────────
# Sources :
#   Performance  : STR Global 2024, HVS 2025 HVI (RevPAR = HVI × 173737 / 365 approximé)
#   Liquidité    : HVS 2025 transactions, JLL Hotels 2024, CBRE 2025
#   Macro        : Eurostat, FMI WEO Oct 2024, UNWTO 2024, CBRE 2025
#   Risque       : Coface 2024, O'Neill 2023, estimation terrain
#   ESG          : BREEAM, HQE, EU Taxonomy estimation 2024
#   Faisabilité  : HVS, Cushman & Wakefield Hotels 2024

MARKETS_DEFAULT = [
    # ── Europe ───────────────────────────────────────────────────────────────

    {"id": "paris", "name": "Paris", "region": "EU",
     "perf":       {"revpar": 175, "occ": 77,  "adr": 227, "revpar_g": 1.5},
     "pipeline":   {"pip_ratio": 2,  "rooms_g": 3,  "saturation": 2},
     "liquidite":  {"vol_tx": 1500, "caprate": 4.0, "nb_deals": 25, **build_hvs_vars("paris")},
     "macro":      {"connect": 5,   **build_macro_vars("paris")},
     "risque":     {"pol_risk": 2,  "reg_stab": 4,  "geo_exp": 2,   **build_oneill_vars("paris")},
     "esg":        {"cert_pct": 35, "reg_esg": 5,   "tax_eu": 4},
     "faisabilite":{"dev_cost": 420, "dev_revpar_idx": dev_revpar_index(175, 420), "yield_on_cost": yield_on_cost(175, 420)}},

    {"id": "london", "name": "Londres", "region": "EU",
     "perf":       {"revpar": 195, "occ": 80,  "adr": 244, "revpar_g": 0.5},
     "pipeline":   {"pip_ratio": 3,  "rooms_g": 4,  "saturation": 2},
     "liquidite":  {"vol_tx": 3000, "caprate": 3.8, "nb_deals": 35, **build_hvs_vars("london")},
     "macro":      {"connect": 5,   **build_macro_vars("london")},
     "risque":     {"pol_risk": 2,  "reg_stab": 4,  "geo_exp": 2,   **build_oneill_vars("london")},
     "esg":        {"cert_pct": 42, "reg_esg": 5,   "tax_eu": 4},
     "faisabilite":{"dev_cost": 480, "dev_revpar_idx": dev_revpar_index(195, 480), "yield_on_cost": yield_on_cost(195, 480)}},

    {"id": "madrid", "name": "Madrid", "region": "EU",
     "perf":       {"revpar": 128, "occ": 76,  "adr": 168, "revpar_g": 7.5},
     "pipeline":   {"pip_ratio": 4,  "rooms_g": 5,  "saturation": 2},
     "liquidite":  {"vol_tx": 440,  "caprate": 4.7, "nb_deals": 14, **build_hvs_vars("madrid")},
     "macro":      {"connect": 4,   **build_macro_vars("madrid")},
     "risque":     {"pol_risk": 2,  "reg_stab": 3,  "geo_exp": 2,   **build_oneill_vars("madrid")},
     "esg":        {"cert_pct": 20, "reg_esg": 3,   "tax_eu": 3},
     "faisabilite":{"dev_cost": 230, "dev_revpar_idx": dev_revpar_index(128, 230), "yield_on_cost": yield_on_cost(128, 230)}},

    {"id": "barcelona", "name": "Barcelone", "region": "MED",
     "perf":       {"revpar": 122, "occ": 76,  "adr": 161, "revpar_g": 3.0},
     "pipeline":   {"pip_ratio": 2,  "rooms_g": 2,  "saturation": 3},
     "liquidite":  {"vol_tx": 444,  "caprate": 4.9, "nb_deals": 12, **build_hvs_vars("barcelona")},
     "macro":      {"connect": 4,   **build_macro_vars("barcelona")},
     "risque":     {"pol_risk": 3,  "reg_stab": 2,  "geo_exp": 2,   **build_oneill_vars("barcelona")},
     "esg":        {"cert_pct": 18, "reg_esg": 3,   "tax_eu": 3},
     "faisabilite":{"dev_cost": 260, "dev_revpar_idx": dev_revpar_index(122, 260), "yield_on_cost": yield_on_cost(122, 260)}},

    {"id": "milan", "name": "Milan", "region": "EU",
     "perf":       {"revpar": 138, "occ": 74,  "adr": 187, "revpar_g": 5.5},
     "pipeline":   {"pip_ratio": 3,  "rooms_g": 4,  "saturation": 2},
     "liquidite":  {"vol_tx": 280,  "caprate": 4.4, "nb_deals": 10, **build_hvs_vars("milan")},
     "macro":      {"connect": 4,   **build_macro_vars("milan")},
     "risque":     {"pol_risk": 2,  "reg_stab": 3,  "geo_exp": 2,   **build_oneill_vars("milan")},
     "esg":        {"cert_pct": 22, "reg_esg": 4,   "tax_eu": 3},
     "faisabilite":{"dev_cost": 300, "dev_revpar_idx": dev_revpar_index(138, 300), "yield_on_cost": yield_on_cost(138, 300)}},

    {"id": "amsterdam", "name": "Amsterdam", "region": "EU",
     "perf":       {"revpar": 155, "occ": 78,  "adr": 199, "revpar_g": 2.0},
     "pipeline":   {"pip_ratio": 2,  "rooms_g": 2,  "saturation": 2},
     "liquidite":  {"vol_tx": 320,  "caprate": 4.2, "nb_deals": 11, **build_hvs_vars("amsterdam")},
     "macro":      {"connect": 5,   **build_macro_vars("amsterdam")},
     "risque":     {"pol_risk": 1,  "reg_stab": 4,  "geo_exp": 1,   **build_oneill_vars("amsterdam")},
     "esg":        {"cert_pct": 40, "reg_esg": 5,   "tax_eu": 5},
     "faisabilite":{"dev_cost": 330, "dev_revpar_idx": dev_revpar_index(155, 330), "yield_on_cost": yield_on_cost(155, 330)}},

    # ── Méditerranée ─────────────────────────────────────────────────────────

    {"id": "lisbon", "name": "Lisbonne", "region": "MED",
     "perf":       {"revpar": 108, "occ": 74,  "adr": 146, "revpar_g": 8.0},
     "pipeline":   {"pip_ratio": 7,  "rooms_g": 8,  "saturation": 3},
     "liquidite":  {"vol_tx": 180,  "caprate": 5.1, "nb_deals": 8,  **build_hvs_vars("lisbon")},
     "macro":      {"connect": 4,   **build_macro_vars("lisbon")},
     "risque":     {"pol_risk": 1,  "reg_stab": 4,  "geo_exp": 1,   **build_oneill_vars("lisbon")},
     "esg":        {"cert_pct": 15, "reg_esg": 3,   "tax_eu": 3},
     "faisabilite":{"dev_cost": 185, "dev_revpar_idx": dev_revpar_index(108, 185), "yield_on_cost": yield_on_cost(108, 185)}},

    {"id": "athens", "name": "Athènes", "region": "MED",
     "perf":       {"revpar": 88,  "occ": 73,  "adr": 121, "revpar_g": 11.0},
     "pipeline":   {"pip_ratio": 9,  "rooms_g": 10, "saturation": 2},
     "liquidite":  {"vol_tx": 130,  "caprate": 5.8, "nb_deals": 7,  **build_hvs_vars("athens")},
     "macro":      {"connect": 3,   **build_macro_vars("athens")},
     "risque":     {"pol_risk": 2,  "reg_stab": 3,  "geo_exp": 2,   **build_oneill_vars("athens")},
     "esg":        {"cert_pct": 8,  "reg_esg": 2,   "tax_eu": 2},
     "faisabilite":{"dev_cost": 145, "dev_revpar_idx": dev_revpar_index(88, 145), "yield_on_cost": yield_on_cost(88, 145)}},

    # ── Afrique du Nord ───────────────────────────────────────────────────────

    {"id": "casablanca", "name": "Casablanca", "region": "AN",
     "perf":       {"revpar": 52,  "occ": 62,  "adr": 84,  "revpar_g": 5.0},
     "pipeline":   {"pip_ratio": 10, "rooms_g": 8,  "saturation": 2},
     "liquidite":  {"vol_tx": 35,   "caprate": 7.8, "nb_deals": 3,  **build_hvs_vars("casablanca")},
     "macro":      {"connect": 3,   **build_macro_vars("casablanca")},
     "risque":     {"pol_risk": 2,  "reg_stab": 3,  "geo_exp": 2,   **build_oneill_vars("casablanca")},
     "esg":        {"cert_pct": 5,  "reg_esg": 2,   "tax_eu": 1},
     "faisabilite":{"dev_cost": 85,  "dev_revpar_idx": dev_revpar_index(52, 85),  "yield_on_cost": yield_on_cost(52, 85)}},

    {"id": "marrakech", "name": "Marrakech", "region": "AN",
     "perf":       {"revpar": 62,  "occ": 67,  "adr": 93,  "revpar_g": 8.0},
     "pipeline":   {"pip_ratio": 12, "rooms_g": 11, "saturation": 2},
     "liquidite":  {"vol_tx": 25,   "caprate": 8.2, "nb_deals": 2,  **build_hvs_vars("marrakech")},
     "macro":      {"connect": 3,   **build_macro_vars("marrakech")},
     "risque":     {"pol_risk": 2,  "reg_stab": 3,  "geo_exp": 2,   **build_oneill_vars("marrakech")},
     "esg":        {"cert_pct": 4,  "reg_esg": 2,   "tax_eu": 1},
     "faisabilite":{"dev_cost": 75,  "dev_revpar_idx": dev_revpar_index(62, 75),  "yield_on_cost": yield_on_cost(62, 75)}},

    {"id": "cairo", "name": "Le Caire", "region": "AN",
     "perf":       {"revpar": 38,  "occ": 58,  "adr": 66,  "revpar_g": 3.0},
     "pipeline":   {"pip_ratio": 7,  "rooms_g": 5,  "saturation": 3},
     "liquidite":  {"vol_tx": 18,   "caprate": 9.2, "nb_deals": 2,  **build_hvs_vars("cairo")},
     "macro":      {"connect": 3,   **build_macro_vars("cairo")},
     "risque":     {"pol_risk": 4,  "reg_stab": 2,  "geo_exp": 4,   **build_oneill_vars("cairo")},
     "esg":        {"cert_pct": 3,  "reg_esg": 1,   "tax_eu": 1},
     "faisabilite":{"dev_cost": 68,  "dev_revpar_idx": dev_revpar_index(38, 68),  "yield_on_cost": yield_on_cost(38, 68)}},

    {"id": "tunis", "name": "Tunis", "region": "AN",
     "perf":       {"revpar": 36,  "occ": 57,  "adr": 63,  "revpar_g": 3.5},
     "pipeline":   {"pip_ratio": 5,  "rooms_g": 4,  "saturation": 3},
     "liquidite":  {"vol_tx": 12,   "caprate": 9.8, "nb_deals": 1,  **build_hvs_vars("tunis")},
     "macro":      {"connect": 2,   **build_macro_vars("tunis")},
     "risque":     {"pol_risk": 3,  "reg_stab": 2,  "geo_exp": 3,   **build_oneill_vars("tunis")},
     "esg":        {"cert_pct": 2,  "reg_esg": 1,   "tax_eu": 1},
     "faisabilite":{"dev_cost": 58,  "dev_revpar_idx": dev_revpar_index(36, 58),  "yield_on_cost": yield_on_cost(36, 58)}},

    # ── Moyen-Orient ─────────────────────────────────────────────────────────

    {"id": "dubai", "name": "Dubaï", "region": "MO",
     "perf":       {"revpar": 168, "occ": 77,  "adr": 218, "revpar_g": 4.0},
     "pipeline":   {"pip_ratio": 8,  "rooms_g": 10, "saturation": 3},
     "liquidite":  {"vol_tx": 650,  "caprate": 6.3, "nb_deals": 18, **build_hvs_vars("dubai")},
     "macro":      {"connect": 5,   **build_macro_vars("dubai")},
     "risque":     {"pol_risk": 2,  "reg_stab": 4,  "geo_exp": 3,   **build_oneill_vars("dubai")},
     "esg":        {"cert_pct": 18, "reg_esg": 4,   "tax_eu": 2},
     "faisabilite":{"dev_cost": 360, "dev_revpar_idx": dev_revpar_index(168, 360), "yield_on_cost": yield_on_cost(168, 360)}},

    {"id": "riyadh", "name": "Riyad", "region": "MO",
     "perf":       {"revpar": 118, "occ": 68,  "adr": 174, "revpar_g": 14.0},
     "pipeline":   {"pip_ratio": 18, "rooms_g": 20, "saturation": 3},
     "liquidite":  {"vol_tx": 180,  "caprate": 7.2, "nb_deals": 8,  **build_hvs_vars("riyadh")},
     "macro":      {"connect": 4,   **build_macro_vars("riyadh")},
     "risque":     {"pol_risk": 3,  "reg_stab": 3,  "geo_exp": 4,   **build_oneill_vars("riyadh")},
     "esg":        {"cert_pct": 8,  "reg_esg": 3,   "tax_eu": 1},
     "faisabilite":{"dev_cost": 210, "dev_revpar_idx": dev_revpar_index(118, 210), "yield_on_cost": yield_on_cost(118, 210)}},

    {"id": "abu_dhabi", "name": "Abu Dhabi", "region": "MO",
     "perf":       {"revpar": 135, "occ": 72,  "adr": 188, "revpar_g": 6.0},
     "pipeline":   {"pip_ratio": 9,  "rooms_g": 9,  "saturation": 2},
     "liquidite":  {"vol_tx": 140,  "caprate": 6.6, "nb_deals": 6,  **build_hvs_vars("abu_dhabi")},
     "macro":      {"connect": 4,   **build_macro_vars("abu_dhabi")},
     "risque":     {"pol_risk": 2,  "reg_stab": 4,  "geo_exp": 3,   **build_oneill_vars("abu_dhabi")},
     "esg":        {"cert_pct": 12, "reg_esg": 4,   "tax_eu": 1},
     "faisabilite":{"dev_cost": 290, "dev_revpar_idx": dev_revpar_index(135, 290), "yield_on_cost": yield_on_cost(135, 290)}},
]


# ── v3.1 — Notation AAA-CCC · Gate 0 politique · Stress tests ────────────────
# Inspiré pratiques cabinet (HVS/Deloitte/PwC Hospitality)

# Grille de notation type agence — score 0-100 → note
RATING_SCALE = [
    # (seuil_min, note, interprétation, couleur)
    # Seuils calibrés sur la distribution empirique du scoring absolu :
    # avec bornes mondiales, le panel EU/MENA se distribue entre ~30 et ~58.
    # Un score 58+ en absolu = marché exceptionnel sur tous les plans.
    (58, "AAA", "Investissement core, risque minimal",          "#1fbd7e"),
    (53, "AA",  "Core+, légères vigilances",                    "#3ecf8e"),
    (48, "A",   "Value-add, bon rendement",                     "#4f7fff"),
    (43, "BBB", "Correct, surveiller les indicateurs",          "#8f9fff"),
    (38, "BB",  "Potentiel mais risques significatifs",         "#f0a030"),
    (33, "B",   "Opportunité à haut risque / distressed",       "#f07030"),
    (0,  "CCC", "À éviter sauf rendement exceptionnel",         "#e2504a"),
]

# Gate 0 — stabilité politique : seuil éliminatoire AVANT scoring.
# Échelle interne pol_risk 1-5 (1 = très stable, 5 = critique).
# Seuils différenciés par profil investisseur : Core est plus exigeant.
GATE0_THRESHOLDS = {
    "Core":         {"pol_risk_max": 2, "geo_exp_max": 3},
    "Value-add":    {"pol_risk_max": 3, "geo_exp_max": 4},
    "Opportuniste": {"pol_risk_max": 4, "geo_exp_max": 5}}

# Haircut politique post-scoring — pour les marchés qui passent Gate 0
# mais restent fragiles. Clé = pol_risk (1-5), valeur = correction multiplicative.
POLITICAL_HAIRCUT = {
    1: 1.00,   # très stable : pas de correction
    2: 1.00,   # stable : neutre
    3: 0.95,   # vigilance : -5%
    4: 0.88,   # élevé : -12%
    5: 0.80,   # critique : -20% (en pratique éliminé par Gate 0 sauf Opportuniste)
}

# Stress tests — 3 scénarios appliqués aux variables de marché.
# Chocs multiplicatifs (×) ou additifs (+) par variable.
# Calibration : downside ≈ récession type 2008-09 hôtelière européenne
# (RevPAR -15/-20%, cap rates +100/150bps), upside ≈ cycle expansion fort.
STRESS_SCENARIOS = {
    "base": {
        "label": "Base", "color": "#4f7fff", "proba": "50%",
        "shocks": {},  # tendances actuelles, aucune modification
    },
    "upside": {
        "label": "Upside", "color": "#1fbd7e", "proba": "20%",
        "shocks": {
            # variable: (mode, valeur) — mode "mult" ou "add"
            "revpar":   ("mult", 1.08),
            "occ":      ("add",  2.0),
            "adr":      ("mult", 1.05),
            "revpar_g": ("add",  3.0),
            "gdp_g":    ("add",  1.5),
            "caprate":  ("add", -0.4),   # compression
            "vol_tx":   ("mult", 1.25),
            "tourists": ("mult", 1.08)}},
    "downside": {
        "label": "Downside", "color": "#e2504a", "proba": "30%",
        "shocks": {
            "revpar":   ("mult", 0.85),
            "occ":      ("add", -6.0),
            "adr":      ("mult", 0.92),
            "revpar_g": ("add", -8.0),
            "gdp_g":    ("add", -2.0),
            "caprate":  ("add",  1.5),   # décompression +150bps
            "vol_tx":   ("mult", 0.55),  # liquidité s'assèche
            "nb_deals": ("mult", 0.55),
            "tourists": ("mult", 0.90),
            "pip_ratio":("mult", 0.60),  # pipeline gelé (constructions annulées)
            "hvi_cagr": ("add", -3.0)}}}

# Zone interdite risque/rendement — règle d'or cabinet :
# risque élevé + attractivité faible = refus quel que soit le narratif.
FORBIDDEN_ZONE = {"risk_min": 55, "score_max": 45}


# ── v3.3 — Données Insights décision (6 signaux comité) ──────────────────────
# Données partiellement fictives calibrées — à remplacer par données STR/UNWTO propriétaires.
# Sources proxy : CBRE taxonomie, ICCA Rankings, STR Demand Segmentation estimates,
#                 Oxford Economics, HVS, JLL Hotels

# Point 1 — Phase de cycle de valeur HVS
# Dérivé du ratio HVI delta_2024 vs CAGR 10 ans
# "early"  : delta_2024 > 0 ET delta < CAGR → appréciation en cours, pas au pic
# "mid"    : delta_2024 ≈ CAGR → dans le trend
# "late"   : delta_2024 > CAGR → surperformance, risque de retournement
# "peak"   : delta_2024 > 1.5×CAGR → sommet probable
# "decline": delta_2024 < 0

def hvi_cycle_phase(market_id: str) -> dict:
    """Phase de cycle de valeur HVS — signal d'entrée/sortie."""
    h = HVS_HVI.get(market_id, {"hvi": 1.0, "cagr": 0.5, "delta_2024": 0.0})
    delta = h["delta_2024"]
    cagr  = h["cagr"]

    if delta < 0:
        phase, color, signal = "Déclin", "#e2504a", "⚠️ Éviter / sortir"
    elif cagr <= 0 and delta > 0:
        phase, color, signal = "Rebond", "#f0a030", "🔍 Surveiller"
    elif delta > cagr * 1.5 and cagr > 0:
        phase, color, signal = "Late / Peak", "#f0a030", "⚠️ Risque sommet"
    elif delta >= cagr * 0.8:
        phase, color, signal = "Mid Expansion", "#4f7fff", "✅ Dans le trend"
    else:
        phase, color, signal = "Early Expansion", "#1fbd7e", "✅ Signal d'entrée"

    return {
        "phase":  phase,
        "color":  color,
        "signal": signal,
        "delta":  delta,
        "cagr":   cagr,
        "hvi":    h["hvi"]}


# Point 3 — Pipeline vs absorption demand (proxy CBRE Supply/Demand quadrant)
# pipeline_absorbability = rooms_g / pip_ratio
# > 1.0 : la demande absorbe le pipeline → pricing power préservé
# < 0.7 : pipeline dilutif → pression ADR probable

# Point 4 — Liquidité structurelle vs cyclique
# Discriminant : hvi_cagr 10 ans
# > +2% = structurelle (liquide même en bas de cycle)
# 0-2%  = mixte
# < 0%  = cyclique (uniquement liquide en expansion)
LIQUIDITY_PROFILE = {
    "paris":      {"type": "Structurelle", "color": "#1fbd7e", "depth": 5,
                   "buyers": ["PE international", "REITs EU", "SWF", "Family offices", "Opérateurs"]},
    "london":     {"type": "Structurelle", "color": "#1fbd7e", "depth": 5,
                   "buyers": ["PE US/UK", "REITs UK", "SWF Asie", "Institutionnels", "Opérateurs"]},
    "madrid":     {"type": "Structurelle", "color": "#1fbd7e", "depth": 4,
                   "buyers": ["PE EU", "Family offices ibériques", "REITs", "Fonds souverains"]},
    "barcelona":  {"type": "Mixte",        "color": "#4f7fff", "depth": 3,
                   "buyers": ["PE EU", "Family offices", "Investisseurs locaux"]},
    "milan":      {"type": "Mixte",        "color": "#4f7fff", "depth": 3,
                   "buyers": ["PE EU", "Family offices italiens", "REITs"]},
    "amsterdam":  {"type": "Mixte",        "color": "#4f7fff", "depth": 3,
                   "buyers": ["PE EU", "Fonds pension NL", "Institutionnels"]},
    "lisbon":     {"type": "Cyclique",     "color": "#f0a030", "depth": 2,
                   "buyers": ["PE opportuniste", "Family offices PT/ES", "Privés"]},
    "athens":     {"type": "Cyclique",     "color": "#f0a030", "depth": 2,
                   "buyers": ["PE value-add", "Fonds grecs", "Investisseurs ME"]},
    "dubai":      {"type": "Structurelle", "color": "#1fbd7e", "depth": 4,
                   "buyers": ["SWF Golfe", "PE international", "Family offices ME", "REITs"]},
    "riyadh":     {"type": "Cyclique",     "color": "#f0a030", "depth": 2,
                   "buyers": ["PIF Saudi", "Partenaires Vision 2030", "PE ME"]},
    "abu_dhabi":  {"type": "Mixte",        "color": "#4f7fff", "depth": 3,
                   "buyers": ["ADIA", "Mubadala", "PE international", "SWF"]},
    "casablanca": {"type": "Cyclique",     "color": "#f0a030", "depth": 2,
                   "buyers": ["CDG Maroc", "Fonds régionaux", "Privés locaux"]},
    "marrakech":  {"type": "Cyclique",     "color": "#f0a030", "depth": 1,
                   "buyers": ["Privés locaux", "Family offices FR/BE", "PE opportuniste"]},
    "cairo":      {"type": "Cyclique",     "color": "#e2504a", "depth": 1,
                   "buyers": ["Fonds locaux", "Partenaires gouvernementaux"]},
    "tunis":      {"type": "Cyclique",     "color": "#e2504a", "depth": 1,
                   "buyers": ["Investisseurs locaux", "Diaspora"]}}


# Point 5 — Coût de remplacement : HVI réel €/ch vs dev_cost €/ch
# HVI_EUR = hvi_index × 173 737 € (base HVS 1993)
HVI_BASE_EUR = 173_737  # €/chambre — base HVS 1993=1.000


def replacement_cost_ratio(market_id: str, dev_cost_k: float) -> dict:
    """
    Ratio valeur de marché / coût de remplacement.
    > 1.0 : marché valorisé au-dessus du remplacement → pipeline à venir
    < 1.0 : achat défensif sous coût de reconstruction → opportunité
    = 1.0 : équilibre
    Source : HVS London 2025 methodology
    """
    h = HVS_HVI.get(market_id, {"hvi": 1.0})
    hvi_eur = h["hvi"] * HVI_BASE_EUR          # valeur €/chambre
    dev_eur = dev_cost_k * 1000                # dev_cost en €/chambre

    if dev_eur <= 0:
        return {"ratio": 0.0, "hvi_eur": 0, "dev_eur": 0, "signal": "—", "color": "#888"}

    ratio = round(hvi_eur / dev_eur, 2)

    if ratio < 0.75:
        signal, color = "🟢 Sous coût — achat défensif attractif", "#1fbd7e"
    elif ratio < 1.0:
        signal, color = "🟡 Légèrement sous coût — opportunité modérée", "#4f7fff"
    elif ratio < 1.25:
        signal, color = "⚪ Valorisé au coût — marché équilibré", "#8b92a8"
    elif ratio < 1.60:
        signal, color = "🟠 Au-dessus coût — pipeline à surveiller", "#f0a030"
    else:
        signal, color = "🔴 Très au-dessus coût — risque suroffre", "#e2504a"

    return {"ratio": ratio, "hvi_eur": int(hvi_eur), "dev_eur": int(dev_eur),
            "signal": signal, "color": color}


# Point 6 — Concentration de la demande et diversification
# Sources : CBRE taxonomie, ICCA Rankings 2024, STR Segmentation estimates
# demand_mix : % estimé par segment (doit sommer à 100)
# corporate_depth : 1-5 (5 = hub mondial d'affaires)
# mice_rank : rang ICCA estimé pour les villes MICE (None si non classé)

DEMAND_PROFILE = {
    "paris":      {"leisure": 45, "corporate": 35, "mice": 15, "transit": 5,
                   "corporate_depth": 5, "mice_rank": 2, "seasonality": "Faible",
                   "dominant": "Mixed — avantage diversification"},
    "london":     {"leisure": 40, "corporate": 40, "mice": 15, "transit": 5,
                   "corporate_depth": 5, "mice_rank": 1, "seasonality": "Faible",
                   "dominant": "Mixed — avantage diversification"},
    "madrid":     {"leisure": 40, "corporate": 35, "mice": 20, "transit": 5,
                   "corporate_depth": 4, "mice_rank": 5, "seasonality": "Modérée",
                   "dominant": "Mixed — fort MICE"},
    "barcelona":  {"leisure": 55, "corporate": 25, "mice": 18, "transit": 2,
                   "corporate_depth": 3, "mice_rank": 4, "seasonality": "Modérée",
                   "dominant": "Leisure dominant — risque saisonnalité"},
    "milan":      {"leisure": 35, "corporate": 42, "mice": 20, "transit": 3,
                   "corporate_depth": 4, "mice_rank": 8, "seasonality": "Modérée",
                   "dominant": "Corporate / MICE — résilient"},
    "amsterdam":  {"leisure": 48, "corporate": 32, "mice": 15, "transit": 5,
                   "corporate_depth": 3, "mice_rank": 10, "seasonality": "Modérée",
                   "dominant": "Leisure / Corporate — mixte"},
    "lisbon":     {"leisure": 60, "corporate": 22, "mice": 14, "transit": 4,
                   "corporate_depth": 2, "mice_rank": 20, "seasonality": "Modérée",
                   "dominant": "Leisure dominant — dépendance tourisme"},
    "athens":     {"leisure": 72, "corporate": 15, "mice": 10, "transit": 3,
                   "corporate_depth": 2, "mice_rank": 35, "seasonality": "Forte",
                   "dominant": "Leisure fort — vulnérabilité saisonnière"},
    "dubai":      {"leisure": 38, "corporate": 35, "mice": 22, "transit": 5,
                   "corporate_depth": 5, "mice_rank": 3, "seasonality": "Modérée",
                   "dominant": "Mixed — hub MICE mondial"},
    "riyadh":     {"leisure": 20, "corporate": 55, "mice": 20, "transit": 5,
                   "corporate_depth": 4, "mice_rank": 15, "seasonality": "Faible",
                   "dominant": "Corporate dominant — faible exposition leisure"},
    "abu_dhabi":  {"leisure": 30, "corporate": 45, "mice": 20, "transit": 5,
                   "corporate_depth": 4, "mice_rank": 12, "seasonality": "Faible",
                   "dominant": "Corporate / MICE — résilient"},
    "casablanca": {"leisure": 30, "corporate": 55, "mice": 12, "transit": 3,
                   "corporate_depth": 3, "mice_rank": None, "seasonality": "Faible",
                   "dominant": "Corporate dominant — base locale solide"},
    "marrakech":  {"leisure": 82, "corporate": 10, "mice": 6,  "transit": 2,
                   "corporate_depth": 1, "mice_rank": None, "seasonality": "Forte",
                   "dominant": "Leisure très dominant — haute volatilité"},
    "cairo":      {"leisure": 45, "corporate": 35, "mice": 12, "transit": 8,
                   "corporate_depth": 3, "mice_rank": None, "seasonality": "Modérée",
                   "dominant": "Mixed — instabilité structurelle"},
    "tunis":      {"leisure": 65, "corporate": 25, "mice": 8,  "transit": 2,
                   "corporate_depth": 2, "mice_rank": None, "seasonality": "Forte",
                   "dominant": "Leisure dominant — marché étroit"}}


def demand_diversification_score(market_id: str) -> dict:
    """
    Indice de diversification de la demande (Herfindahl-Hirschman inversé).
    HHI concentré (un segment dominant) → score bas → risque élevé.
    Fallback complet pour les villes non renseignées dans DEMAND_PROFILE.
    """
    _default = {
        "leisure": 50, "corporate": 30, "mice": 15, "transit": 5,
        "corporate_depth": 3, "mice_rank": None,
        "seasonality": "—", "dominant": "Données non disponibles — saisir manuellement",
    }
    dp = {**_default, **DEMAND_PROFILE.get(market_id, {})}

    shares = [dp["leisure"], dp["corporate"], dp["mice"], dp["transit"]]
    hhi    = sum((s / 100) ** 2 for s in shares)
    diversif = round((1 - hhi) / (1 - 0.25) * 100)

    leisure_pct = dp["leisure"]
    if leisure_pct >= 70:
        risk_label, risk_color = "Concentration élevée — volatilité forte", "#e2504a"
    elif leisure_pct >= 55:
        risk_label, risk_color = "Concentration modérée", "#f0a030"
    else:
        risk_label, risk_color = "Demande diversifiée — résiliente", "#1fbd7e"

    return {
        "diversif_score":  diversif,
        "hhi":             round(hhi, 3),
        "leisure_pct":     dp["leisure"],
        "corporate_pct":   dp["corporate"],
        "mice_pct":        dp["mice"],
        "transit_pct":     dp["transit"],
        "corporate_depth": dp["corporate_depth"],
        "mice_rank":       dp["mice_rank"],
        "seasonality":     dp["seasonality"],
        "dominant":        dp["dominant"],
        "risk_label":      risk_label,
        "risk_color":      risk_color,
    }
