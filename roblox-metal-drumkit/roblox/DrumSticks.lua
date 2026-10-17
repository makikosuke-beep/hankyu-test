--[[
	DrumSticks - Beat Drummer のスティック (6 種) を手に持たせる・叩いたときに光らせる
	※ このファイルは generator/sticks.py が作っています。

	前提: export/sticks/DrumSticks_Setup.lua を実行してできたテンプレート
	      (Folder "DrumSticks" の中の Model "Stick_<ID>") を ReplicatedStorage などに入れておく。

	使い方:
		local DrumSticks = require(ReplicatedStorage.BeatDrummer.DrumSticks)
		local template = DrumSticks.template(ReplicatedStorage.DrumSticks, "SweetRibbon")

		-- サーバー: 演奏するキャラクターに持たせる (全員に見える)
		DrumSticks.attach(character, template)
		DrumSticks.attach(character, template, { tilt = -10, inward = 15, scale = 1.2 })
		DrumSticks.detach(character)

		-- クライアント: ノーツを叩いたとき (見た目だけ)
		DrumSticks.hitLane(character, "SR", 1.0)        -- レーンから叩く手を決めて光らせる
		DrumSticks.hit(DrumSticks.get(character, "Left"), 0.8)

		-- NEON PULSE の光の色を変える
		DrumSticks.setColor(character, DrumSticks.NeonColors.magenta)

	向き:
		スティックは手の GripAttachment の位置で握り、手の正面 (-Z。腕を下ろしたときの前方) に伸びます。
		ゲームの腕のアニメーションに合わせて tilt (上下の角度) と inward (内側への角度) を度で調整してください。
		ずっと同じ値を使うなら DrumSticks.Defaults を書き換えます。

	光る仕組み:
		セットアップで StickGlow 属性が付いたパーツ (飾り・ライン・光る芯) が、叩くと一瞬 Neon になって明るくなります。
]]

local TweenService = game:GetService("TweenService")

local DrumSticks = {}

-- 選べるスティック (ショップや装備画面にそのまま並べられます)
DrumSticks.List = {
	{ id = "Sovereign", name = "ソブリン シグネチャー", nameEn = "SOVEREIGN Signature", theme = "スタンダードの高級品",
	  desc = "厳選ヒッコリーの 5A。ゴールドディップのグリップエンドと金箔ロゴ、どんぐり型のウッドチップ。" },
	{ id = "IronStorm", name = "アイアンストーム", nameEn = "IRON STORM", theme = "メタル",
	  desc = "ガンメタルの合金シャフトに溝付きのラバーグリップ、真紅のライン、スパイク付きのクロームエンド。" },
	{ id = "SweetRibbon", name = "スウィートリボン", nameEn = "SWEET RIBBON", theme = "かわいい",
	  desc = "パステルピンクにキャンディのようなストライプ。エンドにはハート付きのリボン、チップはパール。" },
	{ id = "Starlight", name = "スターライト", nameEn = "STARLIGHT", theme = "ゆめかわ",
	  desc = "ラベンダーに金の星をちりばめた、魔法のステッキのような一本。エンドにはカットした大きな星。" },
	{ id = "Yozakura", name = "夜桜", nameEn = "YOZAKURA", theme = "和モダン",
	  desc = "黒漆に朱のグリップエンドと金の輪。夜に舞う桜の花びらをあしらった和の一本。" },
	{ id = "NeonPulse", name = "ネオンパルス", nameEn = "NEON PULSE", theme = "光る",
	  desc = "透明なシャフトの芯が光るライトアップスティック。叩くたびにフラッシュ。光の色は変えられます。" },
}

-- NEON PULSE の光の色
DrumSticks.NeonColors = {
	cyan = Color3.fromRGB(0, 228, 255),
	magenta = Color3.fromRGB(255, 40, 200),
	lime = Color3.fromRGB(120, 255, 40),
	orange = Color3.fromRGB(255, 130, 20),
	white = Color3.fromRGB(235, 245, 255),
}

-- 手の中での向き (度) と大きさ。ゲームの腕のアニメーションに合わせて調整
DrumSticks.Defaults = { tilt = 0, inward = 0, scale = 1 }

-- レーン -> 叩く手 (BD は足なので無し)。ゲームの持ち手に合わせて変えてください
DrumSticks.HandForLane = {
	HH = "Right", CY = "Left", CR = "Left", SL = "Left", SR = "Right", SN = "Right",
	HT = "Left", LT = "Right", FT = "Right", RD = "Right",
}

local SIDES = { "Right", "Left" }
local HAND_PARTS = {
	Right = { "RightHand", "Right Arm" },
	Left = { "LeftHand", "Left Arm" },
}

