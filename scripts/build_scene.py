"""Rebuild the photographed room as editable geometry. Run with Blender --background --python."""

from pathlib import Path
import sys
import math
import random
import json
import argparse
import time

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
# Blender's --python execution needs the repository script directory first.
from common import (  # noqa: E402
    area,
    box,
    collection,
    curve,
    cyl,
    image_material,
    material,
    mesh,
    noise_bump,
    point_camera,
    uvball,
)
from gltf_cleanup import cleanup_unused_tangents  # noqa: E402
from calibration import CALIBRATION  # noqa: E402

P = argparse.ArgumentParser()
P.add_argument(
    "--render", choices=["none", "bedroom", "kitchen", "desk", "overview", "all"], default="none"
)
P.add_argument("--samples", type=int, default=96)
P.add_argument("--resolution", type=int, default=1600)
P.add_argument("--skip-export", action="store_true")
P.add_argument(
    "--output-dir",
    type=Path,
    default=ROOT,
    help="Candidate output root; source textures/config always come from the repository",
)
ARGS = P.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
OUTPUT_ROOT = ARGS.output_dir.resolve()
random.seed(521)
T = ROOT / "assets" / "textures"
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)
for block in list(bpy.data.materials):
    bpy.data.materials.remove(block)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1
M = {}


def setup_materials():
    for key, col, rough, metal in [
        ("wall", (0.73, 0.705, 0.61), 0.84, 0),
        ("ceiling", (0.77, 0.76, 0.71), 0.93, 0),
        ("laminate", (0.59, 0.58, 0.53), 0.43, 0),
        ("counter", (0.76, 0.76, 0.70), 0.35, 0),
        ("black", (0.018, 0.019, 0.016), 0.34, 0),
        ("white", (0.84, 0.84, 0.79), 0.34, 0),
        ("metal", (0.52, 0.54, 0.53), 0.24, 1),
        ("darkmetal", (0.10, 0.105, 0.10), 0.27, 1),
        ("glass", (0.12, 0.17, 0.18), 0.13, 0.6),
        ("navy", (0.016, 0.024, 0.09), 0.28, 0),
        ("fabric_blue", (0.23, 0.38, 0.55), 0.88, 0),
        ("fabric_cream", (0.76, 0.73, 0.64), 0.95, 0),
        ("blinds", (0.64, 0.65, 0.59), 0.42, 0.25),
        ("grout", (0.32, 0.31, 0.27), 0.9, 0),
        ("tilecream", (0.55, 0.535, 0.47), 0.66, 0),
        ("tilegray", (0.40, 0.38, 0.34), 0.65, 0),
        ("taupe", (0.30, 0.29, 0.24), 0.66, 0),
        ("paper", (0.88, 0.87, 0.82), 0.93, 0),
        ("towel", (0.87, 0.86, 0.81), 0.98, 0),
        ("trim", (0.022, 0.024, 0.022), 0.31, 0),
    ]:
        M[key] = material(key, col, rough, metal)
    noise_bump(M["wall"], 185, 0.13, 0.0009)
    noise_bump(M["ceiling"], 145, 0.4, 0.0025)
    noise_bump(M["laminate"], 450, 0.21, 0.0006)
    noise_bump(M["counter"], 160, 0.15, 0.0006)
    noise_bump(M["towel"], 300, 0.5, 0.0011)
    for k in ["tilecream", "tilegray", "taupe"]:
        noise_bump(M[k], 280, 0.3, 0.0009)
    for k in ["fabric_blue", "fabric_cream", "navy"]:
        noise_bump(M[k], 210, 0.2, 0.0007)
    M["oak"] = image_material(
        "Honey oak / CC0 Oak Veneer 01", T / "red_oak_veneer_diff_2k.jpg", 0.32
    )
    n = M["oak"].node_tree.nodes
    links = M["oak"].node_tree.links
    bs = n.get("Principled BSDF")
    img = next(a for a in n if a.type == "TEX_IMAGE")
    # glTF recognizes a modern RGBA Multiply node with factor 1 and a constant
    # color as baseColorFactor. The same calibrated amber finish therefore
    # survives in the native master and the portable browser material.
    mix = n.new("ShaderNodeMix")
    mix.name = "Oak amber stain"
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1
    mix.inputs[7].default_value = (0.80, 0.47, 0.16, 1)
    links.new(img.outputs["Color"], mix.inputs[6])
    links.new(mix.outputs[2], bs.inputs["Base Color"])
    bs.inputs["Coat Weight"].default_value = 0.17
    bs.inputs["Coat Roughness"].default_value = 0.28
    normal = n.new("ShaderNodeTexImage")
    normal.image = bpy.data.images.load(
        str(T / "red_oak_veneer_nor_gl_2k.jpg"), check_existing=True
    )
    normal.image.colorspace_settings.name = "Non-Color"
    normalmap = n.new("ShaderNodeNormalMap")
    normalmap.inputs["Strength"].default_value = 0.23
    links.new(normal.outputs["Color"], normalmap.inputs["Color"])
    links.new(normalmap.outputs["Normal"], bs.inputs["Normal"])
    M["rose"] = image_material("Small roses on cotton", T / "rose_cotton.png", 0.91, (1.6, 1.0, 1))
    noise_bump(M["rose"], 230, 0.18, 0.0007)
    M["floral"] = image_material(
        "Blue floral duvet / reference-informed art", T / "blue_floral_art.png", 0.87, (1, 1, 1)
    )
    noise_bump(M["floral"], 240, 0.22, 0.0007)
    M["carpet"] = image_material("Charcoal woven carpet tile", T / "carpet_weave.png", 0.98)
    noise_bump(M["carpet"], 240, 0.48, 0.0018)
    M["notice"] = image_material("Generic information graphic", T / "door_notice.png", 0.88)
    M["mirror"] = material("Silver mirror", (0.92, 0.94, 0.93), 0.035, 1)
    M["emission"] = material("Prismatic fluorescent diffuser", (0.88, 0.93, 0.90), 0.28)
    bs = M["emission"].node_tree.nodes.get("Principled BSDF")
    bs.inputs["Emission Color"].default_value = (0.91, 0.98, 1, 1)
    bs.inputs["Emission Strength"].default_value = 1.8
    noise_bump(M["emission"], 480, 0.4, 0.001)


