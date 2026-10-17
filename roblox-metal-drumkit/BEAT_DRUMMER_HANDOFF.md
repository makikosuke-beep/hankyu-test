# Beat Drummer への組み込み手順（PC の Claude Code 向け）

このドキュメントは、Roblox Studio MCP がつながった PC 側の Claude Code が読む前提で書いています。
目的は、次の 2 つのドラムセットを Beat Drummer に入れることです。どちらも、ゲーム内のお金または Robux で買うと、
今のドラムセットと入れ替えられるキット（スキン）にします。

| キット | KitId | イメージ |
| --- | --- | --- |
| **IRON STORM** | `IronStorm` | メタル仕様。ツインペダル、カーブラック、ブラック × 差し色、ブリリアントシンバル |
| **SOVEREIGN** | `Sovereign` | スタンダードの最高峰。杢目の突板（トラ杢メイプルなど）、ゴールド金物、ビーバーテイルのラグ、ダイキャストフープ、スタンド配置、槌目シンバル |

2 つとも同じ仕組み（同じレーン、同じセットアップ、同じ DrumKitFX / DrumKitStyles）で動きます。
先に IRON STORM で一通り組み込み、その後 SOVEREIGN を同じ手順で足すと楽です。

あわせて、キットとは別に選べる**スティック 6 種**（`DrumSticks`、手順 10）と、
バンドのメンバーが構える**ギター 5 本・ベース 5 本**（`BandInstruments`、手順 11）も入れます。

## ゴール

1. 各キットを、**今のドラムセットと同じ構成**（同じレーン・同じ数のタムとシンバル）で、ステージ上の今のキットと差し替えられるようにする
2. ノーツを叩いたときに、キットが動くようにする（シンバルの揺れ、ビーター、ハイハットの開閉、ヘッドの発光）
3. **音は今のキットと変える**（キットごとに専用のサウンドセット）
4. ゲーム内のお金と Robux のどちらかで買えるようにし、持っている人だけが装備を切り替えられるようにする
5. スマホでも重くならないこと（IRON STORM は 63,456 ポリゴン / MeshPart 83 個、SOVEREIGN は 70,464 ポリゴン / MeshPart 69 個）
6. **色と模様を選べるようにする**（キットごとにシェルの色 10 種 × 模様 7 種、差し色・金物・シンバル・ヘッドも選べる。おすすめの組み合わせ 8 種）
7. **スティックを選べるようにする**（6 種。キットとは別に買って装備し、演奏するキャラクターの両手に持たせる。叩くと飾りや芯が光る）
8. **バンドのギターとベースを入れる**（ギター 5 本・ベース 5 本。代表的なモデルの形。メンバーに構えさせ、ノーツに合わせて揺らす）

## 素材の場所

GitHub（公開）: <https://github.com/makikosuke-beep/hankyu-test/tree/claude/metal-drumkit/roblox-metal-drumkit>

```
git clone -b claude/metal-drumkit https://github.com/makikosuke-beep/hankyu-test.git
```

| ファイル | 内容 |
| --- | --- |
| `export/beatdrummer/BeatDrummer_IronStorm.fbx` | Beat Drummer 用モデル（studs 単位、ロゴ画像を埋め込み済み） |
| `export/beatdrummer/BeatDrummer_IronStorm.obj` + `.mtl` + `kick_logo.png` | 同じモデルの OBJ 版 |
| `export/beatdrummer/BeatDrummer_IronStorm_Setup.lua` | 読み込み後に 1 回実行するセットアップ（色・整理・Lane 属性・回転の中心） |
| `export/beatdrummer/BeatDrummer_IronStorm_lanes.json` | 各パーツのレーンと回転の中心のデータ |
| `export/sovereign/BeatDrummer_Sovereign.fbx` | SOVEREIGN のモデル（studs 単位、ロゴ画像を埋め込み済み） |
| `export/sovereign/BeatDrummer_Sovereign.obj` + `.mtl` + `sovereign_logo.png` | 同じモデルの OBJ 版 |
| `export/sovereign/BeatDrummer_Sovereign_Setup.lua` | SOVEREIGN のセットアップ（色・整理・Lane 属性・回転の中心・KitId） |
| `export/sovereign/BeatDrummer_Sovereign_lanes.json` | SOVEREIGN の各パーツのレーンと回転の中心のデータ |
| `roblox/DrumKitFX.lua` | 叩いたときの動きを付ける ModuleScript（クライアント用。どのキットでも共通） |
| `roblox/DrumKitStyles.lua` | 色・模様を切り替える ModuleScript（両キットの選択肢とプリセットの一覧もここ） |
| `export/styles/pattern_*.png`（6 枚）と `logo_overlay.png` | IRON STORM の模様とロゴの画像。Roblox にアップロードして使う |
| `export/styles/sovereign/pattern_*.png`（6 枚）と `logo_overlay.png` | SOVEREIGN の杢目とロゴの画像。同じくアップロードして使う |
| `preview/beatdrummer/styles_lineup.jpg` / `preview/sovereign/styles_lineup.jpg` | 各キットのプリセット 8 種を並べた画像 |
| `generator/specs/beatdrummer_spec.json` / `sovereign_spec.json` | キット構成の設定ファイル（ここを直して再生成できる） |
| `generator/styles_catalog.json` | 色・模様の選択肢の元データ（`make_styles_lua.py` で `DrumKitStyles.lua` を作り直す） |
| `export/sticks/` と `roblox/DrumSticks.lua` | スティック 6 種（手順 10） |
| `export/instruments/` と `roblox/BandInstruments.lua` | ギター 5 本・ベース 5 本（手順 11） |
| `generator/kitspec.py` | 設定ファイルからモデルを作るスクリプト |

