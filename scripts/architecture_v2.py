"""Photo-guided architectural corrections; values remain estimates, in metres."""

import bpy
from mathutils import Matrix
from common import box, collection
from calibration import CALIBRATION

HEIGHT = CALIBRATION["room"]["height"]
WINDOW_X = CALIBRATION["window"]["center_x"]
WINDOW_WIDTH = CALIBRATION["window"]["width"]
WINDOW_BOTTOM = CALIBRATION["window"]["bottom"]
WINDOW_TOP = CALIBRATION["window"]["top"]


def refine_architecture(M):
    collection("01 / Architecture")
    bpy.context.view_layer.update()
    # Explicitly vary top edges while leaving door openings at their fixed height.
    for ob in list(bpy.data.objects):
        if ob.name.startswith("Shell_Wall_Back_"):
            bpy.data.objects.remove(ob, do_unlink=True)
            continue
        if ob.type == "MESH" and ob.name.startswith("Shell_Wall_"):
            old_bottom = ob.location.z - ob.dimensions.z / 2
            old_top = ob.location.z + ob.dimensions.z / 2
            if abs(old_top - 2.82) < 0.02:
                ob.dimensions.z = HEIGHT - old_bottom
                ob.location.z = (HEIGHT + old_bottom) / 2
        if ob.name == "Shell_Ceiling":
            ob.location.z += HEIGHT - 2.82
        if ob.name.startswith(("Ceiling_Light", "Smoke_detector")):
            ob.location.z += HEIGHT - 2.82
    left, right = WINDOW_X - WINDOW_WIDTH / 2, WINDOW_X + WINDOW_WIDTH / 2
    for side, a, b in [("Left", -1.5, left), ("Right", right, 1.5)]:
        box(
            "Shell_Wall_Back_Pier_" + side,
            ((a + b) / 2, 4.225, HEIGHT / 2),
            (b - a, 0.15, HEIGHT),
            M["wall"],
            0,
        )
    box(
        "Shell_Wall_Back_UnderWindow",
        (WINDOW_X, 4.225, WINDOW_BOTTOM / 2),
        (WINDOW_WIDTH, 0.15, WINDOW_BOTTOM),
        M["wall"],
        0,
    )
    box(
        "Shell_Wall_Back_OverWindow",
        (WINDOW_X, 4.225, (HEIGHT + WINDOW_TOP) / 2),
        (WINDOW_WIDTH, 0.15, HEIGHT - WINDOW_TOP),
        M["wall"],
        0,
    )
    # The photographs show shallow vertical service chases behind the bed ends.
    for side, x, w in [("Left", -1.445, 0.11), ("Right", 1.425, 0.15)]:
        box(
            "Shell_Wall_Back_Chase_" + side,
            (x, 3.665, HEIGHT / 2),
            (w, 0.97, HEIGHT),
            M["wall"],
            0.0005,
        )
    bpy.context.view_layer.update()
    xf = (
        Matrix.Translation((WINDOW_X, 0, WINDOW_BOTTOM))
        @ Matrix.Diagonal((WINDOW_WIDTH / 1.294, 1, (WINDOW_TOP - WINDOW_BOTTOM) / 1.344, 1))
        @ Matrix.Translation((0, 0, -0.918))
    )
    for ob in list(bpy.data.objects):
        if ob.name.startswith(("Window_", "Blind_")):
            ob.matrix_world = xf @ ob.matrix_world
        if (
            ob.name.startswith(("Service_Panel", "Service_Grille", "Bed_Vent", "Thermostat"))
            and ob.parent is None
        ):
            ob.location.x += 0.11
    # Move bed-wall skirting onto the exposed chase faces.
    for side, x in [("Left", -1.378), ("Right", 1.338)]:
        box("Baseboard_chase_" + side, (x, 3.665, 0.047), (0.023, 0.97, 0.094), M["trim"], 0.001)


def apply_matched_camera(camera, record):
    world_to_cv = Matrix(record["rotation_world_to_cv"])
    camera.matrix_world = (world_to_cv.transposed() @ Matrix.Diagonal((1, -1, -1))).to_4x4()
    camera.location = record["position"]
    camera.data.lens = record["lens_mm"]
    camera.data.sensor_width = 36
    camera.data.sensor_fit = "HORIZONTAL"
    camera["exposure_ev"] = float(record.get("exposure_ev", 0.0))
