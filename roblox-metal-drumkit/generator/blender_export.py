"""Build the kit inside Blender (bpy module) -> FBX / GLB export + preview renders.

Usage (needs the `bpy` pip module):
    python blender_export.py --out ../export --renders ../preview [--detail 1.0]
"""
import argparse
import math
import os
import sys

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import drumkit  # noqa: E402

# name: base colour (linear-ish sRGB), metallic, roughness, coat
PBR = {
    "Chrome":     ((0.90, 0.91, 0.93), 1.0, 0.07, 0.0),
    "Finish":     ((0.010, 0.010, 0.012), 0.0, 0.32, 0.55),
    "Accent":     ((0.55, 0.005, 0.012), 0.2, 0.25, 1.0),
    "HeadCoated": ((0.88, 0.87, 0.82), 0.0, 0.75, 0.0),
    "HeadBlack":  ((0.02, 0.02, 0.022), 0.0, 0.45, 0.0),
    "HeadClear":  ((0.75, 0.75, 0.72), 0.0, 0.35, 0.0),
    "HeadLogo":   ((1.0, 1.0, 1.0), 0.0, 0.45, 0.0),
    "Bronze":     ((0.86, 0.60, 0.30), 1.0, 0.18, 0.0),
    "BronzeDark": ((0.55, 0.36, 0.16), 1.0, 0.38, 0.0),
    "BlackMetal": ((0.025, 0.025, 0.028), 0.6, 0.38, 0.0),
    "Rubber":     ((0.02, 0.02, 0.02), 0.0, 0.85, 0.0),
    "Felt":       ((0.45, 0.02, 0.03), 0.0, 0.95, 0.0),
    "Leather":    ((0.02, 0.02, 0.02), 0.0, 0.42, 0.3),
    "Rug":        ((0.045, 0.045, 0.05), 0.0, 0.95, 0.0),
}


def yup_to_zup(v):
    return np.stack([v[:, 0], -v[:, 2], v[:, 1]], -1)


def make_materials(tex_path):
    mats = {}
    for name, (col, met, rough, coat) in PBR.items():
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*col, 1)
        bsdf.inputs["Metallic"].default_value = met
        bsdf.inputs["Roughness"].default_value = rough
        if coat and "Coat Weight" in bsdf.inputs:
            bsdf.inputs["Coat Weight"].default_value = coat
            bsdf.inputs["Coat Roughness"].default_value = 0.05
        if name == "HeadLogo" and tex_path and os.path.exists(tex_path):
            img = bpy.data.images.load(tex_path)
            tn = m.node_tree.nodes.new("ShaderNodeTexImage")
            tn.image = img
            m.node_tree.links.new(tn.outputs["Color"], bsdf.inputs["Base Color"])
        mats[name] = m
    return mats


def build(parts, mats, scale=1.0):
    objs = []
    R = drumkit.EXPORT_ROT
    for name, mat, mesh in parts:
        m = mesh.transformed(R)
        v = yup_to_zup(m.v) * scale
        cn = m.cn.reshape(-1, 3)
        cn = np.stack([cn[:, 0], -cn[:, 2], cn[:, 1]], -1)
        me = bpy.data.meshes.new(name)
        me.from_pydata(v.tolist(), [], m.f.tolist())
        me.update()
        uv = me.uv_layers.new(name="UVMap")
        uv.data.foreach_set("uv", m.cuv.reshape(-1).astype(np.float32))
        me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
        me.normals_split_custom_set(cn.tolist())
        me.materials.append(mats[mat])
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        objs.append(ob)
    return objs


def setup_world():
    w = bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.52
    ramp.color_ramp.elements[0].color = (0.002, 0.002, 0.003, 1)
    ramp.color_ramp.elements[1].position = 0.9
    ramp.color_ramp.elements[1].color = (0.22, 0.22, 0.25, 1)
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -1
    mr.inputs["From Max"].default_value = 1
    nt.links.new(tc.outputs["Generated"], sep.inputs[0])
    nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0


def add_light(name, loc, target, power, size, color=(1, 1, 1)):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = power
    ld.size = size
    ld.color = color
    ob = bpy.data.objects.new(name, ld)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(ob)
    return ob


