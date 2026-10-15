--[[
	DrumKitFX - ノーツを叩いたときのドラムセットの動き (クライアント側の見た目だけ)

	前提: キットの Model に DrumKitSetup で Lane / PieceKind 属性と WorldPivot が設定済み。
	      (BeatDrummer_IronStorm_Setup.lua を一度実行しておく)

	使い方 (LocalScript から):
		local DrumKitFX = require(path.to.DrumKitFX)
		local fx = DrumKitFX.new(workspace.Stage.DrumKit)
		fx:hit("SN", 1.0)                 -- レーン名, 強さ 0〜1
		fx:hit("HH", 0.8, { open = true }) -- オープンハイハット
		fx:setHiHatOpen(false)            -- ハイハットを閉じる (ペダルを踏む)
		fx:destroy()                      -- キットを入れ替えるとき

	動き:
		cymbal       … 手前のふちが沈んで揺れ、だんだん収まる
		drum         … 叩いた方向に少し沈んで戻る + 一瞬光る
		kick         … ビーターが振られる (ツインペダルは左右交互) + 胴が少し揺れる
		hihat_top    … オープン時はトップが上がる / クローズ時は小さく揺れる
]]

local RunService = game:GetService("RunService")

export type Options = {
	flash: boolean?, -- ヘッドを光らせる (既定 true)
	flashColor: Color3?,
	intensity: number?, -- 全体の動きの大きさ (既定 1)
}

type Piece = {
	model: Model,
	kind: string,
	base: CFrame,
	t0: number,
	amp: number,
	open: number, -- ハイハットの開き具合 0〜1 (目標)
	openNow: number,
	head: BasePart?,
	light: PointLight?,
}

local DrumKitFX = {}
DrumKitFX.__index = DrumKitFX

local CYMBAL_TILT = math.rad(7) -- 最大の傾き
local CYMBAL_FREQ = 5.5 -- 揺れの速さ (Hz)
local CYMBAL_DECAY = 0.75 -- 収まるまでの時間の目安 (秒)
local DRUM_DIP = 0.035 -- 沈む量 (studs)
local DRUM_TIME = 0.12
local BEATER_SWING = math.rad(38)
local BEATER_TIME = 0.16
local HIHAT_OPEN = 0.13 -- トップが上がる量 (studs)

local function findHead(model: Model): BasePart?
	for _, d in ipairs(model:GetDescendants()) do
		if d:IsA("BasePart") and (d.Name:match("_HeadCoated$") or d.Name:match("_HeadLogo$")) then
			return d
		end
	end
	return nil
end

function DrumKitFX.new(kit: Instance, options: Options?)
	local self = setmetatable({}, DrumKitFX)
	self.options = options or {}
	self.lanes = {} :: { [string]: { Piece } }
	self.active = {} :: { [Piece]: boolean }
	self.beaterTurn = {} :: { [string]: number }
	for _, d in ipairs(kit:GetDescendants()) do
		if d:IsA("Model") and d:GetAttribute("Lane") then
			local lane = d:GetAttribute("Lane") :: string
			local piece: Piece = {
				model = d,
				kind = (d:GetAttribute("PieceKind") :: string?) or "drum",
				base = d:GetPivot(),
				t0 = -1,
				amp = 0,
				open = 0,
				openNow = 0,
				head = nil,
				light = nil,
			}
			if piece.kind == "drum" or piece.kind == "kick" then
				piece.head = findHead(d)
			end
			self.lanes[lane] = self.lanes[lane] or {}
			table.insert(self.lanes[lane], piece)
		end
	end
	self.conn = RunService.RenderStepped:Connect(function()
		self:_step(os.clock())
	end)
	return self
end

-- レーンに属するパーツ一覧 (デバッグ用)
function DrumKitFX:pieces(lane: string): { Piece }
	return self.lanes[lane] or {}
end

function DrumKitFX:_flash(piece: Piece, strength: number)
	if self.options.flash == false or not piece.head then
		return
	end
	local light = piece.light
	if not light then
		light = Instance.new("PointLight")
		light.Range = 6
		light.Shadows = false
		light.Color = self.options.flashColor or Color3.fromRGB(255, 70, 60)
		light.Parent = piece.head
		piece.light = light
	end
	light.Brightness = 3 * strength
end

