"""Builds data.js for the Team 14 website from the clean tables in ../03 Daten und Analyse.

Run:  python3 -I build_data.py
Every number on the website comes from this file, so it matches the deck and the brief.
"""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
CLEAN = ROOT.parent / "03 Daten und Analyse" / "data" / "clean"

teams = pd.read_csv(CLEAN / "teams.csv")
teams = teams[teams.year >= 2006].copy()
matches = pd.read_csv(CLEAN / "matches.csv")
matches = matches[matches.year >= 2006].copy()
sp = pd.read_csv(CLEAN / "squad_positions.csv")
players = pd.read_csv(CLEAN / "players.csv")

ROUNDS = ["Round of 16", "Quarter-final", "Semi-final", "Final"]


def bracket(year):
    """Knockout tree from the round of 16 to the final, leaves in bracket order."""
    m = matches[(matches.year == year) & matches.stage_fifa.isin(ROUNDS)]
    by_round = {r: m[m.stage_fifa == r] for r in ROUNDS}

    def node(team, rnd):
        i = ROUNDS.index(rnd)
        row = by_round[rnd][(by_round[rnd].team_1 == team) | (by_round[rnd].team_2 == team)].iloc[0]
        out = {"t1": row.team_1, "t2": row.team_2, "s1": int(row.score_1), "s2": int(row.score_2),
               "pens": None if row.shootout != 1 else [int(row.pen_1), int(row.pen_2)],
               "w": row.winner, "round": rnd}
        if i > 0:
            out["c1"] = node(row.team_1, ROUNDS[i - 1])
            out["c2"] = node(row.team_2, ROUNDS[i - 1])
        return out

    final = by_round["Final"].iloc[0]
    return node(final.team_1, "Final")


editions = []
for y, g in teams.groupby("year"):
    champ = g[g.stage == "Champion"].iloc[0]
    editions.append({
        "year": int(y), "teams": int(len(g)), "median": round(float(g.value_m.median())),
        "top": g.sort_values("value_rank").iloc[0][["code", "team", "value_m"]].to_dict(),
        "champion": {"code": champ.code, "team": champ.team, "value": float(champ.value_m), "rank": int(champ.value_rank)},
        "bracket": bracket(int(y)),
        "squads": [{"code": r.code, "team": r.team, "value": float(r.value_m), "rank": int(r.value_rank),
                    "stage": r.stage, "stage_n": int(r.stage_n)} for r in g.sort_values("value_rank").itertuples()],
    })


def band(r):
    return "Top 4" if r <= 4 else "Rank 5–8" if r <= 8 else "Rank 9–16" if r <= 16 else "Rank 17+"


teams["band"] = teams.value_rank.map(band)
bands = []
for b in ["Top 4", "Rank 5–8", "Rank 9–16", "Rank 17+"]:
    g = teams[teams.band == b]
    bands.append({"band": b, "n": int(len(g)), "final": int((g.stage_n >= 6).sum()),
                  "semi": int((g.stage_n >= 5).sum()), "qf": int((g.stage_n >= 4).sum())})

# Attack effect: top-10 squads 2010-2026, line ranked within its World Cup
p = sp[sp.year >= 2010].copy()
for k in ["GK", "DF", "MF", "FW"]:
    p[k + "_r"] = p.groupby("year")[k + "_m"].rank(ascending=False, method="min")
top = p[p.value_rank <= 10]
lines = []
for k, name in [("GK", "Goalkeepers"), ("DF", "Defence"), ("MF", "Midfield"), ("FW", "Attack")]:
    a, b = top[top[k + "_r"] <= 5], top[top[k + "_r"] > 5]
    lines.append({"line": name, "top5": [int((a.stage_n >= 6).sum()), int(len(a))],
                  "other": [int((b.stage_n >= 6).sum()), int(len(b))]})

por = p[p.code == "POR"]
portugal_lines = [{"year": int(r.year), "attack_share": round(r.FW_m / r.sum_m, 2), "attack_rank": int(r.FW_r),
                   "GK": r.GK_m, "DF": r.DF_m, "MF": r.MF_m, "FW": r.FW_m, "stage": r.stage} for r in por.itertuples()]

ronaldo = []
for y, g in players[players.code == "POR"].groupby("year"):
    g = g.sort_values("value_m", ascending=False).reset_index(drop=True)
    i = g.index[g.tm_name.fillna("").str.contains("Cristiano")][0]
    ronaldo.append({"year": int(y), "value": float(g.value_m[i]), "share": round(g.value_m[i] / g.value_m.sum(), 3),
                    "rank": int(i + 1), "of": int(len(g)),
                    "top": [{"name": r.tm_name, "value": float(r.value_m), "pos": r.position} for r in g.head(3).itertuples()]})

# Knockouts: richer squad wins in play vs on penalties
ko = matches[(matches.phase != "Group") & matches.richer.notna()]
inplay, pens = ko[ko.shootout == 0], ko[ko.shootout == 1]
knockouts = {"inplay": [int(inplay.richer_won.sum()), int(len(inplay))],
             "pens": [int(pens.richer_won.sum()), int(len(pens))]}

# Shoot-out records by nation
rec = {}
for r in matches[(matches.shootout == 1)].itertuples():
    for t, n in ((r.team_1, r.team_1_name), (r.team_2, r.team_2_name)):
        rec.setdefault(t, {"code": t, "team": n, "won": 0, "lost": 0})
        rec[t]["won" if r.winner == t else "lost"] += 1