### 今のモデルの構成

今のキットと同じ、タム 3 つ（HT・LT・FT）の構成です。画面のキー（HH・CY・SL・SR・BD・HT・LT・FT・RD）に合わせています。
並びも今のキットと同じで、ドラマーから見て左にハイハットとクラッシュ、バスドラムの上にハイタムとロータム、右にフロアタムとライドがあります。

| 画面のキー | Lane 属性（譜面の記号） | パーツ（Model 名） | 種類 | 大きさ |
| --- | --- | --- | --- | --- |
| HH | HH | `HH_Top` / `HH_Bottom` | ハイハット | 14" |
| CY | CR | `CR_Crash` | クラッシュ | 18" |
| SL / SR | SN | `SN_Snare` | スネア（左右の手で同じスネア） | 14" × 6.5" |
| BD | BD | `BD_Kick` ＋ ビーター 2 本（`Pedal_Main_BeaterR` / `Pedal_Main_BeaterL`） | バスドラム（ツインペダル） | 22" × 18" |
| HT | HT | `HT_Tom` | ハイタム | 10" × 8" |
| LT | LT | `LT_Tom` | ロータム | 12" × 9" |
| FT | FT | `FT_FloorTom` | フロアタム | 16" × 16" |
| RD | RD | `RD_Ride` | ライド | 22" |

- Lane 属性には、譜面データで使われている記号（CR・SN）を入れています。
  ゲームの中でクラッシュを `CY`、スネアを `SL` / `SR` と呼んでいる場合も、DrumKitFX はどちらの名前でも動きます
- ゲーム側のコードが別の記号を使っている場合は、`specs/beatdrummer_spec.json` の `lane` を直して作り直すか、DrumKitFX の `ALIASES` に対応を足してください
- ラック、スタンド、スローン、ラグは演奏しない飾り（Hardware）です
- **SOVEREIGN** も同じ 9 キー・同じ Model 名・同じ位置です。違いは次のとおりです
  - シングルペダルなので、BD のビーターは `Pedal_BD_Kick_Beater` の 1 本です（DrumKitFX は自動で対応します）
  - ラックの代わりに、シンバルはブームスタンド、タムはバスドラム上のタムホルダーで支えています。
    スタンドの脚が広がるぶん、全体は **幅 9.3 × 高さ 5.1 × 奥行き 7.2 studs** と IRON STORM より少し広くなります
  - バスドラムの前面は穴なしのロゴヘッド（エンブレム）です

## 手順

### 1. 今のキットを調べる（変更はしない）

Studio MCP で、次のことを調べてユーザーに報告してください。

- 今のドラムセットの場所とインスタンス構成（Model 名、パーツ名、どのパーツがどのレーンか）
- 各パーツの位置と大きさ（キットの中心、スネア・ハイハット・タム・シンバルの位置。studs）
- 今のキットを動かしたり光らせたりしているコード（`BandSetup`、`BandMotion`、`BeatDrummerClient` など）と、パーツを名前で参照している箇所
- 叩いたときの音の鳴らし方（レーンごとの SoundId の表がどこにあるか）
- カメラやノーツの表示が、ドラムのパーツの位置に依存しているか

