--[[
	DrumKitStyles - IRON STORM の色・模様の切り替え

	シェルの色 × 模様 × 差し色 × 金物 × シンバル × ヘッド を組み合わせて、
	キットの見た目を変えます。サーバーで apply すると全員に同じ見た目が見えます。

	使い方:
		local Styles = require(ReplicatedStorage.BeatDrummer.DrumKitStyles)
		Styles.apply(kitModel, Styles.preset("hellfire"))
		Styles.apply(kitModel, { color = "blue", pattern = "lightning", accent = "blue" })

		-- 保存するとき (DataStore など)
		local saved = Styles.encode(style)        -- "blue/lightning/blue/chrome/brilliant/coated"
		local style = Styles.decode(saved)       -- 不正な値は既定値に置き換わる

	模様の画像:
		export/styles/pattern_*.png と logo_overlay.png を Roblox にアップロードし、
		下の TEXTURES に ID を入れてください。ID が空の模様はソリッド (単色) で表示されます。
		画像の透明な部分にシェルの色が見える仕組みなので、1 枚の画像がどの色とも組み合わせられます。
]]

local Styles = {}

-- アップロードした画像の ID ("rbxassetid://123..." の形)
Styles.TEXTURES = {
	sparkle = "",
	flames = "",
	tiger = "",
	carbon = "",
	burst = "",
	lightning = "",
	logo = "", -- logo_overlay.png (エンブレムが差し色になるロゴ)
}

Styles.NeonAccents = false -- true にすると差し色のラインが発光

local SP = Enum.Material.SmoothPlastic
local function mat(name: string, fallback: Enum.Material): Enum.Material
	local ok, m = pcall(function()
		return (Enum.Material :: any)[name]
	end)
	return if ok and m then m else fallback
end
local function rgb(r: number, g: number, b: number): Color3
	return Color3.fromRGB(r, g, b)
end

-- シェルの色 (差し色の候補も同じ一覧)
Styles.Colors = {
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
}

-- 模様。hoop = バスドラムの木のフープの色 ("color" = シェルの色 / "black")
Styles.Patterns = {
	{ id = "solid", name = "ソリッド", nameEn = "Solid", reflectance = 0.12, hoop = "color" },
	{ id = "sparkle", name = "スパークル", nameEn = "Sparkle", reflectance = 0.18, hoop = "color" },
	{ id = "flames", name = "ファイヤー", nameEn = "Flames", reflectance = 0.1, hoop = "black" },
	{ id = "tiger", name = "タイガー", nameEn = "Tiger", reflectance = 0.1, hoop = "black" },
	{ id = "carbon", name = "カーボン", nameEn = "Carbon", reflectance = 0.08, hoop = "black" },
	{ id = "burst", name = "バースト", nameEn = "Burst", reflectance = 0.12, hoop = "black" },
	{ id = "lightning", name = "ライトニング", nameEn = "Lightning", reflectance = 0.1, hoop = "black" },
}

-- 金物 (ラグ、フープ、スタンド、ラックなど)
Styles.Hardware = {
	{ id = "chrome", name = "クローム", nameEn = "Chrome", color = rgb(214, 216, 222), material = SP, reflectance = 0.4 },
	{ id = "black", name = "ブラックニッケル", nameEn = "Black Nickel", color = rgb(40, 40, 46), material = SP, reflectance = 0.22 },
	{ id = "gold", name = "ゴールド", nameEn = "Gold", color = rgb(214, 170, 72), material = SP, reflectance = 0.3 },
}

-- シンバル (main = 通常のシンバル / dark = チャイナなど)
Styles.Cymbals = {
	{ id = "brilliant", name = "ブリリアント", nameEn = "Brilliant", main = rgb(214, 160, 80), dark = rgb(150, 100, 48), material = mat("Metal", SP), reflectance = 0.1 },
	{ id = "dark", name = "ダーク", nameEn = "Dark", main = rgb(120, 84, 42), dark = rgb(90, 60, 30), material = mat("Metal", SP), reflectance = 0.04 },
	{ id = "black", name = "ブラック", nameEn = "Black", main = rgb(32, 30, 30), dark = rgb(26, 24, 24), material = mat("Metal", SP), reflectance = 0.18 },
}

