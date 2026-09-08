"""Rigid desktop refinement from manually matched real photograph corners.

The shared cameras in references 2/9 constrain two rectangles and the laptop
base. Reference 12 is fitted jointly. An authored desk contact prior resolves
small lower-edge ambiguities. This is an estimate, not surveyed geometry.
"""

import json
import math

import bpy
from mathutils import Matrix, Vector

from calibration import CALIBRATION
from common import box, collection

VERSION = "desktop_pose_v4_1"


def _bounds(obj):
    points = [obj.matrix_world @ Vector(v) for v in obj.bound_box]
    return (
        Vector(tuple(min(p[i] for p in points) for i in range(3))),
        Vector(tuple(max(p[i] for p in points) for i in range(3))),
    )


def _frame(origin, x, y, z):
    matrix = Matrix((x, y, z)).transposed().to_4x4()
    matrix.translation = origin
    return matrix


def _apply(names, matrix):
    objects = {bpy.data.objects[name] for name in names}
    for obj in objects:
        if obj.parent not in objects:
            obj.matrix_world = matrix @ obj.matrix_world
    bpy.context.view_layer.update()


def _move_cable_end(name, transform):
    """Preserve the mouse/charger end and smoothly move the laptop connector."""
    obj = bpy.data.objects.get(name)
    if obj is None or obj.type != "CURVE":
        raise ValueError(f"Expected editable cable curve: {name}")
    obj.data = obj.data.copy()
    inverse = obj.matrix_world.inverted()
    for spline in obj.data.splines:
        points = spline.bezier_points if spline.type == "BEZIER" else spline.points
        end = obj.matrix_world @ Vector(points[-1].co[:3])
        delta = transform @ end - end
        for i, point in enumerate(points):
            offset = delta * (i / max(1, len(points) - 1)) ** 3
            if spline.type == "BEZIER":
                for key in ("co", "handle_left", "handle_right"):
                    value = getattr(point, key)
                    setattr(point, key, inverse @ (obj.matrix_world @ value + offset))
            else:
                value = inverse @ (obj.matrix_world @ Vector(point.co[:3]) + offset)
                point.co = (*value, point.co.w)
    return name


