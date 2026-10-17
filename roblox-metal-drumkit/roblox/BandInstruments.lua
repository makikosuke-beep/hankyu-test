--[[
	BandInstruments - Beat Drummer のギター (5 本)・ベース (5 本) をキャラクターに構えさせる
	※ このファイルは generator/instruments.py が作っています。

	前提: export/instruments/BandInstruments_Setup.lua を実行してできたテンプレート
	      (Folder "BandInstruments" の中の Model "Guitar_<ID>" / "Bass_<ID>") を ReplicatedStorage などに入れておく。

	使い方:
		local BandInstruments = require(ReplicatedStorage.BeatDrummer.BandInstruments)
		local template = BandInstruments.template(ReplicatedStorage.BandInstruments, "Manta")

		-- サーバー: バンドのメンバー (またはプレイヤー) に構えさせる (全員に見える)
		BandInstruments.attach(character, template)
		BandInstruments.attach(character, template, { tilt = 22, offset = Vector3.new(0.3, -0.1, 0), scale = 0.9 })
		BandInstruments.detach(character)

		-- クライアント: ノーツに合わせて (見た目だけ)
		BandInstruments.strum(character, 1.0)    -- 楽器が少し揺れて弦が光る

	向き:
		体の正面のアタッチメント (R15 は LowerTorso の WaistFrontAttachment、R6 は Torso の BodyFrontAttachment)
		に楽器の Wear を合わせ、ネックがキャラクターの左へ伸びるように構えます。
		tilt (ネックを上げる角度、度)、offset (アタッチメントからのずれ、studs)、scale で調整してください。
		左手・右手の位置は楽器の Attachment "Neck" / "Strum" で取れます (腕の IK やアニメーションの目標に)。
]]

local TweenService = game:GetService("TweenService")

local BandInstruments = {}

-- 選べる楽器 (ショップや装備画面にそのまま並べられます)
BandInstruments.List = {
	{ id = "Skyline", kind = "Guitar", name = "スカイライン", nameEn = "SKYLINE", style = "ST タイプ",
	  desc = "3 トーンサンバーストに白いピックガード。シングルコイル 3 基とトレモロの、いちばん定番のシェイプ。" },
	{ id = "Prairie", kind = "Guitar", name = "プレーリー", nameEn = "PRAIRIE", style = "TL タイプ",
	  desc = "バタースコッチのアッシュに黒いピックガード、メイプル指板。アッシュトレイのブリッジが目印のシングルカット。" },
	{ id = "Heritage", kind = "Guitar", name = "ヘリテージ", nameEn = "HERITAGE", style = "LP タイプ",
	  desc = "チェリーサンバーストのトラ杢トップにクリームのバインディング。ハムバッカー 2 基のずっしりしたシングルカット。" },
	{ id = "CrimsonHorn", kind = "Guitar", name = "クリムゾンホーン", nameEn = "CRIMSON HORN", style = "SG タイプ",
	  desc = "チェリーレッドの薄いボディに尖った 2 本のホーンと深いベベル。大きな黒いピックガードの攻撃的な一本。" },
	{ id = "Valkyrie", kind = "Guitar", name = "ヴァルキリー", nameEn = "VALKYRIE", style = "V タイプ",
	  desc = "漆黒の V シェイプに白いピックガードと V 字のテールピース。メタルのステージ映えする変形ギター。" },
	{ id = "Velvet", kind = "Bass", name = "ヴェルヴェット", nameEn = "VELVET", style = "JB タイプ",
	  desc = "オフセットしたウエストにシングルコイル 2 基。3 トーンサンバーストとべっ甲柄ピックガードの細いネックのベース。" },
	{ id = "Foundation", kind = "Bass", name = "ファウンデーション", nameEn = "FOUNDATION", style = "PB タイプ",
	  desc = "オリンピックホワイトにべっ甲柄ピックガード。スプリットコイル 1 基と太めのネックの、ロックの土台になる一本。" },
	{ id = "Manta", kind = "Bass", name = "マンタ", nameEn = "MANTA", style = "SR タイプ",
	  desc = "丸いボディに大きなハムバッカー 1 基、3+1 のヘッドと丸いコントロールプレート。ナチュラルアッシュに黒いピックガード。" },
	{ id = "Tempest", kind = "Bass", name = "テンペスト", nameEn = "TEMPEST", style = "TB タイプ",
	  desc = "高音側のホーンが長く伸びたリバースボディ。タバコサンバーストにクロームのハムバッカー 2 基のスルーネック。" },
	{ id = "Crestwave", kind = "Bass", name = "クレストウェーブ", nameEn = "CRESTWAVE", style = "RK タイプ",
	  desc = "波頭のように巻いたホーンとバインディング。ファイアーグローの赤いボディに白い大きなピックガード、三角のインレイ。" },
}

-- 構えたときの角度・位置・大きさ。ゲームのキャラクターに合わせて調整
BandInstruments.Defaults = {
	tilt = 20, -- ネックを上げる角度 (度)
	offset = Vector3.new(0.3, 0, 0), -- R15: 腰の正面から右へ 0.3 studs
	offsetR6 = Vector3.new(0.3, -0.6, 0),
	scale = 1,
}

