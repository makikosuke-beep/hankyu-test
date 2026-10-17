--[[
	Beat Drummer のギター・ベース - Roblox Studio セットアップスクリプト

	使い方:
	  1. 3D インポーター (ホーム > 3D をインポート) で BandInstruments.fbx (または OBJ) を読み込む
	  2. エクスプローラーで読み込まれた Model を選択する
	  3. このファイルの中身をすべてコマンドバー (表示 > コマンドバー) に貼り付けて Enter

	やること:
	  - パーツ名 <楽器>_<部品> (Skyline_Body など) から色・マテリアルを設定
	    (ボディやピックガードの柄は FBX に入っている画像がそのまま使われます)
	  - 楽器ごとに Model "Guitar_<ID>" / "Bass_<ID>" にまとめ、WeldConstraint でつなぐ
	  - PrimaryPart (ボディ) に Attachment を作る
	      Wear  : 体に当たる裏側の位置。LookVector が楽器の表、RightVector がボディの下 (エンド側)、
	              UpVector が低音弦側。キャラクターの体の正面のアタッチメントに合わせると構えた向きになる
	      Neck  : 7 フレットあたり (左手の位置)
	      Strum : ピックアップの上 (右手で弾く位置)
	    Model の WorldPivot は Wear にそろえる
	  - 当たり判定なし・Massless。テンプレートの間は Anchored
	  - Model に属性 InstrumentId / Kind / DisplayName / DisplayNameEn / Style
	  - 全部を Folder "BandInstruments" に入れる (ReplicatedStorage などに移して使う)

	何度実行しても大丈夫です (2 回目以降は BandInstruments フォルダを選択して実行)。
]]