### 2. 構成を合わせる

上の表と、今のキットの構成が違う場合（タムが 2 つある、クラッシュが 2 枚、チャイナがあるなど）は、
`generator/specs/beatdrummer_spec.json` を直して作り直します。

- `pieces` に 1 パーツずつ書きます。`lane` には譜面のレーン記号（例 `MT`、`CR2`、`CH`）を入れます
- `type` は `kick` / `snare` / `hihat` / `tom` / `floortom` / `crash` / `ride` / `china` / `splash` のどれかです
- `pos` は **studs**、キットの中での位置です。向きは、右手側が +X、上が +Y で、ドラマーは −Z を向きます。
  今のキットのパーツの位置に合わせてください
- 太鼓の `pos` は胴の中心、シンバルの `pos` は中心の穴の位置です。ハイハットの `pos` の Y は、ボトムのシンバルの高さです
- 今のキットが現実より大きい（または小さい）ときは、`scale` で全体の大きさを変えられます
- 細かさは `detail` で決まります。今は 0.5（約 6.3 万ポリゴン）です。下げると軽くなります

作り直すコマンドです（作成時は Linux の Python 3.13 で確認済み。Windows では未確認です）。
FBX を作るには Blender が別に必要ですが、Roblox への読み込みは OBJ で十分です。

```
pip install numpy scipy shapely trimesh mapbox_earcut pillow
cd roblox-metal-drumkit/generator
python kitspec.py specs/beatdrummer_spec.json --out ../export/beatdrummer
```

`BeatDrummer_IronStorm.obj` と `BeatDrummer_IronStorm_Setup.lua` が作り直されます。
SOVEREIGN は `python kitspec.py specs/sovereign_spec.json --out ../export/sovereign` です。
2 つのキットの位置をそろえたいときは、両方の spec の `pieces` の `pos` を同じように直してください。

### 3. Studio に読み込む（ユーザーの手作業）

3D インポーターは MCP から操作できないので、ユーザーにお願いします。

1. ホーム ＞ 3D をインポート で `BeatDrummer_IronStorm.fbx`（または OBJ）を選ぶ
2. 大きさがおよそ **幅 7.1 × 高さ 5.1 × 奥行き 6.6 studs**（ラグ込み）になっているか確認する。
   違う場合は、インポート設定の File Dimensions を Studs にする
3. 読み込んだ Model の名前を `BeatDrummer_IronStorm` にする
4. SOVEREIGN も同じように `export/sovereign/BeatDrummer_Sovereign.fbx` を読み込み、名前を `BeatDrummer_Sovereign` にする
   （大きさは **幅 9.3 × 高さ 5.1 × 奥行き 7.2 studs**）

### 4. セットアップを実行する

`BeatDrummer_IronStorm_Setup.lua` の中身を `execute_luau` で実行します（SOVEREIGN は `BeatDrummer_Sovereign_Setup.lua`）。
このスクリプトは、選択中の Model か `workspace.BeatDrummer_IronStorm`（SOVEREIGN は `workspace.BeatDrummer_Sovereign`）を対象にします。
MCP から実行するときは、先頭近くの `local root = ...` の行を、対象の Model を直接指すように書き換えてください。

実行すると、次のように設定されます。

- 各パーツの Model に `Lane`（BD など）と `PieceKind`（drum / kick / beater / cymbal / hihat_top / hihat_bottom）の属性が付く
- 各パーツの Model の `WorldPivot` が、回転の中心に設定される（シンバルは中心の穴、ビーターは軸、ハイハットのトップはクラッチ）
- 色・マテリアルの設定。すべて Anchored にし、当たり判定はラグだけにする
- スローンに `DrummerSeat` を追加する。ゲーム側で不要なら消してください
- キットの Model に `DrumKit = true` と `KitId`（`IronStorm` / `Sovereign`）の属性が付く。DrumKitStyles はこの KitId でキットを見分けます

最後に、テンプレートとして ServerStorage（または ReplicatedStorage）の `DrumKits` フォルダなどにしまいます。

### 5. 今のキットと入れ替えられるようにする