function BandInstruments.info(id: string)
	for _, item in ipairs(BandInstruments.List) do
		if item.id == id then
			return item
		end
	end
	return nil
end

function BandInstruments.template(folder: Instance, id: string): Model?
	local info = BandInstruments.info(id)
	local m = info and folder:FindFirstChild(info.kind .. "_" .. id)
	return if m and m:IsA("Model") then m else nil
end

function BandInstruments.get(character: Model): Model?
	local m = character:FindFirstChild("BandInstrument")
	return if m and m:IsA("Model") then m else nil
end

function BandInstruments.detach(character: Model)
	local m = BandInstruments.get(character)
	if m then
		m:Destroy()
	end
end

local function mount(character: Model): (BasePart?, CFrame, boolean)
	local lower = character:FindFirstChild("LowerTorso")
	if lower and lower:IsA("BasePart") then
		local a = lower:FindFirstChild("WaistFrontAttachment")
		return lower, if a and a:IsA("Attachment") then a.CFrame else CFrame.new(0, 0, -lower.Size.Z / 2), false
	end
	local torso = character:FindFirstChild("Torso") or character:FindFirstChild("UpperTorso")
	if torso and torso:IsA("BasePart") then
		local a = torso:FindFirstChild("BodyFrontAttachment")
		return torso, if a and a:IsA("Attachment") then a.CFrame else CFrame.new(0, 0, -torso.Size.Z / 2), true
	end
	return nil, CFrame.new(), false
end

-- 楽器を構えさせる。戻り値は楽器の Model
function BandInstruments.attach(character: Model, template: Model, options: { [string]: any }?)
	assert(template and template.PrimaryPart, "BandInstruments.attach: テンプレートに PrimaryPart がありません")
	local o = options or {}
	local part, base, r6 = mount(character)
	if not part then
		return nil
	end
	BandInstruments.detach(character)
	local inst = template:Clone()
	inst.Name = "BandInstrument"
	local scale = o.scale or BandInstruments.Defaults.scale
	if scale ~= 1 then
		inst:ScaleTo(inst:GetScale() * scale)
	end
	for _, p in ipairs(inst:GetDescendants()) do
		if p:IsA("BasePart") then
			p.Anchored = false
			p.CanCollide = false
			p.CanTouch = false
			p.CanQuery = false
			p.Massless = true
		end
	end
	local prim = inst.PrimaryPart :: BasePart
	local wear = prim:FindFirstChild("Wear") :: Attachment
	local offset = o.offset or (if r6 then BandInstruments.Defaults.offsetR6 else BandInstruments.Defaults.offset)
	local tilt = o.tilt or BandInstruments.Defaults.tilt
	local weld = Instance.new("Weld")
	weld.Name = "InstrumentWear"
	weld.Part0 = part
	weld.Part1 = prim
	weld.C0 = base * CFrame.new(offset) * CFrame.Angles(0, 0, -math.rad(tilt))
	weld.C1 = wear.CFrame
	weld.Parent = prim
	inst:SetAttribute("BaseC0", weld.C0)
	inst.Parent = character
	return inst
end

local tokens = setmetatable({}, { __mode = "k" })

-- ノーツに合わせて弾いた感じを出す (クライアントで呼ぶ)。strength 0〜1
function BandInstruments.strum(target: Instance?, strength: number?)
	local inst = if target and target:IsA("Model") and target:FindFirstChild("BandInstrument")
		then target:FindFirstChild("BandInstrument")
		else target
	if not inst then
		return
	end
	local k = math.clamp(strength or 1, 0, 1)
	local prim = (inst :: Model).PrimaryPart
	local weld = prim and prim:FindFirstChild("InstrumentWear")
	local baseC0 = inst:GetAttribute("BaseC0")
	if weld and weld:IsA("Weld") and typeof(baseC0) == "CFrame" then
		weld.C0 = baseC0 * CFrame.Angles(0, 0, math.rad(1.6 * k)) * CFrame.new(0, -0.025 * k, 0)
		TweenService:Create(weld, TweenInfo.new(0.22, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
			C0 = baseC0,
		}):Play()
	end
	for _, p in ipairs(inst:GetDescendants()) do
		if not (p:IsA("BasePart") and p:GetAttribute("InstrumentGlow")) then
			continue
		end
		local base = p:GetAttribute("BaseColor")
		if typeof(base) ~= "Color3" then
			base = p.Color
			p:SetAttribute("BaseColor", base)
		end
		local baseMat = p:GetAttribute("BaseMaterial")
		if type(baseMat) ~= "string" then
			baseMat = p.Material.Name
			p:SetAttribute("BaseMaterial", baseMat)
		end
		local token = (tokens[p] or 0) + 1
		tokens[p] = token
		p.Material = Enum.Material.Neon
		p.Color = (base :: Color3):Lerp(Color3.new(1, 1, 1), 0.6 * k)
		task.delay(0.08, function()
			if tokens[p] ~= token then
				return
			end
			TweenService:Create(p, TweenInfo.new(0.2, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
				Color = base,
			}):Play()
			task.delay(0.2, function()
				if tokens[p] == token then
					p.Material = (Enum.Material :: any)[baseMat]
					tokens[p] = nil
				end
			end)
		end)
	end
end

return BandInstruments