-- 打面のヘッド
Styles.Heads = {
	{ id = "coated", name = "ホワイト", nameEn = "Coated White", color = rgb(236, 234, 226) },
	{ id = "black", name = "ブラック", nameEn = "Black", color = rgb(22, 22, 24) },
}

-- ショップに並べるおすすめの組み合わせ
Styles.Presets = {
	{ id = "iron_storm", name = "IRON STORM", style = { color = "black", pattern = "sparkle", accent = "red", hardware = "chrome", cymbals = "brilliant", heads = "coated" } },
	{ id = "hellfire", name = "HELLFIRE", style = { color = "orange", pattern = "flames", accent = "orange", hardware = "black", cymbals = "dark", heads = "black" } },
	{ id = "blue_thunder", name = "BLUE THUNDER", style = { color = "blue", pattern = "lightning", accent = "blue", hardware = "chrome", cymbals = "brilliant", heads = "black" } },
	{ id = "toxic", name = "TOXIC", style = { color = "green", pattern = "carbon", accent = "green", hardware = "black", cymbals = "black", heads = "black" } },
	{ id = "royal_venom", name = "ROYAL VENOM", style = { color = "purple", pattern = "burst", accent = "gold", hardware = "gold", cymbals = "brilliant", heads = "coated" } },
	{ id = "white_tiger", name = "WHITE TIGER", style = { color = "white", pattern = "tiger", accent = "red", hardware = "chrome", cymbals = "brilliant", heads = "coated" } },
	{ id = "golden_god", name = "GOLDEN GOD", style = { color = "gold", pattern = "sparkle", accent = "white", hardware = "gold", cymbals = "brilliant", heads = "coated" } },
	{ id = "ghost", name = "GHOST", style = { color = "gunmetal", pattern = "carbon", accent = "white", hardware = "black", cymbals = "dark", heads = "black" } },
}

Styles.Default = { color = "black", pattern = "sparkle", accent = "red", hardware = "chrome", cymbals = "brilliant", heads = "coated" }

-- style のキー -> 選択肢の一覧
local LISTS = {
	color = Styles.Colors,
	pattern = Styles.Patterns,
	accent = Styles.Colors,
	hardware = Styles.Hardware,
	cymbals = Styles.Cymbals,
	heads = Styles.Heads,
}
local ORDER = { "color", "pattern", "accent", "hardware", "cymbals", "heads" }

function Styles.find(key: string, id: string?): any
	local list = LISTS[key]
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
function Styles.normalize(style: { [string]: any }?): { [string]: string }
	local out = {}
	for _, key in ipairs(ORDER) do
		local id = style and style[key]
		if type(id) ~= "string" or Styles.find(key, id) == nil then
			id = Styles.Default[key]
		end
		out[key] = id
	end
	return out
end

function Styles.preset(id: string): { [string]: string }
	for _, p in ipairs(Styles.Presets) do
		if p.id == id then
			return Styles.normalize(p.style)
		end
	end
	return Styles.normalize(nil)
end

function Styles.encode(style: { [string]: any }?): string
	local s = Styles.normalize(style)
	local parts = {}
	for _, key in ipairs(ORDER) do
		table.insert(parts, s[key])
	end
	return table.concat(parts, "/")
end

function Styles.decode(text: string?): { [string]: string }
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
	return Styles.normalize(style)
end

local function darker(c: Color3, k: number): Color3
	return Color3.new(c.R * k, c.G * k, c.B * k)
end

-- キットの Model に style を反映する
function Styles.apply(kit: Instance, style: { [string]: any }?)
	local s = Styles.normalize(style)
	local color = Styles.find("color", s.color).color
	local pattern = Styles.find("pattern", s.pattern)
	local accent = Styles.find("accent", s.accent).color
	local hw = Styles.find("hardware", s.hardware)
	local cym = Styles.find("cymbals", s.cymbals)
	local head = Styles.find("heads", s.heads)
	local tex = Styles.TEXTURES[pattern.id] or ""
	local hoopColor = if pattern.hoop == "black" and tex ~= "" then Styles.Colors[1].color else color

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
			p.Color = darker(accent, 0.85)
		elseif key == "HeadLogo" then
			if Styles.TEXTURES.logo ~= "" and p:IsA("MeshPart") then
				p.TextureID = Styles.TEXTURES.logo
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
		kit:SetAttribute("KitStyle", Styles.encode(s))
	end
	return s
end

return Styles