def add_floor():
    me = bpy.data.meshes.new("Floor")
    s = 30
    me.from_pydata([(-s, -s, -0.009), (s, -s, -0.009), (s, s, -0.009),
                    (-s, s, -0.009)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new("Floor", me)
    m = bpy.data.materials.new("FloorMat")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.02, 0.02, 0.022, 1)
    b.inputs["Roughness"].default_value = 0.35
    me.materials.append(m)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def camera(loc, target, lens=35):
    cd = bpy.data.cameras.new("Cam")
    cd.lens = lens
    ob = bpy.data.objects.new("Cam", cd)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.collection.objects.link(ob)
    return ob


def render_views(out_dir, views, res=(1600, 1000), samples=64):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.image_settings.file_format = "JPEG"
    sc.render.image_settings.quality = 90
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    os.makedirs(out_dir, exist_ok=True)
    for name, loc, tgt, lens in views:
        cam = camera(loc, tgt, lens)
        sc.camera = cam
        sc.render.filepath = os.path.join(out_dir, name + ".jpg")
        bpy.ops.render.render(write_still=True)
        print("rendered", name, flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--detail", type=float, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--renders", default=None)
    ap.add_argument("--views", default="all")
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--res", default="1600x1000")
    ap.add_argument("--name", default=None)
    ap.add_argument("--spec", default=None,
                    help="build from a kit spec JSON (see kitspec.py)")
    a = ap.parse_args()

    a.detail_set = a.detail is not None
    if a.detail is None:
        a.detail = 1.0
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scale = 1.0
    if a.spec:
        import json
        import kitspec
        spec = json.load(open(a.spec, encoding="utf-8"))
        kit = kitspec.build_from_spec(spec, a.detail if a.detail_set else None)
        scale = spec.get("scale", 1.0)
        a.name = a.name or spec.get("name", "DrumKit")
    else:
        kit = drumkit.build_kit(a.detail)
        a.name = a.name or "MetalDrumKit"
    parts = kit.merged()
    here = os.path.dirname(os.path.abspath(__file__))
    tex = os.path.join(a.out or os.path.join(here, "..", "export"),
                       "kick_logo.png")
    mats = make_materials(tex)
    objs = build(parts, mats)

    if a.renders:
        setup_world()
        add_floor()
        # coordinates: Blender Z-up, audience at +Y, drummer at -Y
        add_light("Key", (3.0, 3.5, 4.0), (0, 0, 0.8), 1500, 3.0)
        add_light("Fill", (-4.0, 2.0, 2.5), (0, 0, 0.8), 500, 4.0,
                  (0.8, 0.85, 1.0))
        add_light("Rim", (0.5, -4.0, 3.5), (0, 0, 1.0), 1200, 3.0,
                  (1.0, 0.75, 0.7))
        add_light("Top", (0, 0, 5.0), (0, 0, 0), 600, 4.0)
        views = {
            "front": ((2.6, 4.6, 2.3), (-0.05, 0.0, 0.75), 35),
            "drummer": ((0.0, -1.55, 1.75), (0.0, 0.35, 0.85), 24),
            "side": ((-4.6, 1.2, 1.6), (0.0, 0.0, 0.7), 40),
            "top": ((0.0, 0.0, 6.5), (0.0, 0.001, 0.0), 30),
            "pedals": ((-0.95, -1.05, 0.6), (-0.2, 0.0, 0.16), 32),
            "stack": ((-1.75, -0.6, 1.55), (-1.0, 0.06, 1.2), 45),
            "detail": ((0.9, 1.7, 1.3), (-0.3, 0.0, 0.75), 50),
            "snare": ((-0.75, -1.0, 0.85), (-0.12, -0.12, 0.45), 40),
            "hihat": ((-1.9, -1.3, 1.45), (-0.85, 0.0, 0.95), 40),
            "bd_front": ((2.1, 3.7, 1.9), (0.0, 0.0, 0.72), 35),
            "bd_drummer": ((0.0, -1.62, 1.72), (0.0, 0.3, 0.85), 26),
            "bd_pedals": ((-0.8, -0.95, 0.55), (-0.12, 0.0, 0.15), 32),
            "bd_top": ((0.0, -0.1, 5.2), (0.0, 0.0, 0.0), 30),
        }
        sel = list(views) if a.views == "all" else a.views.split(",")
        w, h = (int(x) for x in a.res.split("x"))
        render_views(a.renders, [(k, *views[k]) for k in sel], (w, h),
                     a.samples)

    if a.out:
        for ob in list(bpy.data.objects):
            if ob.type != "MESH" or ob.name == "Floor":
                bpy.data.objects.remove(ob, do_unlink=True)
        # GLB in metres (glTF convention)
        bpy.ops.export_scene.gltf(filepath=os.path.join(a.out, a.name + ".glb"),
                                  export_format="GLB", export_yup=True,
                                  export_normals=True, export_texcoords=True)
        # FBX in studs: 1 Blender unit = 1 stud, unit scale 0.01 (cm) so the
        # raw FBX values are studs, which is what Roblox Studio expects.
        s = scale / drumkit.STUD
        for ob in bpy.data.objects:
            ob.scale = (s, s, s)
        bpy.ops.object.select_all(action="SELECT")
        bpy.context.view_layer.objects.active = bpy.data.objects[0]
        bpy.ops.object.transform_apply(location=False, rotation=False,
                                       scale=True)
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.scale_length = 0.01
        bpy.ops.export_scene.fbx(filepath=os.path.join(a.out, a.name + ".fbx"),
                                 use_selection=False, object_types={"MESH"},
                                 apply_unit_scale=True,
                                 apply_scale_options="FBX_SCALE_NONE",
                                 axis_forward="-Z", axis_up="Y",
                                 bake_space_transform=True,
                                 mesh_smooth_type="OFF",
                                 use_custom_props=False,
                                 path_mode="COPY", embed_textures=True)
        print("exported", flush=True)


if __name__ == "__main__":
    main()
