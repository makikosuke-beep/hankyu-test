"""Reads the style choices from roblox/DrumKitStyles.lua so previews use the
same colours and presets as the game (the Luau file is the single source)."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LUA = os.path.join(HERE, "..", "roblox", "DrumKitStyles.lua")

SECTIONS = ["Colors", "Patterns", "Hardware", "Cymbals", "Heads", "Presets"]


def _value(v):
    v = v.strip()
    m = re.match(r'^"(.*)"$', v)
    if m:
        return m.group(1)
    m = re.match(r"^rgb\((\d+),\s*(\d+),\s*(\d+)\)$", v)
    if m:
        return tuple(int(x) for x in m.groups())
    try:
        return float(v)
    except ValueError:
        return v


def _fields(body):
    out = {}
    for m in re.finditer(r'(\w+)\s*=\s*("[^"]*"|rgb\([^)]*\)|\{[^}]*\}|[^,}]+)', body):
        k, v = m.group(1), m.group(2)
        if v.startswith("{"):
            out[k] = _fields(v[1:-1])
        else:
            out[k] = _value(v)
    return out


def load(path=LUA):
    src = open(path, encoding="utf-8").read()
    data = {}
    for sec in SECTIONS:
        m = re.search(r"^Styles\.%s = \{\n(.*?)^\}" % sec, src, re.S | re.M)
        items = []
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            body = line[1:line.rindex("}")]
            items.append(_fields(body))
        data[sec] = items
    data["by_id"] = {sec: {it["id"]: it for it in data[sec]} for sec in SECTIONS}
    return data


if __name__ == "__main__":
    import json
    d = load()
    print(json.dumps({k: d[k] for k in SECTIONS}, ensure_ascii=False, indent=1)[:1500])
