"""Small manufactured details with real geometry, before the kitchen reflection."""

import math
import bpy
from mathutils import Matrix
from common import material, mesh, cyl, collection, box


def _match_front_proportions(M):
    """Fit the microwave face and upper grille to reference 1 at its wall depth.

    Coordinates are before the room layout's +67 mm upper-appliance offset.
    The reference-1 front-plane estimate is approximately 392 mm high; the
    reference-6 upper shell supports a further 12.5 mm at the top only, with
    a deeper grille band than the first authored placeholder. It is not a
    manufacturer measurement.
    """
    bpy.context.view_layer.update()
    for obj in list(bpy.data.objects):
        if not obj.name.startswith("Microwave_"):
            continue
        if obj.name.startswith("Microwave_top_vent"):
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
        if obj.name == "Microwave_body":
            obj.location.z = 1.71525
            obj.scale.z *= 0.405 / 0.36
        elif obj.name == "Microwave_front":
            obj.location.z = 1.677
            obj.scale.z *= 1.10
        elif obj.name == "Microwave_handle":
            obj.matrix_world = (
                Matrix.Translation((0, 0, 1.677))
                @ Matrix.Diagonal((1, 1, 1.10, 1))
                @ Matrix.Translation((0, 0, -1.756))
                @ obj.matrix_world
            )
        else:
            obj.matrix_world = Matrix.Translation((0, 0, -0.0926)) @ obj.matrix_world
    # Extend the short cabinets downward while retaining the aligned top edge.
    for obj in bpy.data.objects:
        if obj.name.startswith("Upper_Left_"):
            obj.matrix_world = (
                Matrix.Translation((0, 0, 2.2785))
                @ Matrix.Diagonal((1, 1, 0.349 / 0.303, 1))
                @ Matrix.Translation((0, 0, -2.2785))
                @ obj.matrix_world
            )
    dark = material("Microwave / recessed ventilation cavity", (0.095, 0.10, 0.088), 0.69)
    box("Microwave_grille_recess", (0.17, 0.445, 1.868), (0.726, 0.007, 0.066), dark, 0.004)
    for i in range(5):
        box(
            "Microwave_grille_horizontal_louver",
            (0.17, 0.452, 1.838 + i * 0.0145),
            (0.733, 0.012, 0.005),
            M["white"],
            0.001,
        )
    for i in range(9):
        box(
            "Microwave_grille_vertical_support",
            (-0.183 + i * 0.088, 0.448, 1.868),
            (0.004, 0.010, 0.063),
            M["white"],
            0.0007,
        )
    bpy.context.view_layer.update()


def _formed_window(obj, width, height, depth, radius, arch):
    """Form the broad XZ corner radius independently of the thin Y extrusion.

    A box bevel is overlap-clamped by a 4 mm sheet thickness and cannot make
    the visibly curved window corners of this microwave door.
    """
    outline = []
    for corner in range(4):
        for step in range(13):
            a = (corner + step / 12) * math.pi / 2
            ca, sa = math.cos(a), math.sin(a)
            cx = (width / 2 - radius) * (1 if corner in (0, 3) else -1)
            cz = (height / 2 - radius) * (1 if corner in (0, 1) else -1)
            x, z = cx + radius * ca, cz + radius * sa
            z += arch * max(z / (height / 2), 0) * (1 - (x / (width / 2)) ** 2)
            outline.append((x, z))
    n = len(outline)
    vertices = [(x, y, z) for y in (-depth / 2, depth / 2) for x, z in outline]
    faces = [tuple(range(n)), tuple(range(2 * n - 1, n - 1, -1))]
    faces += [(i, (i + 1) % n, (i + 1) % n + n, i + n) for i in range(n)]
    old = obj.data
    data = bpy.data.meshes.new(obj.name + " / formed outline")
    data.from_pydata(vertices, [], faces)
    data.update()
    for mat in old.materials:
        data.materials.append(mat)
    for polygon in data.polygons:
        polygon.use_smooth = polygon.index >= 2
    obj.data = data
    obj.modifiers.clear()
    if old.users == 0:
        bpy.data.meshes.remove(old)


