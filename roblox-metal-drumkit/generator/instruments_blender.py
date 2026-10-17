"""Guitars and basses in Blender (bpy module): FBX / GLB export and renders.

    python instruments_blender.py --out ../export/instruments
    python instruments_blender.py --renders ../preview/instruments [--samples 64]
    python instruments_blender.py --viewer-glb instruments_view.glb
"""
import argparse
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import instruments  # noqa: E402
from blender_export import add_light, lin, setup_world  # noqa: E402
from sticks_blender import mesh_object, render  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
EXPORT = os.path.join(HERE, "..", "export", "instruments")
TEX = os.path.join(EXPORT, "textures")


def image(path, non_color=False):
    img = bpy.data.images.load(path, check_existing=True)
    if non_color:
        img.colorspace_settings.name = "Non-Color"
    return img


def make_material(name, p, tex_path=None, for_export=False):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    met, rough, coat = p["pbr"]
    b.inputs["Base Color"].default_value = lin(p["color"])
    b.inputs["Metallic"].default_value = met
    b.inputs["Roughness"].default_value = rough
    if tex_path and os.path.exists(tex_path):
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = image(tex_path)
        nt.links.new(tn.outputs["Color"], b.inputs["Base Color"])
    elif p.get("grain") and not for_export:
        tn = nt.nodes.new("ShaderNodeTexImage")
        tn.image = image(os.path.join(TEX, "%s_grain.png" % p["grain"]), True)
        mix = nt.nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs["Factor"].default_value = 1.0
        mix.inputs[6].default_value = lin(p["color"])
        nt.links.new(tn.outputs["Color"], mix.inputs[7])
        nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    if coat and not for_export:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.05
    return m


def make_materials(for_export=False):
    mats = {}
    for d in instruments.INSTRUMENTS:
        for key, p in d["palette"].items():
            name = "%s_%s" % (d["id"], key)
            tex = os.path.join(TEX, name + ".png") if p.get("texture") else None
            mats[name] = make_material(name, p, tex, for_export)
    return mats


def export(out_dir, mats, name="BandInstruments"):
    built = instruments.build_all()
    objs = [mesh_object(n, m, mats[mat]) for n, mat, m in instruments.parts_of(built)]
    bpy.ops.export_scene.gltf(filepath=os.path.join(out_dir, name + ".glb"),
                              export_format="GLB", export_yup=True,
                              export_normals=True, export_texcoords=True)
    s = 1.0 / instruments.STUD
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


def stage(mats, kind, spacing):
    """One row of instruments standing just above a dark floor."""
    built = [x for x in instruments.build_all() if x[0]["kind"] == kind]
    placed = []
    for i, (d, b, info) in enumerate(built):
        x = (i - (len(built) - 1) / 2) * spacing
        for n, mat, m in instruments.parts_of([(d, b, info)], place=False):
            ob = mesh_object(n, m, mats[mat])
            ob.location = (x, 0, 0.03)
            ob.rotation_euler = (0, 0, math.radians(-8))
        placed.append((d, x, info))
    me = bpy.data.meshes.new("Floor")
    k = 30
    me.from_pydata([(-k, -k, 0), (k, -k, 0), (k, k, 0), (-k, k, 0)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new("Floor", me)
    fm = bpy.data.materials.new("FloorMat")
    fm.use_nodes = True
    fb = fm.node_tree.nodes["Principled BSDF"]
    fb.inputs["Base Color"].default_value = (0.012, 0.012, 0.014, 1)
    fb.inputs["Roughness"].default_value = 0.3
    me.materials.append(fm)
    bpy.context.scene.collection.objects.link(ob)
    return placed


def lights():
    add_light("Key", (2.2, -3.4, 2.8), (0, 0, 0.5), 1300, 2.4)
    add_light("Fill", (-3.0, -2.4, 1.6), (0, 0, 0.5), 450, 3.0, (0.8, 0.86, 1.0))
    add_light("Rim", (0.8, 3.0, 2.2), (0, 0, 0.6), 900, 2.4, (1.0, 0.82, 0.74))
    add_light("Top", (0, -0.6, 4.0), (0, 0, 0), 300, 3.0)


def label(img_path, out_path, placed, cam, strip=120):
    from PIL import Image, ImageDraw, ImageFont
    sc = bpy.context.scene
    im = Image.open(img_path).convert("RGB")
    W, H = im.size
    sheet = Image.new("RGB", (W, H + strip), (12, 12, 14))
    sheet.paste(im, (0, 0))
    dr = ImageDraw.Draw(sheet)
    en = ImageFont.truetype("/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf", 28)
    ja = ImageFont.truetype("/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf", 20)
    for d, x, info in placed:
        p = world_to_camera_view(sc, cam, Vector((x, 0, 0)))
        cx = p.x * W
        for text, font, y, fill in ((d["nameEn"], en, 16, (240, 236, 228)),
                                    (d["name"], ja, 58, (200, 198, 206)),
                                    (d["style"], ja, 88, (150, 148, 156))):
            w = dr.textlength(text, font=font)
            dr.text((cx - w / 2, H + y), text, font=font, fill=fill)
    sheet.save(out_path, quality=92)
    print("labelled", out_path, flush=True)


VIEWS = {
    # name: kind, spacing, camera, target, lens, res
    "guitars": ("Guitar", 0.52, (0, -4.6, 0.62), (0, 0, 0.5), 60, (2400, 1400)),
    "basses": ("Bass", 0.56, (0, -5.4, 0.72), (0, 0, 0.6), 60, (2400, 1400)),
    "guitar_bodies": ("Guitar", 0.52, (0.3, -4.3, 0.9), (0, 0, 0.25), 60, (2400, 820)),
    "bass_bodies": ("Bass", 0.56, (0.3, -4.5, 0.95), (0, 0, 0.27), 60, (2400, 820)),
}


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument("--renders", default=None)
    ap.add_argument("--viewer-glb", default=None)
    ap.add_argument("--samples", type=int, default=64)
    ap.add_argument("--views", default=",".join(VIEWS))
    a = ap.parse_args(argv)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if a.out:
        export(a.out, make_materials(for_export=True))
        return
    mats = make_materials()
    if a.viewer_glb:
        for n, mat, m in instruments.parts_of(instruments.build_all(), place=False):
            mesh_object(n, m, mats[mat])
        bpy.ops.export_scene.gltf(filepath=a.viewer_glb, export_format="GLB",
                                  export_yup=True, export_normals=True,
                                  export_texcoords=True, export_materials="NONE")
        print("viewer glb", a.viewer_glb, flush=True)
        return
    if a.renders:
        import tempfile
        os.makedirs(a.renders, exist_ok=True)
        tmp = tempfile.mkdtemp()
        for v in a.views.split(","):
            kind, spacing, loc, tgt, lens, res = VIEWS[v]
            clear_scene()
            setup_world()
            placed = stage(mats, kind, spacing)
            lights()
            raw = os.path.join(tmp, v + ".png")
            cam = render(raw, loc, tgt, lens, res, a.samples)
            label(raw, os.path.join(a.renders, "instruments_%s.jpg" % v), placed, cam)


if __name__ == "__main__":
    main()