shootouts = sorted(rec.values(), key=lambda d: (-(d["won"] + d["lost"]), -d["won"]))[:10]

# Group place (points, goal difference, goals) for top-8 squads
from importlib.util import spec_from_file_location, module_from_spec  # noqa: E402
gp = {}
for y, g in matches[matches.phase == "Group"].groupby("year"):
    st, par = {}, {}

    def root(x):
        while par.setdefault(x, x) != x:
            x = par[x]
        return x
    for r in g.itertuples():
        par[root(r.team_1)] = root(r.team_2)
        for t, a, b in ((r.team_1, r.score_1, r.score_2), (r.team_2, r.score_2, r.score_1)):
            v = st.setdefault(t, [0, 0, 0])
            v[0] += 3 if a > b else 1 if a == b else 0
            v[1] += a - b
            v[2] += a
    grp = {}
    for t in st:
        grp.setdefault(root(t), []).append(t)
    for mem in grp.values():
        mem.sort(key=lambda t: st[t], reverse=True)
        for i, t in enumerate(mem, 1):
            gp[(y, t)] = i
teams["group_place"] = [gp.get((r.year, r.code)) for r in teams.itertuples()]
t8 = teams[teams.value_rank <= 8]
group = {str(k): [int((t8[t8.group_place == k].stage_n >= 4).sum()), int((t8.group_place == k).sum())] for k in (1, 2)}

# Underdogs: rank 13 or lower that reached the quarter-final
und = teams[(teams.value_rank >= 13) & (teams.stage_n >= 4)].sort_values(["year", "value_rank"])
underdogs = [{"year": int(r.year), "code": r.code, "team": r.team, "rank": int(r.value_rank),
              "value": float(r.value_m), "stage": r.stage,
              "shootout": bool(((matches.year == r.year) & (matches.shootout == 1) & (matches.winner == r.code)).any())}
             for r in und.itertuples()]


# ---- statistical model: chance of reaching each round by value rank (logistic regression on log rank)
import numpy as np  # noqa: E402
import statsmodels.api as sm  # noqa: E402
from scipy.stats import spearmanr  # noqa: E402

teams["lr"] = np.log(teams.value_rank)
model = {"curves": {}, "fits": {}}
grid = list(range(1, 49))
for key, thr in [("qf", 4), ("sf", 5), ("final", 6)]:
    y = (teams.stage_n >= thr).astype(int)
    fit = sm.Logit(y, sm.add_constant(teams.lr)).fit(disp=0)
    b = float(fit.params.lr)
    model["fits"][key] = {"b": round(b, 3), "p": float(fit.pvalues.lr), "pseudo_r2": round(float(fit.prsquared), 3),
                          "odds_per_doubling": round(float(np.exp(b * np.log(2))), 2)}
    model["curves"][key] = [round(float(fit.predict([1.0, np.log(r)])[0]), 4) for r in grid]
rho, p_rho = spearmanr(teams.value_rank, teams.stage_n)
model["spearman"] = {"rho": round(float(rho), 2), "p": float(p_rho), "n": int(len(teams))}
por_t = teams[teams.code == "POR"]
model["portugal_expected_final"] = round(sum(model["curves"]["final"][int(r) - 1] for r in por_t.value_rank), 2)

# ---- Portugal's six runs and where they ended
def exit_of(year):
    mm = matches[(matches.year == year) & ((matches.team_1 == "POR") | (matches.team_2 == "POR"))
                 & ~matches.stage_fifa.str.contains("third|Bronze", case=False)].sort_values("date")
    last = mm.iloc[-1]
    home = last.team_1 == "POR"
    opp = last.team_2_name if home else last.team_1_name
    s = (int(last.score_1), int(last.score_2)) if home else (int(last.score_2), int(last.score_1))
    pens = None
    if last.shootout == 1:
        pens = (int(last.pen_1), int(last.pen_2)) if home else (int(last.pen_2), int(last.pen_1))
    return {"round": last.stage_fifa, "opponent": opp, "score": s, "pens": pens, "won": bool(last.winner == "POR")}

portugal_runs = []
for r in por_t.sort_values("year").itertuples():
    portugal_runs.append({"year": int(r.year), "rank": int(r.value_rank), "value": float(r.value_m), "stage": r.stage,
                          "group_place": int(r.group_place), "last": exit_of(int(r.year))})

overview = {"world_cups": int(teams.year.nunique()), "matches": int(len(matches)),
            "knockouts": int((matches.phase != "Group").sum()), "shootouts": int(matches.shootout.sum()),
            "squads": int(len(teams)), "players": int(len(players)), "valued": int(players.value_m.notna().sum())}

data = {"overview": overview, "editions": editions, "bands": bands, "lines": lines,
        "portugal_lines": portugal_lines, "ronaldo": ronaldo, "knockouts": knockouts,
        "shootouts": shootouts, "group": group, "underdogs": underdogs, "model": model, "portugal_runs": portugal_runs}
(ROOT / "data.js").write_text("window.T14 = " + json.dumps(data, ensure_ascii=False, default=float) + ";\n", encoding="utf-8")
print(json.dumps({k: data[k] for k in ["overview", "bands", "lines", "knockouts", "group"]}, ensure_ascii=False))
print("champions", [(e["year"], e["champion"]) for e in editions])
print("model", model["fits"], model["spearman"], model["portugal_expected_final"])
print("portugal", portugal_runs)
print("underdogs", len(underdogs), "ronaldo", [(r["year"], r["share"]) for r in ronaldo])