- 今のキットもテンプレート化して（例 `DrumKits.Standard`）、**装備中のキットを複製してステージの決まった CFrame に置く**仕組みにします
- 位置合わせ: 新しいキットはドラマーが −Z を向く向きで作ってあります。今のキットの「スローン位置」と「スネア位置」がそろうように、`PivotTo` で置いてください
- ゲームのコードがパーツを名前で探している箇所は、`Lane` 属性で探すように変えると、どのキットでも同じコードで動きます
- 最初は今のキットを既定のままにして、IRON STORM と SOVEREIGN が問題なく動くことを確かめてから切り替えの UI を出してください
- 2 つのキットはスネアとスローンの位置が同じなので、同じ CFrame に置けば入れ替えても叩く位置はずれません

### 6. 叩いたときの動き（DrumKitFX）

`roblox/DrumKitFX.lua` を ReplicatedStorage の BeatDrummer の下などに ModuleScript として入れ、クライアントから使います。

```lua
local DrumKitFX = require(ReplicatedStorage.BeatDrummer.DrumKitFX)
local fx = DrumKitFX.new(currentKitModel)        -- キットを入れ替えたら fx:destroy() して作り直す

-- ノーツを叩いたとき（判定が出たとき、オートプレイも含む）
fx:hit(lane, strength)                           -- lane = "BD" など（"CY" "SL" "SR" も可）、strength = 0〜1
fx:hit("HH", 0.8, { open = true })               -- 譜面の HH の "o"（オープン）
fx:hit("HH", 0.8, { open = false })              -- クローズ
fx:setHiHatOpen(false)                           -- ペダルで閉じる
```

- 動きは見た目だけで、各パーツの Model を `PivotTo` で動かします。サーバーには関係しません
- ツインペダル（IRON STORM）は、BD を叩くたびに左右のビーターが交互に動きます。シングルペダル（SOVEREIGN）は 1 本が毎回動きます
- 太鼓は叩くと一瞬光ります（PointLight）。重い場合は `DrumKitFX.new(kit, { flash = false })` にしてください
- 他のプレイヤーのキットも動かす場合は、そのプレイヤーのクライアントから届く演奏イベントで同じ `fx:hit` を呼びます

### 7. 音をキット専用にする

- キットごとのサウンドセットの表を作り、装備中のキットの `KitId` 属性で表を選んで鳴らします

  ```lua
  KitSounds.IronStorm = { BD = "rbxassetid://...", SN = "...", HH = { closed = "...", open = "..." },
                          HT = "...", LT = "...", FT = "...", CR = "...", RD = "..." }
  KitSounds.Sovereign = { ... }   -- 同じ形
  local sounds = KitSounds[kitModel:GetAttribute("KitId")] or KitSounds.Standard
  ```
- 音そのものは、**ユーザーと一緒に選んでください**（Creator Store の音源、またはユーザーが用意した音を Roblox にアップロード）。
  - IRON STORM（メタル）の方向性の例: アタックの強いクリック感のあるキック、高めにチューニングしたスネア、
    派手で少し汚れたクラッシュ、ベルの鳴りが目立つライド
  - SOVEREIGN（スタンダードの最高峰）の方向性の例: 胴鳴りが豊かで丸いキック、太くて芯のあるウッドスネア、
    よく伸びる温かいタム、ダークで上品な響きのクラッシュとライド（ジャズ〜ポップス〜ロックまで合う、録音スタジオの生ドラムの音）
- 推測した SoundId は入れないでください。実際に Studio で鳴ることを確かめてから入れてください

### 8. 購入と装備

- **ゲーム内のお金**: 購入はサーバーで処理します（残高を確認 → 引く → 持ち物に追加 → DataStore に保存）
- **Robux**: ずっと持っておくアイテムなので、GamePass（`MarketplaceService:PromptGamePassPurchase`、
  `UserOwnsGamePassAsync` で確認）が簡単です。DevProduct にする場合は `ProcessReceipt` で持ち物に追加して保存します
- 装備中のキットも DataStore に保存し、次に入ったときに同じキットが出るようにします
- 持っているかどうかは必ずサーバーで確認し、クライアントから送られた内容だけで装備させないでください
- GamePass の作成と価格設定はユーザーが Creator Dashboard で行います

### 9. 色と模様を選べるようにする（DrumKitStyles）

`roblox/DrumKitStyles.lua` を ModuleScript として ReplicatedStorage に入れます（サーバーとクライアントの両方から使います）。

**仕組み**

