--[[
	Beat Drummer 用スティック - Roblox Studio セットアップスクリプト

	使い方:
	  1. 3D インポーター (ホーム > 3D をインポート) で DrumSticks.fbx (または OBJ) を読み込む
	  2. エクスプローラーで読み込まれた Model を選択する
	  3. このファイルの中身をすべてコマンドバー (表示 > コマンドバー) に貼り付けて Enter

	やること:
	  - パーツ名 <デザイン>_<素材> (Sovereign_Wood など) から色・マテリアルを設定
	  - デザインごとに Model "Stick_<デザイン>" にまとめ、WeldConstraint でつなぐ
	  - PrimaryPart に Attachment "Grip" (持つ位置) と "Tip" (先端) を作る
	      Grip の LookVector がチップの方向、UpVector がロゴや飾りのある面
	      Model の WorldPivot も Grip の位置と向きにそろえる
	  - 当たり判定なし・Massless (手に付けて使う前提)。テンプレートの間は Anchored
	  - Model に属性 StickId / DisplayName / DisplayNameEn
	  - 全部を Folder "DrumSticks" に入れる (ReplicatedStorage などに移して使う)

	何度実行しても大丈夫です (2 回目以降は DrumSticks フォルダを選択して実行)。
]]

local STICKS = {
	Sovereign = {
		name = "ソブリン シグネチャー", nameEn = "SOVEREIGN Signature",
		primary = "Sovereign_Wood",
		grip = Vector3.new(0.00000, -0.28214, 0.00000),
		tip = Vector3.new(0.00000, 0.64643, 0.00000),
		palette = {
			Wood = { Color = Color3.fromRGB(190, 136, 74), Material = "Wood", Reflectance = 0.05 },
			Gold = { Color = Color3.fromRGB(214, 170, 72), Material = "Metal", Reflectance = 0.25 },
		},
	},
	IronStorm = {
		name = "アイアンストーム", nameEn = "IRON STORM",
		primary = "IronStorm_Gunmetal",
		grip = Vector3.new(0.00000, -0.19464, 0.00000),
		tip = Vector3.new(0.00000, 0.73393, 0.00000),
		palette = {
			Gunmetal = { Color = Color3.fromRGB(92, 96, 106), Material = "Metal", Reflectance = 0.20 },
			Rubber = { Color = Color3.fromRGB(24, 24, 27), Material = "Rubber", Reflectance = 0.00 },
			Accent = { Color = Color3.fromRGB(205, 18, 32), Material = "SmoothPlastic", Reflectance = 0.05, Glow = true },
			Nylon = { Color = Color3.fromRGB(18, 18, 20), Material = "SmoothPlastic", Reflectance = 0.10 },
			Chrome = { Color = Color3.fromRGB(214, 216, 222), Material = "Metal", Reflectance = 0.35 },
		},
	},
	SweetRibbon = {
		name = "スウィートリボン", nameEn = "SWEET RIBBON",
		primary = "SweetRibbon_Lacquer",
		grip = Vector3.new(0.00000, -0.20241, 0.00000),
		tip = Vector3.new(0.00000, 0.69808, 0.00000),
		palette = {
			Lacquer = { Color = Color3.fromRGB(255, 184, 208), Material = "SmoothPlastic", Reflectance = 0.08 },
			Stripe = { Color = Color3.fromRGB(255, 250, 252), Material = "SmoothPlastic", Reflectance = 0.05 },
			Ribbon = { Color = Color3.fromRGB(232, 72, 142), Material = "SmoothPlastic", Reflectance = 0.05 },
			Heart = { Color = Color3.fromRGB(236, 160, 150), Material = "Metal", Reflectance = 0.30, Glow = true },
			Pearl = { Color = Color3.fromRGB(252, 246, 244), Material = "SmoothPlastic", Reflectance = 0.25 },
		},
	},
	Starlight = {
		name = "スターライト", nameEn = "STARLIGHT",
		primary = "Starlight_Lacquer",
		grip = Vector3.new(0.00000, -0.21014, 0.00000),
		tip = Vector3.new(0.00000, 0.69036, 0.00000),
		palette = {
			Lacquer = { Color = Color3.fromRGB(196, 170, 255), Material = "SmoothPlastic", Reflectance = 0.08 },
			Gold = { Color = Color3.fromRGB(236, 196, 98), Material = "Metal", Reflectance = 0.25 },
			Star = { Color = Color3.fromRGB(255, 228, 128), Material = "SmoothPlastic", Reflectance = 0.20, Glow = true },
			Pearl = { Color = Color3.fromRGB(252, 248, 255), Material = "SmoothPlastic", Reflectance = 0.25 },
		},
	},
	Yozakura = {
		name = "夜桜", nameEn = "YOZAKURA",
		primary = "Yozakura_Lacquer",
		grip = Vector3.new(0.00000, -0.30750, 0.00000),
		tip = Vector3.new(0.00000, 0.62107, 0.00000),
		palette = {
			Lacquer = { Color = Color3.fromRGB(20, 17, 20), Material = "SmoothPlastic", Reflectance = 0.20 },
			Vermilion = { Color = Color3.fromRGB(182, 32, 26), Material = "SmoothPlastic", Reflectance = 0.15 },
			Gold = { Color = Color3.fromRGB(214, 170, 72), Material = "Metal", Reflectance = 0.25 },
			Petal = { Color = Color3.fromRGB(255, 184, 204), Material = "SmoothPlastic", Reflectance = 0.05, Glow = true },
		},
	},
	NeonPulse = {
		name = "ネオンパルス", nameEn = "NEON PULSE",
		primary = "NeonPulse_Glass",
		grip = Vector3.new(0.00000, -0.46786, 0.00000),
		tip = Vector3.new(0.00000, 0.46071, 0.00000),
		palette = {
			Glass = { Color = Color3.fromRGB(214, 240, 255), Material = "Glass", Reflectance = 0.10, Transparency = 0.55 },
			Neon = { Color = Color3.fromRGB(0, 228, 255), Material = "Neon", Reflectance = 0.00, Glow = true },
			Rubber = { Color = Color3.fromRGB(22, 22, 26), Material = "Rubber", Reflectance = 0.00 },
			Chrome = { Color = Color3.fromRGB(206, 210, 220), Material = "Metal", Reflectance = 0.35 },
		},
	},
}

