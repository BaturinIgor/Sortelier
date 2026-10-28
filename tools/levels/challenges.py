"""Уровни испытаний: ежедневное (один уровень на день) и недельное (3 уровня с особым правилом).

Запуск: python3 tools/levels/challenges.py [--daily N] [--weekly N]
Пишет Sortelier/Resources/Data/daily.json и weekly.json. Каждый уровень проверен решателем.
Игра берет уровень по номеру дня (недели) по кругу, поэтому у всех игроков он одинаковый.
"""
import argparse
import json
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
import generate as G  # noqa: E402

# shelves, max_depth, orders, dishes, free_slots, hidden_share, ingredient_triples, hard, intro
DAILY = [
    (6, 3, 8, 2, 5, 0.2, 0, False, None),
    (7, 3, 9, 3, 6, 0.25, 0, False, None),
    (7, 4, 10, 3, 6, 0.3, 1, False, None),
    (6, 4, 9, 3, 5, 0.3, 0, False, None),
]
WEEKLY = {
    # особые правила недели
    "noboosters": (8, 4, 13, 4, 6, 0.4, 1, True, None),
    "hidden": (8, 4, 12, 4, 7, 1.0, 1, True, None),
    "recipes": (8, 4, 9, 9, 7, 0.35, 0, True, None),
}
WEEKLY_ORDER = ["noboosters", "hidden", "recipes"]


def make(level_id, params, seed):
    lv = G.generate_level(30, params, seed)
    lv["id"] = level_id
    lv["intro"] = None
    lv.pop("attempts", None)
    return lv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", type=int, default=120)
    ap.add_argument("--weekly", type=int, default=52)
    args = ap.parse_args()
    daily = []
    t = time.time()
    for i in range(args.daily):
        params = DAILY[i % len(DAILY)]
        daily.append(make(1001 + i, params, seed=50000 + i))
        if i % 10 == 9:
            print(f"daily {i + 1}/{args.daily} {time.time() - t:.0f}s", flush=True)
    with open(os.path.join(G.DATA, "daily.json"), "w") as f:
        json.dump(daily, f, ensure_ascii=False, separators=(",", ":"))
    weekly = []
    for w in range(args.weekly):
        rule = WEEKLY_ORDER[w % len(WEEKLY_ORDER)]
        levels = []
        for k in range(3):
            lv = make(2001 + w * 3 + k, WEEKLY[rule], seed=90000 + w * 7 + k)
            lv["rule"] = rule
            levels.append(lv)
        weekly.append({"week": w, "rule": rule, "levels": levels})
        print(f"weekly {w + 1}/{args.weekly} {rule} {time.time() - t:.0f}s", flush=True)
    with open(os.path.join(G.DATA, "weekly.json"), "w") as f:
        json.dump(weekly, f, ensure_ascii=False, separators=(",", ":"))
    print("written", len(daily), "daily and", len(weekly), "weekly sets")


if __name__ == "__main__":
    random.seed(0)
    main()