- 1 つのモジュールに両キットの選択肢が入っています。`Styles.apply` はキットの Model の `KitId` 属性を見て、そのキットの選択肢を使います
- 選択肢の数や名前はキットごとに違います（IRON STORM はスパークルやファイヤーなど、SOVEREIGN はトラ杢メイプル・バーズアイ・バール・キルト・マッカーサーなどの杢目）

- シェルのパーツ（`*_Finish`）の `TextureID` に模様の画像を入れ、`Color` にシェルの色を入れます。
  画像の透明な部分にシェルの色が見えるので、模様 1 枚でどの色とも組み合わせられます
- ロゴ（`*_HeadLogo`）も同じ仕組みで、エンブレムと文字のふちが差し色になります
- 差し色はピンストライプ、バスドラムのフープのライン、フェルトにも使われます
- 金物（クローム / ブラックニッケル / ゴールド）、シンバル（ブリリアント / ダーク / ブラック）、打面のヘッド（ホワイト / ブラック）も切り替えられます
  （SOVEREIGN のシンバルはトラディショナル / ダーク / ブリリアント）
- SOVEREIGN は、模様によってフープの色が変わります（シェルと同じ色、シェルより濃い色、黒）。フェルトは黒のままです

**準備（画像のアップロードはユーザーの手作業）**

1. 次の 14 枚を、Studio のアセットマネージャー（一括インポート）か Creator Dashboard でアップロードしてもらう
   - IRON STORM: `export/styles/` の `pattern_sparkle.png` / `pattern_flames.png` / `pattern_tiger.png` / `pattern_carbon.png` /
     `pattern_burst.png` / `pattern_lightning.png` / `logo_overlay.png`
   - SOVEREIGN: `export/styles/sovereign/` の `pattern_flame.png` / `pattern_birdseye.png` / `pattern_burl.png` / `pattern_quilt.png` /
     `pattern_stripe.png` / `pattern_flameburst.png` / `logo_overlay.png`
   - 2 つの `logo_overlay.png` は別の画像です。フォルダ名を付けるなどして取り違えないようにしてください
2. 出てきた画像の ID を、`DrumKitStyles.lua` の先頭の `Styles.TEXTURES` に `"rbxassetid://…"` の形で入れる。
   キットごとに分かれています（`Styles.TEXTURES.IronStorm.flames`、`Styles.TEXTURES.Sovereign.flame` など）。
   ID が空の模様はソリッド（単色）で表示されるので、途中の状態でも壊れません

**ゲームへの組み込み**

```lua
local Styles = require(ReplicatedStorage.BeatDrummer.DrumKitStyles)

-- サーバー: キットを置いたとき・見た目を変えたときに反映 (全員に同じ見た目が見える)
local kitId = Styles.kitOf(kitModel)                    -- KitId 属性 ("IronStorm" / "Sovereign")
Styles.apply(kitModel, Styles.decode(savedStyleString, kitId))

-- 保存 (DataStore には文字列 1 つ。キットごとに別々に保存する)
local text = Styles.encode(style, kitId)   -- 例 "orange/flames/orange/black/dark/black"、"amber/flame/gold/gold/traditional/coated"
Styles.apply(kitModel, Styles.preset("sovereign", "Sovereign"))   -- プリセットを使う
```

- 選ぶ画面（ショップや装備画面）では、`Styles.catalog(kitId)` の `Presets`（おすすめ 8 種）と、各項目の一覧
  （`Colors` / `Patterns` / `Accents` / `Hardware` / `Cymbals` / `Heads`）をそのまま並べられます。
  各項目に日本語名（`name`）と英語名（`nameEn`）が入っています
- `encode` / `decode` / `normalize` / `preset` は、最後の引数に `kitId` を渡します（省くと IRON STORM 扱い）。
  保存した文字列はキットごとに違うので、DataStore には `{ IronStorm = "...", Sovereign = "..." }` のようにキット別に保存してください
- クライアントから届いた選択は、サーバーで `Styles.normalize(style, kitId)` を通してから使ってください（知らない値は既定値に置き換わります）
- 模様ごとに販売する場合は、`Styles.catalog(kitId).Patterns` の `id` を商品として扱い、持っていない模様を選べないようにサーバーで確認します
- 見た目のイメージは `preview/beatdrummer/styles_lineup.jpg`、`preview/sovereign/styles_lineup.jpg` と、ユーザーに渡した 3D プレビューで確認できます

### 10. スティック（DrumSticks）

キットとは別の商品です。どのキットとも組み合わせられます。

