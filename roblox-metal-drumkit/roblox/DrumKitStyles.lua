--[[
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

-- アップロードした画像の ID ("rbxassetid://123..." の形)
Styles.TEXTURES = {
	IronStorm = { sparkle = "", flames = "", tiger = "", carbon = "", burst = "", lightning = "", logo = "" },
	Sovereign = { flame = "", birdseye = "", burl = "", quilt = "", stripe = "", flameburst = "", logo = "" },
}

Styles.NeonAccents = false -- true にすると差し色のラインが発光
Styles.DefaultKit = "IronStorm"

local SP = Enum.Material.SmoothPlastic
local function mat(name: string): Enum.Material
	local ok, m = pcall(function()
		return (Enum.Material :: any)[name]
	end)
	return if ok and m then m else SP
end
local function rgb(r: number, g: number, b: number): Color3
	return Color3.fromRGB(r, g, b)
end

local KITS = {}

-- IRON STORM: メタル仕様。ツインペダル、カーブラック、ロゴ入りフロントヘッド
KITS.IronStorm = {
	name = "IRON STORM",
	Colors = {
		{ id = "black", name = "ブラック", nameEn = "Black", color = rgb(18, 18, 22) },
		{ id = "red", name = "ブラッドレッド", nameEn = "Blood Red", color = rgb(150, 10, 24) },
		{ id = "blue", name = "コバルトブルー", nameEn = "Cobalt Blue", color = rgb(28, 78, 210) },
		{ id = "green", name = "トキシックグリーン", nameEn = "Toxic Green", color = rgb(70, 190, 30) },
		{ id = "purple", name = "パープル", nameEn = "Purple", color = rgb(100, 32, 160) },
		{ id = "orange", name = "オレンジ", nameEn = "Orange", color = rgb(235, 100, 12) },
		{ id = "pink", name = "ピンク", nameEn = "Pink", color = rgb(232, 64, 150) },
		{ id = "gold", name = "ゴールド", nameEn = "Gold", color = rgb(205, 155, 45) },
		{ id = "white", name = "ホワイト", nameEn = "White", color = rgb(232, 232, 228) },
		{ id = "gunmetal", name = "ガンメタル", nameEn = "Gunmetal", color = rgb(72, 76, 84) },
	},
	Patterns = {
		{ id = "solid", name = "ソリッド", nameEn = "Solid", reflectance = 0.12, hoop = "color" },
		{ id = "sparkle", name = "スパークル", nameEn = "Sparkle", reflectance = 0.18, hoop = "color" },
		{ id = "flames", name = "ファイヤー", nameEn = "Flames", reflectance = 0.1, hoop = "black" },
		{ id = "tiger", name = "タイガー", nameEn = "Tiger", reflectance = 0.1, hoop = "black" },
		{ id = "carbon", name = "カーボン", nameEn = "Carbon", reflectance = 0.08, hoop = "black" },
		{ id = "burst", name = "バースト", nameEn = "Burst", reflectance = 0.12, hoop = "black" },
		{ id = "lightning", name = "ライトニング", nameEn = "Lightning", reflectance = 0.1, hoop = "black" },
	},
	Hardware = {
		{ id = "chrome", name = "クローム", nameEn = "Chrome", color = rgb(214, 216, 222), reflectance = 0.4, material = mat("SmoothPlastic") },
		{ id = "black", name = "ブラックニッケル", nameEn = "Black Nickel", color = rgb(40, 40, 46), reflectance = 0.22, material = mat("SmoothPlastic") },
		{ id = "gold", name = "ゴールド", nameEn = "Gold", color = rgb(214, 170, 72), reflectance = 0.3, material = mat("SmoothPlastic") },
	},
	Cymbals = {
		{ id = "brilliant", name = "ブリリアント", nameEn = "Brilliant", main = rgb(214, 160, 80), dark = rgb(150, 100, 48), reflectance = 0.1, material = mat("Metal") },
		{ id = "dark", name = "ダーク", nameEn = "Dark", main = rgb(120, 84, 42), dark = rgb(90, 60, 30), reflectance = 0.04, material = mat("Metal") },
		{ id = "black", name = "ブラック", nameEn = "Black", main = rgb(32, 30, 30), dark = rgb(26, 24, 24), reflectance = 0.18, material = mat("Metal") },
	},
	Heads = {
		{ id = "coated", name = "ホワイト", nameEn = "Coated White", color = rgb(236, 234, 226) },
		{ id = "black", name = "ブラック", nameEn = "Black", color = rgb(22, 22, 24) },
	},
	Presets = {
		{ id = "iron_storm", name = "IRON STORM", style = { color = "black", pattern = "sparkle", accent = "red", hardware = "chrome", cymbals = "brilliant", heads = "coated" } },
		{ id = "hellfire", name = "HELLFIRE", style = { color = "orange", pattern = "flames", accent = "orange", hardware = "black", cymbals = "dark", heads = "black" } },
		{ id = "blue_thunder", name = "BLUE THUNDER", style = { color = "blue", pattern = "lightning", accent = "blue", hardware = "chrome", cymbals = "brilliant", heads = "black" } },
		{ id = "toxic", name = "TOXIC", style = { color = "green", pattern = "carbon", accent = "green", hardware = "black", cymbals = "black", heads = "black" } },
		{ id = "royal_venom", name = "ROYAL VENOM", style = { color = "purple", pattern = "burst", accent = "gold", hardware = "gold", cymbals = "brilliant", heads = "coated" } },
		{ id = "white_tiger", name = "WHITE TIGER", style = { color = "white", pattern = "tiger", accent = "red", hardware = "chrome", cymbals = "brilliant", heads = "coated" } },
		{ id = "golden_god", name = "GOLDEN GOD", style = { color = "gold", pattern = "sparkle", accent = "white", hardware = "gold", cymbals = "brilliant", heads = "coated" } },
		{ id = "ghost", name = "GHOST", style = { color = "gunmetal", pattern = "carbon", accent = "white", hardware = "black", cymbals = "dark", heads = "black" } },
	},
	Default = { color = "black", pattern = "sparkle", accent = "red", hardware = "chrome", cymbals = "brilliant", heads = "coated" },
	FeltColor = nil,
}
KITS.IronStorm.Accents = KITS.IronStorm.Colors

-- SOVEREIGN: スタンダードの最高峰。杢目の突板、ゴールド金物、スタンド配置、槌目シンバル
KITS.Sovereign = {
	name = "SOVEREIGN",
	Colors = {
		{ id = "natural", name = "ナチュラル", nameEn = "Natural", color = rgb(214, 164, 100) },
		{ id = "amber", name = "アンバー", nameEn = "Amber", color = rgb(178, 92, 26) },
		{ id = "cherry", name = "チェリー", nameEn = "Cherry", color = rgb(150, 42, 30) },
		{ id = "wine", name = "ワインレッド", nameEn = "Wine Red", color = rgb(112, 20, 40) },
		{ id = "walnut", name = "ウォルナット", nameEn = "Walnut", color = rgb(104, 64, 38) },
		{ id = "ebony", name = "エボニー", nameEn = "Ebony", color = rgb(34, 26, 22) },
		{ id = "emerald", name = "エメラルド", nameEn = "Emerald", color = rgb(22, 112, 72) },
		{ id = "sapphire", name = "サファイア", nameEn = "Sapphire", color = rgb(26, 66, 142) },
		{ id = "smoke", name = "スモーク", nameEn = "Smoke", color = rgb(112, 110, 106) },
		{ id = "ivory", name = "アイボリー", nameEn = "Ivory", color = rgb(238, 230, 212) },
	},
	Patterns = {
		{ id = "solid", name = "ピアノラッカー", nameEn = "Piano Lacquer", reflectance = 0.18, hoop = "color" },
		{ id = "flame", name = "トラ杢メイプル", nameEn = "Flamed Maple", reflectance = 0.16, hoop = "darker" },
		{ id = "birdseye", name = "バーズアイ", nameEn = "Birdseye Maple", reflectance = 0.16, hoop = "darker" },
		{ id = "burl", name = "バール", nameEn = "Burl", reflectance = 0.16, hoop = "darker" },
		{ id = "quilt", name = "キルト", nameEn = "Quilted Maple", reflectance = 0.16, hoop = "darker" },
		{ id = "stripe", name = "マッカーサー", nameEn = "Macassar", reflectance = 0.16, hoop = "darker" },
		{ id = "flameburst", name = "トラ杢バースト", nameEn = "Flamed Burst", reflectance = 0.16, hoop = "black" },
	},
	Hardware = {
		{ id = "gold", name = "ゴールド", nameEn = "Gold", color = rgb(214, 170, 72), material = mat("SmoothPlastic"), reflectance = 0.3 },
		{ id = "chrome", name = "クローム", nameEn = "Chrome", color = rgb(214, 216, 222), material = mat("SmoothPlastic"), reflectance = 0.4 },
		{ id = "black", name = "ブラックニッケル", nameEn = "Black Nickel", color = rgb(40, 40, 46), material = mat("SmoothPlastic"), reflectance = 0.22 },
	},
	Cymbals = {
		{ id = "traditional", name = "トラディショナル", nameEn = "Traditional", main = rgb(196, 146, 74), dark = rgb(140, 96, 46), material = mat("Metal"), reflectance = 0.06 },
		{ id = "dark", name = "ダーク", nameEn = "Dark", main = rgb(112, 80, 42), dark = rgb(86, 58, 30), material = mat("Metal"), reflectance = 0.03 },
		{ id = "brilliant", name = "ブリリアント", nameEn = "Brilliant", main = rgb(222, 172, 92), dark = rgb(160, 110, 52), material = mat("Metal"), reflectance = 0.12 },
	},
	Heads = {
		{ id = "coated", name = "ホワイト", nameEn = "Coated White", color = rgb(236, 234, 226) },
		{ id = "black", name = "ブラック", nameEn = "Black", color = rgb(22, 22, 24) },
	},
	Accents = {
		{ id = "gold", name = "ゴールド", nameEn = "Gold", color = rgb(205, 165, 75) },
		{ id = "silver", name = "シルバー", nameEn = "Silver", color = rgb(200, 202, 208) },
		{ id = "ivory", name = "アイボリー", nameEn = "Ivory", color = rgb(232, 222, 198) },
		{ id = "black", name = "ブラック", nameEn = "Black", color = rgb(24, 22, 22) },
		{ id = "red", name = "レッド", nameEn = "Red", color = rgb(150, 22, 32) },
	},
	Presets = {
		{ id = "sovereign", name = "SOVEREIGN", style = { color = "amber", pattern = "flame", accent = "gold", hardware = "gold", cymbals = "traditional", heads = "coated" } },
		{ id = "noir", name = "NOIR", style = { color = "ebony", pattern = "solid", accent = "silver", hardware = "chrome", cymbals = "dark", heads = "black" } },
		{ id = "emerald_crown", name = "EMERALD CROWN", style = { color = "emerald", pattern = "birdseye", accent = "gold", hardware = "gold", cymbals = "traditional", heads = "coated" } },
		{ id = "vintage_burl", name = "VINTAGE BURL", style = { color = "walnut", pattern = "burl", accent = "ivory", hardware = "chrome", cymbals = "dark", heads = "coated" } },
		{ id = "sapphire_burst", name = "SAPPHIRE BURST", style = { color = "sapphire", pattern = "flameburst", accent = "silver", hardware = "chrome", cymbals = "brilliant", heads = "coated" } },
		{ id = "bordeaux", name = "BORDEAUX", style = { color = "wine", pattern = "quilt", accent = "gold", hardware = "gold", cymbals = "traditional", heads = "coated" } },
		{ id = "macassar", name = "MACASSAR", style = { color = "natural", pattern = "stripe", accent = "black", hardware = "black", cymbals = "dark", heads = "black" } },
		{ id = "ivory_classic", name = "IVORY CLASSIC", style = { color = "ivory", pattern = "solid", accent = "gold", hardware = "gold", cymbals = "brilliant", heads = "coated" } },
	},
	Default = { color = "amber", pattern = "flame", accent = "gold", hardware = "gold", cymbals = "traditional", heads = "coated" },
	FeltColor = rgb(38, 38, 40),
}

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