local INSTRUMENTS = {
	Skyline = {
		kind = "Guitar", name = "スカイライン", nameEn = "SKYLINE", style = "ST タイプ",
		primary = "Skyline_Body",
		wear = Vector3.new(0.00139, 0.00082, -0.08036),
		neck = Vector3.new(0.00235, 1.15037, 0.11964),
		strum = Vector3.new(0.00235, -0.14423, 0.11964),
		palette = {
			Neck = { Color = Color3.fromRGB(232, 196, 140), Material = "Wood", Reflectance = 0.05 },
			Board = { Color = Color3.fromRGB(62, 36, 26), Material = "Wood", Reflectance = 0.00 },
			Frets = { Color = Color3.fromRGB(208, 206, 198), Material = "Metal", Reflectance = 0.30 },
			Inlay = { Color = Color3.fromRGB(240, 236, 226), Material = "SmoothPlastic", Reflectance = 0.20 },
			Nut = { Color = Color3.fromRGB(238, 230, 210), Material = "SmoothPlastic", Reflectance = 0.05 },
			Hardware = { Color = Color3.fromRGB(214, 216, 222), Material = "Metal", Reflectance = 0.35 },
			Strings = { Color = Color3.fromRGB(206, 206, 202), Material = "Metal", Reflectance = 0.30, Glow = true },
			Pickup = { Color = Color3.fromRGB(24, 24, 26), Material = "SmoothPlastic", Reflectance = 0.08 },
			Knob = { Color = Color3.fromRGB(240, 238, 228), Material = "SmoothPlastic", Reflectance = 0.12 },
			Body = { Color = Color3.fromRGB(214, 120, 38), Material = "SmoothPlastic", Reflectance = 0.12, Textured = true },
			Guard = { Color = Color3.fromRGB(242, 240, 232), Material = "SmoothPlastic", Reflectance = 0.06 },
			Cover = { Color = Color3.fromRGB(240, 238, 228), Material = "SmoothPlastic", Reflectance = 0.08 },
		},
	},
	Prairie = {
		kind = "Guitar", name = "プレーリー", nameEn = "PRAIRIE", style = "TL タイプ",
		primary = "Prairie_Body",
		wear = Vector3.new(-0.00001, 0.00000, -0.08036),
		neck = Vector3.new(-0.00004, 1.27368, 0.11964),
		strum = Vector3.new(-0.00004, -0.02092, 0.11964),
		palette = {
			Neck = { Color = Color3.fromRGB(232, 196, 140), Material = "Wood", Reflectance = 0.05 },
			Board = { Color = Color3.fromRGB(228, 190, 132), Material = "Wood", Reflectance = 0.00 },
			Frets = { Color = Color3.fromRGB(208, 206, 198), Material = "Metal", Reflectance = 0.30 },
			Inlay = { Color = Color3.fromRGB(30, 26, 24), Material = "SmoothPlastic", Reflectance = 0.20 },
			Nut = { Color = Color3.fromRGB(238, 230, 210), Material = "SmoothPlastic", Reflectance = 0.05 },
			Hardware = { Color = Color3.fromRGB(214, 216, 222), Material = "Metal", Reflectance = 0.35 },
			Strings = { Color = Color3.fromRGB(206, 206, 202), Material = "Metal", Reflectance = 0.30, Glow = true },
			Pickup = { Color = Color3.fromRGB(24, 24, 26), Material = "SmoothPlastic", Reflectance = 0.08 },
			Knob = { Color = Color3.fromRGB(214, 216, 222), Material = "SmoothPlastic", Reflectance = 0.12 },
			Body = { Color = Color3.fromRGB(226, 168, 80), Material = "SmoothPlastic", Reflectance = 0.12, Textured = true },
			Guard = { Color = Color3.fromRGB(20, 20, 22), Material = "SmoothPlastic", Reflectance = 0.10 },
		},
	},
	Heritage = {
		kind = "Guitar", name = "ヘリテージ", nameEn = "HERITAGE", style = "LP タイプ",
		primary = "Heritage_Body",
		wear = Vector3.new(-0.00003, 0.00031, -0.07679),
		neck = Vector3.new(0.00003, 1.29254, 0.16250),
		strum = Vector3.new(0.00003, 0.04561, 0.16250),
		palette = {
			Neck = { Color = Color3.fromRGB(120, 52, 30), Material = "Wood", Reflectance = 0.05 },
			Board = { Color = Color3.fromRGB(62, 36, 26), Material = "Wood", Reflectance = 0.00 },
			Frets = { Color = Color3.fromRGB(208, 206, 198), Material = "Metal", Reflectance = 0.30 },
			Inlay = { Color = Color3.fromRGB(240, 236, 226), Material = "SmoothPlastic", Reflectance = 0.20 },
			Nut = { Color = Color3.fromRGB(238, 230, 210), Material = "SmoothPlastic", Reflectance = 0.05 },
			Hardware = { Color = Color3.fromRGB(222, 218, 206), Material = "Metal", Reflectance = 0.35 },
			Strings = { Color = Color3.fromRGB(206, 206, 202), Material = "Metal", Reflectance = 0.30, Glow = true },
			Pickup = { Color = Color3.fromRGB(24, 24, 26), Material = "SmoothPlastic", Reflectance = 0.08 },
			Knob = { Color = Color3.fromRGB(214, 160, 60), Material = "SmoothPlastic", Reflectance = 0.12 },
			Head = { Color = Color3.fromRGB(16, 14, 14), Material = "SmoothPlastic", Reflectance = 0.12 },
			Body = { Color = Color3.fromRGB(96, 16, 12), Material = "SmoothPlastic", Reflectance = 0.12 },
			Top = { Color = Color3.fromRGB(196, 70, 30), Material = "SmoothPlastic", Reflectance = 0.12, Textured = true },
			Binding = { Color = Color3.fromRGB(238, 226, 196), Material = "SmoothPlastic", Reflectance = 0.10 },
			Guard = { Color = Color3.fromRGB(238, 226, 196), Material = "SmoothPlastic", Reflectance = 0.06 },
		},
	},
	CrimsonHorn = {
		kind = "Guitar", name = "クリムゾンホーン", nameEn = "CRIMSON HORN", style = "SG タイプ",
		primary = "CrimsonHorn_Body",
		wear = Vector3.new(0.00097, 0.00006, -0.06071),
		neck = Vector3.new(0.00151, 1.31377, 0.10357),
		strum = Vector3.new(0.00151, 0.06684, 0.10357),
		palette = {
			Neck = { Color = Color3.fromRGB(118, 26, 20), Material = "Wood", Reflectance = 0.05 },
			Board = { Color = Color3.fromRGB(62, 36, 26), Material = "Wood", Reflectance = 0.00 },
			Frets = { Color = Color3.fromRGB(208, 206, 198), Material = "Metal", Reflectance = 0.30 },
			Inlay = { Color = Color3.fromRGB(240, 236, 226), Material = "SmoothPlastic", Reflectance = 0.20 },
			Nut = { Color = Color3.fromRGB(238, 230, 210), Material = "SmoothPlastic", Reflectance = 0.05 },
			Hardware = { Color = Color3.fromRGB(214, 216, 222), Material = "Metal", Reflectance = 0.35 },
			Strings = { Color = Color3.fromRGB(206, 206, 202), Material = "Metal", Reflectance = 0.30, Glow = true },
			Pickup = { Color = Color3.fromRGB(24, 24, 26), Material = "SmoothPlastic", Reflectance = 0.08 },
			Knob = { Color = Color3.fromRGB(20, 20, 22), Material = "SmoothPlastic", Reflectance = 0.12 },
			Head = { Color = Color3.fromRGB(16, 14, 14), Material = "SmoothPlastic", Reflectance = 0.12 },
			Body = { Color = Color3.fromRGB(104, 14, 12), Material = "SmoothPlastic", Reflectance = 0.12 },
			Guard = { Color = Color3.fromRGB(16, 16, 18), Material = "SmoothPlastic", Reflectance = 0.10 },
		},
	},
	Valkyrie = {
		kind = "Guitar", name = "ヴァルキリー", nameEn = "VALKYRIE", style = "V タイプ",
		primary = "Valkyrie_Body",
		wear = Vector3.new(0.00004, 0.00146, -0.06250),
		neck = Vector3.new(0.00004, 1.61792, 0.10536),
		strum = Vector3.new(0.00004, 0.37099, 0.10536),
		palette = {
			Neck = { Color = Color3.fromRGB(30, 28, 28), Material = "Wood", Reflectance = 0.05 },
			Board = { Color = Color3.fromRGB(62, 36, 26), Material = "Wood", Reflectance = 0.00 },
			Frets = { Color = Color3.fromRGB(208, 206, 198), Material = "Metal", Reflectance = 0.30 },
			Inlay = { Color = Color3.fromRGB(240, 236, 226), Material = "SmoothPlastic", Reflectance = 0.20 },
			Nut = { Color = Color3.fromRGB(238, 230, 210), Material = "SmoothPlastic", Reflectance = 0.05 },
			Hardware = { Color = Color3.fromRGB(214, 216, 222), Material = "Metal", Reflectance = 0.35 },
			Strings = { Color = Color3.fromRGB(206, 206, 202), Material = "Metal", Reflectance = 0.30, Glow = true },
			Pickup = { Color = Color3.fromRGB(24, 24, 26), Material = "SmoothPlastic", Reflectance = 0.08 },
			Knob = { Color = Color3.fromRGB(20, 20, 22), Material = "SmoothPlastic", Reflectance = 0.12 },
			Head = { Color = Color3.fromRGB(16, 14, 14), Material = "SmoothPlastic", Reflectance = 0.12 },
			Body = { Color = Color3.fromRGB(14, 14, 16), Material = "SmoothPlastic", Reflectance = 0.12 },
			Guard = { Color = Color3.fromRGB(242, 240, 232), Material = "SmoothPlastic", Reflectance = 0.06 },
		},
	},
	Velvet = {
		kind = "Bass", name = "ヴェルヴェット", nameEn = "VELVET", style = "JB タイプ",
		primary = "Velvet_Body",
		wear = Vector3.new(-0.00046, 0.00076, -0.08036),
		neck = Vector3.new(-0.00078, 1.48732, 0.12679),
		strum = Vector3.new(-0.00078, -0.32215, 0.12679),
		palette = {
			Neck = { Color = Color3.fromRGB(232, 196, 140), Material = "Wood", Reflectance = 0.05 },
			Board = { Color = Color3.fromRGB(62, 36, 26), Material = "Wood", Reflectance = 0.00 },
			Frets = { Color = Color3.fromRGB(208, 206, 198), Material = "Metal", Reflectance = 0.30 },
			Inlay = { Color = Color3.fromRGB(240, 236, 226), Material = "SmoothPlastic", Reflectance = 0.20 },
			Nut = { Color = Color3.fromRGB(238, 230, 210), Material = "SmoothPlastic", Reflectance = 0.05 },
			Hardware = { Color = Color3.fromRGB(214, 216, 222), Material = "Metal", Reflectance = 0.35 },
			Strings = { Color = Color3.fromRGB(206, 206, 202), Material = "Metal", Reflectance = 0.30, Glow = true },
			Pickup = { Color = Color3.fromRGB(24, 24, 26), Material = "SmoothPlastic", Reflectance = 0.08 },
			Knob = { Color = Color3.fromRGB(214, 216, 222), Material = "SmoothPlastic", Reflectance = 0.12 },
			Body = { Color = Color3.fromRGB(210, 112, 36), Material = "SmoothPlastic", Reflectance = 0.12, Textured = true },
			Guard = { Color = Color3.fromRGB(120, 50, 22), Material = "SmoothPlastic", Reflectance = 0.08, Textured = true },
		},
	},
	Foundation = {
		kind = "Bass", name = "ファウンデーション", nameEn = "FOUNDATION", style = "PB タイプ",
		primary = "Foundation_Body",
		wear = Vector3.new(0.00054, 0.00008, -0.08036),
		neck = Vector3.new(0.00090, 1.49537, 0.12679),
		strum = Vector3.new(0.00090, -0.31409, 0.12679),
		palette = {
			Neck = { Color = Color3.fromRGB(232, 196, 140), Material = "Wood", Reflectance = 0.05 },
			Board = { Color = Color3.fromRGB(62, 36, 26), Material = "Wood", Reflectance = 0.00 },
			Frets = { Color = Color3.fromRGB(208, 206, 198), Material = "Metal", Reflectance = 0.30 },
			Inlay = { Color = Color3.fromRGB(240, 236, 226), Material = "SmoothPlastic", Reflectance = 0.20 },
			Nut = { Color = Color3.fromRGB(238, 230, 210), Material = "SmoothPlastic", Reflectance = 0.05 },
			Hardware = { Color = Color3.fromRGB(214, 216, 222), Material = "Metal", Reflectance = 0.35 },
			Strings = { Color = Color3.fromRGB(206, 206, 202), Material = "Metal", Reflectance = 0.30, Glow = true },
			Pickup = { Color = Color3.fromRGB(24, 24, 26), Material = "SmoothPlastic", Reflectance = 0.08 },
			Knob = { Color = Color3.fromRGB(214, 216, 222), Material = "SmoothPlastic", Reflectance = 0.12 },
			Body = { Color = Color3.fromRGB(236, 234, 220), Material = "SmoothPlastic", Reflectance = 0.12 },
			Guard = { Color = Color3.fromRGB(120, 50, 22), Material = "SmoothPlastic", Reflectance = 0.08, Textured = true },
		},
	},
	Manta = {
		kind = "Bass", name = "マンタ", nameEn = "MANTA", style = "SR タイプ",
		primary = "Manta_Body",
		wear = Vector3.new(0.00023, 0.00103, -0.08036),
		neck = Vector3.new(0.00029, 1.56875, 0.12679),
		strum = Vector3.new(0.00029, -0.24072, 0.12679),
		palette = {
			Neck = { Color = Color3.fromRGB(232, 196, 140), Material = "Wood", Reflectance = 0.05 },
			Board = { Color = Color3.fromRGB(228, 190, 132), Material = "Wood", Reflectance = 0.00 },
			Frets = { Color = Color3.fromRGB(208, 206, 198), Material = "Metal", Reflectance = 0.30 },
			Inlay = { Color = Color3.fromRGB(30, 26, 24), Material = "SmoothPlastic", Reflectance = 0.20 },
			Nut = { Color = Color3.fromRGB(238, 230, 210), Material = "SmoothPlastic", Reflectance = 0.05 },
			Hardware = { Color = Color3.fromRGB(214, 216, 222), Material = "Metal", Reflectance = 0.35 },
			Strings = { Color = Color3.fromRGB(206, 206, 202), Material = "Metal", Reflectance = 0.30, Glow = true },
			Pickup = { Color = Color3.fromRGB(24, 24, 26), Material = "SmoothPlastic", Reflectance = 0.08 },
			Knob = { Color = Color3.fromRGB(214, 216, 222), Material = "SmoothPlastic", Reflectance = 0.12 },
			Body = { Color = Color3.fromRGB(214, 176, 120), Material = "SmoothPlastic", Reflectance = 0.12, Textured = true },
			Guard = { Color = Color3.fromRGB(20, 20, 22), Material = "SmoothPlastic", Reflectance = 0.10 },
		},
	},
	Tempest = {
		kind = "Bass", name = "テンペスト", nameEn = "TEMPEST", style = "TB タイプ",
		primary = "Tempest_Body",
		wear = Vector3.new(0.01388, 0.00074, -0.07143),
		neck = Vector3.new(0.02311, 1.52534, 0.11429),
		strum = Vector3.new(0.02311, -0.28412, 0.11429),
		palette = {
			Neck = { Color = Color3.fromRGB(120, 66, 34), Material = "Wood", Reflectance = 0.05 },
			Board = { Color = Color3.fromRGB(62, 36, 26), Material = "Wood", Reflectance = 0.00 },
			Frets = { Color = Color3.fromRGB(208, 206, 198), Material = "Metal", Reflectance = 0.30 },
			Inlay = { Color = Color3.fromRGB(240, 236, 226), Material = "SmoothPlastic", Reflectance = 0.20 },
			Nut = { Color = Color3.fromRGB(238, 230, 210), Material = "SmoothPlastic", Reflectance = 0.05 },
			Hardware = { Color = Color3.fromRGB(214, 216, 222), Material = "Metal", Reflectance = 0.35 },
			Strings = { Color = Color3.fromRGB(206, 206, 202), Material = "Metal", Reflectance = 0.30, Glow = true },
			Pickup = { Color = Color3.fromRGB(24, 24, 26), Material = "SmoothPlastic", Reflectance = 0.08 },
			Knob = { Color = Color3.fromRGB(20, 20, 22), Material = "SmoothPlastic", Reflectance = 0.12 },
			Head = { Color = Color3.fromRGB(16, 14, 14), Material = "SmoothPlastic", Reflectance = 0.12 },
			Body = { Color = Color3.fromRGB(176, 104, 40), Material = "SmoothPlastic", Reflectance = 0.12, Textured = true },
		},
	},
	Crestwave = {
		kind = "Bass", name = "クレストウェーブ", nameEn = "CRESTWAVE", style = "RK タイプ",
		primary = "Crestwave_Body",
		wear = Vector3.new(0.00878, 0.00070, -0.06429),
		neck = Vector3.new(0.01457, 1.44054, 0.10357),
		strum = Vector3.new(0.01457, -0.32364, 0.10357),
		palette = {
			Neck = { Color = Color3.fromRGB(232, 196, 140), Material = "Wood", Reflectance = 0.05 },
			Board = { Color = Color3.fromRGB(62, 36, 26), Material = "Wood", Reflectance = 0.00 },
			Frets = { Color = Color3.fromRGB(208, 206, 198), Material = "Metal", Reflectance = 0.30 },
			Inlay = { Color = Color3.fromRGB(236, 232, 222), Material = "SmoothPlastic", Reflectance = 0.20 },
			Nut = { Color = Color3.fromRGB(238, 230, 210), Material = "SmoothPlastic", Reflectance = 0.05 },
			Hardware = { Color = Color3.fromRGB(214, 216, 222), Material = "Metal", Reflectance = 0.35 },
			Strings = { Color = Color3.fromRGB(206, 206, 202), Material = "Metal", Reflectance = 0.30, Glow = true },
			Pickup = { Color = Color3.fromRGB(24, 24, 26), Material = "SmoothPlastic", Reflectance = 0.08 },
			Knob = { Color = Color3.fromRGB(20, 20, 22), Material = "SmoothPlastic", Reflectance = 0.12 },
			Body = { Color = Color3.fromRGB(196, 32, 24), Material = "SmoothPlastic", Reflectance = 0.12, Textured = true },
			Binding = { Color = Color3.fromRGB(238, 232, 214), Material = "SmoothPlastic", Reflectance = 0.10 },
			Guard = { Color = Color3.fromRGB(244, 242, 236), Material = "SmoothPlastic", Reflectance = 0.06 },
		},
	},
}

