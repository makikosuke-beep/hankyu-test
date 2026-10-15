# Beat Drummer への組み込み手順（PC の Claude Code 向け）

このドキュメントは、Roblox Studio MCP がつながった PC 側の Claude Code が読む前提で書いています。
目的は、メタル仕様のドラムセット **「IRON STORM」** を Beat Drummer に入れることです。
IRON STORM は、ゲーム内のお金または Robux で買うと、今のドラムセットと入れ替えられるキット（スキン）にします。

## ゴール

1. IRON STORM を、**今のドラムセットと同じ構成**（同じレーン・同じ数のタムとシンバル）で、ステージ上の今のキットと差し替えられるようにする
2. ノーツを叩いたときに、キットが動くようにする（シンバルの揺れ、ビーター、ハイハットの開閉、ヘッドの発光）
3. **音は今のキットと変える**（IRON STORM 専用のサウンドセット）
4. ゲーム内のお金と Robux のどちらかで買えるようにし、持っている人だけが装備を切り替えられるようにする
5. スマホでも重くならないこと（今のモデルは 63,456 ポリゴン、MeshPart 82 個）

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
| `roblox/DrumKitFX.lua` | 叩いたときの動きを付ける ModuleScript（クライアント用） |
| `generator/specs/beatdrummer_spec.json` | キット構成の設定ファイル（ここを直して再生成できる） |
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

### 3. Studio に読み込む（ユーザーの手作業）

3D インポーターは MCP から操作できないので、ユーザーにお願いします。

1. ホーム ＞ 3D をインポート で `BeatDrummer_IronStorm.fbx`（または OBJ）を選ぶ
2. 大きさがおよそ **幅 7.1 × 高さ 5.1 × 奥行き 6.6 studs**（ラグ込み）になっているか確認する。
   違う場合は、インポート設定の File Dimensions を Studs にする
3. 読み込んだ Model の名前を `BeatDrummer_IronStorm` にする

### 4. セットアップを実行する

`BeatDrummer_IronStorm_Setup.lua` の中身を `execute_luau` で実行します。
このスクリプトは、選択中の Model か `workspace.BeatDrummer_IronStorm` を対象にします。
MCP から実行するときは、先頭近くの `local root = ...` の行を、対象の Model を直接指すように書き換えてください。

実行すると、次のように設定されます。

- 各パーツの Model に `Lane`（BD など）と `PieceKind`（drum / kick / beater / cymbal / hihat_top / hihat_bottom）の属性が付く
- 各パーツの Model の `WorldPivot` が、回転の中心に設定される（シンバルは中心の穴、ビーターは軸、ハイハットのトップはクラッチ）
- 色・マテリアルの設定。すべて Anchored にし、当たり判定はラグだけにする
- スローンに `DrummerSeat` を追加する。ゲーム側で不要なら消してください

最後に、テンプレートとして ServerStorage（または ReplicatedStorage）の `DrumKits` フォルダなどにしまいます。

### 5. 今のキットと入れ替えられるようにする

- 今のキットもテンプレート化して（例 `DrumKits.Standard`）、**装備中のキットを複製してステージの決まった CFrame に置く**仕組みにします
- 位置合わせ: 新しいキットはドラマーが −Z を向く向きで作ってあります。今のキットの「スローン位置」と「スネア位置」がそろうように、`PivotTo` で置いてください
- ゲームのコードがパーツを名前で探している箇所は、`Lane` 属性で探すように変えると、どのキットでも同じコードで動きます
- 最初は今のキットを既定のままにして、IRON STORM が問題なく動くことを確かめてから切り替えの UI を出してください

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
- ツインペダルは、BD を叩くたびに左右のビーターが交互に動きます
- 太鼓は叩くと一瞬光ります（PointLight）。重い場合は `DrumKitFX.new(kit, { flash = false })` にしてください
- 他のプレイヤーのキットも動かす場合は、そのプレイヤーのクライアントから届く演奏イベントで同じ `fx:hit` を呼びます

### 7. 音を IRON STORM 専用にする

- キットごとのサウンドセットの表を作り、装備中のキットの表を使って鳴らします

  ```lua
  KitSounds.IronStorm = { BD = "rbxassetid://...", SN = "...", HH = { closed = "...", open = "..." },
                          HT = "...", LT = "...", FT = "...", CR = "...", RD = "..." }
  ```
- 音そのものは、**ユーザーと一緒に選んでください**（Creator Store の音源、またはユーザーが用意した音を Roblox にアップロード）。
  メタル向けの方向性の例: アタックの強いクリック感のあるキック、高めにチューニングしたスネア、
  派手で少し汚れたクラッシュ、ベルの鳴りが目立つライド
- 推測した SoundId は入れないでください。実際に Studio で鳴ることを確かめてから入れてください

### 8. 購入と装備

- **ゲーム内のお金**: 購入はサーバーで処理します（残高を確認 → 引く → 持ち物に追加 → DataStore に保存）
- **Robux**: ずっと持っておくアイテムなので、GamePass（`MarketplaceService:PromptGamePassPurchase`、
  `UserOwnsGamePassAsync` で確認）が簡単です。DevProduct にする場合は `ProcessReceipt` で持ち物に追加して保存します
- 装備中のキットも DataStore に保存し、次に入ったときに同じキットが出るようにします
- 持っているかどうかは必ずサーバーで確認し、クライアントから送られた内容だけで装備させないでください
- GamePass の作成と価格設定はユーザーが Creator Dashboard で行います

### 9. 確認

- プレイテストで、9 つのキー（HH・CY・SL・SR・BD・HT・LT・FT・RD）すべてで、対応するパーツが動くこと（オートプレイで全曲を通す）
- スマホのエミュレーター（デバイス設定）で、フレームレートが下がらないこと
- キットを入れ替えても、カメラ・ノーツ表示・バンドのメンバーの位置がずれないこと
- 買っていないプレイヤーは装備できないこと、買った後は再入場しても持っていること

最後に、ユーザーに「保存と公開」をお願いしてください。
