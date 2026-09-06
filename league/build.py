"""Build the draft room's player pool from the ffdraft.app data pipeline.

Reads
  data/processed/Projections-<season>.json   averaged CBS, ESPN and NFL stat projections
  data/raw/adp/FantasyPros-<season>.csv       average draft position
  league/config.json                          league scoring, roster, draft order, watch list, plan
  league/host_snapshot.csv                    optional ADP and projection export from the league host

Writes
  league/league_data.js   a single script the draft room loads with a plain <script> tag

Run it with `python3 league/build.py` or `make league`.
"""

import csv
import glob
import json
import logging
import os
import re
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
CONFIG_PATH = os.path.join(HERE, "config.json")
SNAPSHOT_PATH = os.path.join(HERE, "host_snapshot.csv")
OUT_PATH = os.path.join(HERE, "league_data.js")

# the draft room uses DEF, the pipeline uses DST
POS_MAP = {"DST": "DEF"}
POSITIONS = ["QB", "RB", "WR", "TE", "K", "DEF"]
UNDRAFTED = 999.0


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def newest(pattern):
    files = glob.glob(pattern)
    if not files:
        return None

    def year(path):
        m = re.search(r"(\d{4})\.(csv|json)$", path)
        return int(m.group(1)) if m else -1

    return max(files, key=year)


def load_projections(season):
    path = os.path.join(DATA, "processed", f"Projections-{season}.json")
    if not os.path.exists(path):
        fallback = newest(os.path.join(DATA, "processed", "Projections-*.json"))
        if not fallback:
            sys.exit(f"no projections found under {DATA}/processed. Run `make data` first.")
        logging.warning("no projections for %s, using %s", season, os.path.basename(fallback))
        path = fallback
    with open(path) as f:
        rows = json.load(f)["data"]
    logging.info("loaded %d projection rows from %s", len(rows), os.path.basename(path))
    return rows


def load_adp(season, column):
    path = os.path.join(DATA, "raw", "adp", f"FantasyPros-{season}.csv")
    if not os.path.exists(path):
        fallback = newest(os.path.join(DATA, "raw", "adp", "*.csv"))
        if not fallback:
            logging.warning("no ADP file found, every player will show as undrafted")
            return {}
        logging.warning("no ADP for %s, using %s", season, os.path.basename(fallback))
        path = fallback
    adp = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            try:
                adp[r["key"]] = float(r[column])
            except (KeyError, ValueError, TypeError):
                continue
    logging.info("loaded ADP for %d players from %s", len(adp), os.path.basename(path))
    return adp


def load_snapshot():
    if not os.path.exists(SNAPSHOT_PATH):
        return {}
    snap = {}
    with open(SNAPSHOT_PATH) as f:
        for r in csv.DictReader(f):
            snap[norm(r["name"])] = {
                "pos": r["pos"],
                "team": r["team"],
                "adp": float(r["adp"]),
                "proj": float(r["proj"]),
            }
    logging.info("loaded host snapshot for %d players", len(snap))
    return snap


def norm(name):
    """Loose name key so `A.J. Brown` and `AJ Brown` line up."""
    n = name.lower()
    n = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", n)
    n = re.sub(r"[^a-z0-9 ]", "", n)
    return re.sub(r"\s+", " ", n).strip()


def dst_points_per_game(points_allowed):
    """Port of dstPointsPerGame from app/lib/store/reducers/players.tsx."""
    if points_allowed is None:
        return 0.0
    if points_allowed < 1:
        return 5.0
    if points_allowed < 7:
        return 4.0
    if points_allowed < 14:
        return 3.0
    if points_allowed < 18:
        return 1.0
    if points_allowed < 28:
        return 0.0
    if points_allowed < 35:
        return -1.0
    if points_allowed < 46:
        return -3.0
    return -5.0


def forecast(row, scoring):
    total = 0.0
    for stat, pts in scoring.items():
        v = row.get(stat)
        if v is None:
            continue
        if stat == "dfPointsAllowedPerGame":
            total += pts * 16.0 * dst_points_per_game(v)
        else:
            total += pts * v
    return round(total, 1)


