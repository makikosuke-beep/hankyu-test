"""Drum sticks in Blender (bpy module): FBX / GLB export and preview renders.

    python sticks_blender.py --out ../export/sticks
    python sticks_blender.py --renders ../preview/sticks [--samples 64]
    python sticks_blender.py --viewer-glb sticks_view.glb
"""
import argparse
import math
import os
import sys

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sticks  # noqa: E402
from blender_export import add_light, camera, lin, setup_world, yup_to_zup  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
EXPORT = os.path.join(HERE, "..", "export", "sticks")
TAU_ = 2 * math.pi


def grain_image(path):
    """Straight hickory grain (grey, multiplied over the wood colour) running
    along the stick: soft bands plus fine dark lines that wander a little."""
    if os.path.exists(path):
        return path
    from PIL import Image
    rng = np.random.default_rng(3)
    W, H = 256, 1024
    u = np.arange(W)[None, :].astype(float)
    v = np.arange(H)[:, None].astype(float)
    g = np.ones((H, W))
    for f, a in ((2, 0.05), (5, 0.04), (11, 0.03)):
        g -= a * (0.5 + 0.5 * np.sin(TAU_ * f * u / W + rng.uniform(0, TAU_)))
    for _ in range(46):
        c = rng.uniform(0, W)
        wav = (rng.uniform(1, 4) * np.sin(TAU_ * rng.integers(1, 4) * v / H + rng.uniform(0, TAU_)) +
               rng.uniform(0.5, 1.5) * np.sin(TAU_ * rng.integers(4, 9) * v / H + rng.uniform(0, TAU_)))
        d = np.abs(((u - c - wav) + W / 2) % W - W / 2)
        width = rng.uniform(0.6, 1.8)
        g -= rng.uniform(0.05, 0.16) * np.exp(-(d / width) ** 2)
    g += 0.015 * rng.standard_normal((H, W))
    img = np.clip(g * 255, 0, 255).astype(np.uint8)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(img, "L").save(path)
    return path


