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
SAMPLES=${SAMPLES:-64}

$PY make_logo.py "$OUT/kick_logo.png"

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

# preview renders
if [[ "${RENDER:-1}" == "1" ]]; then
  $BPY_PY blender_export.py --renders "$PREV" --samples "$SAMPLES" \
    --views front,drummer,side,detail,pedals,snare,hihat,stack
  $BPY_PY blender_export.py --spec specs/beatdrummer_spec.json \
    --renders "$PREV/beatdrummer" --samples "$SAMPLES" \
    --views bd_front,bd_drummer,bd_pedals
fi
