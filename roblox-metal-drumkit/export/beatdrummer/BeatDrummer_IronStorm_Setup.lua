--[[
	Metal Drum Kit "IRON STORM" - Roblox Studio セットアップスクリプト

	使い方:
	  1. 3D インポーター (ホーム > 3D をインポート) で FBX (または OBJ) を読み込む
	  2. エクスプローラーで読み込まれた Model を選択する
	  3. このファイルの中身をすべてコマンドバー (表示 > コマンドバー) に貼り付けて Enter

	やること:
	  - パーツ名の末尾 (_Chrome, _Bronze など) から色・マテリアルを設定
	  - Drums / Cymbals / Hardware / 各パーツごとの Model に整理
	  - 全パーツを Anchored・当たり判定を軽量化
	  - スローン (椅子) に座れる Seat を追加
	  - Beat Drummer 用キット (*_Setup.lua) では、各パーツの Model に
	    Lane 属性 (BD / SN / HH / HT / FT / CR / RD など) と PieceKind 属性を付け、
	    叩いたときのアニメーション用に WorldPivot (回転の中心) を設定

	何度実行しても大丈夫です。PALETTE を書き換えて再実行すれば色を変えられます。
]]

local CONFIG = {
	Anchored = true,
	AddSeat = true, -- スローンに座れる Seat を追加する
	NeonAccents = false, -- true にすると赤いラインやインレイが発光 (ライブ演出向け)
	LogoTextureId = "", -- バスドラ前面ロゴ画像の ID (例: "rbxassetid://123456")。空なら変更しない
	GroupByCategory = true, -- Drums / Cymbals / Hardware にまとめる
	CollideOnlyRug = true, -- 当たり判定はラグ (敷物) だけにする
}

local PIVOTS = {
	["BD_Kick"] = {
		["part"] = "BD_Kick_Finish",
		["size"] = Vector3.new(2.1207, 2.1207, 1.7129),
		["offset"] = Vector3.new(0.0, 0.0, -0.0),
		["up"] = Vector3.new(0.0, 0.0, 1.0),
		["face"] = Vector3.new(0.0, 1.0, -0.0),
		["lane"] = "BD",
		["kind"] = "kick",
	},
	["Pedal_Main_BeaterR"] = {
		["part"] = "Pedal_Main_BeaterR_Chrome",
		["size"] = Vector3.new(0.0786, 0.6328, 0.4139),
		["offset"] = Vector3.new(0.0, -0.2679, -0.1572),
		["up"] = Vector3.new(0.0, 1.0, -0.0),
		["face"] = Vector3.new(0.0, 0.0, -1.0),
		["lane"] = "BD",
		["kind"] = "beater",
	},
	["Pedal_Main_BeaterL"] = {
		["part"] = "Pedal_Main_BeaterL_Chrome",
		["size"] = Vector3.new(0.0786, 0.6328, 0.4139),
		["offset"] = Vector3.new(0.0, -0.2679, -0.1572),
		["up"] = Vector3.new(0.0, 1.0, -0.0),
		["face"] = Vector3.new(0.0, 0.0, -1.0),
		["lane"] = "BD",
		["kind"] = "beater",
	},
	["HT_Tom"] = {
		["part"] = "HT_Tom_Finish",
		["size"] = Vector3.new(0.9491, 0.9582, 1.0781),
		["offset"] = Vector3.new(-0.0, 0.0, 0.0),
		["up"] = Vector3.new(0.062, 0.9511, 0.3027),
		["face"] = Vector3.new(0.1917, 0.0, 0.9814),
		["lane"] = "HT",
		["kind"] = "drum",
	},
	["LT_Tom"] = {
		["part"] = "LT_Tom_Finish",
		["size"] = Vector3.new(1.1371, 1.1011, 1.2782),
		["offset"] = Vector3.new(0.0, -0.0, 0.0),
		["up"] = Vector3.new(-0.0637, 0.9511, 0.3024),
		["face"] = Vector3.new(-0.1972, 0.0, 0.9804),
		["lane"] = "LT",
		["kind"] = "drum",
	},
	["FT_FloorTom"] = {
		["part"] = "FT_FloorTom_Finish",
		["size"] = Vector3.new(1.4514, 1.4429, 1.4514),
		["offset"] = Vector3.new(0.0, 0.0, 0.0),
		["up"] = Vector3.new(0.0, 1.0, -0.0),
		["face"] = Vector3.new(-0.7215, 0.0, 0.6924),
		["lane"] = "FT",
		["kind"] = "drum",
	},
	["SN_Snare"] = {
		["part"] = "SN_Snare_Finish",
		["size"] = Vector3.new(1.2834, 0.6884, 1.3132),
		["offset"] = Vector3.new(0.0, 0.0, 0.0),
		["up"] = Vector3.new(0.0242, 0.9962, 0.0837),
		["face"] = Vector3.new(0.2563, 0.0, 0.9666),
		["lane"] = "SN",
		["kind"] = "drum",
	},
	["HH_Top"] = {
		["part"] = "HH_Top_Bronze",
		["size"] = Vector3.new(1.2728, 0.126, 1.2727),
		["offset"] = Vector3.new(0.0, 0.0562, 0.0),
		["up"] = Vector3.new(0.0, 1.0, -0.0),
		["face"] = Vector3.new(0.7797, 0.0, 0.6262),
		["lane"] = "HH",
		["kind"] = "hihat_top",
	},
	["HH_Bottom"] = {
		["part"] = "HH_Bottom_Bronze",
		["size"] = Vector3.new(1.2728, 0.126, 1.2727),
		["offset"] = Vector3.new(0.0, -0.063, 0.0),
		["up"] = Vector3.new(0.0, 1.0, -0.0),
		["face"] = Vector3.new(0.7797, 0.0, 0.6262),
		["lane"] = "HH",
		["kind"] = "hihat_bottom",
	},
	["CR_Crash"] = {
		["part"] = "CR_Crash_Bronze",
		["size"] = Vector3.new(1.6163, 0.5593, 1.5539),
		["offset"] = Vector3.new(0.0315, 0.197, 0.0644),
		["up"] = Vector3.new(0.1504, 0.9397, 0.3072),
		["face"] = Vector3.new(0.4257, 0.0, 0.9049),
		["lane"] = "CR",
		["kind"] = "cymbal",
	},
	["RD_Ride"] = {
		["part"] = "RD_Ride_Bronze",
		["size"] = Vector3.new(1.9823, 0.4772, 1.9712),
		["offset"] = Vector3.new(-0.0326, 0.22, 0.0418),
		["up"] = Vector3.new(-0.1279, 0.9781, 0.1639),
		["face"] = Vector3.new(-0.5971, 0.0, 0.8022),
		["lane"] = "RD",
		["kind"] = "cymbal",
	},
} -- generated: BeatDrummer_IronStorm