| ID | 名前 | テーマ | 特徴 | ポリゴン（1 本） |
| --- | --- | --- | --- | --- |
| `Sovereign` | ソブリン シグネチャー | スタンダードの高級品 | ヒッコリー 5A、ゴールドディップのエンド、金箔ロゴ、どんぐり型チップ | 1,720 |
| `IronStorm` | アイアンストーム | メタル | ガンメタル合金、溝付きラバーグリップ、赤いライン、スパイク付きクロームエンド | 3,756 |
| `SweetRibbon` | スウィートリボン | かわいい | パステルピンク、キャンディストライプ、ハート付きリボン、パールのボールチップ | 4,012 |
| `Starlight` | スターライト | ゆめかわ | ラベンダー、金の星、エンドにカットした大きな星 | 2,576 |
| `Yozakura` | 夜桜 | 和モダン | 黒漆、朱のエンド、金の輪、桜の花びら、縦書きの「夜桜」 | 4,116 |
| `NeonPulse` | ネオンパルス | 光る | 透明なシャフトの芯が光る（色は 5 色から）、溝付きグリップ | 2,928 |

**素材**

| ファイル | 内容 |
| --- | --- |
| `export/sticks/DrumSticks.fbx` | 6 種が 1 列に並んだモデル（studs 単位、ロゴ画像を埋め込み済み）。OBJ 版もあり |
| `export/sticks/DrumSticks_Setup.lua` | 読み込み後に 1 回実行するセットアップ |
| `roblox/DrumSticks.lua` | 手に持たせる・叩いたときに光らせる ModuleScript（一覧 `DrumSticks.List` もここ） |
| `export/sticks/logos/stick_*.png` | 各スティックのロゴ。FBX に入っているので通常はアップロード不要 |
| `preview/sticks/` | 並べた画像、グリップエンドとチップ、ロゴのアップ |

**手順**

1. **今のスティックを調べる（変更はしない）**。演奏するキャラクターがスティックを持っているか、持っているならどのパーツ・どの Weld で手に付いているか。
   叩くときの腕の動き（Animation や Motor6D の操作）をどこで再生しているか。キャラクターが R15 か R6 か。結果をユーザーに報告する
2. **読み込む（ユーザーの手作業）**。3D インポーターで `DrumSticks.fbx` を読み込む。1 本の長さが約 **1.45 studs**（実物の 16 インチ）になっているか確認する
3. **セットアップ**。`DrumSticks_Setup.lua` を `execute_luau` で実行する（MCP からは `local root = ...` の行を読み込んだ Model を直接指すように書き換える）。
   Folder `DrumSticks` の中に Model `Stick_<ID>` が 6 個でき、各 Model の PrimaryPart に Attachment `Grip`（持つ位置）と `Tip`（先端）が付く。
   Folder を ReplicatedStorage に移す
4. `roblox/DrumSticks.lua` を ModuleScript として ReplicatedStorage の BeatDrummer の下などに入れる
5. **持たせる（サーバー）**。演奏が始まるとき・スティックを装備したときに呼ぶ。今のスティックがあれば、先に消すか非表示にする

   ```lua
   local DrumSticks = require(ReplicatedStorage.BeatDrummer.DrumSticks)
   local template = DrumSticks.template(ReplicatedStorage.DrumSticks, equippedStickId)  -- "SweetRibbon" など
   DrumSticks.attach(character, template)                                 -- 両手に持たせる
   DrumSticks.attach(character, template, { tilt = -10, inward = 15, scale = 1.2 })  -- 角度と大きさを調整
   DrumSticks.detach(character)
   ```

   - スティックは手の `RightGripAttachment` / `LeftGripAttachment` の位置で握り、手の正面（−Z）へ伸びます。R6 は `Right Arm` / `Left Arm` に付きます
   - 今のアニメーションで向きが合わないときは、`tilt`（上下の角度）と `inward`（内側への角度）を度で調整し、
     ユーザーにプレイテストで見てもらって決めてください。決まった値は `DrumSticks.Defaults` に書きます
   - キャラクターに対して細く見えるときは `scale` を 1.2〜1.5 にします（実物の太さは約 0.05 studs）
6. **叩いたとき（クライアント）**。DrumKitFX の `fx:hit` と同じところで呼ぶ

   ```lua
   DrumSticks.hitLane(character, lane, strength)   -- レーンから叩く手を決めて、飾り・ライン・光る芯を一瞬光らせる
   ```

   レーンと手の対応は `DrumSticks.HandForLane`（SL は左、SR は右、HH は右など）。ゲームの持ち手に合わせて直してください
