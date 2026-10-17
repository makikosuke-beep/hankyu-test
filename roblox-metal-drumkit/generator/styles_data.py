"""Style choices for each kit, read from styles_catalog.json (the same data
that make_styles_lua.py writes into roblox/DrumKitStyles.lua)."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, "styles_catalog.json")
SECTIONS = ["Colors", "Accents", "Patterns", "Hardware", "Cymbals", "Heads", "Presets"]


def load(kit=None, path=CATALOG):
    cat = json.load(open(path, encoding="utf-8"))
    kid = kit or cat["DefaultKit"]
    d = dict(cat["Kits"][kid])
    if isinstance(d["Accents"], str):
        d["Accents"] = d[d["Accents"]]
    d["id"] = kid
    d["texturesPath"] = os.path.join(HERE, "..", "export", d["texturesDir"])
    d["by_id"] = {sec: {it["id"]: it for it in d[sec]} for sec in SECTIONS}
    return d


def kits(path=CATALOG):
    return list(json.load(open(path, encoding="utf-8"))["Kits"])


if __name__ == "__main__":
    for k in kits():
        d = load(k)
        print(k, {s: len(d[s]) for s in SECTIONS})