function DrumKitFX:hit(lane: string, strength: number?, opts: { open: boolean? }?)
	local list = self.lanes[lane]
	if not list then
		return
	end
	local s = math.clamp(strength or 1, 0.05, 1) * (self.options.intensity or 1)
	local now = os.clock()
	-- ツインペダル: ビーターを左右交互に動かす
	local beaters = {}
	for _, p in ipairs(list) do
		if p.kind == "beater" then
			table.insert(beaters, p)
		end
	end
	local pick: Piece? = nil
	if #beaters > 0 then
		local n = (self.beaterTurn[lane] or 0) % #beaters + 1
		self.beaterTurn[lane] = n
		pick = beaters[n]
	end
	for _, p in ipairs(list) do
		if p.kind == "beater" and p ~= pick then
			continue
		end
		if p.kind == "hihat_bottom" then
			continue
		end
		if p.kind == "hihat_top" and opts and opts.open ~= nil then
			p.open = opts.open and 1 or 0
		end
		-- 揺れている最中に叩かれたら、残りの揺れに足し合わせる
		local left = 0
		if p.t0 >= 0 then
			left = p.amp * math.exp(-(now - p.t0) / CYMBAL_DECAY)
		end
		p.amp = math.min(1.4, left * 0.6 + s)
		p.t0 = now
		self.active[p] = true
		if p.kind == "drum" or p.kind == "kick" then
			self:_flash(p, s)
		end
	end
end

function DrumKitFX:setHiHatOpen(open: boolean, lane: string?)
	for _, p in ipairs(self.lanes[lane or "HH"] or {}) do
		if p.kind == "hihat_top" then
			p.open = open and 1 or 0
			self.active[p] = true
		end
	end
end

function DrumKitFX:_offset(p: Piece, now: number): (CFrame, boolean)
	local t = now - p.t0
	if p.kind == "cymbal" then
		if t > CYMBAL_DECAY * 5 then
			return CFrame.identity, false
		end
		local e = math.exp(-t / CYMBAL_DECAY)
		local w = 2 * math.pi * CYMBAL_FREQ
		local a = -CYMBAL_TILT * p.amp * e * math.cos(w * t)
		local b = CYMBAL_TILT * 0.35 * p.amp * e * math.sin(w * 0.73 * t)
		return CFrame.Angles(a, 0, b), true
	elseif p.kind == "drum" or p.kind == "kick" then
		if t > DRUM_TIME then
			return CFrame.identity, false
		end
		local k = math.sin(math.pi * t / DRUM_TIME)
		local d = (p.kind == "kick" and 0.5 or 1) * DRUM_DIP * p.amp * k
		return CFrame.new(0, -d, 0), true
	elseif p.kind == "beater" then
		if t > BEATER_TIME then
			return CFrame.identity, false
		end
		local x = t / BEATER_TIME
		local k = if x < 0.3 then x / 0.3 else 1 - (x - 0.3) / 0.7
		return CFrame.Angles(-BEATER_SWING * k * math.min(1, p.amp), 0, 0), true
	elseif p.kind == "hihat_top" then
		p.openNow += (p.open - p.openNow) * 0.35
		if math.abs(p.open - p.openNow) < 0.002 then
			p.openNow = p.open
		end
		local wob = 0
		if p.t0 >= 0 and t < 0.6 then
			wob = math.rad(2.5) * p.amp * math.exp(-t / 0.15) * math.cos(2 * math.pi * 9 * t)
		end
		local moving = math.abs(p.open - p.openNow) > 0.002 or (p.t0 >= 0 and t < 0.6)
		return CFrame.new(0, HIHAT_OPEN * p.openNow, 0) * CFrame.Angles(wob, 0, 0), moving
	end
	return CFrame.identity, false
end

function DrumKitFX:_step(now: number)
	for p in pairs(self.active) do
		local off, still = self:_offset(p, now)
		p.model:PivotTo(p.base * off)
		if p.light then
			p.light.Brightness = math.max(0, p.light.Brightness - 0.5)
		end
		if not still and not (p.light and p.light.Brightness > 0) then
			self.active[p] = nil
		end
	end
end

function DrumKitFX:destroy()
	if self.conn then
		self.conn:Disconnect()
		self.conn = nil
	end
	for _, list in pairs(self.lanes) do
		for _, p in ipairs(list) do
			if p.model.Parent then
				p.model:PivotTo(p.base)
			end
			if p.light then
				p.light:Destroy()
			end
		end
	end
	table.clear(self.active)
end

return DrumKitFX