7. **NEON PULSE の光の色**は `DrumSticks.setColor(character, DrumSticks.NeonColors.magenta)` で変えられます（cyan / magenta / lime / orange / white）。
   色も選べるようにする場合は、選んだ色の名前も保存します
8. **購入と装備**はキットと同じ考え方です（GamePass またはゲーム内のお金、持っているかはサーバーで確認）。
   装備中のスティックの ID（`"Yozakura"` など）を DataStore に保存し、次に入ったときに持たせます。ショップの一覧には `DrumSticks.List`（`name` / `nameEn` / `theme` / `desc`）を使えます
9. スティックの音は変えません（叩いた音はキットの音のまま）

### 11. ギターとベース（BandInstruments）

バンドのメンバー（または他の楽器を担当するプレイヤー）が構える楽器です。代表的なモデルの形にしてありますが、
**ブランド名・ロゴ・メーカーの型番は入れていません**。ヘッドはすべてオリジナルの形です。形の商標が強いモデル（V シェイプ・フレアホーン・スウェプトホーン・ベース）は、翼やホーンの形を変えてアレンジしています。
ゲーム内でも元のブランド名・モデル名・型番（ST、SG、LP など）や、メーカー固有の色名は使わず、下の名前とボディ名で表示してください。ゲーム内コインなどで販売するアイテムなので、ヘッドや V・SG・RK 系のボディを実物の形に近づける変更はしないでください。

| ID | 名前 | ボディ | 仕上げ | ポリゴン |
| --- | --- | --- | --- | --- |
| `Skyline` | スカイライン | ダブルカッタウェイ（ギター） | 3 トーンサンバースト、白いピックガード、シングルコイル 3 基、トレモロ | 8,369 |
| `Prairie` | プレーリー | スラブ・シングルカット（ギター） | バタースコッチのアッシュ、黒いピックガード、メイプル指板 | 7,093 |
| `Sunforge` | サンフォージ | カーブドトップ・シングルカット（ギター） | チェリーサンバーストのトラ杢トップ、クリームのバインディング、ハムバッカー 2 基 | 9,276 |
| `CrimsonHorn` | クリムゾンホーン | フレアホーン（ギター） | チェリーレッド、外へ開いた 2 本のホーン、大きな黒いピックガード | 8,360 |
| `Valkyrie` | ヴァルキリー | V シェイプ（ギター） | 翼の先が尖った黒い V シェイプ、白いピックガード、V 字テールピース | 7,590 |
| `Velvet` | ヴェルヴェット | オフセット・ベース | 3 トーンサンバースト、べっ甲柄ピックガード、シングルコイル 2 基 | 7,543 |
| `Foundation` | ファウンデーション | スプリットコイル・ベース | ヴィンテージホワイト、べっ甲柄ピックガード、スプリットコイル | 6,836 |
| `Manta` | マンタ | ハムバッカー・ベース | ナチュラルアッシュ、黒いピックガード、大きなハムバッカー、3+1 ヘッド、丸いコントロールプレート | 7,104 |
| `Tempest` | テンペスト | リバースボディ・ベース | タバコサンバーストのリバースボディ、クリームのピックガード、ハムバッカー 2 基 | 6,162 |
| `Crestwave` | クレストウェーブ | スウェプトホーン・ベース | 赤いサンバースト、すっと伸びた低音側のホーン、白いピックガード、三角インレイ | 6,524 |

**素材**

| ファイル | 内容 |
| --- | --- |
| `export/instruments/BandInstruments.fbx` | 10 本が 2 列に並んだモデル（studs 単位、ボディやピックガードの柄の画像を埋め込み済み）。OBJ 版もあり |
| `export/instruments/BandInstruments_Setup.lua` | 読み込み後に 1 回実行するセットアップ |
| `roblox/BandInstruments.lua` | キャラクターに構えさせる・ノーツに合わせて揺らす ModuleScript（一覧 `BandInstruments.List` もここ） |
| `export/instruments/textures/` | 柄の画像（FBX に入っているので通常はアップロード不要） |
| `preview/instruments/` | ギター・ベースを並べた画像とボディのアップ |

**手順**