def group(name, fn, loc=(0, 0, 0), rz=0):
    collection(name)
    before = set(bpy.data.objects)
    fn()
    made = set(bpy.data.objects) - before
    e = bpy.data.objects.new(name + " / origin", None)
    bpy.context.scene.collection.objects.link(e)
    for o in made:
        if o.parent is None:
            o.parent = e
    e.location = loc
    e.rotation_euler.z = rz
    return e


def panel(name, x, y, z, w, h):
    # Solid oak five-piece raised panel with recessed field and beveled frame.
    box(name + " field", (x, y - 0.009, z), (w - 0.088, 0.032, h - 0.095), M["oak"], 0.006)
    for xx in [x - w / 2 + 0.028, x + w / 2 - 0.028]:
        box(name + " stile", (xx, y + 0.006, z), (0.056, 0.050, h), M["oak"], 0.003)
    for zz in [z - h / 2 + 0.031, z + h / 2 - 0.031]:
        box(name + " rail", (x, y + 0.006, zz), (w - 0.08, 0.050, 0.062), M["oak"], 0.003)
    for xx in [x - w / 2 + 0.063, x + w / 2 - 0.063]:
        box(name + " inner molding", (xx, y + 0.004, z), (0.014, 0.042, h - 0.09), M["oak"], 0.002)
    for zz in [z - h / 2 + 0.065, z + h / 2 - 0.065]:
        box(name + " inner molding", (x, y + 0.004, zz), (w - 0.116, 0.042, 0.014), M["oak"], 0.002)


def cabinet(name, loc, w, d, h, rz=0, drawers=False):
    def create():
        box(name + " carcass", (0, 0, h / 2), (w, d, h - 0.05), M["oak"])
        box(
            name + " toe kick",
            (0, d / 2 - 0.035, 0.05),
            (w - 0.055, 0.075, 0.10),
            M["black"],
            0.001,
        )
        if drawers:
            for i in range(3):
                z = 0.1 + (h - 0.12) / 3 * (i + 0.5)
                box(
                    name + " drawer " + str(i + 1),
                    (0, d / 2 + 0.013, z),
                    (w - 0.028, 0.034, (h - 0.12) / 3 - 0.012),
                    M["oak"],
                    0.009,
                )
                box(
                    name + " finger recess " + str(i),
                    (0, d / 2 + 0.012, z + (h - 0.12) / 6 - 0.025),
                    (w - 0.07, 0.007, 0.016),
                    M["darkmetal"],
                    0.003,
                )
        else:
            for x in [-w / 4, w / 4]:
                panel(name + " door", x, d / 2 + 0.022, h * 0.43 + 0.055, w / 2 - 0.017, h * 0.75)
            box(
                name + " drawer",
                (0, d / 2 + 0.025, h - 0.086),
                (w - 0.027, 0.043, 0.14),
                M["oak"],
                0.009,
            )
        box(
            name + " laminate top",
            (0, 0.014, h + 0.014),
            (w + 0.023, d + 0.036, 0.028),
            M["laminate"],
            0.004,
        )

    return group(name, create, loc, rz)


def vent(name, loc, w, h, rz=0):
    def create():
        box(name + " frame", (0, 0, 0), (w, 0.024, h), M["white"], 0.003)
        box(name + " darkness", (0, 0.014, 0), (w - 0.035, 0.008, h - 0.035), M["black"], 0.001)
        for i in range(max(3, int(h / 0.017))):
            z = -h / 2 + 0.026 + i * (h - 0.048) / (max(3, int(h / 0.017)) - 1)
            b = box(name + " louver", (0, 0.023, z), (w - 0.043, 0.016, 0.005), M["metal"], 0.001)
            b.rotation_euler.x = 0.3
        for x in [-w * 0.32, 0, w * 0.32]:
            box(name + " crossbar", (x, 0.028, 0), (0.004, 0.009, h - 0.04), M["white"], 0.001)

    group(name, create, loc, rz)


def outlet(name, loc, rz=0, switch=False):
    def create():
        box(name + " faceplate", (0, 0, 0), (0.070, 0.006, 0.113), M["metal"], 0.003)
        for z in [-0.027, 0.027]:
            if switch:
                box(name + " toggle", (0, 0.012, z), (0.014, 0.014, 0.027), M["black"], 0.001)
                continue
            uvball(name + " socket", (0, 0.005, z), (0.020, 0.006, 0.022), M["black"])
            for x in [-0.007, 0.007]:
                box(name + " slot", (x, 0.012, z + 0.004), (0.003, 0.002, 0.009), M["taupe"], 0)
            cyl(
                name + " ground",
                (0, 0.013, z - 0.009),
                0.003,
                0.002,
                M["taupe"],
                (math.pi / 2, 0, 0),
            )
        for z in [-0.048, 0.048]:
            cyl(name + " screw", (0, 0.005, z), 0.0022, 0.003, M["metal"], (math.pi / 2, 0, 0))

    group(name, create, loc, rz)


def door(name, loc, rz=0, notice=False):
    def create():
        box(name + " leaf", (0, 0, 1.02), (0.872, 0.042, 2.035), M["oak"], 0.004)
        for x in [-0.465, 0.465]:
            box(name + " jamb", (x, 0, 1.045), (0.044, 0.09, 2.09), M["trim"], 0.002)
        box(name + " head", (0, 0, 2.079), (0.97, 0.09, 0.045), M["trim"], 0.002)
        box(name + " lock plate", (0.31, 0.028, 0.91), (0.066, 0.017, 0.17), M["metal"], 0.004)
        cyl(
            name + " lock barrel",
            (0.31, 0.055, 0.94),
            0.019,
            0.016,
            M["darkmetal"],
            (math.pi / 2, 0, 0),
        )
        curve(
            name + " lever",
            [(0.31, 0.055, 0.87), (0.31, 0.088, 0.87), (0.26, 0.091, 0.858), (0.19, 0.087, 0.858)],
            0.009,
            M["metal"],
        )
        for z in [0.22, 1.02, 1.81]:
            box(name + " hinge", (-0.427, 0.029, z), (0.030, 0.006, 0.095), M["metal"], 0.001)
            cyl(name + " hinge pin", (-0.447, 0.035, z), 0.009, 0.098, M["metal"])
        if notice:
            cyl(
                name + " peephole",
                (0, 0.025, 1.36),
                0.007,
                0.004,
                M["darkmetal"],
                (math.pi / 2, 0, 0),
            )
            mesh(
                name + " generic notice",
                [
                    (-0.10, 0.024, 0.995),
                    (0.10, 0.024, 0.995),
                    (0.10, 0.024, 1.265),
                    (-0.10, 0.024, 1.265),
                ],
                [(0, 1, 2, 3)],
                M["notice"],
                [(0, 0), (1, 0), (1, 1), (0, 1)],
            )
            box(
                name + " closer", (-0.29, 0.065, 1.974), (0.31, 0.075, 0.072), M["darkmetal"], 0.009
            )
            # Two rigid stamped-steel links and their hinge, not a bent tube.
            arm = [
                Vector(p)
                for p in [(-0.31, 0.075, 2.025), (-0.35, 0.24, 2.065), (-0.12, 0.035, 2.085)]
            ]
            for i, (a, b) in enumerate(zip(arm, arm[1:])):
                link = box(
                    name + " closer arm link " + str(i),
                    (a + b) / 2,
                    (0.019, 0.007, (b - a).length),
                    M["darkmetal"],
                    0.001,
                )
                link.rotation_euler = (b - a).to_track_quat("Z", "Y").to_euler()
            for i, co in enumerate(arm):
                cyl(name + " closer hinge " + str(i), co, 0.010, 0.009, M["metal"])

    group(name, create, loc, rz)


