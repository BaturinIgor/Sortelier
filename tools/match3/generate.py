"""Подбор ходов и звезд для уровней "Рынка" и отчет по балансу.

python3 tools/match3/generate.py [--runs 40] [--only 1-10]

Для каждого уровня бот играет runs раз без ограничения ходов. Лимит ходов - перцентиль по целевой доле побед
(levels.target), звезды - по тому, сколько ходов обычно остается у быстрых прохождений. Потом тот же бот
проверяет лимит в режимах: без бустеров, с бустерами перед уровнем, +5 ходов, серия из 5 побед.
Результат: Sortelier/Resources/Data/match3.json и tools/match3/balance.json.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(__file__))
from bot import play  # noqa: E402
from levels import LEVELS, target  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(ROOT, "Sortelier", "Resources", "Data", "match3.json")
REPORT = os.path.join(os.path.dirname(__file__), "balance.json")

# Полная проверка режимов - tools/match3/balance.py; здесь только контроль без бустеров.
MODES = {
    "free": [],
}


def pct(values, q):
    values = sorted(values)
    k = (len(values) - 1) * q
    lo, hi = math.floor(k), math.ceil(k)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def run(args):
    lv, seed, specials = args
    return play(lv, seed, limit=160, specials=specials)


def tune(pool, lv, runs):
    jobs = [(lv, 1000 + s, []) for s in range(runs)]
    used = [m if m is not None else 999 for m in pool.map(run, jobs)]
    w = target(lv)
    moves = int(math.ceil(pct(used, min(0.98, w)))) + (3 if w >= 1 else 0)
    moves = max(10, min(60, moves))
    fast = pct(used, 0.25)
    mid = pct(used, 0.55)
    s3 = max(2, int(moves - fast))
    s2 = max(1, min(s3 - 1, int(moves - mid)))
    lv = dict(lv, moves=moves, stars=[s2, s3])
    report = {"id": lv["id"], "moves": moves, "used_p50": pct(used, 0.5), "stars": [s2, s3], "hard": lv["hard"]}
    for name, specials in MODES.items():
        jobs = [(lv, 5000 + s, specials) for s in range(runs)]
        res = [m if m is not None else 999 for m in pool.map(run, jobs)]
        report[name] = round(sum(1 for m in res if m <= moves) / len(res), 2)
        if name == "free":
            report["plus5"] = round(sum(1 for m in res if m <= moves + 5) / len(res), 2)
        if name == "pre":
            report["pre_plus5"] = round(sum(1 for m in res if m <= moves + 5) / len(res), 2)
    return lv, report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=40)
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    only = set()
    for part in filter(None, args.only.split(",")):
        a, _, b = part.partition("-")
        only |= set(range(int(a), int(b or a) + 1))
    existing = {}
    if os.path.exists(OUT):
        existing = {lv["id"]: lv for lv in json.load(open(OUT))["levels"]}
    reports = {}
    if os.path.exists(REPORT):
        reports = {r["id"]: r for r in json.load(open(REPORT))}
    with Pool(os.cpu_count() or 2) as pool:
        for lv in LEVELS:
            if only and lv["id"] not in only:
                continue
            tuned, rep = tune(pool, lv, args.runs)
            existing[lv["id"]] = tuned
            reports[lv["id"]] = rep
            print(json.dumps(rep), flush=True)
    levels = []
    for lv in LEVELS:
        t = existing.get(lv["id"])
        if not t:
            continue
        levels.append({k: t[k] for k in ("id", "chapter", "cells", "colors", "moves", "stars", "goals", "intro", "hard")
                       if k in t and t[k] is not None})
    with open(OUT, "w") as f:
        json.dump({"levels": levels}, f, ensure_ascii=False, separators=(",", ":"))
    with open(REPORT, "w") as f:
        json.dump([reports[k] for k in sorted(reports)], f, indent=1)


if __name__ == "__main__":
    main()
