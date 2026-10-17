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

local INSTRUMENTS = {} -- (filled in by instruments.py)

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