local Selection = game:GetService("Selection")
local root = Selection:Get()[1] or workspace:FindFirstChild("DrumSticks")
assert(root, "読み込んだスティックの Model (または DrumSticks フォルダ) を選択してから実行してください")

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

local folder = if root:IsA("Folder") and root.Name == "DrumSticks" then root else Instance.new("Folder")
folder.Name = "DrumSticks"
folder.Parent = root.Parent

local models = {}
local styled = 0
for _, p in ipairs(parts) do
	local id, key = p.Name:match("^(%w+)_(%w+)$")
	local info = id and STICKS[id]
	if info then
		local look = info.palette[key]
		if look then
			p.Color = look.Color
			p.Material = mat(look.Material, SP)
			p.Reflectance = look.Reflectance or 0
			p.Transparency = look.Transparency or 0
			p:SetAttribute("StickGlow", look.Glow or nil)
			p:SetAttribute("BaseColor", look.Color)
			styled += 1
		end
		p.Anchored = true
		p.CanCollide = false
		p.CanTouch = false
		p.CanQuery = false
		p.Massless = true
		local model = models[id]
		if not model then
			model = folder:FindFirstChild("Stick_" .. id) or Instance.new("Model")
			model.Name = "Stick_" .. id
			model.Parent = folder
			models[id] = model
		end
		p.Parent = model
	end
end

for id, model in pairs(models) do
	local info = STICKS[id]
	local primary = model:FindFirstChild(info.primary)
	assert(primary, "PrimaryPart が見つかりません: " .. info.primary)
	model.PrimaryPart = primary
	for _, p in ipairs(model:GetChildren()) do
		if p:IsA("BasePart") and p ~= primary then
			local w = p:FindFirstChild("StickWeld") or Instance.new("WeldConstraint")
			w.Name = "StickWeld"
			w.Part0 = primary
			w.Part1 = p
			w.Parent = p
		end
	end
	-- the first run measures from the imported layout; later runs keep the attachments
	local grip = primary:FindFirstChild("Grip")
	if not grip then
		grip = Instance.new("Attachment")
		grip.Name = "Grip"
		grip.CFrame = CFrame.lookAt(info.grip, info.tip, Vector3.zAxis)
		grip.Parent = primary
		local tip = Instance.new("Attachment")
		tip.Name = "Tip"
		tip.CFrame = CFrame.lookAt(info.tip, info.tip + (info.tip - info.grip), Vector3.zAxis)
		tip.Parent = primary
	end
	model.WorldPivot = grip.WorldCFrame
	model:SetAttribute("StickId", id)
	model:SetAttribute("DisplayName", info.name)
	model:SetAttribute("DisplayNameEn", info.nameEn)
end

if root ~= folder and #root:GetChildren() == 0 then
	root:Destroy()
end
Selection:Set({ folder })

local n = 0
for _ in pairs(models) do
	n += 1
end
print(("[DrumSticksSetup] スティック %d 種、%d パーツを設定しました"):format(n, styled))
