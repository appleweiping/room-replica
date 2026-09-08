"""Apply multi-view geometry estimates to the authored furniture assemblies.

The calibration is a constrained architectural hypothesis, not a measured scan.
Transforms explicitly start from the v2 construction coordinates. Existing
furniture detailing stays editable; dimensions and camera poses live in JSON.
"""

import math
import bpy
from mathutils import Matrix
from common import box, collection, curve
from calibration import CALIBRATION


def transform(objects, matrix):
    members = set(objects)
    for obj in members:
        if obj.parent not in members:
            obj.matrix_world = matrix @ obj.matrix_world


def assembly(name, matrix):
    group = bpy.data.collections.get(name)
    if group:
        transform(group.all_objects, matrix)


def affine(old, new, scale=(1, 1, 1)):
    return (
        Matrix.Translation(new)
        @ Matrix.Diagonal((*scale, 1))
        @ Matrix.Translation(tuple(-v for v in old))
    )


def envelope(M):
    room = CALIBRATION["room"]
    left, right, length, height = (room[k] for k in ("left", "right", "length", "height"))
    transition = room["floor_transition_y"]
    entry = CALIBRATION["layout"]["entry"]
    side = CALIBRATION["layout"]["side_door"]
    cx, cy, chase_y = room["chase_right_x"], length, room["chase_start_y"]
    for obj in list(bpy.data.objects):
        if obj.name.startswith(("Shell_", "Baseboard_", "Floor_")):
            bpy.data.objects.remove(obj, do_unlink=True)
    collection("01 / Architecture")

    def wall(name, xa, xb, ya, yb, za, zb, mat=None):
        return box(
            name,
            ((xa + xb) / 2, (ya + yb) / 2, (za + zb) / 2),
            (xb - xa, yb - ya, zb - za),
            mat or M["wall"],
            0,
        )

    wall("Shell_Foundation", left - 0.15, right + 0.15, -0.15, length + 0.15, -0.12, 0, M["grout"])
    wall(
        "Shell_Ceiling",
        left - 0.15,
        right + 0.15,
        -0.15,
        length + 0.15,
        height,
        height + 0.10,
        M["ceiling"],
    )
    wall("Shell_Wall_Right", right, right + 0.15, -0.15, length + 0.15, 0, height)
    wall("Shell_Wall_Right_Chase", cx, right, chase_y, cy, 0, height)
    ea, eb = (
        entry["center_x"] - entry["opening_width"] / 2,
        entry["center_x"] + entry["opening_width"] / 2,
    )
    wall("Shell_Wall_Front_Left", left - 0.15, ea, -0.15, 0, 0, height)
    wall("Shell_Wall_Front_Kitchen", eb, right + 0.15, -0.15, 0, 0, height)
    wall("Shell_Wall_Front_Header", ea, eb, -0.15, 0, entry["opening_height"], height)
    sa, sb = (
        side["center_y"] - side["opening_width"] / 2,
        side["center_y"] + side["opening_width"] / 2,
    )
    for i, (a, b) in enumerate([(0, 0.025), (0.98, sa), (sb, length)]):
        wall("Shell_Wall_Left_" + str(i), left - 0.15, left, a, b, 0, height)
    wall("Shell_Wall_Left_DoorHeader", left - 0.15, left, sa, sb, side["opening_height"], height)
    wall("Shell_Wall_Left_AlcoveHeader", left - 0.15, left, 0.025, 0.98, 2.50, height)
    wall("Shell_Wall_Alcove_Back", left - 0.67, left - 0.52, -0.07, 1.04, 0, height)
    for i, (a, b) in enumerate([(-0.07, 0.025), (0.98, 1.04)]):
        wall("Shell_Wall_Alcove_Return_" + str(i), left - 0.52, left - 0.15, a, b, 0, height)
    wall("Floor_Alcove", left - 0.52, left, 0.025, 0.98, 0, 0.014, M["tilecream"])
    window = CALIBRATION["window"]
    wa = window["center_x"] - window["width"] / 2
    wb = wa + window["width"]
    for i, (a, b) in enumerate([(left, wa), (wb, right)]):
        wall("Shell_Wall_Back_Pier_" + str(i), a, b, length, length + 0.18, 0, height)
    wall("Shell_Wall_Back_UnderWindow", wa, wb, length, length + 0.18, 0, window["bottom"])
    wall("Shell_Wall_Back_OverWindow", wa, wb, length, length + 0.18, window["top"], height)
    # Carpet is laid as square modules; only the perimeter tiles are clipped.
    for i in range(math.ceil((right - left) / 0.5)):
        for j in range(math.ceil((length - transition) / 0.5)):
            a, b = left + i * 0.5, min(right, left + (i + 1) * 0.5)
            c, d = transition + j * 0.5, min(length, transition + (j + 1) * 0.5)
            tile_dims = (b - a - 0.0003, d - c - 0.0003, 0.006)
            quarter_turn = (i + j) % 2
            if quarter_turn:
                tile_dims = (tile_dims[1], tile_dims[0], tile_dims[2])
            tile = box(
                f"Floor_Carpet_{i}_{j}",
                ((a + b) / 2, (c + d) / 2, 0.015),
                tile_dims,
                M["carpet"],
                0.00008,
            )
            if quarter_turn:
                # Rotate the actual local fibre frame as well as the image.
                # Swapped local dimensions keep clipped perimeter tiles fitted.
                tile.rotation_euler.z = math.pi / 2
    for i in range(math.ceil((right - left) / 0.305)):
        for j in range(math.ceil(transition / 0.305)):
            a, b = left + i * 0.305, min(right, left + (i + 1) * 0.305)
            c, d = j * 0.305, min(transition, (j + 1) * 0.305)
            box(
                f"Floor_Vinyl_{i}_{j}",
                ((a + b) / 2, (c + d) / 2, 0.007),
                (b - a - 0.0004, d - c - 0.0004, 0.014),
                M["tilegray" if (i + 3 * j) % 7 in (1, 4) else "tilecream"],
                0.0003,
            )
    box(
        "Floor_Transition",
        ((left + right) / 2, transition, 0.021),
        (right - left, 0.014, 0.018),
        M["trim"],
        0.001,
    )
    for name, x, a, b in [
        ("right", right - 0.012, 0, chase_y),
        ("right_chase", cx - 0.012, chase_y, length),
    ]:
        box("Baseboard_" + name, (x, (a + b) / 2, 0.047), (0.023, b - a, 0.094), M["trim"], 0.001)
    for i, (a, b) in enumerate([(0.98, sa), (sb, length)]):
        box(
            "Baseboard_left_" + str(i),
            (left + 0.012, (a + b) / 2, 0.047),
            (0.023, b - a, 0.094),
            M["trim"],
            0.001,
        )
    for name, a, b, y in [
        ("front", eb, right, 0.012),
        ("back", left, cx, length - 0.012),
        ("chase_front", cx, right, chase_y - 0.012),
    ]:
        box("Baseboard_" + name, ((a + b) / 2, y, 0.047), (b - a, 0.023, 0.094), M["trim"], 0.001)


