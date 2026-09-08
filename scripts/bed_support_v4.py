"""Photo-constrained support height and quilt loft, after the final bed layout.

The nominal mattress top in the original builder is .643 m (its center is
.539 m). Seven separately reviewed exposed-cover tracks support a .601 m cover
surface, rather than the old .658 m surface. This refinement lowers the mattress,
piping and support steel, repositions the cover's roundover, and releases the
quilt's lower casing while retaining the already fitted upper silhouette.
Bed posts, ladder rails, guard, hanging textiles and material/UV data are untouched.
"""

from dataclasses import dataclass, asdict
import json
import math
import numpy as np


@dataclass(frozen=True)
class BedSupportConfig:
    lowering_m: float = 0.057
    bed_center_x: float = 0.00011
    bed_center_y: float = 3.98993
    bed_yaw_degrees: float = 1.666
    sheet_front_retraction_m: float = 0.050
    sheet_retraction_start_y: float = -0.360
    sheet_retraction_span_m: float = 0.160
    right_cover_ridge_m: float = 0.014
    right_cover_ridge_x: float = 0.830
    right_cover_ridge_width_m: float = 0.048
    quilt_lower_band_z: float = 0.660
    quilt_retained_upper_z: float = 0.735


def _config(config):
    c = config if isinstance(config, BedSupportConfig) else BedSupportConfig(**(config or {}))
    if not 0 <= c.right_cover_ridge_m < c.lowering_m < 0.10:
        raise ValueError(
            "Support lowering must be positive, below .10 m and greater than the local ridge"
        )
    if not 0 <= c.sheet_front_retraction_m < c.sheet_retraction_span_m / 1.5:
        raise ValueError("Front retraction must keep the horizontal mapping monotonic")
    if c.right_cover_ridge_width_m <= 0 or c.quilt_retained_upper_z <= c.quilt_lower_band_z:
        raise ValueError("Ridge width and quilt transition interval must be positive")
    return c


def _smooth(value):
    t = np.clip(value, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _frame(c):
    angle = math.radians(c.bed_yaw_degrees)
    return np.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])


def _points(points):
    p = np.array(points, dtype=np.float64, copy=True)
    if p.ndim != 2 or p.shape[1] != 3 or not np.isfinite(p).all():
        raise ValueError("Expected finite N x 3 world coordinates")
    return p


def _ridge(local_xy, c):
    # A narrow, nonuniform cover wrinkle is supported by three exposed right
    # patch tracks. It fades before the front/rear hanging faces and bed ends.
    x, y = local_xy.T
    amount = c.right_cover_ridge_m * np.exp(
        -0.5 * ((x - c.right_cover_ridge_x) / c.right_cover_ridge_width_m) ** 2
    )
    amount *= _smooth((y + 0.47) / 0.07) * (1 - _smooth((y - 0.31) / 0.12))
    return amount


def warp_sheet_points(points, config=None):
    """Return the support-corrected cover and sewn hems in world coordinates."""
    c = _config(config)
    p = _points(points)
    rotation = _frame(c)
    xy = (p[:, :2] - [c.bed_center_x, c.bed_center_y]) @ rotation
    p[:, 2] += -c.lowering_m + _ridge(xy, c)
    xy[:, 1] += c.sheet_front_retraction_m * _smooth(
        (c.sheet_retraction_start_y - xy[:, 1]) / c.sheet_retraction_span_m
    )
    p[:, :2] = xy @ rotation.T + [c.bed_center_x, c.bed_center_y]
    return p


def release_quilt_lower_shell(points, config=None):
    """Release an already pose-v4 quilt's lower shell, keeping upper points fixed.

    For a fixed XY, dZ'/dZ is at least one: this restores loft rather than
    compressing an already thin quilt. The XY coordinates never change here.
    At or above .735 m the old v4 silhouette is exactly retained.
    """
    c = _config(config)
    p = _points(points)
    xy = (p[:, :2] - [c.bed_center_x, c.bed_center_y]) @ _frame(c)
    weight = 1 - _smooth(
        (p[:, 2] - c.quilt_lower_band_z) / (c.quilt_retained_upper_z - c.quilt_lower_band_z)
    )
    p[:, 2] += (-c.lowering_m + _ridge(xy, c)) * weight
    return p