def architecture():
    collection("01 / Architecture")
    box("Shell_Foundation", (0, 2.075, -0.06), (3.18, 4.33, 0.12), M["grout"], 0)
    # Two distinct floors with aligned 0.5 m carpet tiles and 0.305 m resilient tiles.
    for i in range(6):
        for j in range(7):
            x = -1.25 + i * 0.5
            y = 1.0 + j * 0.5
            dep = min(0.5, 4.15 - (y - 0.25))
            if dep <= 0:
                continue
            b = box(
                "Floor_Carpet_%d_%d" % (i, j),
                (x, y - 0.25 + dep / 2, 0.015),
                (0.4997, dep - 0.0003, 0.006),
                M["carpet"],
                0.00008,
            )
            b.rotation_euler.z = (i + j) % 2 * math.pi / 2 if dep == 0.5 else 0
    for i in range(10):
        for j in range(3):
            x = -1.35 + i * 0.30
            tile_depth = 0.30 if j < 2 else 0.15
            y = j * 0.30 + tile_depth / 2
            box(
                "Floor_Vinyl_%d_%d" % (i, j),
                (x, y, 0.007),
                (0.2995, tile_depth - 0.0005, 0.014),
                M["tilegray" if (i + j * 3) % 7 in [1, 4] else "tilecream"],
                0.0005,
            )
    box("Floor_Transition", (0, 0.756, 0.021), (3, 0.017, 0.020), M["trim"], 0.002)
    box("Shell_Wall_Front_Header", (0, -0.075, 2.46), (3.16, 0.15, 0.72), M["wall"], 0)
    box("Shell_Wall_Front_Kitchen", (0.59, -0.075, 1.05), (1.82, 0.15, 2.1), M["wall"], 0)
    box("Shell_Wall_Front_Left", (-1.43, -0.075, 1.05), (0.14, 0.15, 2.1), M["wall"], 0)
    box("Shell_Wall_Right", (1.575, 2.075, 1.41), (0.15, 4.30, 2.82), M["wall"], 0)
    # Left wall has a recessed sink at y .14-.97 and an interior door at y1.29-2.25.
    for ya, yb in [(0, 0.13), (0.99, 1.28), (2.27, 4.15)]:
        box(
            "Shell_Wall_Left_" + str(ya),
            (-1.575, (ya + yb) / 2, 1.41),
            (0.15, yb - ya, 2.82),
            M["wall"],
            0,
        )
    box("Shell_Wall_Left_DoorHeader", (-1.575, 1.775, 2.455), (0.15, 1.01, 0.73), M["wall"], 0)
    box("Shell_Wall_Left_AlcoveHeader", (-1.575, 0.56, 2.58), (0.15, 0.86, 0.48), M["wall"], 0)
    box("Shell_Wall_Alcove_Back", (-2.05, 0.56, 1.41), (0.15, 0.98, 2.82), M["wall"], 0)
    for y in [0.07, 1.05]:
        # Terminate against the left-wall segment rather than overlapping it.
        # The old coplanar double surface produced a pitch-black strip in Cycles.
        box("Shell_Wall_Alcove_Return", (-1.85, y, 1.41), (0.40, 0.12, 2.82), M["wall"], 0)
    box("Floor_Alcove", (-1.77, 0.56, 0.008), (0.55, 0.89, 0.016), M["tilecream"], 0)
    # Window aperture, reveals, steel frame and sill.
    for x in [-1.065, 1.065]:
        box("Shell_Wall_Back_Pier", (x, 4.225, 1.41), (0.87, 0.15, 2.82), M["wall"], 0)
    box("Shell_Wall_Back_UnderWindow", (0, 4.225, 0.465), (1.26, 0.15, 0.93), M["wall"], 0)
    box("Shell_Wall_Back_OverWindow", (0, 4.225, 2.535), (1.26, 0.15, 0.57), M["wall"], 0)
    box("Shell_Ceiling", (0, 2.075, 2.87), (3.18, 4.33, 0.10), M["ceiling"], 0)
    for x in [-1.488, 1.488]:
        if x > 0:
            box("Baseboard_right", (x, 2.075, 0.047), (0.023, 4.15, 0.094), M["trim"], 0.002)
        else:
            for a, b in [(0, 0.12), (0.99, 1.26), (2.28, 4.15)]:
                box(
                    "Baseboard_left",
                    (x, (a + b) / 2, 0.047),
                    (0.023, b - a, 0.094),
                    M["trim"],
                    0.002,
                )
    box("Baseboard_back", (0, 4.139, 0.047), (3, 0.025, 0.094), M["trim"], 0.002)
    box("Baseboard_front", (0.58, 0.011, 0.047), (1.82, 0.025, 0.094), M["trim"], 0.002)
    for x in [-0.647, 0.647]:
        box("Window_Frame_side", (x, 4.175, 1.59), (0.033, 0.065, 1.35), M["metal"], 0.002)
    for z in [0.918, 2.262]:
        box("Window_Frame_rail", (0, 4.175, z), (1.33, 0.065, 0.034), M["metal"], 0.002)
    box("Window_Sill", (0, 4.108, 0.917), (1.39, 0.24, 0.026), M["laminate"], 0.004)
    box("Window_Glass", (0, 4.232, 1.59), (1.24, 0.008, 1.3), M["glass"], 0.001)
    box("Blind_Headrail", (0, 4.119, 2.231), (1.25, 0.045, 0.035), M["blinds"], 0.003)
    slat_count = CALIBRATION["window"].get("blind_slats", 68)
    slat_step = (2.197 - 0.9648) / (slat_count - 1)
    for i in range(slat_count):
        z = 2.197 - i * slat_step
        b = box("Blind_Slat_%02d" % i, (0, 4.102, z), (1.231, 0.025, 0.0013), M["blinds"], 0.0005)
        b.rotation_euler.x = math.radians(64)
    box("Blind_Bottomrail", (0, 4.092, 0.947), (1.239, 0.03, 0.018), M["blinds"], 0.002)
    for x in [-0.47, 0.0, 0.47]:
        curve(
            "Blind_Ladder_cord",
            [(x, 4.083, 2.224), (x, 4.077, 1.59), (x, 4.071, 0.948)],
            0.0011,
            M["fabric_cream"],
        )
        for i in range(0, slat_count, 2):
            curve(
                "Blind_Ladder_rung",
                [
                    (x - 0.003, 4.08, 2.197 - i * slat_step),
                    (x + 0.003, 4.115, 2.197 - i * slat_step - 0.01),
                ],
                0.0006,
                M["fabric_cream"],
            )
    curve(
        "Blind_Pull_cord",
        [(0.56, 4.085, 2.22), (0.56, 4.065, 1.42), (0.552, 4.06, 1.35)],
        0.0012,
        M["fabric_cream"],
    )
    uvball("Blind_Pull_end", (0.552, 4.06, 1.35), (0.006, 0.006, 0.014), M["white"])
    door("Entry_Door", (-0.85, 0.01, 0), 0, True)
    door("Interior_Door", (-1.49, 1.775, 0), -math.pi / 2, False)
    for x in [-0.35, 1.17]:
        box("Wall_Panel_seam", (x, 0.001, 2.45), (0.0017, 0.001, 0.7), M["taupe"], 0)
    outlet("Kitchen_Outlet_A", (0.0, 0.009, 1.14))
    outlet("Kitchen_Outlet_B", (0.53, 0.009, 1.14))
    outlet("Entry_Switch", (-0.3, 0.009, 1.14), switch=True)
    vent("Front_Vent", (-1.0, 0.016, 2.63), 0.19, 0.15)
    vent("Bed_Vent", (-1.488, 3.55, 1.85), 0.29, 0.34, -math.pi / 2)
    group(
        "Service_Panel",
        lambda: box("Service_Panel_cover", (0, 0, 0), (0.47, 0.013, 0.96), M["white"], 0.007),
        (-1.478, 3.54, 0.88),
        -math.pi / 2,
    )
    vent("Service_Grille", (-1.46, 3.54, 0.5), 0.41, 0.20, -math.pi / 2)
    cyl("Thermostat_back", (-1.46, 3.54, 1.50), 0.059, 0.027, M["white"], (0, math.pi / 2, 0))
    cyl("Thermostat_dial", (-1.439, 3.54, 1.50), 0.035, 0.020, M["metal"], (0, math.pi / 2, 0))
    outlet("Bed_Outlet_Right", (1.487, 3.46, 0.32), math.pi / 2)
    outlet("Dresser_Outlet", (-1.485, 2.85, 0.36), -math.pi / 2)
    collection("02 / Lights and hardware")
    box("Ceiling_Light_housing", (0, 1.97, 2.775), (0.33, 1.24, 0.09), M["white"], 0.016)
    box("Ceiling_Light_diffuser", (0, 1.97, 2.724), (0.305, 1.20, 0.023), M["emission"], 0.008)
    for x in [-0.07, 0.07]:
        box("Ceiling_Light_tube", (x, 1.97, 2.725), (0.026, 1.13, 0.026), M["emission"], 0.012)
    cyl("Smoke_detector", (0, 2.87, 2.78), 0.069, 0.041, M["white"])
    for i in range(8):
        a = i * math.tau / 8
        box(
            "Smoke_detector_slot",
            (math.cos(a) * 0.043, 2.87 + math.sin(a) * 0.043, 2.756),
            (0.013, 0.003, 0.002),
            M["taupe"],
            0.001,
        )
    # True reflective full-length mirror on the shallow alcove jamb.
    box("Mirror_full_back", (-1.478, 1.132, 1.27), (0.018, 0.267, 1.66), M["metal"], 0.001)
    box("Mirror_full_surface", (-1.464, 1.132, 1.27), (0.003, 0.257, 1.646), M["mirror"], 0.001)