def refine_desktop_pose(materials, config=None):
    """Refine existing rigid objects once; keep mesh coordinates and UVs intact."""
    scene = bpy.context.scene
    if scene.get("desktop_pose_refinement") == VERSION:
        return json.loads(scene["desktop_pose_audit"])
    config = config or CALIBRATION["desktop_pose"]
    points = [Vector(value) for value in config["fitted_points_world"]]
    base_prefix = (
        "Laptop aluminium lower shell",
        "Laptop black keyboard recess",
        "Laptop touchpad inset",
        "Laptop key ",
        "Key legend",
        "Long spacebar",
        "Touchpad engraved border",
        "Laptop hinge barrel",
        "Laptop status LED",
        "Laptop edge port",
    )
    screen_prefix = (
        "Laptop screen lid",
        "Laptop screen bezel",
        "Laptop active display",
        "Editor ",
        "Screen neutral heading",
        "Laptop camera lens",
    )
    base_names = [o.name for o in bpy.data.objects if o.name.startswith(base_prefix)]
    screen_names = [o.name for o in bpy.data.objects if o.name.startswith(screen_prefix)]
    tablet_names = [o.name for o in bpy.data.objects if o.name.startswith("Tablet ")]
    base = bpy.data.objects["Laptop aluminium lower shell"]
    lid = bpy.data.objects["Laptop screen lid"]
    tablet = bpy.data.objects["Tablet folio rim"]
    if not base_names or not screen_names or not tablet_names:
        raise ValueError("Desktop construction objects are missing")

    # Native lower front perimeter maps to the photographed lower perimeter.
    lo, hi = _bounds(base)
    old_origin = Vector((lo.x, (lo.y + hi.y) / 2, lo.z))
    front = (points[4] + points[5]) / 2
    hinge = (points[2] + points[3]) / 2
    y = (points[2] - points[3]).normalized()
    direction = hinge - front
    direction -= y * direction.dot(y)
    distance = direction.length
    depth_direction = direction.normalized()
    initial_normal = depth_direction.cross(y).normalized()
    thickness = hi.z - lo.z
    alpha = math.asin(thickness / distance)
    x = depth_direction * math.cos(alpha) - initial_normal * math.sin(alpha)
    z = x.cross(y).normalized()
    depth = math.sqrt(distance**2 - thickness**2)
    width = (points[3] - points[2]).length
    base_transform = _frame(
        front, x * depth / (hi.x - lo.x), y * width / (hi.y - lo.y), z
    ) @ Matrix.Translation(-old_origin)
    _apply(base_names, base_transform)

    corners = [lid.matrix_world @ Vector(value) for value in lid.bound_box]
    old_bottom = (corners[0] + corners[3]) / 2
    old_up = (corners[1] + corners[2]) / 2 - old_bottom
    old_y = corners[3] - corners[0]
    old_frame = _frame(
        old_bottom,
        old_y.normalized().cross(old_up.normalized()),
        old_y.normalized(),
        old_up.normalized(),
    )
    new_up = (points[0] + points[1]) / 2 - hinge
    new_frame = _frame(
        hinge,
        y.cross(new_up.normalized()),
        y * width / old_y.length,
        new_up.normalized() * new_up.length / old_up.length,
    )
    _apply(screen_names, new_frame @ old_frame.inverted())
    floor = config.get("desk_contact_z_m", 0.7412)
    lift = max(0, floor - _bounds(base)[0].z)
    if lift:
        translation = Matrix.Translation((0, 0, lift))
        _apply(base_names + screen_names, translation)
        base_transform = translation @ base_transform
        front.z += lift

    lo, hi = _bounds(tablet)
    old_origin = Vector((lo.x, (lo.y + hi.y) / 2, lo.z))
    tablet_front = (points[8] + points[9]) / 2
    tablet_back = (points[6] + points[7]) / 2
    tx = (tablet_back - tablet_front).normalized()
    ty = (points[8] - points[9]).normalized()
    _apply(
        tablet_names,
        _frame(
            tablet_front,
            tx * (tablet_back - tablet_front).length / (hi.x - lo.x),
            ty * (points[9] - points[8]).length / (hi.y - lo.y),
            tx.cross(ty).normalized(),
        )
        @ Matrix.Translation(-old_origin),
    )
    tablet_lift = max(0, floor - _bounds(tablet)[0].z)
    if tablet_lift:
        _apply(tablet_names, Matrix.Translation((0, 0, tablet_lift)))

    cables = [
        _move_cable_end(name, base_transform)
        for name in (
            "Mouse USB lead",
            "Laptop power cord to wall",
        )
    ]
    # Only the incline is observed. These small obscured rear supports are an
    # explicit inferred mechanical completion, not an identified product.
    collection("Props / Desktop pose v4 inferred supports")
    supports = []
    for index, offset in enumerate((-0.29, 0.29)):
        contact = front + x * depth * 0.83 + y * width * offset
        height = contact.z - floor
        support = box(
            f"DesktopV4_Inferred_rear_support_{index}",
            (contact.x, contact.y, floor + height / 2),
            (0.019, 0.015, height),
            materials["black"],
            0.0012,
        )
        support["geometry_status"] = "Inferred obscured support; design not observed"
        supports.append(support.name)
    audit = {
        "version": VERSION,
        "base_objects": base_names,
        "screen_objects": screen_names,
        "tablet_objects": tablet_names,
        "cables": cables,
        "inferred_supports": supports,
        "laptop_contact_raise_m": lift,
        "tablet_contact_raise_m": tablet_lift,
        "desk_contact_z_m": floor,
        "camera_reference": 12,
        "status": "Reviewed incremental pose refinement; manual geometry and camera estimates",
    }
    scene["desktop_pose_refinement"] = VERSION
    scene["desktop_pose_audit"] = json.dumps(audit)
    return audit


def apply_review_camera(camera, config=None):
    """Apply the jointly estimated reference-12 pose after its camera exists."""
    config = config or CALIBRATION["desktop_pose"]
    fit = config["camera_fit"]
    matrix = (
        Matrix(fit["rotation_world_to_cv"]).transposed() @ Matrix.Diagonal((1.0, -1.0, -1.0))
    ).to_4x4()
    matrix.translation = Vector(fit["position_world"])
    camera.matrix_world = matrix
    camera.data.lens = fit["focal_px"] * camera.data.sensor_width / 1707
    camera["fit_status"] = "Manual multiview rigid-corner/contact-prior estimate; not automatic SfM"
    camera["fit_geometry_status"] = (
        "Residuals describe analytic corner fitting; bevels/support/contact corrections are independently reviewed"
    )
    camera["residuals_apply_to_current_geometry"] = False
    camera["fit_rmse_px"] = config["camera_fit_rmse_px"]
    camera["held_out_rmse_px"] = config["independent_desk_corner"]["error_px"]
    camera["held_out_max_px"] = config["independent_desk_corner"]["error_px"]
    camera["fit_observations"] = 10
    camera["held_out_observations"] = 1
    camera["source_native_sha256"] = ""
    camera["pose_refinement_source"] = VERSION