local function mat(name, fallback)
	local ok, m = pcall(function()
		return Enum.Material[name]
	end)
	return ok and m or fallback
end

local SP = Enum.Material.SmoothPlastic

-- パーツ名の末尾キー -> 見た目
local PALETTE = {
	Chrome = { Color = Color3.fromRGB(214, 216, 222), Material = SP, Reflectance = 0.4 },
	Finish = { Color = Color3.fromRGB(18, 18, 22), Material = SP, Reflectance = 0.12 },
	Accent = { Color = Color3.fromRGB(175, 12, 24), Material = SP, Reflectance = 0.05 },
	HeadCoated = { Color = Color3.fromRGB(236, 234, 226), Material = SP },
	HeadBlack = { Color = Color3.fromRGB(16, 16, 18), Material = SP, Reflectance = 0.05 },
	HeadClear = { Color = Color3.fromRGB(205, 205, 200), Material = SP },
	HeadLogo = { Color = Color3.fromRGB(16, 16, 18), Material = SP },
	Bronze = { Color = Color3.fromRGB(214, 160, 80), Material = mat("Metal", SP), Reflectance = 0.1 },
	BronzeDark = { Color = Color3.fromRGB(150, 100, 48), Material = mat("Metal", SP) },
	BlackMetal = { Color = Color3.fromRGB(30, 30, 34), Material = mat("Metal", SP) },
	Rubber = { Color = Color3.fromRGB(24, 24, 24), Material = mat("Rubber", SP) },
	Felt = { Color = Color3.fromRGB(150, 16, 26), Material = mat("Fabric", SP) },
	Leather = { Color = Color3.fromRGB(20, 20, 22), Material = mat("Leather", SP) },
	Rug = { Color = Color3.fromRGB(34, 34, 38), Material = mat("Carpet", mat("Fabric", SP)) },
}

local function category(comp)
	local function has(s)
		return comp:find(s, 1, true) ~= nil
	end
	if comp:find("Rug$") then
		return nil
	end
	local info = PIVOTS[comp]
	if info and info.kind ~= "beater" then
		if info.kind == "cymbal" or info.kind == "hihat_top" or info.kind == "hihat_bottom" then
			return "Cymbals"
		end
		return "Drums"
	end
	if has("Boom_") or has("TomArm_") or has("Stand") or has("Pedal_") or has("Rack") or has("Throne") then
		return "Hardware"
	end
	if has("Kick_") or has("Snare") or has("Tom_") then
		return "Drums"
	end
	if has("Crash_") or has("Ride_") or has("China_") or has("Splash_") or has("Stack_") or has("HiHat_") then
		return "Cymbals"
	end
	return "Hardware"
end

local Selection = game:GetService("Selection")
local root = Selection:Get()[1] or workspace:FindFirstChild("BeatDrummer_IronStorm")
assert(root, "インポートしたドラムセットの Model を選択してから実行してください")
if root:IsA("BasePart") then
	root = root:FindFirstAncestorWhichIsA("Model") or root