def kitchen():
    before_kitchen = set(bpy.data.objects)
    cabinet("Kitchen_Base", (0.23, 0.30, 0), 0.93, 0.56, 0.89)
    collection("03 / Kitchen")
    box("Kitchen_Counter", (0.59, 0.305, 0.918), (1.66, 0.642, 0.044), M["counter"], 0.009)
    box("Kitchen_BackSplash", (0.59, 0.026, 0.98), (1.66, 0.024, 0.123), M["counter"], 0.002)
    box("Kitchen_EndSupport", (1.395, 0.30, 0.456), (0.037, 0.57, 0.91), M["oak"], 0.003)
    box("Hob_enamel", (0.11, 0.35, 0.948), (0.54, 0.44, 0.014), M["white"], 0.018)
    for x, r in [(-0.03, 0.071), (0.21, 0.092)]:
        cyl("Hob_recess", (x, 0.337, 0.958), r + 0.006, 0.005, M["darkmetal"])
        pts = []
        for i in range(260):
            t = i / 259
            rr = 0.013 + t * (r - 0.018)
            a = t * math.tau * 4.8
            pts.append((x + rr * math.cos(a), 0.337 + rr * math.sin(a), 0.964))
        curve("Hob_spiral_heating_element", pts, 0.0036, M["black"])
    for x in [-0.07, 0.10]:
        cyl("Hob_control", (x, 0.526, 0.963), 0.025, 0.012, M["white"])
    # Refrigerator: rounded enameled two-door unit, separate gasket, recessed handles.
    box("Fridge_housing", (0.99, 0.325, 0.423), (0.472, 0.526, 0.822), M["white"], 0.013)
    box("Fridge_gasket", (0.99, 0.596, 0.447), (0.457, 0.014, 0.775), M["taupe"], 0.022)
    for z, h in [(0.335, 0.53), (0.724, 0.222)]:
        box("Fridge_door", (0.99, 0.613, z), (0.454, 0.047, h), M["white"], 0.011)
    box("Fridge_division", (0.99, 0.641, 0.606), (0.43, 0.005, 0.009), M["taupe"], 0.002)
    box("Fridge_handle", (0.99, 0.646, 0.624), (0.331, 0.023, 0.014), M["white"], 0.006)
    cyl("Fridge_badge", (0.99, 0.641, 0.18), 0.015, 0.003, M["metal"], (math.pi / 2, 0, 0))
    # Upper raised-panel cabinetry with the asymmetric microwave niche.
    box("Upper_Left_body", (0.17, 0.178, 2.127), (0.80, 0.33, 0.303), M["oak"])
    for x in [-0.03, 0.37]:
        panel("Upper_Left_door", x, 0.35, 2.127, 0.39, 0.292)
    box("Upper_Right_body", (0.98, 0.178, 1.915), (0.77, 0.33, 0.725), M["oak"])
    for x in [0.79, 1.17]:
        panel("Upper_Right_door", x, 0.35, 1.915, 0.37, 0.704)
    box("Microwave_body", (0.17, 0.225, 1.775), (0.789, 0.399, 0.36), M["white"], 0.029)
    box("Microwave_front", (0.17, 0.435, 1.756), (0.76, 0.032, 0.294), M["white"], 0.023)
    box("Microwave_window", (0.079, 0.456, 1.77), (0.49, 0.007, 0.191), M["taupe"], 0.034)
    box("Microwave_window_inner", (0.079, 0.461, 1.77), (0.452, 0.004, 0.161), M["glass"], 0.032)
    # Mesh screen pinholes add scale without duplicating thousands of objects.
    curve(
        "Microwave_handle",
        [(0.348, 0.472, 1.899), (0.334, 0.505, 1.858), (0.334, 0.52, 1.68), (0.35, 0.473, 1.624)],
        0.014,
        M["white"],
    )
    box("Microwave_display", (0.45, 0.459, 1.866), (0.087, 0.004, 0.027), M["darkmetal"], 0.003)
    for row in range(7):
        for col in range(3):
            box(
                "Microwave_key",
                (0.414 + col * 0.028, 0.461, 1.824 - row * 0.019),
                (0.019, 0.005, 0.008),
                M["laminate"],
                0.002,
            )
    for i in range(6):
        box(
            "Microwave_top_vent",
            (0.17, 0.435, 1.929 + i * 0.007),
            (0.70, 0.009, 0.003),
            M["taupe"],
            0.001,
        )
    from appliance_details import microwave_details

    microwave_details(M)
    # Photo-facing order: hob/microwave at the outer corner, fridge/tall upper
    # doors toward entry. Reflect the assembly around its countertop midpoint.
    kitchen_objects = set(bpy.data.objects) - before_kitchen
    for ob in kitchen_objects:
        if ob.parent not in kitchen_objects:
            ob.location.x = 1.18 - ob.location.x
            ob.scale.x *= -1

    # Sink in recessed alcove; physically modeled basin and separate countertop rim.
    def sink_unit():
        # Hollow case: a solid cabinet cube would fill the basin below z=.854.
        for x in (-0.411, 0.411):
            box("Sink_Base_side", (x, 0, 0.427), (0.018, 0.53, 0.854), M["oak"], 0.003)
        box("Sink_Base_back", (0, -0.256, 0.427), (0.804, 0.018, 0.854), M["oak"], 0.003)
        box("Sink_Base_bottom", (0, 0, 0.035), (0.804, 0.494, 0.018), M["oak"], 0.003)
        box("Sink_Base_front_rail", (0, 0.246, 0.825), (0.804, 0.036, 0.058), M["oak"], 0.003)
        for x in [-0.21, 0.21]:
            panel("Sink_Base_door", x, 0.277, 0.436, 0.404, 0.778)
        box("Sink_toekick", (0, 0.22, 0.05), (0.79, 0.05, 0.10), M["black"], 0.001)
        # Four rim slabs leave a real opening.
        for x in [-0.333, 0.333]:
            box("Sink_counter_side", (x, 0.015, 0.882), (0.204, 0.58, 0.041), M["counter"], 0.006)
        for y in [-0.219, 0.246]:
            box("Sink_counter_end", (0, y, 0.882), (0.49, 0.115, 0.041), M["counter"], 0.006)
        box("Sink_backsplash", (0, -0.264, 0.943), (0.87, 0.02, 0.13), M["counter"], 0.002)
        # Rounded rectangular basin cross sections; top rim, curved walls and bottom.
        rings = [
            (0.253, 0.205, 0.905),
            (0.226, 0.177, 0.897),
            (0.211, 0.165, 0.864),
            (0.196, 0.15, 0.733),
            (0.176, 0.13, 0.711),
        ]
        verts = []
        faces = []
        N = 64
        for sx, sy, z in rings:
            for i in range(N):
                a = i * math.tau / N
                co = math.cos(a)
                si = math.sin(a)
                verts.append(
                    (
                        sx * math.copysign(abs(co) ** 0.33, co),
                        sy * math.copysign(abs(si) ** 0.33, si),
                        z,
                    )
                )
        for j in range(len(rings) - 1):
            for i in range(N):
                faces.append(
                    (j * N + i, j * N + (i + 1) % N, (j + 1) * N + (i + 1) % N, (j + 1) * N + i)
                )
        faces.append(tuple(range((len(rings) - 1) * N, len(rings) * N)))
        mesh("Sink_stainless_basin", verts, faces, M["metal"], smooth=True)
        cyl("Sink_drain", (0, 0, 0.713), 0.024, 0.003, M["darkmetal"])
        cyl("Sink_drain_strainer", (0, 0, 0.715), 0.019, 0.003, M["metal"])
        for i in range(8):
            a = i * math.tau / 8
            cyl(
                "Sink_strainer_hole",
                (0.013 * math.cos(a), 0.013 * math.sin(a), 0.717),
                0.002,
                0.001,
                M["black"],
            )
        box("Faucet_base", (0, -0.217, 0.909), (0.174, 0.045, 0.018), M["metal"], 0.009)
        curve(
            "Faucet_gooseneck",
            [
                (0, -0.218, 0.92),
                (0, -0.218, 1.07),
                (0, -0.19, 1.122),
                (0, -0.13, 1.12),
                (0, -0.113, 1.061),
            ],
            0.012,
            M["metal"],
        )
        for x in [-0.064, 0.064]:
            cyl("Tap_base", (x, -0.217, 0.928), 0.02, 0.019, M["metal"])
            curve(
                "Tap_lever",
                [
                    (x, -0.217, 0.939),
                    (x, -0.207, 0.957),
                    (x + (0.035 if x > 0 else -0.035), -0.192, 0.957),
                ],
                0.006,
                M["metal"],
            )
        box("Sink_mirror_frame", (0, -0.273, 1.654), (0.43, 0.028, 0.59), M["metal"], 0.003)
        box("Sink_mirror", (0, -0.254, 1.654), (0.417, 0.004, 0.577), M["mirror"], 0.001)
        box("Sink_wall_light", (0, -0.233, 2.187), (0.64, 0.09, 0.108), M["metal"], 0.006)
        box("Sink_wall_diffuser", (0, -0.18, 2.187), (0.611, 0.013, 0.083), M["emission"], 0.003)
        # A soap dispenser and toothpaste packet.
        uvball("Soap_bottle", (0.33, -0.06, 0.994), (0.040, 0.026, 0.093), M["white"])
        cyl("Soap_neck", (0.33, -0.06, 1.08), 0.014, 0.02, M["navy"])
        box("Soap_pump", (0.32, -0.06, 1.099), (0.054, 0.016, 0.012), M["navy"], 0.003)
        box("Toothpaste", (-0.337, 0.012, 0.916), (0.057, 0.16, 0.024), M["white"], 0.009)
        box("Toothpaste_label", (-0.337, 0.012, 0.931), (0.039, 0.104, 0.001), M["navy"], 0.001)

    group("04 / Sink alcove", sink_unit, (-1.72, 0.56, 0), -math.pi / 2)


