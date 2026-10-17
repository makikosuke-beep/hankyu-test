#!/usr/bin/env bash
# Regenerate every deliverable.
#   PY      : python with numpy/scipy/shapely/trimesh/mapbox_earcut/pillow
#   BPY_PY  : python that has the `bpy` (Blender) module - for FBX/GLB/renders
set -euo pipefail
cd "$(dirname "$0")"
PY=${PY:-python3}
BPY_PY=${BPY_PY:-python3}
OUT=../export
PREV=../preview
mkdir -p "$OUT/styles"
SAMPLES=${SAMPLES:-64}

mkdir -p "$OUT/styles/sovereign" "$OUT/sovereign"
$PY make_logo.py "$OUT/kick_logo.png" "$OUT/styles/logo_overlay.png"
$PY make_logo.py "$OUT/sovereign/sovereign_logo.png" "$OUT/styles/sovereign/logo_overlay.png" sovereign
$PY make_patterns.py "$OUT/styles"
$PY make_patterns.py "$OUT/styles/sovereign" wood
$PY make_styles_lua.py

# OBJ (+MTL) in studs
$PY drumkit.py --out "$OUT" --name MetalDrumKit
$PY drumkit.py --out "$OUT" --name MetalDrumKit_Lite --detail 0.5

# FBX (studs) + GLB (metres)
$BPY_PY blender_export.py --out "$OUT" --name MetalDrumKit
$BPY_PY blender_export.py --out "$OUT" --name MetalDrumKit_Lite --detail 0.5

# Beat Drummer kit: same pieces as the in-game kit (HT/LT/FT toms), lane-coded
$PY kitspec.py specs/beatdrummer_spec.json --out "$OUT/beatdrummer"
cp "$OUT/kick_logo.png" "$OUT/beatdrummer/"
$BPY_PY blender_export.py --spec specs/beatdrummer_spec.json --out "$OUT/beatdrummer"

# SOVEREIGN: same lanes and layout, wood veneers + gold hardware on stands
$PY kitspec.py specs/sovereign_spec.json --out "$OUT/sovereign"
$BPY_PY blender_export.py --spec specs/sovereign_spec.json --out "$OUT/sovereign"

# Drum sticks: six designs (also writes roblox/DrumSticks.lua)
$PY stick_logos.py "$OUT/sticks/logos"
$PY sticks.py --out "$OUT/sticks"
$BPY_PY sticks_blender.py --out "$OUT/sticks"

# Guitars and basses for the band (also writes roblox/BandInstruments.lua)
$PY instrument_textures.py "$OUT/instruments/textures"
$PY instruments.py --out "$OUT/instruments"
$BPY_PY instruments_blender.py --out "$OUT/instruments"

# preview renders
if [[ "${RENDER:-1}" == "1" ]]; then
  $BPY_PY blender_export.py --renders "$PREV" --samples "$SAMPLES" \
    --views front,drummer,side,detail,pedals,snare,hihat,stack
  $BPY_PY blender_export.py --spec specs/beatdrummer_spec.json \
    --renders "$PREV/beatdrummer" --samples "$SAMPLES" \
    --views bd_front,bd_drummer,bd_pedals
  $BPY_PY blender_export.py --spec specs/beatdrummer_spec.json \
    --renders "$PREV/beatdrummer" --lineup "$PREV/beatdrummer/styles_lineup.jpg" \
    --views bd_front --samples 24 --res 800x500
  $BPY_PY blender_export.py --spec specs/sovereign_spec.json \
    --renders "$PREV/sovereign" --samples "$SAMPLES" \
    --views bd_front,bd_drummer,bd_pedals,bd_holder
  $BPY_PY blender_export.py --spec specs/sovereign_spec.json \
    --renders "$PREV/sovereign" --lineup "$PREV/sovereign/styles_lineup.jpg" \
    --views bd_front --samples 24 --res 800x500
  $BPY_PY sticks_blender.py --renders "$PREV/sticks" --samples "$SAMPLES"
  $BPY_PY instruments_blender.py --renders "$PREV/instruments" --samples "$SAMPLES"
fi