def export_material(name, p, logo):
    """Plain material for FBX: the logo image wired straight into Base
    Color so the Roblox importer picks it up as the MeshPart texture."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = lin(p["color"])
    b.inputs["Metallic"].default_value = p["pbr"][0]
    b.inputs["Roughness"].default_value = p["pbr"][1]
    if logo and os.path.exists(logo):
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(logo, check_existing=True)
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    return m


def make_material(name, p, logo=None, grain=None):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    met, rough, coat = p["pbr"]
    b.inputs["Metallic"].default_value = met
    b.inputs["Roughness"].default_value = rough
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.06
    col = lin(p["color"])
    b.inputs["Base Color"].default_value = col
    out = None
    if p.get("grain") and grain:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(grain, check_existing=True)
        tex.image.colorspace_settings.name = "Non-Color"
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        mix.inputs[6].default_value = col
        nt.links.new(tex.outputs["Color"], mix.inputs[7])
        out = mix.outputs[2]
    if logo and os.path.exists(logo):
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(logo, check_existing=True)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        if out is not None:
            nt.links.new(out, mix.inputs[6])
        else:
            mix.inputs[6].default_value = col
        nt.links.new(tex.outputs["Alpha"], mix.inputs["Factor"])
        nt.links.new(tex.outputs["Color"], mix.inputs[7])
        out = mix.outputs[2]
    if out is not None:
        nt.links.new(out, b.inputs["Base Color"])
    if p.get("glass"):
        b.inputs["Transmission Weight"].default_value = 1.0
        b.inputs["IOR"].default_value = 1.45
    if p.get("neon"):
        b.inputs["Emission Color"].default_value = col
        b.inputs["Emission Strength"].default_value = 14.0
    if p.get("sheen"):
        b.inputs["Sheen Weight"].default_value = 0.6
    return m


def make_materials(logo_dir=None, for_export=False):
    grain = grain_image(os.path.join(EXPORT, "textures", "hickory_grain.png"))
    mats = {}
    for d in sticks.DESIGNS:
        for key, p in d["palette"].items():
            name = "%s_%s" % (d["id"], key)
            logo = None
            if logo_dir and key == d["logo"]:
                logo = os.path.join(logo_dir, "stick_%s.png" % d["id"])
            if for_export:
                mats[name] = export_material(name, p, logo)
            else:
                mats[name] = make_material(name, p, logo, grain)
    return mats


def mesh_object(name, mesh, mat):
    v = yup_to_zup(mesh.v)
    cn = mesh.cn.reshape(-1, 3)
    cn = np.stack([cn[:, 0], -cn[:, 2], cn[:, 1]], -1)
    me = bpy.data.meshes.new(name)
    me.from_pydata(v.tolist(), [], mesh.f.tolist())
    me.update()
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", mesh.cuv.reshape(-1).astype(np.float32))
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.normals_split_custom_set(cn.tolist())
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def export(out_dir, mats, name="DrumSticks"):
    built = sticks.build_all()
    objs = [mesh_object(n, m, mats[mat]) for n, mat, m in sticks.parts_of(built)]
    bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, name + ".glb"),
                              export_format="GLB", export_yup=True,
                              export_normals=True, export_texcoords=True)
    s = 1.0 / sticks.STUD
    for ob in objs:
        ob.scale = (s, s, s)
    bpy.ops.object.select_all(action="SELECT")
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 0.01
    bpy.ops.export_scene.fbx(filepath=os.path.join(out_dir, name + ".fbx"),
                             use_selection=False, object_types={"MESH"},
                             apply_unit_scale=True, apply_scale_options="FBX_SCALE_NONE",
                             axis_forward="-Z", axis_up="Y", bake_space_transform=True,
                             mesh_smooth_type="OFF", use_custom_props=False,
                             path_mode="COPY", embed_textures=True)
    print("exported", out_dir, flush=True)


def stage(mats, spacing=0.09):
    """Every design as a standing pair, resting on the floor."""
    built = sticks.build_all()
    placed = []
    for i, (d, s) in enumerate(built):
        s.x = (i - (len(built) - 1) / 2) * spacing
        parts = [(n, mat, m) for n, mat, m in sticks.parts_of([(d, s)], place=False)]
        lift = -min(m.v[:, 1].min() for _, _, m in parts)
        datas = [(mesh_object(n, m, mats[mat]), n) for n, mat, m in parts]
        for side, (dx, rot) in enumerate(((-0.0118, 16), (0.0118, -16))):
            for ob, n in datas:
                o = ob if side == 0 else ob.copy()
                if side:
                    bpy.context.scene.collection.objects.link(o)
                o.location = (s.x + dx, 0, lift)
                o.rotation_euler = (0, 0, math.radians(rot))
        placed.append((d, s.x, lift, s.L))
    me = bpy.data.meshes.new("Floor")
    k = 20
    me.from_pydata([(-k, -k, 0), (k, -k, 0), (k, k, 0), (-k, k, 0)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new("Floor", me)
    fm = bpy.data.materials.new("FloorMat")
    fm.use_nodes = True
    fb = fm.node_tree.nodes["Principled BSDF"]
    fb.inputs["Base Color"].default_value = (0.012, 0.012, 0.014, 1)
    fb.inputs["Roughness"].default_value = 0.22
    me.materials.append(fm)
    bpy.context.scene.collection.objects.link(ob)
    return placed


def lights():
    add_light("Key", (1.4, -2.0, 1.7), (0, 0, 0.2), 380, 1.4)
    add_light("Fill", (-1.9, -1.4, 0.9), (0, 0, 0.2), 150, 2.0, (0.8, 0.86, 1.0))
    add_light("Rim", (0.6, 2.2, 1.4), (0, 0, 0.25), 420, 1.6, (1.0, 0.82, 0.74))
    add_light("Top", (0, -0.3, 2.6), (0, 0, 0), 120, 2.5)


def render(path, cam_loc, target, lens, res, samples):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = res
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    cam = camera(cam_loc, target, lens)
    sc.camera = cam
    sc.render.filepath = path
    bpy.ops.render.render(write_still=True)
    print("rendered", path, flush=True)
    return cam


def label(img_path, out_path, placed, cam, strip=120, small=False):
    from PIL import Image, ImageDraw, ImageFont
    sc = bpy.context.scene
    im = Image.open(img_path).convert("RGB")
    W, H = im.size
    sheet = Image.new("RGB", (W, H + strip), (12, 12, 14))
    sheet.paste(im, (0, 0))
    dr = ImageDraw.Draw(sheet)
    en = ImageFont.truetype("/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf", 24)
    ja = ImageFont.truetype("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf", 19)
    for d, x, lift, L in placed:
        p = world_to_camera_view(sc, cam, Vector((x, 0, lift)))
        cx = p.x * W
        for text, font, y, fill in ((d["nameEn"], en, 16, (240, 236, 228)),
                                    (d["name"], ja, 56, (200, 198, 206)),
                                    (d["theme"], ja, 88, (150, 148, 156))):
            w = dr.textlength(text, font=font)
            dr.text((cx - w / 2, H + y), text, font=font, fill=fill)
    sheet.save(out_path, quality=92)
    print("labelled", out_path, flush=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--renders", default=None)
    ap.add_argument("--viewer-glb", default=None)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--views", default="lineup,tips,butts")
    ap.add_argument("--exposure", type=float, default=0.0)
    a = ap.parse_args(argv)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    logos = os.path.join(EXPORT, "logos")
    if a.out:
        export(a.out, make_materials(logos, for_export=True))
        return
    mats = make_materials(logos)
    if a.viewer_glb:
        built = sticks.build_all()
        for n, mat, m in sticks.parts_of(built, place=False):
            mesh_object(n, m, mats[mat])
        bpy.ops.export_scene.gltf(filepath=a.viewer_glb, export_format="GLB",
                                  export_yup=True, export_normals=True,
                                  export_texcoords=True, export_materials="NONE")
        print("viewer glb", a.viewer_glb, flush=True)
        return
    if a.renders:
        import tempfile
        os.makedirs(a.renders, exist_ok=True)
        setup_world()
        bpy.context.scene.view_settings.exposure = a.exposure
        placed = stage(mats)
        lights()
        tmp = tempfile.mkdtemp()
        views = {
            "lineup": ((0, -1.62, 0.27), (0, 0, 0.215), 85, (2000, 1300), 130, False),
            "tips": ((0, -1.3, 0.43), (0, 0, 0.365), 85, (2000, 640), 130, True),
            "butts": ((0, -1.3, 0.12), (0, 0, 0.045), 85, (2000, 640), 130, True),
            "logos": ((0, -1.3, 0.2), (0, 0, 0.19), 85, (2000, 640), 130, True),
        }
        for v in a.views.split(","):
            loc, tgt, lens, res, strip, small = views[v]
            raw = os.path.join(tmp, v + ".png")
            cam = render(raw, loc, tgt, lens, res, a.samples)
            label(raw, os.path.join(a.renders, "sticks_%s.jpg" % v), placed, cam, strip, small)


if __name__ == "__main__":
    main()