def furniture():
    cabinet("Dresser", (-1.172, 2.585, 0), 0.956, 0.606, 0.865, -math.pi / 2, True)

    def wardrobe():
        box("Wardrobe_body", (0, 0, 0.914), (0.86, 0.53, 1.828), M["oak"], 0.005)
        box("Wardrobe_cap", (0, 0.006, 1.837), (0.884, 0.55, 0.023), M["laminate"], 0.004)
        for x in [-0.218, 0.218]:
            box("Wardrobe_slab_door", (x, 0.278, 0.921), (0.419, 0.024, 1.797), M["oak"], 0.003)
            for z in [0.2, 1.65]:
                box(
                    "Wardrobe_hinge",
                    (math.copysign(0.419, x), 0.294, z),
                    (0.018, 0.009, 0.055),
                    M["metal"],
                    0.002,
                )

    group("05 / Wardrobe", wardrobe, (1.212, 2.683, 0), math.pi / 2)

    def desk():
        box("Desk_top", (0, 0, 0.752), (1.12, 0.645, 0.031), M["laminate"], 0.005)
        box("Desk_top_oak_edge", (0, 0.324, 0.751), (1.12, 0.016, 0.038), M["oak"], 0.004)
        for x in [-0.538, 0.25]:
            box("Desk_vertical", (x, -0.004, 0.362), (0.030, 0.582, 0.724), M["oak"], 0.003)
        box("Desk_outer_right", (0.544, 0, 0.362), (0.029, 0.595, 0.724), M["oak"], 0.003)
        box("Desk_back", (0, -0.29, 0.421), (1.07, 0.024, 0.615), M["oak"], 0.001)
        box("Desk_drawer", (0.399, 0.30, 0.641), (0.266, 0.045, 0.182), M["oak"], 0.005)
        for z in [0.08, 0.358]:
            box("Desk_open_shelf", (0.4, -0.02, z), (0.265, 0.57, 0.026), M["oak"], 0.002)
        box("Desk_pencil_apron", (-0.139, 0.30, 0.699), (0.76, 0.037, 0.07), M["oak"], 0.004)
        box(
            "Desk_pencil_recess",
            (-0.139, 0.322, 0.721),
            (0.54, 0.005, 0.019),
            M["darkmetal"],
            0.005,
        )
        for z in [0.392, 0.406]:
            box("Desk_notebook", (0.4, 0.006, z), (0.22, 0.32, 0.012), M["paper"], 0.004)

    desk_root = group("06 / Writing desk", desk, (1.163, 1.633, 0), math.pi / 2)
    desk_root.scale.x = -1  # Pedestal is toward the kitchenette in the references.


