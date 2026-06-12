# report.py — REIV Market Scorer v3.4
# Rapports HTML institutionnels : fiche individuelle + rapport comparatif Top N
# Niveau : présentation comité d'investissement / one-pager LP

from datetime import date
from data import (
    DIMS, REGION_LABELS, REGION_COLORS,
    hvi_cycle_phase, replacement_cost_ratio,
    demand_diversification_score, LIQUIDITY_PROFILE,
)
from scoring import score_color, risk_color, score_to_rating

# ── CSS institutionnel ────────────────────────────────────────────────────────

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'Inter',sans-serif;background:#ffffff;color:#1a1f2e;font-size:12px;line-height:1.6;padding:36px 40px;max-width:960px;margin:0 auto;}
h1{font-size:22px;font-weight:700;color:#0d0f18;margin-bottom:4px;}
h2{font-size:14px;font-weight:600;color:#1a1f2e;margin-bottom:10px;}
h3{font-size:10px;font-weight:600;letter-spacing:.10em;text-transform:uppercase;color:#8b92a8;margin-bottom:8px;}
.mono{font-family:'JetBrains Mono',monospace;}
/* Cards */
.card{background:#f8f9fc;border:1px solid #e4e8f0;border-radius:8px;padding:16px;margin-bottom:14px;}
.card-dark{background:#0d1117;border:1px solid #252b3b;border-radius:8px;padding:16px;margin-bottom:14px;}
.row{display:flex;gap:14px;}
.col{flex:1;min-width:0;}
/* Tags */
.tag{display:inline-block;font-size:10px;padding:2px 9px;border-radius:10px;font-weight:600;letter-spacing:.02em;}
.rating-pill{display:inline-block;font-family:'JetBrains Mono',monospace;font-size:22px;font-weight:700;padding:6px 18px;border-radius:8px;letter-spacing:.04em;}
/* Bars */
.bar-bg{height:5px;background:#e4e8f0;border-radius:3px;overflow:hidden;margin-top:3px;}
.bar-fill{height:100%;border-radius:3px;}
.bar-bg-dark{height:4px;background:#1c2130;border-radius:2px;overflow:hidden;margin-top:2px;}
/* Dim rows */
.dim-row{margin-bottom:9px;}
.dim-label{display:flex;justify-content:space-between;font-size:11px;color:#555e78;margin-bottom:2px;}
.dim-val{font-weight:600;}
.dot{display:inline-block;width:6px;height:6px;border-radius:50%;margin-right:5px;vertical-align:middle;}
/* Score */
.score-big{font-size:42px;font-weight:700;line-height:1;font-family:'JetBrains Mono',monospace;}
/* Signal blocks */
.signal{background:#f8f9fc;border:1px solid #e4e8f0;border-radius:6px;padding:10px 12px;margin-bottom:8px;}
.signal-val{font-size:18px;font-weight:700;font-family:'JetBrains Mono',monospace;}
.signal-lbl{font-size:10px;color:#8b92a8;text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px;}
.signal-sub{font-size:11px;margin-top:2px;}
/* Table */
table.vars{width:100%;border-collapse:collapse;font-size:11px;}
table.vars th{background:#f0f2f7;color:#8b92a8;padding:5px 8px;text-align:left;font-weight:500;border-bottom:1px solid #e4e8f0;}
table.vars td{padding:5px 8px;border-bottom:1px solid #f0f2f7;color:#1a1f2e;}
/* Stress */
table.stress{width:100%;border-collapse:collapse;font-size:11px;}
table.stress th{background:#f0f2f7;color:#8b92a8;padding:5px 10px;text-align:left;font-weight:500;border-bottom:2px solid #e4e8f0;}
table.stress td{padding:6px 10px;border-bottom:1px solid #f0f2f7;}
/* Comparatif */
table.synth{width:100%;border-collapse:collapse;font-size:11px;margin-bottom:20px;}
table.synth th{background:#0d1117;color:#8b92a8;padding:7px 10px;text-align:left;font-weight:500;border-bottom:1px solid #252b3b;white-space:nowrap;}
table.synth td{padding:6px 10px;border-bottom:1px solid #f0f2f7;}
table.synth tr:nth-child(even) td{background:#f8f9fc;}
/* Divider */
hr{border:none;border-top:1px solid #e4e8f0;margin:16px 0;}
/* Footer */
.footer{margin-top:28px;padding-top:12px;border-top:1px solid #e4e8f0;font-size:9px;color:#aab0c0;display:flex;justify-content:space-between;align-items:flex-start;gap:20px;}
.footer-sources{flex:1;line-height:1.5;}
/* Recommendation box */
.reco{border-radius:8px;padding:14px 16px;margin-bottom:14px;}
/* Print */
@media print{
  body{padding:16px;max-width:100%;}
  .card,.signal{break-inside:avoid;}
}
</style>
"""


def _rating_bg(color: str) -> str:
    """Convertit une couleur hex en version pastel pour fond."""
    return color + "18"


# ── FICHE INDIVIDUELLE ────────────────────────────────────────────────────────

def generate_fiche(
    market_data: dict,
    score_result: dict,
    dim_weights: dict,
    profile_name: str,
    stress_data: dict = None,
    debt_cost: float = 5.5,
) -> str:
    s   = score_result
    mid = market_data["id"]
    c   = score_color(s["total"])
    rc  = risk_color(s["risk_raw"])
    rt  = score_to_rating(s["total"])
    region_color = REGION_COLORS.get(s["region"], "#888")
    region_label = REGION_LABELS.get(s["region"], s["region"])
    today = date.today().strftime("%d %B %Y")

    # ── Notation & Gate 0 ──
    stress = stress_data or {}
    st_m   = stress.get(mid, {})
    gate0  = st_m.get("gate0", {"passed": True, "reasons": []})
    scens  = st_m.get("scenarios", {})
    base_s = scens.get("base", {})
    up_s   = scens.get("upside", {})
    dn_s   = scens.get("downside", {})
    delta  = st_m.get("delta_downside", 0)
    resil  = st_m.get("resilience", "—")
    resil_c = st_m.get("resilience_color", "#888")

    gate0_html = ""
    if not gate0["passed"]:
        gate0_html = f"""
        <div style="background:#e2504a15;border-left:3px solid #e2504a;
                    border-radius:4px;padding:8px 12px;margin-bottom:12px;font-size:11px;">
          <span style="color:#e2504a;font-weight:600;">❌ Gate 0 — Éliminé ({profile_name})</span>
          <span style="color:#8b92a8;margin-left:8px;">{' · '.join(gate0['reasons'])}</span>
        </div>"""

    # ── Scores dimensions ──
    dims_html = ""
    for d in DIMS:
        v  = s["dims"][d["id"]]
        dc = score_color(v)
        dw = dim_weights.get(d["id"], 0)
        dims_html += f"""
        <div class="dim-row">
          <div class="dim-label">
            <span><span class="dot" style="background:{d['color']};"></span>
              {d['label']} <span style="color:#c8ccd8;margin-left:4px;font-size:9px;">({dw}%)</span>
            </span>
            <span class="dim-val mono" style="color:{dc};">{v}</span>
          </div>
          <div class="bar-bg"><div class="bar-fill" style="width:{v}%;background:{d['color']};"></div></div>
        </div>"""

    # ── Données brutes ──
    vars_rows = ""
    for d in DIMS:
        for var in d["vars"]:
            val  = market_data[d["id"]][var["id"]]
            unit = var.get("unit", "")
            vars_rows += f"""
            <tr>
              <td><span class="dot" style="background:{d['color']};"></span>{d['label']}</td>
              <td style="color:#555e78;">{var['label']}</td>
              <td class="mono" style="font-weight:500;">{val}{' '+unit if unit else ''}</td>
            </tr>"""

    # ── Signaux Insights ──
    cyc = hvi_cycle_phase(mid)
    rcr = replacement_cost_ratio(mid, float(market_data["faisabilite"]["dev_cost"]))
    dd  = demand_diversification_score(mid)
    lp  = LIQUIDITY_PROFILE.get(mid, {"type": "—", "depth": 1, "buyers": []})
    cap = float(market_data["liquidite"]["caprate"])
    spread = round(cap - debt_cost, 2)
    sp_color = "#1fbd7e" if spread >= 2.5 else "#4f7fff" if spread >= 1.0 else "#f0a030" if spread >= 0 else "#e2504a"
    sp_signal = "Signal d'entrée fort" if spread >= 2.5 else "Signal d'entrée modéré" if spread >= 1.0 else "Spread serré" if spread >= 0 else "Spread négatif"
    pip   = float(market_data["pipeline"]["pip_ratio"])
    rmg   = float(market_data["pipeline"]["rooms_g"])
    ab    = round(rmg / pip, 2) if pip > 0 else 99.0
    ab_color = "#1fbd7e" if ab >= 1.2 else "#4f7fff" if ab >= 0.8 else "#f0a030" if ab >= 0.6 else "#e2504a"

    # ── Recommandation ──
    total = s["total"]
    if not gate0["passed"]:
        reco_color = "#e2504a"
        reco_icon  = "❌"
        reco_text  = f"Marché éliminé Gate 0 pour le profil {profile_name}. Requiert un profil Opportuniste."
    elif total >= 53:
        reco_color = "#1fbd7e"
        reco_icon  = "✅"
        reco_text  = f"Marché attractif — recommandé pour due diligence approfondie ({profile_name})."
    elif total >= 43:
        reco_color = "#4f7fff"
        reco_icon  = "🔍"
        reco_text  = f"Marché correct — éligible avec conditions et suivi des indicateurs clés."
    elif total >= 33:
        reco_color = "#f0a030"
        reco_icon  = "⚠️"
        reco_text  = f"Risques significatifs — due diligence renforcée requise, prime de risque explicite."
    else:
        reco_color = "#e2504a"
        reco_icon  = "🚫"
        reco_text  = f"Marché déconseillé dans les conditions actuelles pour le profil {profile_name}."

    # ── Stress section ──
    stress_html = ""
    if scens:
        rows = ""
        for scen_id, scen_label, scen_c in [
            ("base",    "Base (50%)",    "#4f7fff"),
            ("upside",  "Upside (20%)",  "#1fbd7e"),
            ("downside","Downside (30%)","#e2504a"),
        ]:
            sc = scens.get(scen_id, {})
            if not sc:
                continue
            rows += f"""
            <tr>
              <td><span style="color:{scen_c};font-weight:600;">{scen_label}</span></td>
              <td class="mono" style="font-weight:600;">{sc.get('score_final','—')}</td>
              <td><span class="tag" style="background:{sc.get('color','#888')}22;
                  color:{sc.get('color','#888')};">{sc.get('rating','—')}</span></td>
              <td style="color:#8b92a8;">{'-' + str(sc.get('haircut_pct',0)) + '%' if sc.get('haircut_pct',0) > 0 else '—'}</td>
            </tr>"""

        stress_html = f"""
        <div class="card" style="margin-top:0;">
          <h3>Stress test marché</h3>
          <table class="stress">
            <thead><tr><th>Scénario</th><th>Score</th><th>Note</th><th>Haircut pol.</th></tr></thead>
            <tbody>{rows}</tbody>
          </table>
          <div style="display:flex;justify-content:space-between;font-size:11px;
                      margin-top:10px;padding-top:8px;border-top:1px solid #e4e8f0;">
            <span style="color:#8b92a8;">Dégradation base → downside</span>
            <span style="font-weight:600;color:{resil_c};">{delta} cran{'s' if delta > 1 else ''} — {resil}</span>
          </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>REIV — {s['name']} · Fiche marché</title>
{CSS}
</head>
<body>

<!-- EN-TÊTE -->
<div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px;">
  <div>
    <div style="font-size:9px;color:#aab0c0;font-family:'JetBrains Mono',monospace;
                letter-spacing:.12em;margin-bottom:8px;">
      REIV HOSPITALITY · SCORING MARCHÉS HÔTELIERS · FICHE INDIVIDUELLE
    </div>
    <h1>{s['name']}</h1>
    <div style="margin-top:6px;display:flex;align-items:center;gap:8px;">
      <span class="tag" style="background:{region_color}22;color:{region_color};">{region_label}</span>
      <span style="color:#8b92a8;font-size:11px;">Profil : {profile_name}</span>
      <span style="color:#8b92a8;font-size:11px;">·</span>
      <span style="color:#8b92a8;font-size:11px;">{today}</span>
    </div>
  </div>
  <div style="text-align:right;">
    <div class="score-big" style="color:{c};">{s['total']}</div>
    <div style="font-size:10px;color:#8b92a8;margin-top:2px;">Score / 100</div>
    <div style="margin-top:8px;">
      <span class="rating-pill" style="background:{rt['color']}18;color:{rt['color']};">{rt['rating']}</span>
    </div>
    <div style="font-size:10px;color:#8b92a8;margin-top:4px;">{rt['label']}</div>
  </div>
</div>

<!-- GATE 0 + RECOMMANDATION -->
{gate0_html}
<div class="reco" style="background:{reco_color}12;border-left:3px solid {reco_color};">
  <span style="font-size:13px;font-weight:600;color:{reco_color};">{reco_icon} Recommandation</span>
  <p style="font-size:12px;color:#1a1f2e;margin-top:4px;">{reco_text}</p>
</div>

<hr>

<!-- SCORES + DONNÉES -->
<div class="row">
  <div class="col">
    <div class="card">
      <h3>Scores par dimension</h3>
      {dims_html}
      <div style="display:flex;justify-content:space-between;font-size:11px;
                  color:#8b92a8;border-top:1px solid #e4e8f0;padding-top:8px;margin-top:4px;">
        <span>Risque brut composite</span>
        <span class="mono" style="font-weight:600;color:{rc};">{s['risk_raw']}/100</span>
      </div>
    </div>
    {stress_html}
  </div>
  <div class="col">
    <div class="card">
      <h3>Données brutes</h3>
      <table class="vars">
        <thead><tr><th>Dimension</th><th>Variable</th><th>Valeur</th></tr></thead>
        <tbody>{vars_rows}</tbody>
      </table>
    </div>
  </div>
</div>

<hr>

<!-- 6 SIGNAUX INSIGHTS -->
<h2 style="margin-bottom:12px;">Signaux décision comité</h2>
<div class="row">
  <div class="col">

    <div class="signal">
      <div class="signal-lbl">📈 Cycle de valeur HVS 2025</div>
      <div class="signal-val" style="color:{cyc['color']};">{cyc['phase']}</div>
      <div class="signal-sub" style="color:{cyc['color']};">{cyc['signal']}</div>
      <div style="font-size:10px;color:#8b92a8;margin-top:5px;font-family:'JetBrains Mono',monospace;">
        HVI {cyc['hvi']:.2f} · Δ2024 {'+' if cyc['delta']>=0 else ''}{cyc['delta']}% · CAGR10a {'+' if cyc['cagr']>=0 else ''}{cyc['cagr']}%
      </div>
    </div>

    <div class="signal">
      <div class="signal-lbl">💰 Spread cap rate / coût dette (Corgel 2004)</div>
      <div class="signal-val" style="color:{sp_color};">{'+' if spread>=0 else ''}{spread}%</div>
      <div class="signal-sub" style="color:{sp_color};">{sp_signal}</div>
      <div style="font-size:10px;color:#8b92a8;margin-top:5px;">
        Cap rate {cap}% · Coût dette {debt_cost}% · Règle : &gt;250bps = signal achat
      </div>
    </div>

    <div class="signal">
      <div class="signal-lbl">🏗️ Pipeline vs absorption (CBRE 2025)</div>
      <div class="signal-val" style="color:{ab_color};">{ab}×</div>
      <div class="signal-sub" style="color:{ab_color};">{'Absorption correcte' if ab>=0.8 else 'Pipeline dilutif — pression ADR'}</div>
      <div style="font-size:10px;color:#8b92a8;margin-top:5px;">
        Pipeline {pip}% · Croissance parc {rmg}%/3a
      </div>
    </div>

  </div>
  <div class="col">

    <div class="signal">
      <div class="signal-lbl">🔄 Liquidité de sortie</div>
      <div class="signal-val" style="color:{lp.get('color','#888')};">{lp.get('type','—')}</div>
      <div class="signal-sub" style="color:#8b92a8;">
        Profondeur {lp.get('depth',1)}/5 · {', '.join(lp.get('buyers',[])[:3])}
      </div>
      <div style="font-size:10px;color:#8b92a8;margin-top:5px;">
        CAGR HVS 10a : {'+' if cyc['cagr']>=0 else ''}{cyc['cagr']}%
      </div>
    </div>

    <div class="signal">
      <div class="signal-lbl">🏗️ Valeur marché vs coût remplacement (HVS 2025)</div>
      <div class="signal-val" style="color:{rcr['color']};">{rcr['ratio']}×</div>
      <div class="signal-sub" style="color:{rcr['color']};">{rcr['signal']}</div>
      <div style="font-size:10px;color:#8b92a8;margin-top:5px;font-family:'JetBrains Mono',monospace;">
        HVI réel {rcr['hvi_eur']:,}€/ch · Dev cost {rcr['dev_eur']:,}€/ch
      </div>
    </div>

    <div class="signal">
      <div class="signal-lbl">🎯 Concentration de la demande (CBRE + ICCA)</div>
      <div class="signal-val" style="color:{dd['risk_color']};">{dd['diversif_score']}/100</div>
      <div class="signal-sub" style="color:{dd['risk_color']};">{dd['risk_label']}</div>
      <div style="font-size:10px;color:#8b92a8;margin-top:5px;">
        Loisirs {dd['leisure_pct']}% · Corporate {dd['corporate_pct']}% · MICE {dd['mice_pct']}%
        · Saisonnalité : {dd['seasonality']}
      </div>
    </div>

  </div>
</div>

<!-- FOOTER SOURCES -->
<div class="footer">
  <div class="footer-sources">
    <strong style="color:#8b92a8;">Sources académiques & institutionnelles</strong><br>
    O'Neill J.W. et al. (2023), Cornell Hospitality Quarterly — GOPPAR RSD, Risk Penetration Index ·
    HVS London (2025), European Hotel Valuation Index — HVI, CAGR 2015-24 ·
    CBRE Research (déc. 2025), European Hotels Destination Index — labour costs, HWE ·
    Choi (1999) — cycle hôtelier · Corgel (2004) — spread cap rate/coût dette ·
    STR Global, JLL Hotels, Eurostat, FMI WEO, UNWTO, Coface, ICCA Rankings 2024.<br>
    <em>Données indicatives — à remplacer par données STR propriétaires pour usage décisionnel.
    REIV Hospitality · Market Scorer v3.4 · Scoring absolu</em>
  </div>
  <div style="text-align:right;white-space:nowrap;color:#aab0c0;">
    REIV Hospitality<br>{today}
  </div>
</div>

</body>
</html>"""
    return html


# ── RAPPORT COMPARATIF TOP N ──────────────────────────────────────────────────

def generate_comparatif(
    scores: list,
    top_n: int,
    dim_weights: dict,
    profile_name: str,
    markets: list = None,
    stress_data: dict = None,
    debt_cost: float = 5.5,
) -> str:
    top   = scores[:top_n]
    today = date.today().strftime("%d %B %Y")
    stress = stress_data or {}

    # ── Tableau de synthèse ──
    thead = "<tr><th>#</th><th>Marché</th><th>Note</th><th>Score</th>"
    for d in DIMS:
        thead += f"<th>{d['label'][:16]}</th>"
    thead += "<th>Risque</th><th>Cycle valeur</th><th>Spread</th><th>Résilience</th></tr>"

    tbody = ""
    for i, s in enumerate(top):
        c  = score_color(s["total"])
        rc = risk_color(s["risk_raw"])
        rt = score_to_rating(s["total"])
        region_color = REGION_COLORS.get(s["region"], "#888")
        region_label = REGION_LABELS.get(s["region"], s["region"])

        cyc   = hvi_cycle_phase(s["id"])
        st_m  = stress.get(s["id"], {})
        resil = st_m.get("resilience", "—")
        resil_c = st_m.get("resilience_color", "#888")

        # Spread
        cap_r = 5.0  # fallback
        if markets:
            m = next((mm for mm in markets if mm["id"] == s["id"]), None)
            if m:
                cap_r = float(m["liquidite"]["caprate"])
        sprd  = round(cap_r - debt_cost, 2)
        sp_c  = "#1fbd7e" if sprd >= 1.0 else "#f0a030" if sprd >= 0 else "#e2504a"

        tbody += f"<tr>"
        tbody += f"<td class='mono' style='color:#8b92a8;font-weight:500;'>{i+1}</td>"
        tbody += f"<td style='font-weight:600;'>{s['name']}<br><span class='tag' style='background:{region_color}22;color:{region_color};margin-top:2px;'>{region_label}</span></td>"
        tbody += f"<td><span class='tag' style='background:{rt['color']}22;color:{rt['color']};font-size:12px;font-family:JetBrains Mono,monospace;'>{rt['rating']}</span></td>"
        tbody += f"<td class='mono' style='color:{c};font-weight:700;font-size:14px;'>{s['total']}</td>"
        for d in DIMS:
            dv = s["dims"][d["id"]]
            dc = score_color(dv)
            tbody += f"<td class='mono' style='color:{dc};'>{dv}</td>"
        tbody += f"<td class='mono' style='color:{rc};'>{s['risk_raw']}</td>"
        tbody += f"<td style='color:{cyc['color']};font-size:10px;'>{cyc['phase']}</td>"
        tbody += f"<td class='mono' style='color:{sp_c};'>{'+' if sprd>=0 else ''}{sprd}%</td>"
        tbody += f"<td style='color:{resil_c};font-size:10px;font-weight:500;'>{resil}</td>"
        tbody += "</tr>"

    # ── Fiches compactes ──
    cards_html = ""
    for i, s in enumerate(top):
        c  = score_color(s["total"])
        rt = score_to_rating(s["total"])
        region_color = REGION_COLORS.get(s["region"], "#888")
        region_label = REGION_LABELS.get(s["region"], s["region"])
        st_m  = stress.get(s["id"], {})
        scens = st_m.get("scenarios", {})
        dn_s  = scens.get("downside", {})

        # Signaux clés
        cyc = hvi_cycle_phase(s["id"])
        dd  = demand_diversification_score(s["id"])

        # Dim bars
        dim_bars = ""
        for d in DIMS:
            v  = s["dims"][d["id"]]
            dc = score_color(v)
            dim_bars += f"""
            <div style="margin-bottom:6px;">
              <div style="display:flex;justify-content:space-between;
                          font-size:10px;color:#8b92a8;margin-bottom:2px;">
                <span><span class="dot" style="background:{d['color']};"></span>{d['label']}</span>
                <span class="mono" style="color:{dc};font-weight:600;">{v}</span>
              </div>
              <div class="bar-bg"><div class="bar-fill" style="width:{v}%;background:{d['color']};"></div></div>
            </div>"""

        down_html = ""
        if dn_s:
            dn_rt = dn_s.get("rating", "—")
            dn_c  = dn_s.get("color", "#888")
            resil = st_m.get("resilience", "—")
            rc_c  = st_m.get("resilience_color", "#888")
            down_html = f"""
            <div style="display:flex;justify-content:space-between;font-size:10px;
                        border-top:1px solid #e4e8f0;padding-top:8px;margin-top:6px;">
              <span style="color:#8b92a8;">Downside</span>
              <span>
                <span class="tag" style="background:{dn_c}22;color:{dn_c};">{dn_rt}</span>
                <span style="color:{rc_c};font-weight:500;margin-left:6px;">{resil}</span>
              </span>
            </div>"""

        cards_html += f"""
        <div class="card" style="break-inside:avoid;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px;">
            <div style="display:flex;align-items:center;gap:10px;">
              <div style="width:26px;height:26px;border-radius:50%;background:{c}22;color:{c};
                          display:flex;align-items:center;justify-content:center;
                          font-size:11px;font-weight:700;font-family:JetBrains Mono,monospace;
                          flex-shrink:0;">{i+1}</div>
              <div>
                <div style="font-size:14px;font-weight:700;">{s['name']}</div>
                <span class="tag" style="background:{region_color}22;color:{region_color};">{region_label}</span>
              </div>
            </div>
            <div style="text-align:right;">
              <div class="mono" style="font-size:22px;font-weight:700;color:{c};">{s['total']}</div>
              <span class="rating-pill" style="background:{rt['color']}18;color:{rt['color']};
                    font-size:14px;padding:3px 10px;">{rt['rating']}</span>
            </div>
          </div>
          {dim_bars}
          <div style="display:flex;justify-content:space-between;font-size:10px;
                      color:#8b92a8;border-top:1px solid #e4e8f0;padding-top:6px;margin-top:4px;">
            <span>Cycle : <span style="color:{cyc['color']};font-weight:500;">{cyc['phase']}</span></span>
            <span>Diversif. <span style="color:{dd['risk_color']};font-weight:500;">{dd['diversif_score']}/100</span></span>
          </div>
          {down_html}
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>REIV — Rapport comparatif Top {top_n}</title>
{CSS}
<style>
.compare-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;}}
</style>
</head>
<body>

<div style="margin-bottom:20px;">
  <div style="font-size:9px;color:#aab0c0;font-family:'JetBrains Mono',monospace;
              letter-spacing:.12em;margin-bottom:8px;">
    REIV HOSPITALITY · SCORING MARCHÉS HÔTELIERS · RAPPORT COMPARATIF
  </div>
  <h1>Top {top_n} marchés — {profile_name}</h1>
  <p style="color:#8b92a8;font-size:11px;margin-top:6px;">
    Pondérations : {' · '.join([f"{d['label'][:14]} {dim_weights.get(d['id'],0)}%" for d in DIMS])}
  </p>
</div>

<div class="card">
  <h3>Tableau de synthèse</h3>
  <div style="overflow-x:auto;">
    <table class="synth">
      <thead>{thead}</thead>
      <tbody>{tbody}</tbody>
    </table>
  </div>
</div>

<h2 style="margin-bottom:12px;">Fiches détaillées</h2>
<div class="compare-grid">{cards_html}</div>

<div class="footer">
  <div class="footer-sources">
    <strong style="color:#8b92a8;">Sources</strong> ·
    O'Neill et al. (2023) Cornell HQ · HVS London (2025) European HVI ·
    CBRE Research (déc. 2025) Destination Index · STR Global · JLL Hotels ·
    Eurostat · FMI WEO · UNWTO · Coface · ICCA Rankings 2024 ·
    Choi (1999) · Corgel (2004).<br>
    <em>Données partiellement indicatives — REIV Hospitality · Market Scorer v3.4 · Scoring absolu</em>
  </div>
  <div style="text-align:right;white-space:nowrap;color:#aab0c0;">
    REIV Hospitality<br>{today}
  </div>
</div>

</body>
</html>"""
    return html
