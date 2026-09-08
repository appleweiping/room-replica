"""Photo-matched front-wall spacing and small architectural fittings.

This is an authored, reversible dimensional hypothesis, not a surveyed plan.
The doorway nearly meets the sink-side corner in the supplied kitchen view.
"""

import math
import bpy
from mathutils import Matrix
from common import box, cyl, mesh, material, collection
from calibration import CALIBRATION

KITCHEN_X_ANCHOR = CALIBRATION["front_wall"]["kitchen_anchor_x"]
KITCHEN_X_SCALE = CALIBRATION["front_wall"]["kitchen_scale_x"]
ENTRY_CENTER_X = CALIBRATION["front_wall"]["entry_center_x"]


def _transform_roots(objects, matrix):
    members = set(objects)
    for ob in members:
        if ob.parent not in members:
            ob.matrix_world = matrix @ ob.matrix_world


def refine_furniture_spacing():
    """Leave the photographed strip of wall between the wardrobe and bed end."""
    bpy.context.view_layer.update()
    wardrobe = bpy.data.objects.get("05 / Wardrobe / origin")
    if wardrobe:
        wardrobe.location.y -= 0.34
        wardrobe.scale.z *= 1.045
    desk = bpy.data.objects.get("06 / Writing desk / origin")
    if desk:
        desk.location.y -= 0.30
    translation = Matrix.Translation((0, -0.30, 0))
    for name in ("Props / Study desk electronics", "Props / Paper and food packaging"):
        group = bpy.data.collections.get(name)
        if group:
            _transform_roots(group.all_objects, translation)


def refine_fittings(M):
    bpy.context.view_layer.update()
    assembly = [
        o
        for o in bpy.data.objects
        if o.name.startswith(("Kitchen_", "Hob_", "Fridge_", "Upper_", "Microwave_"))
    ]
    assembly_set = set(assembly)
    transform = (
        Matrix.Translation((KITCHEN_X_ANCHOR, 0, 0))
        @ Matrix.Diagonal((KITCHEN_X_SCALE, 1, 1, 1))
        @ Matrix.Translation((-KITCHEN_X_ANCHOR, 0, 0))
    )
    for ob in assembly:
        if ob.parent not in assembly_set:
            ob.matrix_world = transform @ ob.matrix_world
    # Same transformation applies to the countertop still life as one assembly.
    props = bpy.data.collections.get("Props / Kitchen counter details")
    if props:
        members = set(props.all_objects)
        for ob in members:
            if ob.parent not in members:
                ob.matrix_world = transform @ ob.matrix_world
    door = bpy.data.objects.get("Entry_Door / origin")
    if door:
        door.location.x = ENTRY_CENTER_X
    stub = bpy.data.objects.get("Shell_Wall_Front_Left")
    if stub:
        bpy.data.objects.remove(stub, do_unlink=True)
    wall = bpy.data.objects.get("Shell_Wall_Front_Kitchen")
    wall_start = ENTRY_CENTER_X + 0.487
    wall.dimensions.x = 1.5 - wall_start
    wall.location.x = (1.5 + wall_start) / 2
    skirt = bpy.data.objects.get("Baseboard_front")
    skirt.dimensions.x = 1.5 - wall_start
    skirt.location.x = (1.5 + wall_start) / 2
    seams = sorted(
        (o for o in bpy.data.objects if o.name.startswith("Wall_Panel_seam")), key=lambda o: o.name
    )
    for ob, x in zip(seams, (wall_start, -1.497)):
        ob.location.x = x
        ob.location.z = (2.10 + CALIBRATION["room"]["height"]) / 2
        ob.dimensions.z = CALIBRATION["room"]["height"] - 2.10
    counter = bpy.data.objects.get("Kitchen_Counter")
    # A real overhang reaches the side wall while the cabinet has a small scribe gap.
    bpy.context.view_layer.update()
    right_edge = counter.location.x - counter.dimensions.x / 2
    counter.dimensions.x = 1.50 - right_edge
    counter.location.x = (1.50 + right_edge) / 2
    vent = bpy.data.objects.get("Front_Vent / origin")
    if vent:
        vent.location.x = -1.16
        vent.location.z = 2.70
    collection("02 / Lights and hardware")
    # Small perforated speaker plate to the left of the entrance, visible in #1/6.
    box("Entry_Speaker_plate", (-0.3, 0.007, 1.927), (0.128, 0.012, 0.135), M["white"], 0.0015)
    dark = M["taupe"]
    verts, faces = [], []
    for row in range(-11, 12):
        for col in range(-11, 12):
            x, z = col * 0.0034, row * 0.0034
            if x * x + z * z > 0.037**2:
                continue
            a = len(verts)
            for k in range(6):
                th = math.tau * k / 6
                verts.append(
                    (
                        -0.3 + x + 0.00075 * math.cos(th),
                        0.0132,
                        1.927 + z + 0.00075 * math.sin(th),
                    )
                )
            faces.append(tuple(range(a, a + 6)))
    mesh("Entry_Speaker_perforations", verts, faces, dark)
    cyl(
        "Entry_Sprinkler_escutcheon",
        (-0.76, 0.014, 2.724),
        0.034,
        0.012,
        M["metal"],
        (math.pi / 2, 0, 0),
    )
    cyl(
        "Entry_Sprinkler_inset",
        (-0.76, 0.022, 2.724),
        0.022,
        0.014,
        M["darkmetal"],
        (math.pi / 2, 0, 0),
    )
    box("Entry_Sprinkler_bridge", (-0.76, 0.032, 2.738), (0.032, 0.023, 0.012), M["metal"], 0.002)
    # Photograph's maroon bed-rail M as vector geometry, not a projected photo.
    maroon = material("Bed / maroon rail mark", (0.19, 0.019, 0.039), 0.51)
    outline = [
        (-0.060, -0.019),
        (-0.038, -0.019),
        (-0.038, 0.017),
        (-0.014, -0.019),
        (0.004, -0.019),
        (0.027, 0.017),
        (0.027, -0.019),
        (0.057, -0.019),
        (0.057, -0.030),
        (0.004, -0.030),
        (0.004, -0.011),
        (-0.012, -0.030),
        (-0.033, -0.011),
        (-0.033, -0.030),
        (-0.060, -0.030),
    ]
    mesh(
        "Bed_guard_maroon_mark",
        [(x, 2.9845, 0.832 + z) for x, z in outline],
        [tuple(range(len(outline)))],
        maroon,
    )