def _deform_object(obj, mapper):
    world = np.array(obj.matrix_world, dtype=np.float64)
    inverse = np.linalg.inv(world)

    def local(coordinates):
        co = np.asarray(coordinates, dtype=np.float64)
        mapped = mapper(co @ world[:3, :3].T + world[:3, 3])
        return (mapped - world[:3, 3]) @ inverse[:3, :3].T

    if obj.data.users > 1:
        obj.data = obj.data.copy()
    if obj.type == "MESH":
        values = np.empty(len(obj.data.vertices) * 3, dtype=np.float64)
        obj.data.vertices.foreach_get("co", values)
        obj.data.vertices.foreach_set("co", local(values.reshape(-1, 3)).ravel())
        obj.data.update()
    elif obj.type == "CURVE":
        for spline in obj.data.splines:
            if spline.type == "BEZIER":
                for point in spline.bezier_points:
                    point.co, point.handle_left, point.handle_right = local(
                        [point.co[:], point.handle_left[:], point.handle_right[:]]
                    )
            else:
                for point, co in zip(
                    spline.points, local([point.co[:3] for point in spline.points])
                ):
                    point.co = (*co, point.co.w)
    else:
        raise RuntimeError("Unsupported textile type: " + obj.type)


def refine_bed_support(config=None, quilt_config=None):
    """Apply once after final layout; includes the preceding quilt-v4 pose.

    Leave the original builder's mattress ``surface_z=.643`` unchanged. This
    post-layout operation produces a .586 m mattress top and a nominal .601 m
    cover. It must not be combined with another global bed-height translation.
    Identical calls are no-ops; changed parameters require a fresh build.
    """
    import bpy
    from quilt_pose_v4 import refine_quilt_pose, QuiltPoseConfig

    c = _config(config)
    qc = (
        quilt_config
        if isinstance(quilt_config, QuiltPoseConfig)
        else QuiltPoseConfig(**(quilt_config or {}))
    )
    stamp = json.dumps({"support": asdict(c), "quilt_pose": asdict(qc)}, sort_keys=True)
    scene = bpy.context.scene
    previous = scene.get("bed_support_v4_config")
    if previous is not None:
        if previous != stamp:
            raise RuntimeError(
                "Bed support already refined differently; rebuild before changing parameters"
            )
        return {"changed_objects": [], "config": asdict(c), "already_applied": True}
    mattress = bpy.data.objects.get("Mattress")
    sheet = bpy.data.objects.get("BedV2_Rose_Sheet")
    quilt = bpy.data.objects.get("BedV2_Blue_Quilt_Folded")
    if mattress is None or sheet is None or quilt is None:
        raise RuntimeError("Expected final-layout mattress, cover and quilt")
    # The source mattress's data bounds precede its bevel modifier.
    matrix = np.array(mattress.matrix_world)
    co = np.array([v.co[:] for v in mattress.data.vertices])
    source_top = float((co @ matrix[:3, :3].T + matrix[:3, 3])[:, 2].max())
    if abs(source_top - 0.643) > 0.003:
        raise RuntimeError(
            f"Expected original .643 m mattress top, found {source_top:.6f}; avoid double height correction"
        )
    pose_result = refine_quilt_pose(qc)
    cover_targets = [sheet] + [o for o in bpy.data.objects if o.name.startswith("BedV2_Sheet_")]
    quilt_targets = [quilt] + [
        o for o in bpy.data.objects if o.name.startswith("BedV2_Quilt_bound_edge")
    ]
    rigid_targets = [
        o
        for o in bpy.data.objects
        if o.name == "Mattress" or o.name.startswith(("Mattress_piping", "Bed_support_steel"))
    ]
    changed = []
    for obj in rigid_targets:
        matrix = obj.matrix_world.copy()
        matrix.translation.z -= c.lowering_m
        obj.matrix_world = matrix
        changed.append(obj.name)
    for obj in cover_targets:
        _deform_object(obj, lambda points: warp_sheet_points(points, c))
        changed.append(obj.name)
    # Even-thickness miters are unbounded at the cover's sharp gathered corner
    # normals. A .6 mm half-thickness must not become a 24 cm spike. Normal
    # offset keeps this thin textile shell bounded without altering its base
    # surface, UV coordinates or the visible large-scale drape.
    for modifier in sheet.modifiers:
        if modifier.type == "SOLIDIFY":
            modifier.use_even_offset = False
    for obj in quilt_targets:
        _deform_object(obj, lambda points: release_quilt_lower_shell(points, c))
        changed.append(obj.name)
    for obj in cover_targets + quilt_targets + rigid_targets:
        obj["bed_support_v4_config"] = stamp
    quilt["quilt_pose_v4_status"] = (
        "Pose v4 upper silhouette retained; lower casing released onto photo-constrained support"
    )
    scene["bed_support_v4_config"] = stamp
    return {
        "changed_objects": changed,
        "config": asdict(c),
        "quilt_pose_result": pose_result,
        "mattress_top_m": source_top - c.lowering_m,
        "nominal_cover_top_m": 0.658 - c.lowering_m,
        "retained_quilt_upper_z": c.quilt_retained_upper_z,
    }