def _printed_text(name, body, location, size, mat):
    font = bpy.data.curves.new(name, "FONT")
    font.body = body
    font.size = size
    font.align_x = "CENTER"
    font.align_y = "CENTER"
    ob = bpy.data.objects.new(name, font)
    group = bpy.data.collections["03 / Kitchen"]
    group.objects.link(ob)
    ob.matrix_world = Matrix(
        ((1, 0, 0, location[0]), (0, 0, -1, location[1]), (0, 1, 0, location[2]), (0, 0, 0, 1))
    )
    font.materials.append(mat)
    return ob


def microwave_details(M):
    collection("03 / Kitchen")
    bezel = bpy.data.objects["Microwave_window"]
    _formed_window(bezel, 0.49, 0.191, 0.007, 0.026, 0.012)
    bezel.data.materials.clear()
    bezel.data.materials.append(M["white"])
    screen = material("Microwave / gray perforated screen", (0.22, 0.229, 0.213), 0.32)
    perforation = material("Microwave / screen apertures", (0.034, 0.037, 0.031), 0.57)
    inner = bpy.data.objects["Microwave_window_inner"]
    _formed_window(inner, 0.452, 0.161, 0.004, 0.022, 0.012)
    inner.data.materials.clear()
    inner.data.materials.append(screen)
    verts, faces = [], []
    for row in range(44):
        z = 1.699 + row * 0.0033
        for column in range(127):
            x = -0.128 + column * 0.0033 + (row % 2) * 0.00165
            # Keep the fine pattern within the rounded window corners.
            rx = max(abs(x - 0.079) - 0.187, 0)
            rz = max(abs(z - 1.77) - 0.05, 0)
            if rx * rx + rz * rz > 0.023**2:
                continue
            start = len(verts)
            for i in range(6):
                a = i * math.tau / 6
                verts.append((x + 0.00071 * math.cos(a), 0.4632, z + 0.00071 * math.sin(a)))
            faces.append(tuple(range(start, start + 6)))
    mesh("Microwave_window_screen_pattern", verts, faces, perforation)
    ink = material("Microwave / control pad printing", (0.16, 0.17, 0.15), 0.62)
    lcd = material("Microwave / LCD digits", (0.39, 0.45, 0.32), 0.54)
    _printed_text("Microwave_clock_digits", "5:00", (0.45, 0.462, 1.866), 0.011, lcd)
    legends = [
        ["TIME", "COOK", "DEF."],
        ["AUTO", "REHEAT", "TIMER"],
        ["1", "2", "3"],
        ["4", "5", "6"],
        ["7", "8", "9"],
        ["POWER", "0", "CLOCK"],
        ["STOP", "PAUSE", "START"],
    ]
    for row, items in enumerate(legends):
        for col, label in enumerate(items):
            _printed_text(
                f"Microwave_key_legend_{row}_{col}",
                label,
                (0.414 + col * 0.028, 0.464, 1.824 - row * 0.019),
                0.0047 if len(label) > 1 else 0.0065,
                ink,
            )
    cyl(
        "Microwave_manufacturer_medallion",
        (-0.166, 0.455, 1.625),
        0.009,
        0.002,
        M["darkmetal"],
        (math.pi / 2, 0, 0),
    )
    _printed_text("Microwave_medallion_letters", "GE", (-0.166, 0.4565, 1.625), 0.008, M["white"])
    # Font geometry is evaluated once so the same label meshes reach glTF.
    bpy.context.view_layer.update()
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for ob in list(bpy.data.objects):
        if ob.type == "FONT" and ob.name.startswith("Microwave_"):
            data = bpy.data.meshes.new_from_object(ob.evaluated_get(depsgraph))
            matrix = ob.matrix_world.copy()
            name = ob.name
            bpy.data.objects.remove(ob, do_unlink=True)
            replacement = bpy.data.objects.new(name, data)
            bpy.data.collections["03 / Kitchen"].objects.link(replacement)
            replacement.matrix_world = matrix
    _match_front_proportions(M)
