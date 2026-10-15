# IRON STORM — Roblox 用メタルドラムセット 3D モデル

![正面](preview/front.jpg)

ツーバス（バスドラム 2 台）、3 面カーブラック、チャイナスタックまでそろえたメタル向けドラムセットです。
すべて Python で手続き的に生成しており、Roblox Studio の 3D インポーターでそのまま読み込めます。

| ドラマー視点 | 足元（ツインペダル） |
| --- | --- |
| ![ドラマー視点](preview/drummer.jpg) | ![ペダル](preview/pedals.jpg) |
| ![スネア](preview/snare.jpg) | ![スタック](preview/stack.jpg) |

## 構成

| 区分 | 内容 |
| --- | --- |
| ドラム | バスドラム 22"×18" ×2（ポート穴・ロゴ入りフロントヘッド）、スネア 14"×6.5"（ストレイナー・響き線）、タム 10" / 12" / 13"、フロアタム 16" / 18" |
| シンバル | ハイハット 14"（クラッチ付き）、クラッシュ 18" / 19" / 20"、ライド 22"、チャイナ 18"（逆さ取り付け）、スプラッシュ 10"、スタック（チャイナ 16" + スプラッシュ 12"） |
| ハードウェア | 3 面カーブラック（クランプ・T 字脚）、シンバルブーム ×7、タムホルダー ×3、ツインペダル（チェーン・スプリング・ビーター）、ハイハットスタンド、スネアスタンド、ドラムスローン、ドラムラグ |

ディテール: チューブラグ・テンションロッド・ワッシャー、バスドラムのクロー＆T ロッド、トリプルフランジフープ、
シェルのバッジとエアベント、シンバルのレイズ（旋盤溝）表現、フェルト・ウイングナット、ペダルのチェーンとコイルスプリング など。

## ファイル

| ファイル | 説明 |
| --- | --- |
| `export/MetalDrumKit.fbx` | **おすすめ**。標準版（219,336 ポリゴン / 126 MeshPart）。ロゴ画像を埋め込み済み |
| `export/MetalDrumKit.obj` + `.mtl` + `kick_logo.png` | 同じモデルの OBJ 版（3 ファイルを同じフォルダに置いて読み込む） |
| `export/MetalDrumKit_Lite.fbx` / `.obj` | 軽量版（105,244 ポリゴン）。モバイル向けや複数台置くとき用 |
| `export/MetalDrumKit.glb` | glTF 版（メートル単位）。Roblox 以外のツールでの確認用 |
| `export/kick_logo.png` | バスドラム前面ヘッドのロゴ（1024×1024） |
| `roblox/DrumKitSetup.lua` | 読み込み後に実行するセットアップスクリプト |
| `generator/` | モデルを生成した Python スクリプト一式 |

## Roblox Studio への読み込み手順

1. Studio で **ホーム > 3D をインポート**（Import 3D）を開き、`export/MetalDrumKit.fbx` を選ぶ。
2. インポート画面のプレビューでサイズを確認する。
   正しく読み込めていれば **幅 約 10.7 × 高さ 約 5.5 × 奥行き 約 7.5 studs**（ラグ込み）です。
   極端に小さい／大きい場合は、インポート設定の **File Dimensions（ファイルの寸法）を `Studs`** にしてください。
3. 「インポート」を押すと、126 個の MeshPart が入った Model がワークスペースに追加されます。
4. エクスプローラーでその Model を選択し、**表示 > コマンドバー** に `roblox/DrumKitSetup.lua` の中身をすべて貼り付けて Enter。
   - パーツ名の末尾（`_Chrome`、`_Bronze` など）から色とマテリアルを自動設定
   - `Drums` / `Cymbals` / `Hardware` ごとに Model を整理
   - 全パーツを Anchored にし、当たり判定はラグだけ（軽量化）
   - スローンに見えない `Seat` を追加（座るとスネア側を向きます）
5. プレイテストして、スローンに座れることを確認してください。

> フロントヘッドのロゴが表示されない場合は、`export/kick_logo.png` を画像としてアップロードし、
> `DrumKitSetup.lua` 冒頭の `LogoTextureId` にその ID（`rbxassetid://...`）を入れて再実行してください。

## カスタマイズ

- **色を変える**: `DrumKitSetup.lua` の `PALETTE` を書き換えて再実行（何度実行しても OK）。
  例: `Finish`（シェル）を赤にすれば赤いキットに、`Accent` を `NeonAccents = true` にすると赤いラインが発光します。
- **パーツ名**: `<部品>_<素材>` の形式です（例: `Kick_L_Chrome`、`Crash_18_Bronze`、`Pedal_R_Beater_Chrome`）。
  シンバル（`Crash_18` など）、ハイハットのトップ（`HiHat_Top`）、ペダルのビーター（`Pedal_L_Beater`）は独立した Model なので、
  叩いたときに揺らす・動かすアニメーションを付けやすくしてあります。
- **向き・スケール**: ドラマーは −Z 方向（Roblox の正面方向）を向いています。スケールは 1 stud = 0.28 m。
  大きさを変えたいときは Model を選んで `Model:ScaleTo()` やスケールツールを使ってください。

## 仕様

| 項目 | 標準版 | 軽量版 |
| --- | --- | --- |
| ポリゴン数 | 219,336 | 105,244 |
| MeshPart 数 | 126 | 126 |
| 1 MeshPart の最大ポリゴン数 | 9,072（Roblox 上限 20,000） | 4,876 |
| サイズ | 10.7 × 5.5 × 7.5 studs（3.0 × 1.55 × 2.1 m） | 同じ |
| スローン座面の高さ | 2.0 studs | 同じ |

## 再生成

```bash
cd generator
pip install numpy scipy shapely trimesh mapbox_earcut pillow   # OBJ とロゴ
pip install bpy                                                # FBX / GLB / レンダリング用（Blender モジュール）
./build_all.sh            # すべて書き出し（RENDER=0 でレンダリングを省略）
python drumkit.py --detail 0.7 --name MyKit --out ../export    # 細かさを変えた OBJ を作る
```

`drumkit.py` の `build_kit()` 内で配置（タムの角度、シンバルの位置や大きさなど）を、
`make_logo.py` でロゴのデザインを変更できます。