end

local function getModel(parent, name)
	local m = parent:FindFirstChild(name)
	if not (m and m:IsA("Model")) then
		m = Instance.new("Model")
		m.Name = name
		m.Parent = parent
	end
	return m
end

local parts = {}
for _, d in ipairs(root:GetDescendants()) do
	if d:IsA("BasePart") and d.Name ~= "DrummerSeat" then
		table.insert(parts, d)
	end
end

local styled = 0
for _, p in ipairs(parts) do
	local comp, key = p.Name:match("^(.+)_(%w+)$")
	local style = key and PALETTE[key]
	if style then
		local textured = (p:IsA("MeshPart") and p.TextureID ~= "") or p:FindFirstChildOfClass("SurfaceAppearance") ~= nil
		if key == "HeadLogo" and CONFIG.LogoTextureId ~= "" and p:IsA("MeshPart") then
			p.TextureID = CONFIG.LogoTextureId
			textured = true
		end
		if not (key == "HeadLogo" and textured) then
			p.Color = style.Color
			p.Material = style.Material
			p.Reflectance = style.Reflectance or 0
		end
		if key == "Accent" and CONFIG.NeonAccents then
			p.Material = Enum.Material.Neon
		end
		styled += 1
	end
	p.Anchored = CONFIG.Anchored
	p.CanCollide = (not CONFIG.CollideOnlyRug) or key == "Rug"
	p.CanTouch = false
	pcall(function()
		p.CollisionFidelity = Enum.CollisionFidelity.Box
	end)
	pcall(function()
		p.RenderFidelity = Enum.RenderFidelity.Automatic
	end)
	if comp and CONFIG.GroupByCategory then
		comp = comp:gsub("^MetalDrumKit_", "")
		local cat = category(comp)
		local parent = cat and getModel(root, cat) or root
		p.Parent = getModel(parent, comp)
	end
end

-- 空になった古いフォルダ / Model を掃除
for _, d in ipairs(root:GetDescendants()) do
	if (d:IsA("Model") or d:IsA("Folder")) and #d:GetDescendants() == 0 then
		d:Destroy()
	end
end

local function findPart(suffix)
	for _, d in ipairs(root:GetDescendants()) do
		if d:IsA("BasePart") and d.Name:sub(-#suffix) == suffix then
			return d
		end
	end
end

-- Lane 属性と回転の中心 (WorldPivot) を設定
local laned = 0
for comp, info in pairs(PIVOTS) do
	local ref = findPart(info.part)
	local model = ref and ref.Parent
	if ref and model and model:IsA("Model") and model.Name == comp then
		-- インポート後に拡大・縮小されていても合うように、パーツの大きさから倍率を求める
		local k = 1
		if info.size.Magnitude > 1e-4 then
			k = ref.Size.Magnitude / info.size.Magnitude
		end
		local pos = ref.CFrame:PointToWorldSpace(info.offset * k)
		local up = ref.CFrame:VectorToWorldSpace(info.up)
		local face = ref.CFrame:VectorToWorldSpace(info.face)
		if math.abs(face:Dot(up)) > 0.98 then
			face = ref.CFrame.LookVector
		end
		model.WorldPivot = CFrame.lookAt(pos, pos + face, up)
		if info.lane then
			model:SetAttribute("Lane", info.lane)
		end
		model:SetAttribute("PieceKind", info.kind)
		laned += 1
	end
end
if next(PIVOTS) ~= nil and root:IsA("Model") then
	root:SetAttribute("DrumKit", true)
end

-- スローンに Seat を追加 (キャラクターはスネア側を向いて座る)
if CONFIG.AddSeat then
	local cushion = findPart("Throne_Leather")
	local snare = findPart("Snare_Finish")
	local old = root:FindFirstChild("DrummerSeat", true)
	if old then
		old:Destroy()
	end
	if cushion then
		local top = cushion.Position + Vector3.new(0, cushion.Size.Y / 2 - 0.15, 0)
		local dir = snare and (snare.Position - cushion.Position) or Vector3.new(0, 0, -1)
		dir = Vector3.new(dir.X, 0, dir.Z)
		dir = dir.Magnitude > 1e-3 and dir.Unit or Vector3.new(0, 0, -1)
		local seat = Instance.new("Seat")
		seat.Name = "DrummerSeat"
		seat.Size = Vector3.new(1.2, 0.2, 1.2)
		seat.Transparency = 1
		seat.Anchored = true
		seat.CanCollide = false
		seat.CFrame = CFrame.lookAt(top, top + dir)
		seat.Parent = cushion.Parent
	end
end

if root:IsA("Model") then
	root.PrimaryPart = findPart("Rug_Rug") or root.PrimaryPart
end

print(("[DrumKitSetup] %d パーツを設定 (色・マテリアル %d、Lane/回転中心 %d)"):format(#parts, styled, laned))