def cloth_grid(name, fn, mat, nu=120, nv=85):
    vs = []
    uv = []
    fs = []
    for j in range(nv + 1):
        for i in range(nu + 1):
            u = i / nu
            v = j / nv
            vs.append(fn(u, v))
            uv.append((u, v))
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            fs.append((a, a + 1, a + nu + 2, a + nu + 1))
    ob = mesh(name, vs, fs, mat, uv, True)
    s = ob.modifiers.new("Cloth thickness", "SOLIDIFY")
    s.thickness = 0.002
    s = ob.modifiers.new("Soft fabric subdivision", "SUBSURF")
    s.levels = 1
    return ob


def bedding():
    collection("07 / Bed and textiles")
    # Official Yudof mattress: 36 x 80 inches. Two tall oak end frames.
    for x in [-1.07, 1.07]:
        for y in [3.092, 4.08]:
            box("Bed_4x4_post", (x, y, 0.88), (0.069, 0.073, 1.76), M["oak"], 0.004)
            box(
                "Bed_mortise_slot",
                (x - math.copysign(0.036, x), y, 0.995),
                (0.003, 0.016, 1.18),
                M["black"],
                0.003,
            )
            for z in [0.43, 0.78, 1.15, 1.59]:
                cyl(
                    "Bed_bolt",
                    (x - math.copysign(0.038, x), y, z),
                    0.005,
                    0.003,
                    M["darkmetal"],
                    (0, math.pi / 2, 0),
                )
        for z in [0.22, 0.79, 1.16, 1.61]:
            box("Bed_end_ladder_rail", (x, 3.585, z), (0.039, 0.944, 0.064), M["oak"], 0.003)
    for y in [3.11, 4.04]:
        box("Bed_support_steel", (0, y, 0.392), (2.12, 0.026, 0.055), M["darkmetal"], 0.003)
    box("Mattress", (0, 3.586, 0.539), (2.032, 0.9144, 0.208), M["fabric_cream"], 0.065)
    for z in [0.446, 0.631]:
        curve(
            "Mattress_piping",
            [
                (-0.96, 3.15, z),
                (0.96, 3.15, z),
                (1.01, 3.2, z),
                (1.01, 3.97, z),
                (0.96, 4.027, z),
                (-0.96, 4.027, z),
                (-1.01, 3.98, z),
                (-1.01, 3.2, z),
                (-0.96, 3.15, z),
            ],
            0.003,
            M["white"],
        )

    from textiles_v2 import build_bedding

    build_bedding(M)

    # Black steel safety rail with the familiar oak cap.
    for x in [-0.16, 0.16]:
        box("Bed_guard_upright", (x, 3.005, 0.62), (0.03, 0.035, 0.48), M["black"], 0.006)
    box("Bed_guard_panel", (0, 3.005, 0.812), (0.71, 0.038, 0.123), M["black"], 0.009)
    box("Bed_guard_oak_cap", (0, 3.005, 0.881), (0.747, 0.052, 0.02), M["oak"], 0.005)
    # Clip-on flexible bedside reading light.
    box("Bed_clip_light_mount", (1.014, 3.73, 0.88), (0.045, 0.047, 0.09), M["white"], 0.007)
    curve(
        "Bed_clip_light_flex",
        [(1.015, 3.72, 0.88), (0.87, 3.7, 0.85), (0.84, 3.52, 0.75), (0.9, 3.43, 0.70)],
        0.006,
        M["white"],
    )
    uvball("Bed_clip_light_head", (0.901, 3.427, 0.70), (0.022, 0.049, 0.010), M["white"])


