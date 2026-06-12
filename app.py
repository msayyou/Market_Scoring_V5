# app.py — REIV Market Scorer v3.0
# UX simplifiée : page d'accueil · sidebar allégée · tab Données guidé

import copy
import json
import uuid
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from data import (
    DIMS, MARKETS_DEFAULT, PROFILES, REGION_COLORS, REGION_LABELS,
    VARIABLE_BOUNDS, ONEILL_RSD_CLASS, ONEILL_RSD_PROPTYPE, ONEILL_RSD_LOCTYPE,
    hvi_cycle_phase, replacement_cost_ratio, demand_diversification_score,
    LIQUIDITY_PROFILE, DEMAND_PROFILE, HVI_BASE_EUR,
)
from scoring import (
    compute_scores, default_var_weights, score_color, risk_color, confidence_color,
    score_to_rating, apply_gate0,
)
from scoring_advanced import (
    full_analysis, sensitivity_analysis,
    compute_momentum, compute_caprate_spread,
    risk_penetration_index, CYCLE_PHASES,
    stress_test_markets,
)
from report import generate_fiche, generate_comparatif

# ── Config ────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="REIV — Scoring Marchés Hôteliers",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
[data-testid="stSidebar"] { background: #0d1117; }
.block-container { padding-top: 1.5rem; }
.stMetric label { font-size: 11px !important; color: #8b92a8 !important; }
div[data-testid="stMetricValue"] { font-size: 1.2rem !important; }

/* ── Fix tabs tronqués ── */
[data-testid="stTabs"] > div:first-child {
    overflow-x: auto !important;
    flex-wrap: nowrap !important;
}
button[data-baseweb="tab"] {
    white-space: nowrap !important;
    min-width: fit-content !important;
    padding-left: 16px !important;
    padding-right: 16px !important;
    font-size: 13px !important;
    overflow: visible !important;
}
button[data-baseweb="tab"] p {
    white-space: nowrap !important;
    overflow: visible !important;
    text-overflow: unset !important;
    font-size: 13px !important;
}
[role="tablist"] {
    overflow-x: auto !important;
    overflow-y: hidden !important;
    flex-wrap: nowrap !important;
    scrollbar-width: thin;
}
</style>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────

if "markets_pool"  not in st.session_state:
    st.session_state.markets_pool  = copy.deepcopy(MARKETS_DEFAULT)
if "active_ids"    not in st.session_state:
    st.session_state.active_ids    = [m["id"] for m in MARKETS_DEFAULT]
if "dim_weights"   not in st.session_state:
    st.session_state.dim_weights   = dict(PROFILES["Value-add"])
if "var_weights"   not in st.session_state:
    st.session_state.var_weights   = default_var_weights()
if "profile_name"  not in st.session_state:
    st.session_state.profile_name  = "Value-add"
if "norm_method"   not in st.session_state:
    st.session_state.norm_method   = "absolute"

# ── Helpers ───────────────────────────────────────────────────────────────────

def get_active_markets():
    pool = {m["id"]: m for m in st.session_state.markets_pool}
    return [pool[i] for i in st.session_state.active_ids if i in pool]

def blank_market(name, region):
    m = {"id": f"custom_{uuid.uuid4().hex[:8]}", "name": name, "region": region}
    for d in DIMS:
        m[d["id"]] = {v["id"]: 0.0 for v in d["vars"]}
    return m

def badge(text, color, size="10px"):
    return (f"<span style='background:{color}22;color:{color};font-size:{size};"
            f"padding:2px 8px;border-radius:10px;font-weight:600;display:inline-block;'>"
            f"{text}</span>")

def safe_hvi_cycle(mid):
    try:
        return hvi_cycle_phase(mid)
    except Exception:
        return {"phase": "—", "color": "#8b92a8", "signal": "Données HVS non disponibles",
                "delta": 0, "cagr": 0, "hvi": 1.0}

def safe_rcr(mid, dev_cost_k):
    try:
        return replacement_cost_ratio(mid, dev_cost_k)
    except Exception:
        return {"ratio": 0.0, "hvi_eur": 0, "dev_eur": int(dev_cost_k*1000),
                "signal": "Données HVS non disponibles", "color": "#8b92a8"}

def safe_demand_div(mid):
    try:
        return demand_diversification_score(mid)
    except Exception:
        return {"diversif_score": 50, "hhi": 0.4, "leisure_pct": 50,
                "corporate_pct": 30, "mice_pct": 15, "transit_pct": 5,
                "corporate_depth": 3, "mice_rank": None, "seasonality": "—",
                "dominant": "Données non disponibles", "risk_label": "—", "risk_color": "#8b92a8"}

def safe_liquidity(mid):
    return LIQUIDITY_PROFILE.get(mid, {
        "type": "Non renseigné", "color": "#8b92a8", "depth": 1,
        "buyers": ["Données non disponibles — saisir manuellement"]
    })
    return (f"<span style='background:{color}22;color:{color};font-size:{size};"
            f"padding:2px 8px;border-radius:10px;font-weight:600;display:inline-block;'>"
            f"{text}</span>")

# ── SIDEBAR ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 🏨 REIV Market Scorer")
    st.caption("v3.0 · Scoring absolu · HVS + CBRE + O'Neill 2023")
    st.divider()

    # ── Profil : 3 boutons bien visibles ──
    st.markdown("**Profil investisseur**")
    profile_cols = st.columns(3)
    for i, (pname, pcols) in enumerate(zip(PROFILES.keys(), profile_cols)):
        colors = {"Core": "#1fbd7e", "Value-add": "#4f7fff", "Opportuniste": "#f0a030"}
        col = colors[pname]
        active = st.session_state.profile_name == pname
        with pcols:
            if st.button(
                pname,
                key=f"profile_btn_{pname}",
                use_container_width=True,
                type="primary" if active else "secondary",
            ):
                st.session_state.profile_name = pname
                st.session_state.dim_weights  = dict(PROFILES[pname])
                st.rerun()

    st.divider()

    # ── Poids dimensions ──
    st.markdown("**Poids des dimensions (%)**")
    for d in DIMS:
        val = st.slider(
            d["label"], 0, 60,
            value=st.session_state.dim_weights.get(d["id"], 0),
            step=1, key=f"dw_{d['id']}",
        )
        st.session_state.dim_weights[d["id"]] = val

    total_w = sum(st.session_state.dim_weights.values())
    delta   = total_w - 100
    if total_w == 100:
        st.caption("Total : **100%** ✅")
    else:
        st.warning(f"Total : **{total_w}%** — {'−' if delta < 0 else '+'}{abs(delta)}% à ajuster", icon="⚠️")

    st.divider()

    # ── Options avancées (cachées par défaut) ──
    with st.expander("⚙️ Options avancées"):
        st.markdown("**Poids intra-dimension**")
        for d in DIMS:
            st.markdown(
                f"<span style='color:{d['color']};font-size:11px;font-weight:500;'>● {d['label']}</span>",
                unsafe_allow_html=True,
            )
            for v in d["vars"]:
                val = st.slider(
                    v["label"], 0, 100,
                    value=st.session_state.var_weights[d["id"]].get(v["id"], 25),
                    step=1, key=f"vw_{d['id']}_{v['id']}",
                )
                st.session_state.var_weights[d["id"]][v["id"]] = val

        st.divider()
        st.markdown("**Moteur de normalisation**")
        norm_method = st.radio(
            "Normalisation", key="norm_radio",
            options=["absolute", "percentile"],
            format_func=lambda x: {
                "absolute":   "Absolu — bornes fixes ✅ (recommandé)",
                "percentile": "Relatif — rang dans le panel",
            }[x],
            index=0,
        )
        st.session_state.norm_method = norm_method

        st.divider()
        st.markdown("**Options moteur**")
        use_nonlinear   = st.toggle("Transformations non-linéaires", value=True)
        use_reliability = st.toggle("Pondération fiabilité source",  value=True)
        use_corr_adjust = st.toggle("Correction corrélations",       value=True)
        run_mc          = st.toggle("Monte Carlo (IC scores)",        value=False,
                                    help="~500 simulations · quelques secondes")
        n_sim           = st.slider("Simulations MC", 100, 2000, 500, 100, disabled=not run_mc)

        st.divider()
        st.markdown("**Paramètres dette**")
        debt_cost = st.number_input("Coût dette hôtelière (%)", 1.0, 12.0, 5.5, 0.1)
        risk_free = st.number_input("Taux sans risque (%)",      0.0,  8.0, 3.2, 0.1)

    st.divider()
    nm = st.session_state.norm_method
    st.caption(
        f"**{len(st.session_state.active_ids)}** marchés actifs · "
        f"{'Absolu' if nm == 'absolute' else 'Relatif'}"
    )

# Valeurs par défaut si options avancées non ouvertes
if "debt_cost" not in dir():
    debt_cost       = 5.5
    risk_free       = 3.2
    use_nonlinear   = True
    use_reliability = True
    use_corr_adjust = True
    run_mc          = False
    n_sim           = 500

# ── Calcul ────────────────────────────────────────────────────────────────────

active_markets = get_active_markets()
if len(active_markets) < 2:
    st.warning("Sélectionnez au moins 2 marchés dans l'onglet **🌍 Marchés**.")
    st.stop()

with st.spinner("Calcul du scoring..."):
    result = full_analysis(
        active_markets,
        st.session_state.dim_weights,
        st.session_state.var_weights,
        norm_method=st.session_state.norm_method,
        debt_cost=debt_cost,
        risk_free=risk_free,
        run_monte_carlo=run_mc,
        n_simulations=n_sim if run_mc else 0,
    )

scores      = result["scores"]
sensitivity = result["sensitivity"]

# ── TABS ──────────────────────────────────────────────────────────────────────

# Navigation custom — radio horizontal (jamais tronqué)
if "current_tab" not in st.session_state:
    st.session_state.current_tab = "Marchés"

current_tab = st.radio(
    "Navigation",
    ["Marchés", "Scores", "Notation", "Insights", "Matrice", "Cycle", "Rapport"],
    index=["Marchés", "Scores", "Notation", "Insights", "Matrice", "Cycle", "Rapport"].index(
        st.session_state.current_tab
    ),
    horizontal=True,
    label_visibility="collapsed",
    key="nav_radio",
)
st.session_state.current_tab = current_tab
st.divider()

# ── TAB 1 : GESTION MARCHÉS ──────────────────────────────────────────────────

if current_tab == "Marchés":
    st.markdown("#### Sélection et gestion des marchés")
    col_sel, col_add = st.columns([1.4, 1])

    with col_sel:
        st.markdown("**Marchés disponibles**")
        region_groups = {}
        for m in st.session_state.markets_pool:
            region_groups.setdefault(m["region"], []).append(m)

        new_active = []
        for region_id, region_markets in sorted(region_groups.items()):
            rc = REGION_COLORS.get(region_id, "#888")
            st.markdown(
                f"<span style='color:{rc};font-size:11px;font-weight:600;"
                f"text-transform:uppercase;letter-spacing:.08em;'>"
                f"● {REGION_LABELS.get(region_id, region_id)}</span>",
                unsafe_allow_html=True,
            )
            for m in region_markets:
                checked = m["id"] in st.session_state.active_ids
                col_cb, col_name, col_del = st.columns([0.08, 0.7, 0.22])
                with col_cb:
                    val = st.checkbox("", value=checked, key=f"cb_{m['id']}",
                                      label_visibility="collapsed")
                with col_name:
                    new_name = st.text_input("Nom", value=m["name"],
                                             key=f"rename_{m['id']}",
                                             label_visibility="collapsed")
                    if new_name != m["name"]:
                        m["name"] = new_name
                with col_del:
                    if st.button("🗑", key=f"del_{m['id']}"):
                        st.session_state.markets_pool = [
                            x for x in st.session_state.markets_pool if x["id"] != m["id"]
                        ]
                        st.session_state.active_ids = [
                            x for x in st.session_state.active_ids if x != m["id"]
                        ]
                        st.rerun()
                if val:
                    new_active.append(m["id"])

        st.session_state.active_ids = [
            mid for mid in [m["id"] for m in st.session_state.markets_pool]
            if mid in new_active
        ]
        st.caption(f"**{len(st.session_state.active_ids)}** marchés sélectionnés")

    with col_add:
        st.markdown("**Ajouter un marché**")
        with st.form("add_market_form"):
            new_name   = st.text_input("Nom de la ville", placeholder="ex: Istanbul")
            new_region = st.selectbox("Région", options=list(REGION_LABELS.keys()),
                                      format_func=lambda x: REGION_LABELS[x])
            if st.form_submit_button("➕ Ajouter", use_container_width=True):
                if new_name.strip():
                    existing = [m["name"].lower() for m in st.session_state.markets_pool]
                    if new_name.strip().lower() in existing:
                        st.error(f"'{new_name}' existe déjà.")
                    else:
                        nm = blank_market(new_name.strip(), new_region)
                        st.session_state.markets_pool.append(nm)
                        st.session_state.active_ids.append(nm["id"])
                        st.success(f"'{new_name}' ajouté — renseignez ses données dans l'onglet **Données**.")
                        st.rerun()

        st.divider()
        ca, cb = st.columns(2)
        with ca:
            if st.button("✅ Tout", key="sel_all", use_container_width=True):
                st.session_state.active_ids = [m["id"] for m in st.session_state.markets_pool]
                st.rerun()
        with cb:
            if st.button("☐ Aucun", key="sel_none", use_container_width=True):
                st.session_state.active_ids = []
                st.rerun()
        for region_id, region_label in REGION_LABELS.items():
            ids = [m["id"] for m in st.session_state.markets_pool if m["region"] == region_id]
            if ids and st.button(f"● {region_label}", key=f"sel_region_{region_id}",
                                  use_container_width=True):
                existing = set(st.session_state.active_ids)
                for rid in ids:
                    existing.add(rid)
                st.session_state.active_ids = [
                    m["id"] for m in st.session_state.markets_pool if m["id"] in existing
                ]
                st.rerun()
        st.divider()
        if st.button("🔄 Réinitialiser pool", key="reset_markets_tab", use_container_width=True):
            st.session_state.markets_pool = copy.deepcopy(MARKETS_DEFAULT)
            st.session_state.active_ids   = [m["id"] for m in MARKETS_DEFAULT]
            st.rerun()

    # ── Données marchés (édition + export CSV) ───────────────────────────────
    st.divider()
    st.markdown("#### 📋 Données marchés — édition & export")

    with st.expander("📖 Guide bornes par variable", expanded=False):
        bounds_rows = []
        for d in DIMS:
            for v in d["vars"]:
                b = VARIABLE_BOUNDS.get(v["id"])
                if b:
                    bounds_rows.append({
                        "Dimension": d["label"], "Variable": v["label"],
                        "Min": b[0], "Max": b[1], "Unité": v.get("unit", ""),
                        "Sens": "↑ mieux" if v["dir"] == 1 else "↓ mieux",
                    })
        st.dataframe(pd.DataFrame(bounds_rows), hide_index=True, use_container_width=True)
        st.caption("Valeurs hors bornes → clampées automatiquement. Sources : STR, HVS, CBRE, Eurostat, Coface.")

    # Tableau éditable
    rows_d = []
    for m in st.session_state.markets_pool:
        row = {"Marché": m["name"], "Région": m["region"]}
        for d in DIMS:
            for v in d["vars"]:
                row[v["label"]] = m[d["id"]].get(v["id"], 0.0)
        rows_d.append(row)

    df_edit = pd.DataFrame(rows_d)

    col_config_d = {}
    for d in DIMS:
        for v in d["vars"]:
            b = VARIABLE_BOUNDS.get(v["id"])
            if b:
                col_config_d[v["label"]] = st.column_config.NumberColumn(
                    v["label"], min_value=float(b[0]), max_value=float(b[1]),
                    help=f"[{b[0]}, {b[1]}] {v.get('unit','')}",
                )

    edited_d = st.data_editor(
        df_edit, use_container_width=True, hide_index=True,
        key="data_editor_markets", column_config=col_config_d,
    )

    da1, da2, da3, da4, da5 = st.columns(5)
    with da1:
        if st.button("✅ Appliquer", key="apply_data_mkt", use_container_width=True):
            for i, m in enumerate(st.session_state.markets_pool):
                for d in DIMS:
                    for v in d["vars"]:
                        try:
                            m[d["id"]][v["id"]] = float(edited_d.at[i, v["label"]])
                        except Exception:
                            pass
            st.success("Données mises à jour.")
            st.rerun()
    with da2:
        if st.button("🔄 Réinitialiser", key="reset_data_tab", use_container_width=True):
            st.session_state.markets_pool = copy.deepcopy(MARKETS_DEFAULT)
            st.session_state.active_ids   = [m["id"] for m in MARKETS_DEFAULT]
            st.rerun()
    with da3:
        # Export CSV
        csv_data = edited_d.to_csv(index=False, encoding="utf-8")
        st.download_button(
            "⬇️ CSV", data=csv_data,
            file_name="reiv_markets.csv", mime="text/csv",
            use_container_width=True,
        )
    with da4:
        # Export JSON
        json_data = json.dumps(st.session_state.markets_pool, ensure_ascii=False, indent=2)
        st.download_button(
            "⬇️ JSON", data=json_data,
            file_name="reiv_markets.json", mime="application/json",
            use_container_width=True,
        )
    with da5:
        uploaded = st.file_uploader("Import CSV/JSON", type=["csv","json"],
                                    label_visibility="collapsed", key="upload_data")
        if uploaded:
            try:
                if uploaded.name.endswith(".csv"):
                    df_up = pd.read_csv(uploaded)
                    # Reconstruire les marchés depuis le CSV
                    for i, m in enumerate(st.session_state.markets_pool):
                        if i >= len(df_up):
                            break
                        for d in DIMS:
                            for v in d["vars"]:
                                if v["label"] in df_up.columns:
                                    try:
                                        m[d["id"]][v["id"]] = float(df_up.at[i, v["label"]])
                                    except Exception:
                                        pass
                    st.success(f"CSV importé — {len(df_up)} lignes.")
                else:
                    imported = json.load(uploaded)
                    st.session_state.markets_pool = imported
                    st.session_state.active_ids   = [m["id"] for m in imported]
                    st.success(f"{len(imported)} marchés importés.")
                st.rerun()
            except Exception as e:
                st.error(f"Erreur import : {e}")

# ── TAB 2 : CLASSEMENT ───────────────────────────────────────────────────────

if current_tab == "Scores":
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown("#### Classement enrichi")
        rows = []
        for i, s in enumerate(scores):
            cluster = s.get("cluster", {})
            mc_d    = s.get("mc", {})
            rows.append({
                "Rang":      i + 1,
                "Marché":    s["name"],
                "Région":    REGION_LABELS.get(s["region"], s["region"]),
                "Score":     s["total"],
                "IC P10-P90":f"{mc_d.get('ci_low','?')}–{mc_d.get('ci_high','?')}" if mc_d else "—",
                "Cluster":   cluster.get("label", "—"),
                "Confiance": round(s["confidence"] * 100),
                **{d["label"][:14]: s["dims"][d["id"]] for d in DIMS},
                "Risque":    s["risk_raw"],
            })
        df_rank = pd.DataFrame(rows)
        st.dataframe(
            df_rank, use_container_width=True, hide_index=True,
            column_config={
                "Score":     st.column_config.ProgressColumn("Score",    min_value=0, max_value=100),
                "Risque":    st.column_config.ProgressColumn("Risque",   min_value=0, max_value=100),
                "Confiance": st.column_config.ProgressColumn("Confiance %", min_value=0, max_value=100),
            },
        )

    with col_right:
        st.markdown("#### Fiche marché")
        sel_name = st.selectbox("Marché", [s["name"] for s in scores], key="fiche_sel")
        sel      = next((s for s in scores if s["name"] == sel_name), scores[0])
        c        = score_color(sel["total"])
        rc       = risk_color(sel["risk_raw"])
        cc       = confidence_color(sel["confidence"])
        region_color = REGION_COLORS.get(sel["region"], "#888")
        mc_d    = sel.get("mc", {})
        cluster = sel.get("cluster", {})

        st.markdown(f"""
        <div style="background:#141720;border:1px solid #252b3b;border-radius:10px;padding:16px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
            <div>
              <div style="font-size:17px;font-weight:600;">{sel['name']}</div>
              {badge(REGION_LABELS.get(sel['region'],''), region_color)}
              {(' ' + badge(cluster.get('label',''), cluster.get('color','#888'))) if cluster else ''}
            </div>
            <div style="text-align:right;">
              <div style="font-size:30px;font-weight:600;font-family:monospace;color:{c};">{sel['total']}</div>
              <div style="font-size:10px;color:#555e78;">/ 100</div>
              {'<div style="font-size:10px;color:#555e78;">IC P10-P90 : ' + str(mc_d.get('ci_low','?')) + '–' + str(mc_d.get('ci_high','?')) + '</div>' if mc_d else ''}
            </div>
          </div>
        """, unsafe_allow_html=True)

        for d in DIMS:
            v  = sel["dims"][d["id"]]
            dc = score_color(v)
            # Borne max pour affichage relatif dans la fiche
            bound_info = f"{v}/100"
            st.markdown(f"""
            <div style="margin-bottom:7px;">
              <div style="display:flex;justify-content:space-between;font-size:11px;color:#8b92a8;margin-bottom:2px;">
                <span><span style="display:inline-block;width:6px;height:6px;border-radius:50%;
                  background:{d['color']};margin-right:4px;vertical-align:middle;"></span>{d['label']}</span>
                <span style="font-weight:500;color:{dc};">{bound_info}</span>
              </div>
              <div style="height:3px;background:#1c2130;border-radius:2px;overflow:hidden;">
                <div style="width:{v}%;height:100%;background:{d['color']};border-radius:2px;"></div>
              </div>
            </div>""", unsafe_allow_html=True)

        outliers    = sel.get("outlier_flags", {})
        outlier_str = ", ".join(outliers.keys()) if outliers else "Aucun"
        st.markdown(f"""
          <div style="border-top:1px solid #252b3b;padding-top:8px;margin-top:6px;font-size:10px;color:#8b92a8;">
            <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
              <span>Risque brut composite</span>
              <span style="font-weight:500;color:{rc};font-family:monospace;">{sel['risk_raw']}/100</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:3px;">
              <span>Indice de confiance</span>
              <span style="font-weight:500;color:{cc};font-family:monospace;">{round(sel['confidence']*100)}%</span>
            </div>
            <div style="display:flex;justify-content:space-between;">
              <span>Variables outliers détectés</span>
              <span style="color:#f0a030;">{outlier_str}</span>
            </div>
          </div>
        </div>
        """, unsafe_allow_html=True)

# ── TAB : NOTATION & STRESS ──────────────────────────────────────────────────

if current_tab == "Notation":
    st.markdown("#### Notation AAA-CCC · Gate 0 politique · Stress tests")
    st.caption(
        f"Profil **{st.session_state.profile_name}** — "
        "Gate 0 = filtre éliminatoire de stabilité politique avant scoring. "
        "Haircut politique appliqué post-scoring. "
        "Stress : Base (50%) / Upside (20%) / Downside (30%) — chocs calibrés récession 2008-09 hôtelière."
    )

    with st.spinner("Stress test en cours..."):
        stress = stress_test_markets(
            active_markets,
            st.session_state.dim_weights,
            st.session_state.var_weights,
            profile_name=st.session_state.profile_name,
        )

    # ── Marchés éliminés Gate 0 ──
    eliminated = {mid: r for mid, r in stress.items() if not r["gate0"]["passed"]}
    if eliminated:
        st.markdown("##### 🚪 Gate 0 — marchés éliminés")
        for mid, r in eliminated.items():
            reasons = " · ".join(r["gate0"]["reasons"])
            st.markdown(
                f"<div style='background:#e2504a15;border-left:3px solid #e2504a;"
                f"border-radius:4px;padding:8px 12px;margin-bottom:6px;'>"
                f"<span style='font-size:13px;font-weight:600;color:#e2504a;'>❌ {r['name']}</span>"
                f"<span style='font-size:11px;color:#8b92a8;margin-left:10px;'>{reasons}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        st.caption(
            f"Le profil {st.session_state.profile_name} exige une stabilité politique minimale "
            "— aucune pondération ne peut compenser un risque pays rédhibitoire."
        )
        st.divider()

    # ── Matrice de stress ──
    st.markdown("##### Matrice de stress — notation par scénario")

    rows_stress = []
    for mid, r in sorted(stress.items(),
                          key=lambda x: -x[1]["scenarios"].get("base", {}).get("score_final", 0)):
        b = r["scenarios"].get("base", {})
        u = r["scenarios"].get("upside", {})
        d = r["scenarios"].get("downside", {})
        rows_stress.append({
            "Marché":        r["name"],
            "Gate 0":        "✅" if r["gate0"]["passed"] else "❌ Éliminé",
            "Haircut pol.":  f"−{b.get('haircut_pct', 0)}%" if b.get("haircut_pct", 0) > 0 else "—",
            "Base":          b.get("score_final", 0),
            "Note base":     b.get("rating", "—"),
            "Upside":        u.get("score_final", 0),
            "Note upside":   u.get("rating", "—"),
            "Downside":      d.get("score_final", 0),
            "Note downside": d.get("rating", "—"),
            "Δ crans":       r["delta_downside"],
            "Résilience":    r["resilience"],
            "Zone interdite":"🚫" if r["forbidden"] else "",
        })

    df_stress = pd.DataFrame(rows_stress)
    st.dataframe(
        df_stress, use_container_width=True, hide_index=True,
        column_config={
            "Base":     st.column_config.ProgressColumn("Base",     min_value=0, max_value=70),
            "Upside":   st.column_config.ProgressColumn("Upside",   min_value=0, max_value=70),
            "Downside": st.column_config.ProgressColumn("Downside", min_value=0, max_value=70),
        },
    )

    st.divider()
    col_s1, col_s2 = st.columns([1.3, 1])

    with col_s1:
        st.markdown("##### Vue par marché — barres base / downside")
        # Tri par score base
        sorted_stress = sorted(
            [(mid, r) for mid, r in stress.items() if r["gate0"]["passed"]],
            key=lambda x: -x[1]["scenarios"].get("base", {}).get("score_final", 0),
        )
        for mid, r in sorted_stress:
            b = r["scenarios"].get("base", {})
            d = r["scenarios"].get("downside", {})
            u = r["scenarios"].get("upside", {})
            base_score = b.get("score_final", 0)
            down_score = d.get("score_final", 0)
            up_score   = u.get("score_final", 0)
            res_color  = r["resilience_color"]
            forbidden  = " 🚫" if r["forbidden"] else ""

            st.markdown(f"""
            <div style="margin-bottom:10px;">
              <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:3px;">
                <span style="font-weight:500;">{r['name']}{forbidden}</span>
                <span>
                  <span style="background:{d.get('color','#888')}22;color:{d.get('color','#888')};
                        font-size:10px;padding:1px 6px;border-radius:8px;font-family:monospace;">
                    {d.get('rating','—')}</span>
                  <span style="color:#555e78;font-size:10px;">←</span>
                  <span style="background:{b.get('color','#888')}22;color:{b.get('color','#888')};
                        font-size:10px;padding:1px 6px;border-radius:8px;font-weight:600;font-family:monospace;">
                    {b.get('rating','—')}</span>
                  <span style="color:#555e78;font-size:10px;">→</span>
                  <span style="background:{u.get('color','#888')}22;color:{u.get('color','#888')};
                        font-size:10px;padding:1px 6px;border-radius:8px;font-family:monospace;">
                    {u.get('rating','—')}</span>
                  <span style="color:{res_color};font-size:10px;font-weight:500;margin-left:8px;">
                    {r['resilience']}</span>
                </span>
              </div>
              <div style="position:relative;height:8px;background:#1c2130;border-radius:4px;overflow:hidden;">
                <div style="position:absolute;left:0;width:{up_score}%;height:100%;
                     background:#1fbd7e22;border-radius:4px;"></div>
                <div style="position:absolute;left:0;width:{base_score}%;height:100%;
                     background:{b.get('color','#4f7fff')}66;border-radius:4px;"></div>
                <div style="position:absolute;left:0;width:{down_score}%;height:100%;
                     background:{b.get('color','#4f7fff')};border-radius:4px;"></div>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:9px;color:#555e78;font-family:monospace;">
                <span>down {down_score}</span><span>base {base_score}</span><span>up {up_score}</span>
              </div>
            </div>""", unsafe_allow_html=True)

    with col_s2:
        st.markdown("##### Grille de notation")
        from data import RATING_SCALE, GATE0_THRESHOLDS, STRESS_SCENARIOS
        df_scale = pd.DataFrame([
            {"Note": r[1], "Seuil": f"≥ {r[0]}" if r[0] > 0 else "< 33", "Interprétation": r[2]}
            for r in RATING_SCALE
        ])
        st.dataframe(df_scale, hide_index=True, use_container_width=True)
        st.caption(
            "Seuils calibrés sur la distribution empirique du scoring absolu "
            "(bornes mondiales → panel EU/MENA entre ~30 et ~58)."
        )

        st.markdown("##### Seuils Gate 0 par profil")
        df_gate = pd.DataFrame([
            {"Profil": p, "Risque pol. max": f"{t['pol_risk_max']}/5",
             "Expo géo max": f"{t['geo_exp_max']}/5"}
            for p, t in GATE0_THRESHOLDS.items()
        ])
        st.dataframe(df_gate, hide_index=True, use_container_width=True)

        st.markdown("##### Chocs downside appliqués")
        down = STRESS_SCENARIOS["downside"]["shocks"]
        shock_labels = {
            "revpar": "RevPAR", "occ": "Occupation", "adr": "ADR",
            "revpar_g": "Croissance RevPAR", "gdp_g": "Croissance PIB",
            "caprate": "Cap rate", "vol_tx": "Volume transactions",
            "nb_deals": "Nb deals", "tourists": "Arrivées",
            "pip_ratio": "Pipeline", "hvi_cagr": "HVI CAGR",
        }
        df_shocks = pd.DataFrame([
            {"Variable": shock_labels.get(k, k),
             "Choc": f"×{v[1]}" if v[0] == "mult" else f"{'+' if v[1] > 0 else ''}{v[1]}"}
            for k, v in down.items()
        ])
        st.dataframe(df_shocks, hide_index=True, use_container_width=True)


    st.divider()
    with st.expander('🎛️ Analyse de sensibilité', expanded=False):
        st.caption('Impact ±10% de chaque dimension sur le classement.')
        st.markdown("#### Analyse de sensibilité des pondérations")
        st.caption("Impact d'une variation ±10% de chaque dimension sur le classement final.")
    
        dim_labels = [data["dim_label"][:18] for data in sensitivity.values()]
        dim_values = [data["sensitivity_index"] for data in sensitivity.values()]
    
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=dim_values + [dim_values[0]],
            theta=dim_labels + [dim_labels[0]],
            fill="toself",
            fillcolor="rgba(79,127,255,0.15)",
            line=dict(color="#4f7fff", width=2),
            name="Sensibilité",
        ))
        fig_radar.update_layout(
            polar=dict(
                bgcolor="#141720",
                radialaxis=dict(
                    visible=True, range=[0, max(dim_values) * 1.2],
                    gridcolor="#252b3b", tickcolor="#555e78",
                    tickfont=dict(size=9, color="#8b92a8"),
                ),
                angularaxis=dict(tickfont=dict(size=10, color="#e8eaf0")),
            ),
            paper_bgcolor="#0d0f12", plot_bgcolor="#0d0f12",
            height=350, showlegend=False,
            margin=dict(l=60, r=60, t=30, b=30),
        )
        st.plotly_chart(fig_radar, use_container_width=True)
    
        st.markdown("#### Impact par dimension (Δ rang)")
        for dim_id, data in sensitivity.items():
            with st.expander(f"{data['dim_label']} — sensibilité {data['sensitivity_index']} rangs"):
                rows_s = []
                for s in scores:
                    mid  = s["id"]
                    rc_d = data["rank_changes"].get(mid, {})
                    sc_d = data["score_changes"].get(mid, {})
                    rows_s.append({
                        "Marché":            s["name"],
                        "Score base":        s["total"],
                        "Δ rang (+10%)":     rc_d.get("up", 0),
                        "Δ rang (−10%)":     rc_d.get("down", 0),
                        "Δ score (+10%)":    sc_d.get("up", 0),
                        "Δ score (−10%)":    sc_d.get("down", 0),
                        "Vulnérabilité max": rc_d.get("max_abs", 0),
                    })
                st.dataframe(pd.DataFrame(rows_s), hide_index=True, use_container_width=True)
    

    st.divider()
    with st.expander('🏨 Risque O\'Neill — GOPPAR RSD', expanded=False):
        st.caption('O\'Neill et al. 2023 — Cornell Hospitality Quarterly · 3219 hôtels US.')
        st.markdown("#### Risk Penetration Index — O'Neill et al. 2023 (Cornell)")
        st.caption(
            "Indice 100 = moyenne du panel. "
            "Source : GOPPAR RSD benchmarks — 3 219 hôtels US 2015-2020, Cornell Hospitality Quarterly."
        )
    
        rows_rpi = []
        for i, s in enumerate(scores):
            rpi    = s.get("rpi", {})
            oneill = s.get("oneill", {})
            if not rpi:
                continue
            rows_rpi.append({
                "Rang":            i + 1,
                "Marché":          s["name"],
                "Classe":          oneill.get("class", "—").replace("_", " ").title(),
                "Type":            oneill.get("proptype", "—").replace("_", " ").title(),
                "GOP Margin %":    rpi.get("gop_margin_raw", 0),
                "Margin Index":    rpi.get("gop_margin_idx", 100),
                "GOPPAR (€)":      rpi.get("goppar_raw", 0),
                "GOPPAR Index":    rpi.get("goppar_idx", 100),
                "GOPPAR RSD %":    rpi.get("goppar_rsd_raw", 0),
                "RSD Index":       rpi.get("goppar_rsd_idx", 100),
                "Verdict":         rpi.get("verdict", "—"),
            })
    
        if rows_rpi:
            st.dataframe(
                pd.DataFrame(rows_rpi), use_container_width=True, hide_index=True,
                column_config={
                    "Margin Index": st.column_config.ProgressColumn("Margin Index", min_value=0, max_value=200),
                    "GOPPAR Index": st.column_config.ProgressColumn("GOPPAR Index", min_value=0, max_value=200),
                    "RSD Index":    st.column_config.NumberColumn("RSD Index", help="< 100 = moins risqué"),
                },
            )
    
        st.divider()
        col_r1, col_r2 = st.columns(2)
    
        with col_r1:
            st.markdown("#### Profil O'Neill par marché")
            for s in scores:
                oneill = s.get("oneill", {})
                rpi    = s.get("rpi", {})
                if not oneill or not rpi:
                    continue
                vc    = rpi.get("verdict_color", "#888")
                verd  = rpi.get("verdict", "—")
                rsd   = rpi.get("goppar_rsd_raw", 0)
                rsd_c = "#1fbd7e" if rsd < 35 else "#f0a030" if rsd < 50 else "#e2504a"
                st.markdown(f"""
                <div style="background:#141720;border:1px solid #252b3b;border-radius:8px;
                            padding:8px 12px;margin-bottom:5px;display:flex;
                            justify-content:space-between;align-items:center;">
                  <div>
                    <span style="font-size:13px;font-weight:500;">{s['name']}</span>
                    <span style="font-size:10px;color:#8b92a8;margin-left:8px;">
                      {oneill.get('class','').replace('_',' ').title()} ·
                      {oneill.get('proptype','').replace('_',' ').title()}
                    </span>
                  </div>
                  <div style="display:flex;align-items:center;gap:10px;">
                    <span style="font-family:monospace;font-size:11px;color:{rsd_c};">RSD {rsd}%</span>
                    <span style="font-size:11px;font-weight:500;color:{vc};">{verd}</span>
                  </div>
                </div>""", unsafe_allow_html=True)
    
        with col_r2:
            st.markdown("#### GOPPAR vs RSD")
            df_scatter = pd.DataFrame([{
                "Marché":       s["name"],
                "GOPPAR (€)":   s.get("rpi", {}).get("goppar_raw", 0),
                "GOPPAR RSD %": s.get("rpi", {}).get("goppar_rsd_raw", 0),
                "Score":        s["total"],
                "Verdict":      s.get("rpi", {}).get("verdict", "—"),
            } for s in scores if s.get("rpi")])
    
            if not df_scatter.empty:
                fig_rpi = px.scatter(
                    df_scatter, x="GOPPAR RSD %", y="GOPPAR (€)",
                    text="Marché", size="Score", size_max=22,
                    color="Verdict",
                    color_discrete_map={
                        "★ Attractif": "#1fbd7e", "◎ Correct": "#4f7fff",
                        "△ Mitigé": "#f0a030", "✗ Défavorable": "#e2504a",
                    },
                    template="plotly_dark",
                )
                fig_rpi.update_traces(textposition="top center", textfont_size=9)
                fig_rpi.update_layout(
                    plot_bgcolor="#0d0f12", paper_bgcolor="#0d0f12", height=360,
                    font=dict(family="Inter", size=11, color="#8b92a8"),
                    xaxis=dict(title="GOPPAR RSD % →", gridcolor="#1c2130"),
                    yaxis=dict(title="GOPPAR € →",     gridcolor="#1c2130"),
                    margin=dict(l=40, r=20, t=20, b=40),
                )
                med_rsd    = df_scatter["GOPPAR RSD %"].median()
                med_goppar = df_scatter["GOPPAR (€)"].median()
                fig_rpi.add_shape(type="line", x0=med_rsd, x1=med_rsd,
                    y0=0, y1=df_scatter["GOPPAR (€)"].max() * 1.1,
                    line=dict(color="#252b3b", dash="dot"))
                fig_rpi.add_shape(type="line",
                    x0=0, x1=df_scatter["GOPPAR RSD %"].max() * 1.1,
                    y0=med_goppar, y1=med_goppar,
                    line=dict(color="#252b3b", dash="dot"))
                fig_rpi.add_annotation(
                    x=df_scatter["GOPPAR RSD %"].min() + 1,
                    y=df_scatter["GOPPAR (€)"].max() * 1.05,
                    text="★ Idéal", showarrow=False, font=dict(size=9, color="#1fbd7e"),
                )
                st.plotly_chart(fig_rpi, use_container_width=True)
    
        st.divider()
        st.markdown("#### Référentiels O'Neill 2023")
        col_ref1, col_ref2, col_ref3 = st.columns(3)
        with col_ref1:
            st.markdown("**Par classe**")
            st.dataframe(pd.DataFrame([
                {"Classe": k.replace("_", " ").title(), "RSD %": v}
                for k, v in sorted(ONEILL_RSD_CLASS.items(), key=lambda x: x[1])
            ]), hide_index=True, use_container_width=True)
        with col_ref2:
            st.markdown("**Par type de propriété**")
            st.dataframe(pd.DataFrame([
                {"Type": k.replace("_", " ").title(), "RSD %": v}
                for k, v in sorted(ONEILL_RSD_PROPTYPE.items(), key=lambda x: x[1])
            ]), hide_index=True, use_container_width=True)
        with col_ref3:
            st.markdown("**Par localisation**")
            st.dataframe(pd.DataFrame([
                {"Localisation": k.replace("_", " ").title(), "RSD %": v}
                for k, v in sorted(ONEILL_RSD_LOCTYPE.items(), key=lambda x: x[1])
            ]), hide_index=True, use_container_width=True)
    