1. **今のバンドを調べる（変更はしない）**。バンドのメンバーが誰か（NPC かプレイヤーか、R15 か R6 か）、楽器を持っているか、
   持っているならどのパーツで体に付いているか、腕や体の動き（`BandMotion` など）をどこで動かしているか。結果をユーザーに報告する
2. **読み込む（ユーザーの手作業）**。3D インポーターで `BandInstruments.fbx` を読み込む。
   全長がギター約 **3.4〜3.9 studs**、ベース約 **4.1〜4.4 studs**（実物の大きさ）になっているか確認する
3. **セットアップ**。`BandInstruments_Setup.lua` を `execute_luau` で実行する（MCP からは `local root = ...` の行を読み込んだ Model を直接指すように書き換える）。
   Folder `BandInstruments` の中に Model `Guitar_<ID>` / `Bass_<ID>` ができ、ボディ（PrimaryPart）に Attachment `Wear`（体に当てる位置）、
   `Neck`（左手の位置）、`Strum`（右手で弾く位置）が付く。Folder を ReplicatedStorage に移す
4. `roblox/BandInstruments.lua` を ModuleScript として ReplicatedStorage の BeatDrummer の下などに入れる
5. **構えさせる（サーバー）**。今の楽器があれば、先に消すか非表示にする

   ```lua
   local BandInstruments = require(ReplicatedStorage.BeatDrummer.BandInstruments)
   local template = BandInstruments.template(ReplicatedStorage.BandInstruments, "Sunforge")
   BandInstruments.attach(guitarist, template)                                  -- 体の正面に構える
   BandInstruments.attach(bassist, BandInstruments.template(ReplicatedStorage.BandInstruments, "Manta"),
       { tilt = 22, offset = Vector3.new(0.3, -0.1, 0), scale = 0.9 })           -- 角度・位置・大きさを調整
   BandInstruments.detach(guitarist)
   ```

   - R15 は LowerTorso の `WaistFrontAttachment`、R6 は Torso の `BodyFrontAttachment` を基準に、ネックがキャラクターの左へ伸びる向きで付けます
   - 向きや位置が合わないときは `tilt`（ネックを上げる角度、度）、`offset`（studs）、`scale` で調整し、ユーザーにプレイテストで見てもらって決めてください。
     決まった値は `BandInstruments.Defaults` に書きます
   - 実物の大きさなので、キャラクターに対して大きく見えるときは `scale` を 0.8〜0.9 にします
   - 腕を楽器に合わせたいときは、楽器の Attachment `Neck`（左手）と `Strum`（右手）を IK やアニメーションの目標に使えます
6. **ノーツに合わせて（クライアント）**。ギターやベースのパートのノーツ、またはドラムのノーツに合わせて呼ぶ

   ```lua
   BandInstruments.strum(guitarist, strength)   -- 楽器が少し揺れて、弦が一瞬光る
   ```

7. **購入と装備**を付ける場合は、キットやスティックと同じ考え方です（`BandInstruments.List` の `name` / `nameEn` / `style` / `desc` をショップに並べられます）。
   バンドの見た目を変えるだけなら、メンバーごとに使う ID を決めて構えさせるだけで構いません
8. ギターとベースの音は付けていません（Beat Drummer の曲の音のまま）

### 12. 確認

- プレイテストで、9 つのキー（HH・CY・SL・SR・BD・HT・LT・FT・RD）すべてで、対応するパーツが動くこと（オートプレイで全曲を通す）
- プリセット 8 種を順に適用して、模様・ロゴ・金物・シンバルの色が変わること。再入場しても選んだ見た目が残ること
- 両方のキットで同じ確認をすること。キットを入れ替えたとき、それぞれのキットで選んだ見た目と音に切り替わること
- スマホのエミュレーター（デバイス設定）で、フレームレートが下がらないこと
- キットを入れ替えても、カメラ・ノーツ表示・バンドのメンバーの位置がずれないこと
- 買っていないプレイヤーは装備できないこと、買った後は再入場しても持っていること
- スティック 6 種を順に持たせて、両手で正しく握っていること（向き・位置・大きさ）、叩いたときに光ること。他のプレイヤーからも見えること
- スティックとキットを別々に切り替えても、互いに影響しないこと
- ギター 5 本・ベース 5 本を順に構えさせて、向き・位置・大きさが自然なこと、`strum` で揺れて弦が光ること。他のプレイヤーからも見えること

最後に、ユーザーに「保存と公開」をお願いしてください。