def lighting_and_cameras():
    collection("09 / Camera rig")
    area("Light_Fluorescent", (0, 1.97, 2.68), (0, 1.97, 0), 80, (1, 0.956, 0.88), 0.27, 1.14)
    area("Light_Window", (0, 4.13, 1.7), (0, 1.3, 1), 14, (0.74, 0.84, 1), 1.14, 1.14)
    area("Light_Sink", (-1.85, 0.56, 2.15), (-1.4, 0.56, 0.8), 12, (1, 0.95, 0.85), 0.51, 0.09)
    world = bpy.data.worlds.new("Low ambient studio exterior")
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes.get("Background").inputs[0].default_value = (0.46, 0.53, 0.62, 1)
    world.node_tree.nodes.get("Background").inputs[1].default_value = 0.15
    cams = {
        "bedroom": point_camera("Camera_Bedroom", (-0.15, 0.67, 1.66), (0, 3.33, 1.04), 21),
        "kitchen": point_camera("Camera_Kitchen", (-0.15, 2.91, 1.62), (-0.09, 0.28, 1.16), 21),
        "desk": point_camera("Camera_Desk", (-0.65, 1.21, 1.54), (1.11, 1.88, 0.91), 30),
        "overview": point_camera("Camera_Overview", (-5.1, -4.7, 6.4), (0, 2.12, 0.64), 42),
    }
    from architecture_v2 import apply_matched_camera
    from lighting_v2 import refine_lighting

    for name, record in CALIBRATION["cameras"].items():
        apply_matched_camera(cams[name], record)
    for number, record in CALIBRATION.get("reference_cameras", {}).items():
        cam = point_camera(
            "Camera_Reference_" + number.zfill(2), record["position"], (0, 2, 1), record["lens_mm"]
        )
        apply_matched_camera(cam, record)
        cam["reference_number"] = int(number)
        cam["calibration_method"] = "shared-intrinsic COLMAP SfM plus constrained room alignment"
    bpy.data.objects["Light_Fluorescent"].location.z += CALIBRATION["room"]["height"] - 2.82
    refine_lighting()
    scene.camera = cams["bedroom"]
    for name, cam in cams.items():
        marker = scene.timeline_markers.new(name, frame=list(cams).index(name) * 60 + 1)
        marker.camera = cam
    return cams


def validate_and_manifest(cameras, bed_support=None):
    meshes = [o for o in scene.objects if o.type == "MESH"]
    data = {
        "title": "Room Replica / Observed everyday interior",
        "units": "meters",
        "seed": 521,
        "dimensions": {
            "width": CALIBRATION["room"]["width"],
            "length": CALIBRATION["room"]["length"],
            "height": CALIBRATION["room"]["height"],
            "status": "photo-estimated",
            "mattress": [2.032, 0.9144, 0.208],
            "mattress_source": "https://housing.umn.edu/yudof",
            "resolved_bed_support": bed_support,
        },
        "objects": len(scene.objects),
        "meshes": len(meshes),
        "materials": len(bpy.data.materials),
        "vertices_base": sum(len(o.data.vertices) for o in meshes),
        "cameras": {
            name: {
                "position": list(o.location),
                "rotation_euler": list(o.rotation_euler),
                "lens_mm": o.data.lens,
            }
            for name, o in cameras.items()
        },
        "reference_cameras": {
            o.name: {
                "position": list(o.location),
                "rotation_euler": list(o.rotation_euler),
                "lens_mm": o.data.lens,
                "method": o.get("fit_status", o.get("calibration_method", "unclassified")),
                "fit_rmse_px": o.get("fit_rmse_px"),
                "held_out_rmse_px": o.get("held_out_rmse_px"),
                "fit_geometry_status": o.get("fit_geometry_status"),
                "residuals_apply_to_current_geometry": o.get("residuals_apply_to_current_geometry"),
                "exposure_ev": o.get("exposure_ev"),
            }
            for o in scene.objects
            if o.type == "CAMERA" and o.name.startswith("Camera_Reference_")
        },
        "engine": "Cycles",
        "blender_version": bpy.app.version_string,
        "notes": [
            "Authored editable geometry constrained by multi-view photo reconstruction; not a dense photogrammetry mesh.",
            "Room envelope is an estimate; official mattress dimensions anchor scale.",
            "Original photos and screen content are excluded from public assets.",
            "Browser glTF is a simplified material representation; Cycles renders are the visual master.",
        ],
    }
    assert all(math.isfinite(v) for o in meshes for v in o.location), "Nonfinite object position"
    assert len(meshes) > 300, "Incomplete scene"
    (OUTPUT_ROOT / "scene" / "scene-manifest.json").write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )
    return data


