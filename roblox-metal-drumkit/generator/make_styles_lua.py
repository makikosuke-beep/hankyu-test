"""Generates roblox/DrumKitStyles.lua from styles_catalog.json.

The JSON is the single source for the selectable colours / patterns of every
kit; the Blender renders and the web preview read the same file.

Run:  python make_styles_lua.py
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CATALOG = os.path.join(HERE, "styles_catalog.json")
OUT = os.path.join(HERE, "..", "roblox", "DrumKitStyles.lua")

SECTIONS = ["Colors", "Patterns", "Hardware", "Cymbals", "Heads"]

HEADER = '''--[[
	DrumKitStyles - ドラムキットの色・模様の切り替え (IRON STORM / SOVEREIGN)
	※ このファイルは generator/make_styles_lua.py が styles_catalog.json から作っています。
	   選択肢を増やすときは JSON を直して作り直すか、このファイルの KITS を直接直してください。

	シェルの色 × 模様 × 差し色 × 金物 × シンバル × ヘッド を組み合わせて、キットの見た目を変えます。
	サーバーで apply すると全員に同じ見た目が見えます。
	どのキットかは Model の KitId 属性 (セットアップスクリプトが付ける) で決まります。

	使い方:
		local Styles = require(ReplicatedStorage.BeatDrummer.DrumKitStyles)
		Styles.apply(kitModel, Styles.preset("hellfire", "IronStorm"))
		Styles.apply(kitModel, { color = "emerald", pattern = "birdseye" })   -- KitId 属性のキットとして扱う

		-- 保存するとき (DataStore など)
		local saved = Styles.encode(style, "Sovereign")    -- "amber/flame/gold/gold/traditional/coated"
		local style = Styles.decode(saved, "Sovereign")    -- 不正な値は既定値に置き換わる

	模様の画像:
		export/styles/ (IRON STORM) と export/styles/sovereign/ (SOVEREIGN) の pattern_*.png と
		logo_overlay.png を Roblox にアップロードし、下の TEXTURES に ID を入れてください。
		ID が空の模様はソリッド (単色) で表示されます。
		画像の透明な部分にシェルの色が見える仕組みなので、1 枚の画像がどの色とも組み合わせられます。
]]

local Styles = {}
'''

LOGIC = '''
Styles.Kits = KITS

local SECTION_FOR = {
	color = "Colors",
	pattern = "Patterns",
	accent = "Accents",
	hardware = "Hardware",
	cymbals = "Cymbals",
	heads = "Heads",
}
local ORDER = { "color", "pattern", "accent", "hardware", "cymbals", "heads" }

-- Model からキットの ID を調べる (KitId 属性。無ければ既定のキット)
function Styles.kitOf(model: Instance?): string
	local id = model and model:GetAttribute("KitId")
	if type(id) == "string" and KITS[id] then
		return id
	end
	return Styles.DefaultKit
end

function Styles.catalog(kitId: string?)
	return KITS[kitId or Styles.DefaultKit] or KITS[Styles.DefaultKit]
end

function Styles.find(key: string, id: string?, kitId: string?): any
	local cat = Styles.catalog(kitId)
	local list = cat[SECTION_FOR[key] or ""]
	if not list or id == nil then
		return nil
	end
	for _, item in ipairs(list) do
		if item.id == id then
			return item
		end
	end
	return nil
end

-- 足りない項目や知らない ID を既定値で埋めた style を返す (サーバーでの検証にも使う)
function Styles.normalize(style: { [string]: any }?, kitId: string?): { [string]: string }
	local cat = Styles.catalog(kitId)
	local out = {}
	for _, key in ipairs(ORDER) do
		local id = style and style[key]
		if type(id) ~= "string" or Styles.find(key, id, kitId) == nil then
			id = cat.Default[key]
		end
		out[key] = id
	end
	return out
end

function Styles.preset(id: string, kitId: string?): { [string]: string }
	for _, p in ipairs(Styles.catalog(kitId).Presets) do
		if p.id == id then
			return Styles.normalize(p.style, kitId)
		end
	end
	return Styles.normalize(nil, kitId)
end

function Styles.encode(style: { [string]: any }?, kitId: string?): string
	local s = Styles.normalize(style, kitId)
	local parts = {}
	for _, key in ipairs(ORDER) do
		table.insert(parts, s[key])
	end
	return table.concat(parts, "/")
end

function Styles.decode(text: string?, kitId: string?): { [string]: string }
	local style = {}
	if type(text) == "string" then
		local i = 1
		for id in string.gmatch(text, "[^/]+") do
			local key = ORDER[i]
			if key then
				style[key] = id
			end
			i += 1
		end
	end
	return Styles.normalize(style, kitId)
end

local function scaled(c: Color3, k: number): Color3
	return Color3.new(c.R * k, c.G * k, c.B * k)
end

-- キットの Model に style を反映する。kitId を省くと KitId 属性で判断
function Styles.apply(kit: Instance, style: { [string]: any }?, kitId: string?)
	kitId = kitId or Styles.kitOf(kit)
	local cat = Styles.catalog(kitId)
	local textures = Styles.TEXTURES[kitId] or {}
	local s = Styles.normalize(style, kitId)
	local color = Styles.find("color", s.color, kitId).color
	local pattern = Styles.find("pattern", s.pattern, kitId)
	local accent = Styles.find("accent", s.accent, kitId).color
	local hw = Styles.find("hardware", s.hardware, kitId)
	local cym = Styles.find("cymbals", s.cymbals, kitId)
	local head = Styles.find("heads", s.heads, kitId)
	local tex = textures[pattern.id] or ""
	local hoopColor = color
	if tex ~= "" and pattern.hoop == "black" then
		hoopColor = Color3.fromRGB(18, 18, 22)
	elseif pattern.hoop == "darker" then
		hoopColor = scaled(color, 0.55)
	end
	local felt = cat.FeltColor or scaled(accent, 0.85)

	for _, p in ipairs(kit:GetDescendants()) do
		if not p:IsA("BasePart") then
			continue
		end
		local key = p.Name:match("_(%w+)$")
		if key == "Finish" then
			p.Color = color
			p.Material = SP
			p.Reflectance = pattern.reflectance
			if p:IsA("MeshPart") then
				p.TextureID = tex
			end
		elseif key == "Hoop" then
			p.Color = hoopColor
			p.Material = SP
			p.Reflectance = 0.12
		elseif key == "Accent" then
			p.Color = accent
			p.Material = if Styles.NeonAccents then Enum.Material.Neon else SP
			p.Reflectance = 0.05
		elseif key == "Felt" then
			p.Color = felt
		elseif key == "HeadLogo" then
			if (textures.logo or "") ~= "" and p:IsA("MeshPart") then
				p.TextureID = textures.logo
				p.Color = accent
			end
		elseif key == "Chrome" then
			p.Color = hw.color
			p.Material = hw.material
			p.Reflectance = hw.reflectance
		elseif key == "Bronze" or key == "BronzeDark" then
			p.Color = if key == "Bronze" then cym.main else cym.dark
			p.Material = cym.material
			p.Reflectance = cym.reflectance
		elseif key == "HeadCoated" then
			p.Color = head.color
		end
	end
	if kit:IsA("Model") then
		kit:SetAttribute("KitStyle", Styles.encode(s, kitId))
	end
	return s
end

return Styles
'''


def lua_str(s):
    return json.dumps(s, ensure_ascii=False)


def item_lua(it):
    fields = []
    for k, v in it.items():
        if isinstance(v, list) and len(v) == 3:
            fields.append("%s = rgb(%d, %d, %d)" % (k, *v))
        elif k == "material":
            fields.append('material = mat("%s")' % v)
        elif isinstance(v, str):
            fields.append("%s = %s" % (k, lua_str(v)))
        elif isinstance(v, dict):
            inner = ", ".join("%s = %s" % (a, lua_str(b)) for a, b in v.items())
            fields.append("%s = { %s }" % (k, inner))
        else:
            fields.append("%s = %s" % (k, v))
    return "{ " + ", ".join(fields) + " }"


def texture_names(kit):
    return [p["id"] for p in kit["Patterns"] if p["id"] != "solid"] + ["logo"]


def build(cat):
    out = [HEADER]
    out.append("-- アップロードした画像の ID (\"rbxassetid://123...\" の形)")
    out.append("Styles.TEXTURES = {")
    for kid, kit in cat["Kits"].items():
        names = ", ".join("%s = \"\"" % n for n in texture_names(kit))
        out.append("\t%s = { %s }," % (kid, names))
    out.append("}")
    out.append("")
    out.append("Styles.NeonAccents = false -- true にすると差し色のラインが発光")
    out.append("Styles.DefaultKit = %s" % lua_str(cat["DefaultKit"]))
    out.append("")
    out.append("local SP = Enum.Material.SmoothPlastic")
    out.append("local function mat(name: string): Enum.Material")
    out.append("\tlocal ok, m = pcall(function()")
    out.append("\t\treturn (Enum.Material :: any)[name]")
    out.append("\tend)")
    out.append("\treturn if ok and m then m else SP")
    out.append("end")
    out.append("local function rgb(r: number, g: number, b: number): Color3")
    out.append("\treturn Color3.fromRGB(r, g, b)")
    out.append("end")
    out.append("")
    out.append("local KITS = {}")
    for kid, kit in cat["Kits"].items():
        out.append("")
        out.append("-- %s: %s" % (kit["name"], kit.get("description", "")))
        out.append("KITS.%s = {" % kid)
        out.append("\tname = %s," % lua_str(kit["name"]))
        for sec in SECTIONS + (["Accents"] if isinstance(kit["Accents"], list) else []):
            out.append("\t%s = {" % sec)
            for it in kit[sec]:
                out.append("\t\t%s," % item_lua(it))
            out.append("\t},")
        out.append("\tPresets = {")
        for p in kit["Presets"]:
            out.append("\t\t%s," % item_lua(p))
        out.append("\t},")
        out.append("\tDefault = %s," % item_lua(kit["Default"]))
        fc = kit.get("FeltColor")
        out.append("\tFeltColor = %s," % ("rgb(%d, %d, %d)" % tuple(fc) if fc else "nil"))
        out.append("}")
        if isinstance(kit["Accents"], str):
            out.append("KITS.%s.Accents = KITS.%s.%s" % (kid, kid, kit["Accents"]))
    out.append(LOGIC)
    return "\n".join(out)


def main():
    cat = json.load(open(CATALOG, encoding="utf-8"))
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(build(cat))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