# ── TAB 3 : MATRICE ──────────────────────────────────────────────────────────

if current_tab == "Matrice":
    col_m1, col_m2 = st.columns([2, 1])

    with col_m1:
        st.markdown("#### Matrice attractivité / risque")
        df_matrix = pd.DataFrame([{
            "Marché":       s["name"],
            "Attractivité": s["total"],
            "Risque":       s["risk_raw"],
            "Région":       REGION_LABELS.get(s["region"], s["region"]),
            "Score":        s["total"],
            "Cluster":      s.get("cluster", {}).get("label", "—"),
        } for s in scores])

        color_map = {REGION_LABELS[k]: v for k, v in REGION_COLORS.items()}
        fig = px.scatter(
            df_matrix, x="Risque", y="Attractivité", text="Marché",
            color="Région", size="Score", size_max=28,
            color_discrete_map=color_map, template="plotly_dark",
            hover_data=["Cluster"],
        )
        fig.update_traces(textposition="top center", textfont_size=10)
        fig.update_layout(
            plot_bgcolor="#0d0f12", paper_bgcolor="#0d0f12", height=480,
            font=dict(family="Inter", size=11, color="#8b92a8"),
            xaxis=dict(title="← Faible risque   Risque élevé →",
                       gridcolor="#1c2130", range=[0, 100]),
            yaxis=dict(title="Attractivité →",
                       gridcolor="#1c2130", range=[20, 100]),
            legend=dict(bgcolor="#141720", bordercolor="#252b3b", borderwidth=1),
            margin=dict(l=40, r=20, t=20, b=40),
        )
        fig.add_shape(type="line", x0=50, x1=50, y0=20, y1=100,
                      line=dict(color="#252b3b", dash="dot"))
        fig.add_shape(type="line", x0=0,  x1=100, y0=50, y1=50,
                      line=dict(color="#252b3b", dash="dot"))
        fig.add_annotation(x=15, y=95, text="★ Core cibles",   showarrow=False, font=dict(size=9, color="#1fbd7e"))
        fig.add_annotation(x=78, y=95, text="⚡ Opportuniste", showarrow=False, font=dict(size=9, color="#f0a030"))
        fig.add_annotation(x=15, y=25, text="⚠ Éviter",        showarrow=False, font=dict(size=9, color="#555e78"))
        fig.add_annotation(x=78, y=25, text="🔍 Surveiller",   showarrow=False, font=dict(size=9, color="#555e78"))
        st.plotly_chart(fig, use_container_width=True)

    with col_m2:
        st.markdown("#### Clusters K-means")
        cluster_groups = {}
        for s in scores:
            cl    = s.get("cluster", {})
            label = cl.get("label", "—")
            cluster_groups.setdefault(label, {"color": cl.get("color", "#888"), "markets": []})
            cluster_groups[label]["markets"].append(s["name"])

        for label, data in cluster_groups.items():
            st.markdown(
                f"<div style='background:{data['color']}15;border-left:3px solid {data['color']};"
                f"border-radius:4px;padding:8px 10px;margin-bottom:8px;'>"
                f"<div style='font-size:12px;font-weight:500;color:{data['color']};margin-bottom:4px;'>"
                f"{label}</div>"
                f"<div style='font-size:11px;color:#8b92a8;'>{', '.join(data['markets'])}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        sil = scores[0].get("cluster", {}).get("silhouette", None)
        if sil:
            st.caption(f"Silhouette : **{sil}** {'✅' if sil > 0.4 else '(acceptable)'}")

# ── TAB 4 : CYCLE & SPREAD ───────────────────────────────────────────────────

if current_tab == "Cycle":
    st.markdown("#### Momentum hôtelier & Spread cap rate / coût dette")
    st.caption("Cycle hôtelier (Choi 1999) · Signal d'entrée spread (Corgel 2004)")

    rows_cycle = []
    for s in scores:
        m = next((mm for mm in active_markets if mm["id"] == s["id"]), None)
        if not m:
            continue
        mom = s.get("momentum", compute_momentum(m))
        spr = s.get("spread",   compute_caprate_spread(m, debt_cost, risk_free))
        rows_cycle.append({
            "Marché":        s["name"],
            "Score":         s["total"],
            "Phase cycle":   mom["cycle_label"],
            "Momentum":      mom["momentum_score"],
            "RevPAR growth": f"{mom['revpar_g']}%",
            "Occupation":    f"{mom['occ']}%",
            "Cap rate":      f"{spr['caprate']}%",
            "Spread":        f"{spr['spread']}%",
            "Signal entrée": spr["entry_signal"],
        })

    df_cycle = pd.DataFrame(rows_cycle)
    fig_cyc = px.scatter(
        df_cycle, x="Momentum", y="Score", text="Marché",
        color="Phase cycle",
        color_discrete_map={
            "Expansion": "#1fbd7e", "Peak":       "#f0a030",
            "Contraction": "#e2504a", "Creux":    "#4f7fff",
        },
        template="plotly_dark", title="Positionnement cycle hôtelier",
    )
    fig_cyc.update_traces(textposition="top center", textfont_size=9)
    fig_cyc.update_layout(
        plot_bgcolor="#0d0f12", paper_bgcolor="#0d0f12", height=380,
        font=dict(family="Inter", size=11, color="#8b92a8"),
        margin=dict(l=40, r=20, t=40, b=40),
    )
    st.plotly_chart(fig_cyc, use_container_width=True)
    st.markdown("#### Tableau cycle & spread")
    st.dataframe(df_cycle, use_container_width=True, hide_index=True)

if current_tab == "Rapport":
    st.markdown("#### Génération de rapport HTML")
    st.caption("Le rapport est téléchargeable et s'ouvre dans tout navigateur.")

    report_type = st.radio(
        "Type de rapport",
        ["Fiche individuelle", "Rapport comparatif Top N"],
        horizontal=True,
    )

    if report_type == "Fiche individuelle":
        sel_r      = st.selectbox("Marché à exporter", [s["name"] for s in scores], key="rep_mkt")
        sel_score  = next((s for s in scores if s["name"] == sel_r), scores[0])
        sel_data   = next((m for m in active_markets if m["name"] == sel_r), active_markets[0])

        if st.button("📄 Générer la fiche", key="gen_fiche", type="primary"):
            with st.spinner("Génération rapport..."):
                # Stress pour la fiche
                from scoring_advanced import stress_test_markets
                stress_rep = stress_test_markets(
                    active_markets,
                    st.session_state.dim_weights,
                    st.session_state.var_weights,
                    profile_name=st.session_state.profile_name,
                )
                html = generate_fiche(
                    sel_data, sel_score,
                    st.session_state.dim_weights,
                    st.session_state.profile_name,
                    stress_data=stress_rep,
                    debt_cost=debt_cost,
                )
            st.download_button(
                f"⬇️ fiche_{sel_r.replace(' ','_').lower()}.html",
                data=html.encode("utf-8"),
                file_name=f"reiv_fiche_{sel_r.replace(' ','_').lower()}.html",
                mime="text/html",
            )
            with st.expander("Aperçu"):
                st.components.v1.html(html, height=700, scrolling=True)

    else:
        top_n = st.slider("Nombre de marchés", 2, len(scores), min(5, len(scores)))
        st.caption(f"Top {top_n} : {', '.join([s['name'] for s in scores[:top_n]])}")
        if st.button("📄 Générer le comparatif", key="gen_comparatif", type="primary"):
            with st.spinner("Génération rapport..."):
                from scoring_advanced import stress_test_markets
                stress_rep = stress_test_markets(
                    active_markets,
                    st.session_state.dim_weights,
                    st.session_state.var_weights,
                    profile_name=st.session_state.profile_name,
                )
                html = generate_comparatif(
                    scores, top_n,
                    st.session_state.dim_weights,
                    st.session_state.profile_name,
                    markets=active_markets,
                    stress_data=stress_rep,
                    debt_cost=debt_cost,
                )
            st.download_button(
                f"⬇️ comparatif_top{top_n}.html",
                data=html.encode("utf-8"),
                file_name=f"reiv_comparatif_top{top_n}.html",
                mime="text/html",
            )
            with st.expander("Aperçu"):
                st.components.v1.html(html, height=700, scrolling=True)

# ── TAB INSIGHTS DÉCISION ────────────────────────────────────────────────────

if current_tab == "Insights":
    st.markdown("## 💡 Insights décision — signaux comité")
    st.caption(
        "6 signaux synthétiques orientés comité d'investissement. "
        "Données partiellement proxy — à remplacer par données STR/UNWTO propriétaires."
    )

    # ── Selector de marché ──
    sel_insight = st.selectbox(
        "Marché analysé", [m["name"] for m in active_markets],
        key="insight_mkt",
    )
    mi = next((m for m in active_markets if m["name"] == sel_insight), active_markets[0])
    mid = mi["id"]
    region_color = REGION_COLORS.get(mi["region"], "#888")
    s_score = next((s for s in scores if s["id"] == mid), scores[0])
    rt = score_to_rating(s_score["total"])

    st.markdown(f"""
    <div style="background:#141720;border:1px solid #252b3b;border-radius:10px;
                padding:12px 16px;margin-bottom:18px;display:flex;
                align-items:center;justify-content:space-between;">
      <div>
        <span style="font-size:18px;font-weight:600;">{mi['name']}</span>
        {badge(REGION_LABELS.get(mi['region'],''), region_color, "11px")}
      </div>
      <div style="text-align:right;">
        <span style="font-size:28px;font-weight:700;font-family:monospace;
              color:{rt['color']};">{rt['rating']}</span>
        <span style="font-size:11px;color:#8b92a8;margin-left:8px;">{s_score['total']}/100</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    # ────────────────────────────────────────────────────────────────────────
    with col1:

        # ── SIGNAL 1 : Phase de cycle de valeur HVS ──────────────────────
        cyc = safe_hvi_cycle(mid)
        st.markdown(f"""
        <div style="background:#141720;border:1px solid #252b3b;border-radius:8px;
                    padding:14px 16px;margin-bottom:12px;">
          <div style="font-size:10px;color:#555e78;text-transform:uppercase;
                      letter-spacing:.08em;margin-bottom:6px;">
            📈 Signal 1 — Phase de cycle de valeur (HVS 2025)
          </div>
          <div style="font-size:20px;font-weight:600;color:{cyc['color']};margin-bottom:4px;">
            {cyc['phase']}
          </div>
          <div style="font-size:12px;color:#8b92a8;margin-bottom:8px;">{cyc['signal']}</div>
          <div style="display:flex;gap:20px;font-size:11px;font-family:monospace;">
            <span>HVI 2024 <span style="color:#e8eaf0;font-weight:600;">{cyc['hvi']:.2f}</span></span>
            <span>Δ 2024 <span style="color:{cyc['color']};font-weight:600;">
              {'+' if cyc['delta']>=0 else ''}{cyc['delta']}%</span></span>
            <span>CAGR 10a <span style="color:#e8eaf0;font-weight:600;">
              {'+' if cyc['cagr']>=0 else ''}{cyc['cagr']}%</span></span>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── SIGNAL 2 : Spread cap rate / coût dette ───────────────────────
        caprate = float(mi["liquidite"]["caprate"])
        spread  = round(caprate - debt_cost, 2)
        if spread >= 2.5:
            sp_color, sp_signal = "#1fbd7e", "✅ Signal d'entrée fort"
        elif spread >= 1.0:
            sp_color, sp_signal = "#4f7fff", "✅ Signal d'entrée modéré"
        elif spread >= 0.0:
            sp_color, sp_signal = "#f0a030", "⚠️ Spread serré — vigilance"
        else:
            sp_color, sp_signal = "#e2504a", "🔴 Spread négatif — dette non rentable"

        bar_cap  = min(caprate / 12 * 100, 100)
        bar_debt = min(debt_cost / 12 * 100, 100)
        st.markdown(f"""
        <div style="background:#141720;border:1px solid #252b3b;border-radius:8px;
                    padding:14px 16px;margin-bottom:12px;">
          <div style="font-size:10px;color:#555e78;text-transform:uppercase;
                      letter-spacing:.08em;margin-bottom:6px;">
            💰 Signal 2 — Spread cap rate / coût dette (Corgel 2004)
          </div>
          <div style="font-size:20px;font-weight:600;color:{sp_color};margin-bottom:4px;">
            {'+' if spread>=0 else ''}{spread}%
          </div>
          <div style="font-size:12px;color:#8b92a8;margin-bottom:10px;">{sp_signal}</div>
          <div style="margin-bottom:4px;">
            <div style="display:flex;justify-content:space-between;font-size:10px;color:#555e78;">
              <span>Cap rate</span><span style="color:#4f7fff;">{caprate}%</span>
            </div>
            <div style="height:5px;background:#1c2130;border-radius:3px;overflow:hidden;margin:2px 0;">
              <div style="width:{bar_cap}%;height:100%;background:#4f7fff;border-radius:3px;"></div>
            </div>
          </div>
          <div>
            <div style="display:flex;justify-content:space-between;font-size:10px;color:#555e78;">
              <span>Coût dette</span><span style="color:#e2504a;">{debt_cost}%</span>
            </div>
            <div style="height:5px;background:#1c2130;border-radius:3px;overflow:hidden;margin:2px 0;">
              <div style="width:{bar_debt}%;height:100%;background:#e2504a;border-radius:3px;"></div>
            </div>
          </div>
          <div style="font-size:10px;color:#555e78;margin-top:8px;">
            Règle cabinet : spread &lt; 100bps → ne pas entrer · &gt; 250bps → signal d'achat
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── SIGNAL 5 : Coût de remplacement ──────────────────────────────
        dev_cost_k = float(mi["faisabilite"]["dev_cost"])
        rcr = safe_rcr(mid, dev_cost_k)
        st.markdown(f"""
        <div style="background:#141720;border:1px solid #252b3b;border-radius:8px;
                    padding:14px 16px;margin-bottom:12px;">
          <div style="font-size:10px;color:#555e78;text-transform:uppercase;
                      letter-spacing:.08em;margin-bottom:6px;">
            🏗️ Signal 5 — Valeur marché vs coût de remplacement (HVS 2025)
          </div>
          <div style="font-size:20px;font-weight:600;color:{rcr['color']};margin-bottom:4px;">
            Ratio {rcr['ratio']}×
          </div>
          <div style="font-size:12px;color:#8b92a8;margin-bottom:8px;">{rcr['signal']}</div>
          <div style="display:flex;gap:24px;font-size:11px;font-family:monospace;">
            <span>HVI réel <span style="color:#e8eaf0;font-weight:600;">
              {rcr['hvi_eur']:,}€/ch</span></span>
            <span>Dev cost <span style="color:#8b92a8;font-weight:600;">
              {rcr['dev_eur']:,}€/ch</span></span>
          </div>
          <div style="font-size:10px;color:#555e78;margin-top:8px;">
            Ratio &lt; 1 : achat sous coût → défensif ·
            Ratio &gt; 1.5 : pipeline à venir → surveiller offre
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ────────────────────────────────────────────────────────────────────────
    with col2:

        # ── SIGNAL 3 : Pipeline vs absorption ────────────────────────────
        pip   = float(mi["pipeline"]["pip_ratio"])
        roomg = float(mi["pipeline"]["rooms_g"])
        absorp = round(roomg / pip, 2) if pip > 0 else 99.0

        if absorp >= 1.2:
            abs_color, abs_signal = "#1fbd7e", "✅ Demande absorbe le pipeline"
        elif absorp >= 0.8:
            abs_color, abs_signal = "#4f7fff", "⚪ Absorption correcte"
        elif absorp >= 0.6:
            abs_color, abs_signal = "#f0a030", "⚠️ Pipeline potentiellement dilutif"
        else:
            abs_color, abs_signal = "#e2504a", "🔴 Pipeline dilutif — pression ADR"

        # Quadrant CBRE
        if pip <= 5 and roomg >= 4:
            quadrant, q_color = "Stronger demand / Lower supply ★", "#1fbd7e"
        elif pip <= 5:
            quadrant, q_color = "Steady demand / Lower supply", "#4f7fff"
        elif pip > 12:
            quadrant, q_color = "Stronger demand / Higher supply risk", "#f0a030"
        else:
            quadrant, q_color = "Steady demand / Higher supply risk", "#8b92a8"

        st.markdown(f"""
        <div style="background:#141720;border:1px solid #252b3b;border-radius:8px;
                    padding:14px 16px;margin-bottom:12px;">
          <div style="font-size:10px;color:#555e78;text-transform:uppercase;
                      letter-spacing:.08em;margin-bottom:6px;">
            🏗️ Signal 3 — Pipeline vs absorption (CBRE 2025)
          </div>
          <div style="font-size:20px;font-weight:600;color:{abs_color};margin-bottom:4px;">
            Ratio absorption {absorp}×
          </div>
          <div style="font-size:12px;color:#8b92a8;margin-bottom:6px;">{abs_signal}</div>
          <div style="display:flex;gap:20px;font-size:11px;font-family:monospace;margin-bottom:8px;">
            <span>Pipeline <span style="color:#e8eaf0;font-weight:600;">{pip}%</span></span>
            <span>Croissance <span style="color:#e8eaf0;font-weight:600;">{roomg}%/3a</span></span>
          </div>
          <div style="background:{q_color}18;border-left:3px solid {q_color};
                      border-radius:3px;padding:5px 8px;font-size:11px;color:{q_color};">
            Quadrant CBRE : {quadrant}
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── SIGNAL 4 : Liquidité structurelle vs cyclique ─────────────────
        lp = safe_liquidity(mid)
        hvi_cagr = float(mi["liquidite"]["hvi_cagr"])
        depth_bar = lp["depth"] / 5 * 100

        st.markdown(f"""
        <div style="background:#141720;border:1px solid #252b3b;border-radius:8px;
                    padding:14px 16px;margin-bottom:12px;">
          <div style="font-size:10px;color:#555e78;text-transform:uppercase;
                      letter-spacing:.08em;margin-bottom:6px;">
            🔄 Signal 4 — Liquidité de sortie (HVS + CBRE 2025)
          </div>
          <div style="font-size:20px;font-weight:600;color:{lp['color']};margin-bottom:4px;">
            {lp['type']}
          </div>
          <div style="font-size:12px;color:#8b92a8;margin-bottom:8px;">
            Profondeur acheteurs : {lp['depth']}/5
          </div>
          <div style="height:5px;background:#1c2130;border-radius:3px;overflow:hidden;margin-bottom:8px;">
            <div style="width:{depth_bar}%;height:100%;background:{lp['color']};border-radius:3px;"></div>
          </div>
          <div style="font-size:10px;color:#8b92a8;margin-bottom:6px;">
            Acquéreurs potentiels à la revente :
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:4px;">
            {"".join(f'<span style="background:#252b3b;color:#8b92a8;font-size:9px;padding:2px 7px;border-radius:8px;">{b}</span>' for b in lp["buyers"])}
          </div>
          <div style="font-size:10px;color:#555e78;margin-top:8px;">
            CAGR HVS 10a : {'+' if hvi_cagr >= 0 else ''}{hvi_cagr}% —
            {'Liquidité structurelle confirmée' if hvi_cagr >= 2 else 'Liquidité cyclique uniquement' if hvi_cagr < 0 else 'Profil mixte'}
          </div>
        </div>
        """, unsafe_allow_html=True)

        # ── SIGNAL 6 : Concentration de la demande ────────────────────────
        dd = safe_demand_div(mid)
        dp = DEMAND_PROFILE.get(mid, {})

        # Donut proxy en barres
        segs = [
            ("Loisirs",    dd["leisure_pct"],   "#4f7fff"),
            ("Corporate",  dd["corporate_pct"],  "#1fbd7e"),
            ("MICE",       dd["mice_pct"],        "#f0a030"),
            ("Transit",    dd["transit_pct"],     "#7f6fff"),
        ]

        bars_html = "".join(f"""
          <div style="margin-bottom:5px;">
            <div style="display:flex;justify-content:space-between;
                        font-size:10px;color:#8b92a8;margin-bottom:2px;">
              <span>{label}</span><span>{pct}%</span>
            </div>
            <div style="height:4px;background:#1c2130;border-radius:2px;overflow:hidden;">
              <div style="width:{pct}%;height:100%;background:{color};border-radius:2px;"></div>
            </div>
          </div>""" for label, pct, color in segs)

        mice_str = f"#{dd['mice_rank']} ICCA" if dd.get("mice_rank") else "Non classé ICCA"
        st.markdown(f"""
        <div style="background:#141720;border:1px solid #252b3b;border-radius:8px;
                    padding:14px 16px;margin-bottom:12px;">
          <div style="font-size:10px;color:#555e78;text-transform:uppercase;
                      letter-spacing:.08em;margin-bottom:6px;">
            🎯 Signal 6 — Concentration de la demande (CBRE + ICCA)
          </div>
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:8px;">
            <div>
              <span style="font-size:20px;font-weight:600;color:{dd['risk_color']};">
                {dd['diversif_score']}/100</span>
              <span style="font-size:10px;color:#555e78;margin-left:4px;">diversification</span>
            </div>
            <div style="font-size:11px;color:{dd['risk_color']};">{dd['risk_label']}</div>
          </div>
          {bars_html}
          <div style="display:flex;gap:16px;margin-top:8px;font-size:10px;color:#8b92a8;">
            <span>Corporate depth <span style="color:#e8eaf0;font-weight:600;">{dd['corporate_depth']}/5</span></span>
            <span>MICE <span style="color:#e8eaf0;font-weight:600;">{mice_str}</span></span>
            <span>Saisonnalité <span style="color:#e8eaf0;font-weight:600;">{dd['seasonality']}</span></span>
          </div>
          <div style="font-size:10px;color:#555e78;margin-top:6px;font-style:italic;">
            {dp.get('dominant', '')}
          </div>
        </div>
        """, unsafe_allow_html=True)

    # ── Vue comparative tous marchés ──────────────────────────────────────
    st.divider()
    st.markdown("#### Synthèse comparative — tous marchés actifs")

    rows_ins = []
    for m in active_markets:
        m_id = m["id"]
        s    = next((x for x in scores if x["id"] == m_id), None)
        if not s:
            continue

        cyc   = safe_hvi_cycle(m_id)
        rcr   = safe_rcr(m_id, float(m["faisabilite"]["dev_cost"]))
        dd    = safe_demand_div(m_id)
        lp    = safe_liquidity(m_id)
        cap   = float(m["liquidite"]["caprate"])
        sprd  = round(cap - debt_cost, 2)
        pip_r = float(m["pipeline"]["pip_ratio"])
        rm_g  = float(m["pipeline"]["rooms_g"])
        ab    = round(rm_g / pip_r, 2) if pip_r > 0 else 99.0
        rt_m  = score_to_rating(s["total"])

        rows_ins.append({
            "Marché":          m["name"],
            "Note":            rt_m["rating"],
            "Cycle valeur":    cyc["phase"],
            "Spread (%)":      sprd,
            "Pipeline abs.":   ab,
            "Liquidité":       lp["type"],
            "Coût rempl.":     rcr["ratio"],
            "Diversif. dem.":  dd["diversif_score"],
            "Loisirs %":       dd["leisure_pct"],
            "Saisonnalité":    dd["seasonality"],
        })

    df_ins = pd.DataFrame(rows_ins)
    st.dataframe(
        df_ins, use_container_width=True, hide_index=True,
        column_config={
            "Spread (%)":    st.column_config.NumberColumn("Spread (%)", format="%.2f"),
            "Pipeline abs.": st.column_config.NumberColumn("Absorption pipeline", format="%.2f"),
            "Coût rempl.":   st.column_config.NumberColumn("Coût remplacement ×", format="%.2f"),
            "Diversif. dem.":st.column_config.ProgressColumn("Diversif. demande", min_value=0, max_value=100),
        },
    )

    st.caption(
        "⚠️ Données proxy calibrées — Profils demande (CBRE taxonomie, ICCA 2024, "
        "STR Segmentation estimates). Remplacer par données STR propriétaires pour usage décisionnel."
    )


# ── FOOTER — Sources ──────────────────────────────────────────────────────────

st.divider()
st.markdown("""
<div style="font-size:10px;color:#555e78;line-height:1.7;padding:4px 0 16px 0;">
<b style="color:#8b92a8;">Sources académiques & institutionnelles</b><br>
O'Neill J.W., Zhao J., Liu P., Caligiuri M.D. (2023), <i>Benchmarking Hotel Investment Risk: Differences Based on Types of Hotels</i>, Cornell Hospitality Quarterly — GOPPAR RSD, Risk Penetration Index ·
HVS London (2025), <i>European Hotel Valuation Index</i> — indices valeur/chambre, CAGR 2015-24 ·
CBRE Research (déc. 2025), <i>European Hotels Destination Index</i> — labour costs, Hospitality Workforce Elasticity ·
Choi J.G. (1999) — cycle hôtelier ·
Corgel J. (2004) — spread cap rate / coût dette ·
STR Global, JLL Hotels & Hospitality, Eurostat, FMI WEO, UNWTO, Coface — données marché & macro.<br>
<i>Données marchés indicatives, calibrées sur les sources ci-dessus — à remplacer par données STR propriétaires pour usage décisionnel. REIV Hospitality · Scoring absolu v3.2</i>
</div>
""", unsafe_allow_html=True)
