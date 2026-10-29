"""Собирает уровни, посчитанные в CI (workflow "Generate levels"), в файлы игры.

Запуск: python3 tools/levels/merge_ci.py <папка с распакованными артефактами>
levels_<биом>_<с какого>.json сливаются в levels_<биом>.json, events_<тема>.json - в events.json.
"""
import glob
import json
import os
import sys

DATA = os.path.join(os.path.dirname(__file__), "..", "..", "Sortelier", "Resources", "Data")


def main():
    src = sys.argv[1]
    biomes = {}
    events_path = os.path.join(DATA, "events.json")
    events = json.load(open(events_path)) if os.path.exists(events_path) else {}
    for f in glob.glob(os.path.join(src, "**", "*.json"), recursive=True):
        name = os.path.basename(f)
        data = json.load(open(f))
        if name.startswith("levels_"):
            biome = int(name.split("_")[1])
            biomes.setdefault(biome, {}).update({l["id"]: l for l in data})
        elif name.startswith("events_"):
            theme = name[len("events_"):-5]
            events[theme] = data[theme]
    for biome, levels in biomes.items():
        path = os.path.join(DATA, f"levels_{biome}.json")
        old = {l["id"]: l for l in json.load(open(path))} if os.path.exists(path) else {}
        old.update(levels)
        out = sorted(old.values(), key=lambda l: l["id"])
        json.dump(out, open(path, "w"), ensure_ascii=False, separators=(",", ":"))
        print(f"biome {biome}: {len(out)} levels")
    if events:
        # порядок тем как в events.py
        order = ["halloween", "winter", "sweets", "bbq", "autumn"]
        events = {k: events[k] for k in sorted(events, key=lambda k: order.index(k) if k in order else 99)}
        json.dump(events, open(events_path, "w"), ensure_ascii=False, separators=(",", ":"))
        print("events:", {k: len(v) for k, v in events.items()})


if __name__ == "__main__":
    main()