local Selection = game:GetService("Selection")
local root = Selection:Get()[1] or workspace:FindFirstChild("BandInstruments")
assert(root, "読み込んだ楽器の Model (または BandInstruments フォルダ) を選択してから実行してください")

local SP = Enum.Material.SmoothPlastic
local function mat(name, fallback)
	local ok, m = pcall(function()
		return (Enum.Material :: any)[name]
	end)
	return if ok and m then m else fallback
end

local parts = {}
for _, p in ipairs(root:GetDescendants()) do
	if p:IsA("BasePart") then
		table.insert(parts, p)
	end
end

local folder = if root:IsA("Folder") and root.Name == "BandInstruments" then root else Instance.new("Folder")
folder.Name = "BandInstruments"
folder.Parent = root.Parent

local models = {}
local styled = 0
for _, p in ipairs(parts) do
	local id, key = p.Name:match("^(%w+)_(%w+)$")
	local info = id and INSTRUMENTS[id]
	if info then
		local look = info.palette[key]
		if look then
			-- textured parts keep the importer's image; the colour only shows where it is transparent
			local hasTexture = look.Textured and p:IsA("MeshPart") and p.TextureID ~= ""
			p.Color = if hasTexture then Color3.new(1, 1, 1) else look.Color
			p.Material = mat(look.Material, SP)
			p.Reflectance = look.Reflectance or 0
			p:SetAttribute("InstrumentGlow", look.Glow or nil)
			styled += 1
		end
		p.Anchored = true
		p.CanCollide = false
		p.CanTouch = false
		p.CanQuery = false
		p.Massless = true
		local model = models[id]
		if not model then
			local name = info.kind .. "_" .. id
			model = folder:FindFirstChild(name) or Instance.new("Model")
			model.Name = name
			model.Parent = folder
			models[id] = model
		end
		p.Parent = model
	end