function DrumSticks.info(id: string)
	for _, item in ipairs(DrumSticks.List) do
		if item.id == id then
			return item
		end
	end
	return nil
end

function DrumSticks.template(folder: Instance, id: string): Model?
	local m = folder:FindFirstChild("Stick_" .. id)
	return if m and m:IsA("Model") then m else nil
end

local function handOf(character: Model, side: string): BasePart?
	for _, name in ipairs(HAND_PARTS[side]) do
		local h = character:FindFirstChild(name)
		if h and h:IsA("BasePart") then
			return h
		end
	end
	return nil
end

function DrumSticks.get(character: Model, side: string): Model?
	local s = character:FindFirstChild("DrumStick_" .. side)
	return if s and s:IsA("Model") then s else nil
end

function DrumSticks.detach(character: Model)
	for _, side in ipairs(SIDES) do
		local s = DrumSticks.get(character, side)
		if s then
			s:Destroy()
		end
	end
end

-- 両手にスティックを持たせる。戻り値 { Right = Model, Left = Model }
function DrumSticks.attach(character: Model, template: Model, options: { [string]: number }?)
	assert(template and template.PrimaryPart, "DrumSticks.attach: テンプレートに PrimaryPart がありません")
	local o = options or {}
	local tilt = o.tilt or DrumSticks.Defaults.tilt
	local inward = o.inward or DrumSticks.Defaults.inward
	local scale = o.scale or DrumSticks.Defaults.scale
	DrumSticks.detach(character)
	local out = {}
	for _, side in ipairs(SIDES) do
		local hand = handOf(character, side)
		if not hand then
			continue
		end
		local stick = template:Clone()
		stick.Name = "DrumStick_" .. side
		if scale ~= 1 then
			stick:ScaleTo(stick:GetScale() * scale)
		end
		for _, p in ipairs(stick:GetDescendants()) do
			if p:IsA("BasePart") then
				p.Anchored = false
				p.CanCollide = false
				p.CanTouch = false
				p.CanQuery = false
				p.Massless = true
			end
		end
		local prim = stick.PrimaryPart :: BasePart
		local grip = prim:FindFirstChild("Grip") :: Attachment
		local handGrip = hand:FindFirstChild(side .. "GripAttachment")
		local pos = if handGrip and handGrip:IsA("Attachment")
			then handGrip.Position
			else Vector3.new(0, -hand.Size.Y * 0.4, 0)
		local yaw = math.rad(if side == "Right" then inward else -inward)
		local weld = Instance.new("Weld")
		weld.Name = "StickGrip"
		weld.Part0 = hand
		weld.Part1 = prim
		weld.C0 = CFrame.new(pos) * CFrame.Angles(0, yaw, 0) * CFrame.Angles(math.rad(tilt), 0, 0)
		weld.C1 = grip.CFrame
		weld.Parent = prim
		stick:SetAttribute("Side", side)
		stick.Parent = character
		out[side] = stick
	end
	return out
end

local tokens = setmetatable({}, { __mode = "k" })

-- 叩いたときの光 (クライアントで呼ぶ)。strength 0〜1
function DrumSticks.hit(stick: Model?, strength: number?)
	if not stick then
		return
	end
	local k = math.clamp(strength or 1, 0, 1)
	for _, p in ipairs(stick:GetDescendants()) do
		if not (p:IsA("BasePart") and p:GetAttribute("StickGlow")) then
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
		p.Color = (base :: Color3):Lerp(Color3.new(1, 1, 1), 0.5 * k)
		task.delay(0.06, function()
			if tokens[p] ~= token then
				return
			end
			TweenService:Create(p, TweenInfo.new(0.25, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), {
				Color = base,
			}):Play()
			task.delay(0.25, function()
				if tokens[p] == token then
					p.Material = (Enum.Material :: any)[baseMat]
					tokens[p] = nil
				end
			end)
		end)
	end
end

function DrumSticks.hitLane(character: Model, lane: string, strength: number?)
	local side = DrumSticks.HandForLane[lane]
	if side then
		DrumSticks.hit(DrumSticks.get(character, side), strength)
	end
end

-- 光る芯 (*_Neon パーツ) の色を変える。character でもスティック 1 本でも可
function DrumSticks.setColor(target: Instance, color: Color3)
	for _, p in ipairs(target:GetDescendants()) do
		if p:IsA("BasePart") and p.Name:match("_Neon$") then
			p.Color = color
			p:SetAttribute("BaseColor", color)
		end
	end
end

return DrumSticks