def render_views(cameras):
    """Use the same camera logic and auditable statistics as saved-scene renders."""
    import render as saved_renderer

    saved_renderer.ROOT = OUTPUT_ROOT

    # main() has already saved the packed master and preserved these named
    # cameras. Calling the shared renderer keeps both documented workflows
    # compatible with final delivery checks without rebuilding a second time.
    saved_renderer.main(
        [
            "--view",
            ARGS.render,
            "--resolution",
            str(ARGS.resolution),
            "--samples",
            str(ARGS.samples),
            "--threads",
            "12",
        ]
    )


def main():
    t = time.time()
    for subdirectory in ("scene", "renders"):
        (OUTPUT_ROOT / subdirectory).mkdir(parents=True, exist_ok=True)
    setup_materials()
    from materials_v2 import apply_material_upgrades

    apply_material_upgrades(M, T)
    from cotton_relief_v3 import refine_cotton_relief

    refine_cotton_relief(list(M.values()))
    architecture()
    from architecture_v2 import refine_architecture

    refine_architecture(M)
    kitchen()
    furniture()
    bedding()
    import props

    props.build(
        {"box": box, "uvball": uvball, "cyl": cyl, "curve": curve, "M": M, "collection": collection}
    )
    from soft_packages_v3 import refine_soft_packages

    refine_soft_packages(M)
    from floor_prop_details_v3 import refine_floor_prop_geometry

    refine_floor_prop_geometry(M)
    from fittings_v2 import refine_fittings

    refine_fittings(M)
    from layout_v3 import refine_layout

    refine_layout(M)
    from desktop_pose_v4 import refine_desktop_pose

    refine_desktop_pose(M)
    from desktop_surface_v4 import refine_desktop_surfaces

    refine_desktop_surfaces()
    from desktop_packages_v5 import refine_desktop_packages

    refine_desktop_packages()
    from desktop_package_capture_v6 import refine_desktop_package_capture

    refine_desktop_package_capture()
    from counter_props_v4 import refine_counter_props

    refine_counter_props(M)
    from puffer_shape_v5 import rebuild_puffer_shape

    rebuild_puffer_shape()
    from puffer_shape_v6 import refine_puffer_shape

    refine_puffer_shape()
    from bed_support_v4 import refine_bed_support

    bed_support = refine_bed_support(CALIBRATION["bed_support"]["parameters"])
    from bedding_surface_v5 import refine_bedding_surface

    refine_bedding_surface()
    from bedding_print_v6 import refine_bedding_print

    refine_bedding_print()
    from rail_shirt_v5 import refine_rail_shirt_v5

    refine_rail_shirt_v5(M, CALIBRATION["right_bed_rails"]["parameters"])
    from bed_guard_v4 import refine_bed_guard

    refine_bed_guard()
    from carpet_material_v3 import refine_carpet_material

    refine_carpet_material(M["carpet"], T)
    from vinyl_layout_v4 import refine_vinyl_layout
    from vinyl_material_v4 import refine_vinyl_material

    vinyl = CALIBRATION["vinyl_grid"]
    refine_vinyl_layout(M, CALIBRATION["room"], vinyl["parameters"], vinyl["observed_gray_cells"])
    refine_vinyl_material(M)
    from backpack_shape_v3 import refine_backpack_shape

    refine_backpack_shape(M)
    from backpack_surface_v4 import refine_backpack_surface

    refine_backpack_surface()
    from chair_pillow_v4 import refine_chair_pillow

    refine_chair_pillow(M)
    from chair_pillow_finish_v4 import refine_chair_pillow_finish

    refine_chair_pillow_finish(M)
    from cabinet_profiles_v4 import refine_cabinet_profiles

    refine_cabinet_profiles()
    from wood_materials_v3 import refine_wood_materials
    from wood_uv_v3 import refine_wood_uvs

    refine_wood_materials(M, T)
    refine_wood_uvs()
    from wood_photo_v4 import refine_photo_wood

    refine_photo_wood(M)
    from dresser_photo_v5 import refine_dresser_wood

    refine_dresser_wood()
    from window_details_v3 import refine_blinds

    refine_blinds()
    cameras = lighting_and_cameras()
    from reference_cameras_v4 import add_manual_reference_cameras_v4

    add_manual_reference_cameras_v4()
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = max(96, ARGS.samples)
    scene.cycles.use_denoising = True
    scene.cycles.adaptive_threshold = 0.02
    scene.cycles.max_bounces = 10
    scene.cycles.diffuse_bounces = 5
    scene.cycles.glossy_bounces = 5
    scene.cycles.transmission_bounces = 6
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 12
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.0
    scene.render.resolution_x = 1600
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.quality = 95
    manifest = validate_and_manifest(cameras, bed_support)
    # Embed textures so the native master opens on any machine.
    bpy.ops.file.pack_all()
    for screen in bpy.data.screens:
        for a in screen.areas:
            if a.type == "VIEW_3D":
                a.spaces.active.region_3d.view_perspective = "CAMERA"
                a.spaces.active.overlay.show_overlays = False
    bpy.ops.wm.save_as_mainfile(filepath=str(OUTPUT_ROOT / "scene" / "room.blend"), compress=True)
    print("SCENE_READY", json.dumps(manifest), flush=True)
    if not ARGS.skip_export:
        dest = OUTPUT_ROOT / "demo" / "public" / "models"
        dest.mkdir(parents=True, exist_ok=True)
        # Keep the same oak stain graph: its constant Multiply exports as a
        # portable glTF baseColorFactor, preserving the Cycles amber finish.
        bpy.ops.export_scene.gltf(
            filepath=str(dest / "room.glb"),
            export_format="GLB",
            use_selection=False,
            export_apply=True,
            export_tangents=True,
            export_lights=False,
            export_cameras=True,
            export_extras=True,
            export_image_format="AUTO",
        )
        print(
            "GLB_TANGENT_CLEANUP",
            json.dumps(cleanup_unused_tangents(dest / "room.glb")),
            flush=True,
        )
        print("GLB_READY", flush=True)
    if ARGS.render != "none":
        render_views(cameras)
    print("FINISHED_SECONDS", round(time.time() - t, 1), flush=True)


if __name__ == "__main__":
    main()