end

local function attach(parent, name, pos, cf)
	local a = parent:FindFirstChild(name)
	if a then
		return a
	end
	a = Instance.new("Attachment")
	a.Name = name
	a.CFrame = cf or CFrame.new(pos)
	a.Parent = parent
	return a
end

for id, model in pairs(models) do
	local info = INSTRUMENTS[id]
	local primary = model:FindFirstChild(info.primary)
	assert(primary, "PrimaryPart が見つかりません: " .. info.primary)
	model.PrimaryPart = primary
	for _, p in ipairs(model:GetChildren()) do
		if p:IsA("BasePart") and p ~= primary then
			local w = p:FindFirstChild("InstrumentWeld") or Instance.new("WeldConstraint")
			w.Name = "InstrumentWeld"
			w.Part0 = primary
			w.Part1 = p
			w.Parent = p
		end
	end
	-- right = toward the end of the body, up = bass-string edge, look = the top of the instrument
	local wear = attach(primary, "Wear", nil,
		CFrame.fromMatrix(info.wear, Vector3.new(0, -1, 0), Vector3.new(-1, 0, 0)))
	attach(primary, "Neck", info.neck)
	attach(primary, "Strum", info.strum)
	model.WorldPivot = wear.WorldCFrame
	model:SetAttribute("InstrumentId", id)
	model:SetAttribute("Kind", info.kind)
	model:SetAttribute("DisplayName", info.name)
	model:SetAttribute("DisplayNameEn", info.nameEn)
	model:SetAttribute("Style", info.style)
end

if root ~= folder and #root:GetChildren() == 0 then
	root:Destroy()
end
Selection:Set({ folder })

local n = 0
for _ in pairs(models) do
	n += 1
end
print(("[BandInstrumentsSetup] 楽器 %d 本、%d パーツを設定しました"):format(n, styled))