def refine_layout(M):
    if "layout" not in CALIBRATION:
        return
    bpy.context.view_layer.update()
    cfg = CALIBRATION["layout"]
    envelope(M)
    # Window dimensions were applied by architecture_v2; its depth remains v2.
    dy = CALIBRATION["window"]["frame_y"] - 4.175
    transform(
        [o for o in bpy.data.objects if o.name.startswith(("Window_", "Blind_"))],
        Matrix.Translation((0, dy, 0)),
    )
    # Doors retain separate leaf, metal jambs, closer, lever, and hardware.
    for name, key, old_width, old_height in [
        ("Entry_Door / origin", "entry", 0.872, 2.035),
        ("Interior_Door / origin", "side_door", 0.872, 2.035),
    ]:
        obj = bpy.data.objects[name]
        rec = cfg[key]
        obj.scale.x = rec["leaf_width"] / old_width
        obj.scale.z = rec["leaf_height"] / old_height
        if key == "entry":
            obj.location.x = rec["center_x"]
        else:
            obj.location.y = rec["center_y"]
            obj.location.x = CALIBRATION["room"]["left"] + 0.01
    # Appliance and cabinet horizontal placement is fitted to photo 1, after
    # preserving the photograph's hob/mini-fridge order from the v2 reflection.
    mat = affine((0, 0, 0), (0.2205, 0, 0), (1.092, 1, 1))
    objects = [
        o
        for o in bpy.data.objects
        if o.name.startswith(("Kitchen_", "Hob_", "Fridge_", "Upper_", "Microwave_"))
    ]
    transform(objects, mat)
    assembly("Props / Kitchen counter details", mat)
    for obj in objects:
        if obj.parent in objects:
            continue
        if obj.name.startswith(("Upper_", "Microwave_")):
            obj.location.z += 0.067
        elif not obj.name.startswith("Kitchen_Outlet"):
            obj.location.z *= 0.95
            obj.scale.z *= 0.95
    assembly("Props / Kitchen counter details", Matrix.Translation((0, 0, -0.047)))
    counter = bpy.data.objects["Kitchen_Counter"]
    bpy.context.view_layer.update()
    minx = counter.location.x - counter.dimensions.x / 2
    counter.dimensions.x = CALIBRATION["room"]["right"] - minx
    counter.location.x = (CALIBRATION["room"]["right"] + minx) / 2
    # Each furniture transform is measured at its actual laminate surface.
    dresser = cfg["dresser"]
    desk = cfg["desk"]
    wardrobe = cfg["wardrobe"]
    dmat = affine(
        (-1.158, 2.585, 0),
        (*dresser["center_xy"], 0),
        (dresser["depth"] / 0.642, dresser["width"] / 0.979, dresser["top"] / 0.893),
    )
    transform([bpy.data.objects["Dresser / origin"]], dmat)
    # Travel objects keep real sizes. Their base heights follow the countertop.
    assembly(
        "Props / Dresser travel bag",
        affine(
            (-1.172, 2.585, 0.893),
            (*dresser["center_xy"], dresser["top"]),
            (1, dresser["width"] / 0.979, 1),
        ),
    )
    # Photo 4 establishes the order along the dresser: backpack by the door,
    # narrow paper bag by the bed. Move each item rigidly rather than mirroring
    # labels or shrinking the backpack with the shorter furniture top.
    dress_y_scale = dresser["width"] / 0.979
    arrangements = [
        (("Backpack",), 2.805, 2.800, True),
        (("Dresser paper shopping bag", "Paper bag twisted handle"), 2.382, 3.155, True),
        (("Turquoise wipes", "Wipes "), 2.790, 2.845, True),
        (("Small yellow snack", "Yellow packet"), 2.602, 3.02, True),
        (("Coiled white cable", "Coiled cable USB"), 2.944, 2.710, True),
        (
            ("Dresser extension strip", "Extension strip plug hole", "Power plug"),
            2.294,
            3.270,
            True,
        ),
    ]
    for prefixes, source_y, target_y, restore_size in arrangements:
        current_y = dresser["center_xy"][1] + (source_y - 2.585) * dress_y_scale
        mat = affine(
            (0, current_y, 0), (0, target_y, 0), (1, 1 / dress_y_scale if restore_size else 1, 1)
        )
        transform([o for o in bpy.data.objects if o.name.startswith(prefixes)], mat)
    backpack = cfg["backpack"]
    transform(
        [o for o in bpy.data.objects if o.name.startswith("Backpack")],
        affine(
            (-1.2700, 2.8000, 0.7380),
            backpack["base_axis_pivot"],
            (backpack["uniform_scale"],) * 3,
        ),
    )
    old_cable = bpy.data.objects.get("Dresser cable to floor")
    if old_cable:
        bpy.data.objects.remove(old_cable, do_unlink=True)
    collection("Props / Dresser travel bag")
    curve(
        "Dresser cable to floor",
        [
            (-0.900, 3.196, dresser["top"] + 0.054),
            (-0.830, 3.194, dresser["top"] + 0.016),
            (-0.803, 3.188, dresser["top"] - 0.18),
            (-0.812, 3.178, 0.37),
            (-0.790, 3.16, 0.12),
            (-0.775, 3.13, 0.019),
            (-0.686, 2.96, 0.020),
            (-0.649, 2.69, 0.019),
            (-0.504, 2.52, 0.020),
        ],
        0.0025,
        M["white"],
    )
    deskmat = affine(
        (1.163, 1.633, 0), (*desk["center_xy"], 0), (1, desk["width"] / 1.12, desk["top"] / 0.7675)
    )
    transform([bpy.data.objects["06 / Writing desk / origin"]], deskmat)
    deskprops = affine(
        (1.163, 1.633, 0.7675), (*desk["center_xy"], desk["top"]), (1, desk["width"] / 1.12, 1)
    )
    for name in ("Props / Study desk electronics", "Props / Paper and food packaging"):
        assembly(name, deskprops)
    wmat = affine((1.212, 2.683, 0), (*wardrobe["center_xy"], 0), (1, 1, wardrobe["top"] / 1.8485))
    transform([bpy.data.objects["05 / Wardrobe / origin"]], wmat)
    # Translate the official 36 x 80-inch mattress rigidly. Only the tall posts
    # are shortened; mattress length/width must never be globally rescaled.
    bed = cfg["bed"]
    span = bed.get("post_spacing_y", 0.988)
    for obj in bpy.data.objects:
        if obj.name.startswith(("Bed_4x4_post", "Bed_mortise_slot", "Bed_bolt")):
            obj.location.y = 3.586 + (obj.location.y - 3.586) * span / 0.988
        elif obj.name.startswith("Bed_end_ladder_rail"):
            obj.location.y = 3.586
            obj.scale.y *= (0.944 + span - 0.988) / 0.944
    bpy.context.view_layer.update()
    bedmat = (
        Matrix.Translation((bed["center_x"], bed["center_y"], bed["surface_z"] - 0.643))
        @ Matrix.Rotation(math.radians(bed.get("yaw_degrees", 0)), 4, "Z")
        @ Matrix.Translation((0, -3.586, 0))
    )
    for name in ("07 / Bed and textiles", "07 / Bed and textiles V2"):
        assembly(name, bedmat)
    for obj in bpy.data.objects:
        if obj.name.startswith(
            ("Bed_4x4_post", "Bed_mortise_slot", "Bed_end_ladder_rail", "Bed_bolt")
        ):
            obj.location.z = (obj.location.z - (bed["surface_z"] - 0.643)) * bed["post_top"] / 1.76
            if obj.name.startswith(("Bed_4x4_post", "Bed_mortise_slot")):
                obj.scale.z *= bed["post_top"] / 1.76
    mark = bpy.data.objects.get("Bed_guard_maroon_mark")
    if mark:
        mark.matrix_world = bedmat @ mark.matrix_world
    guard_shift = Matrix.Translation(
        (
            0,
            bed.get("guard_y", 3.4645) - (3.005 + bed["center_y"] - 3.586),
            bed.get("guard_top", 0.754) - (0.891 + bed["surface_z"] - 0.643),
        )
    )
    transform([o for o in bpy.data.objects if o.name.startswith("Bed_guard_")], guard_shift)
    floor_props = cfg["floor_props"]
    case = floor_props["upright_case"]
    upright = (
        Matrix.Translation((*case["center_xy"], 0))
        @ Matrix.Rotation(math.radians(case["yaw_degrees"]), 4, "Z")
        @ Matrix.Diagonal((1, case["depth"] / 0.267, 1, 1))
        @ Matrix.Translation((0.995, -0.725, 0))
    )
    assembly("Props / Upright silver suitcase", upright)
    assembly("Props / Open suitcase and puffer jacket", Matrix.Translation((0, 0.40, 0)))
    chair = floor_props["chair"]
    assembly(
        "Props / Black desk chair",
        Matrix.Translation((*chair["center_xy"], 0))
        @ Matrix.Rotation(math.radians(chair["yaw_degrees"]), 4, "Z")
        @ Matrix.Translation((-0.38, -1.78, 0)),
    )
    storage = floor_props["storage"]
    assembly(
        "Props / Transparent storage box",
        Matrix.Translation((*storage["center_xy"], 0.017))
        @ Matrix.Rotation(math.radians(storage["yaw_degrees"]), 4, "Z")
        @ Matrix.Diagonal(
            (
                storage["lid_width"] / 0.450,
                storage["lid_length"] / 0.557,
                (storage["lid_top"] - 0.017) / (0.367 - 0.017),
                1,
            )
        )
        @ Matrix.Translation((-0.665, -0.82, -0.017)),
    )
    waste = floor_props["wastebasket"]
    assembly(
        "Props / Entry wastebasket",
        affine(
            (-0.44, 0.49, 0.014), (*waste["center_xy"], 0.014), (1, 1, waste["body_height"] / 0.412)
        ),
    )
    for name, old_xy, old_angle, key in [
        ("Entry left sneaker", (-0.36, 0.91), -0.22, "left_shoe"),
        ("Entry right sneaker", (-0.22, 0.95), 0.16, "right_shoe"),
    ]:
        shoe = floor_props[key]
        # Existing sneaker meshes already include their authored yaw.
        transform(
            [o for o in bpy.data.objects if o.name.startswith(name)],
            Matrix.Translation((*shoe["center_xy"], 0.004))
            @ Matrix.Rotation(math.radians(shoe["yaw_degrees"]) - old_angle, 4, "Z")
            @ Matrix.Translation((-old_xy[0], -old_xy[1], 0)),
        )
    transform(
        [o for o in bpy.data.objects if o.name.startswith("Under dresser white sneaker")],
        Matrix.Translation((0, 0.48, 0)),
    )
    # Sink-recess and the much wider full-length mirror are independently fitted.
    sink = bpy.data.objects.get("04 / Sink alcove / origin")
    if sink:
        sink.location.y = 0.495
    assembly("Props / Sink toiletries", Matrix.Translation((0, -0.065, 0)))
    for name in ("Mirror_full_back", "Mirror_full_surface"):
        obj = bpy.data.objects[name]
        obj.location.y = 1.325
        obj.location.z = 1.28
        obj.dimensions.y = 0.587
    # Wall fittings move with their supporting walls and furniture zone.
    for obj in bpy.data.objects:
        if obj.parent is None and obj.name.startswith(
            ("Service_Panel", "Service_Grille", "Bed_Vent", "Thermostat")
        ):
            obj.location.x -= 0.11
            obj.location.y += bed["center_y"] - 3.586
        if obj.name.startswith("Entry_Speaker"):
            obj.location.x += 0.034
            obj.location.z += 0.1306
        if obj.name.startswith("Entry_Sprinkler"):
            obj.location.x += 0.13115
            obj.location.z += 0.17097
    for name, x, z in [
        ("Front_Vent / origin", -1.02692, 2.88521),
        ("Kitchen_Outlet_A / origin", 0.33372, 1.18846),
        ("Kitchen_Outlet_B / origin", 0.91783, 1.18785),
        ("Entry_Switch / origin", -0.23617, 1.18906),
    ]:
        obj = bpy.data.objects.get(name)
        if obj:
            obj.location.x = x
            obj.location.z = z
    outlet = bpy.data.objects.get("Bed_Outlet_Right / origin")
    if outlet:
        outlet.location.x = CALIBRATION["room"]["chase_right_x"] - 0.013
        outlet.location.y += bed["center_y"] - 3.586
    for obj in bpy.data.objects:
        if obj.name.startswith(("Ceiling_Light", "Smoke_detector")):
            obj.location.y += 0.28
    bpy.context.view_layer.update()