def starters_by_position(config):
    """How many players at each position get started league wide.

    Mirrors updatePlayerVORs in the ffdraft.app reducer. Flex spots are handed to
    WR in reception scoring, otherwise split between WR and RB.
    """
    lineup = config["lineup"]
    n = len(config["teams"])
    counts = {p: lineup.count(p) for p in POSITIONS}
    flex = sum(1 for s in lineup if s in ("W/R", "W/R/T", "FLEX"))
    superflex = sum(1 for s in lineup if s in ("SUPERFLEX", "Q/W/R/T"))
    counts["QB"] += superflex
    if config["scoring"].get("receptions", 0) > 0:
        counts["WR"] += flex + 1
        counts["RB"] += 1
    else:
        counts["WR"] += flex + 1
        counts["RB"] += flex + 1
    counts["K"] = 0
    counts["DEF"] = 0
    return {p: round(c * n) for p, c in counts.items()}


def build():
    config = load_config()
    season = config["season"]
    scoring = config["scoring"]
    rows = load_projections(season)
    adp = load_adp(season, config["adp"].get("fantasypros_column", "std"))
    snapshot = load_snapshot() if config["adp"].get("prefer_host_snapshot", True) else {}

    players = []
    for r in rows:
        pos = POS_MAP.get(r["pos"], r["pos"])
        if pos not in POSITIONS:
            continue
        host = snapshot.get(norm(r["name"]))
        fp_adp = adp.get(r["key"])
        if host and host["pos"] == pos:
            adp_val, adp_src = host["adp"], "host"
        elif fp_adp is not None:
            adp_val, adp_src = fp_adp, "fantasypros"
        else:
            adp_val, adp_src = UNDRAFTED, "none"
        players.append(
            {
                "key": r["key"],
                "name": r["name"],
                "pos": pos,
                "team": r.get("team") or "",
                "bye": int(r["bye"]) if r.get("bye") else None,
                "adp": adp_val,
                "adpSource": adp_src,
                "proj": forecast(r, scoring),
                "hostProj": host["proj"] if host else None,
            }
        )

    # value over replacement, same method as ffdraft.app
    starters = starters_by_position(config)
    replacement = {}
    for pos in POSITIONS:
        ranked = sorted((p for p in players if p["pos"] == pos), key=lambda p: -p["proj"])
        idx = starters[pos]
        replacement[pos] = ranked[idx]["proj"] if idx < len(ranked) else 0.0
    for p in players:
        p["vor"] = round(p["proj"] - replacement[p["pos"]], 1)

    players.sort(key=lambda p: (-p["vor"], p["adp"]))
    for i, p in enumerate(players):
        p["vorRank"] = i + 1
    players.sort(key=lambda p: (p["adp"], -p["proj"]))
    for i, p in enumerate(players):
        p["id"] = i

    # warn about plan and list names that do not resolve to a pipeline player
    known = {norm(p["name"]) for p in players}
    referenced = set(config["watch"]) | set(config["avoid"])
    for slot in config["plan"]:
        referenced |= set(slot["targets"])
    unresolved = sorted(n for n in referenced if norm(n) not in known)
    if unresolved:
        logging.warning("%d names in config.json are not in the projections: %s", len(unresolved), ", ".join(unresolved))

    # rewrite config names to the pipeline spelling so lookups in the browser are exact
    by_norm = {norm(p["name"]): p["name"] for p in players}
    fix = lambda n: by_norm.get(norm(n), n)
    config["watch"] = [fix(n) for n in config["watch"]]
    config["avoid"] = [fix(n) for n in config["avoid"]]
    for slot in config["plan"]:
        slot["targets"] = [fix(n) for n in slot["targets"]]

    payload = {
        "season": season,
        "builtFrom": {
            "projections": f"Projections-{season}.json",
            "hostSnapshot": bool(snapshot),
            "replacementLevel": replacement,
            "startersByPosition": starters,
        },
        "config": config,
        "players": players,
    }
    with open(OUT_PATH, "w") as f:
        f.write("// generated by league/build.py. Do not edit by hand, edit league/config.json and rebuild.\n")
        f.write("window.LEAGUE_DATA = ")
        json.dump(payload, f, separators=(",", ":"))
        f.write(";\n")
    logging.info("wrote %d players to %s", len(players), os.path.relpath(OUT_PATH, ROOT))
    logging.info("replacement level: %s", {k: v for k, v in replacement.items()})


if __name__ == "__main__":
    build()
