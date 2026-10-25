"""Small photo-matched reshaping of the blue quilt, after the final bed layout.

Only the blue quilt and its bound-edge seam are changed. The lower contact shell,
sheet, mattress, bed and materials remain outside this operation. This is an
authored smooth deformation informed by sparse tracks and silhouettes, not a
claim of dense photogrammetric reconstruction. Pure ``warp_points`` can be
evaluated without Blender for reproducible projection checks.
"""

from dataclasses import dataclass, asdict
import json
import numpy as np


@dataclass(frozen=True)
class QuiltPoseConfig:
    contact_lock_z: float = 0.675
    motion_transition_height: float = 0.060
    right_shift_x: float = -0.160
    right_shift_y: float = 0.035
    front_shift_y: float = -0.095
    right_height_ratio: float = 0.170
    central_height_ratio: float = 0.580
    front_height_ratio: float = 0.750
    compression_transition_height: float = 0.015
    rear_edge_retention: float = 0.500


def _smooth(values):
    t = np.clip(values, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def warp_points(points, config=None):
    """Return deformed world points, without modifying the input array.

    A horizontal warp followed by monotonic vertical compression keeps the
    contact band exactly fixed. The two stages deliberately separate the
    vertical monotonicity from the horizontal height-dependent motion.
    """
    c = config if isinstance(config, QuiltPoseConfig) else QuiltPoseConfig(**(config or {}))
    p = np.array(points, dtype=np.float64, copy=True)
    if p.ndim != 2 or p.shape[1] != 3 or not np.isfinite(p).all():
        raise ValueError("Quilt points must be a finite N x 3 world-coordinate array")
    if not (
        0 < c.right_height_ratio <= 1
        and 0 < c.central_height_ratio <= 1
        and 0 < c.front_height_ratio <= 1
    ):
        raise ValueError("Height ratios must remain positive and at most one")
    if c.motion_transition_height <= 0 or c.compression_transition_height <= 0:
        raise ValueError("Transition heights must be positive")
    if not 0 <= c.rear_edge_retention <= 1:
        raise ValueError("Rear-edge retention must be between zero and one")
    x, y, z = p.T.copy()
    lift = np.maximum(z - c.contact_lock_z, 0.0)
    motion = _smooth(lift / c.motion_transition_height)
    right = _smooth((x - 0.10) / 0.40) * _smooth((y - 3.82) / 0.19)
    front = _smooth((x + 0.82) / 0.22) * (1 - _smooth((x - 0.05) / 0.25))
    front *= 1 - _smooth((y - 3.82) / 0.24)
    p[:, 0] = x + c.right_shift_x * right * motion
    p[:, 1] = y + (c.right_shift_y * right + c.front_shift_y * front) * motion

    # Weight vertical compression in the already-deformed horizontal frame.
    # This preserves dZ'/dZ > 0 for every fixed post-warp XY coordinate.
    xx, yy = p[:, 0], p[:, 1]
    right_z = _smooth((xx - 0.08) / 0.32) * _smooth((yy - 3.80) / 0.21)
    central = _smooth((xx + 0.84) / 0.44) * (1 - _smooth((xx - 0.20) / 0.22))
    central *= _smooth((yy - 3.87) / 0.20)
    front_z = _smooth((xx + 0.80) / 0.24) * (1 - _smooth((xx - 0.08) / 0.22))
    front_z *= 1 - _smooth((yy - 3.87) / 0.20)
    # The left rear floral roll has a strong five-view anchor; suppress all
    # compression there, with a broad smooth transition to the central fold.
    preserve_left_back = (1 - _smooth((xx + 0.68) / 0.20)) * _smooth((yy - 4.13) / 0.14)
    ratio = 1.0 - (1.0 - c.central_height_ratio) * central
    ratio = ratio * (1 - front_z) + c.front_height_ratio * front_z
    ratio = ratio * (1 - right_z) + c.right_height_ratio * right_z
    # Ref 13 sees the central rear edge against the wall. Retain part of that
    # boundary instead of fitting only the wide views' upper silhouette.
    rear = _smooth((yy - 4.25) / 0.16) * _smooth((xx + 0.65) / 0.20)
    rear *= 1 - _smooth((xx - 0.15) / 0.30)
    ratio += (1 - ratio) * rear * c.rear_edge_retention
    ratio = ratio * (1 - preserve_left_back) + preserve_left_back
    h = c.compression_transition_height
    compressed = ratio * lift + (1 - ratio) * h * (-np.expm1(-lift / h))
    p[:, 2] = np.where(z <= c.contact_lock_z, z, c.contact_lock_z + compressed)
    return p


def refine_quilt_pose(config=None):
    """Apply once after ``refine_layout``; return a compact change manifest.

    The operation is intentionally idempotent within a built scene. Calling it
    with a different configuration after application raises instead of silently
    applying a second deformation. Rebuild the scene to use different settings.
    """
    import bpy

    c = config if isinstance(config, QuiltPoseConfig) else QuiltPoseConfig(**(config or {}))
    stamp = json.dumps(asdict(c), sort_keys=True)
    quilt = bpy.data.objects.get("BedV2_Blue_Quilt_Folded")
    if quilt is None or quilt.type != "MESH":
        raise RuntimeError("Expected BedV2_Blue_Quilt_Folded after final bed layout")
    targets = [quilt] + [
        obj for obj in bpy.data.objects if obj.name.startswith("BedV2_Quilt_bound_edge")
    ]
    for obj in targets:
        previous = obj.get("quilt_pose_v4_config")
        if previous is not None and previous != stamp:
            raise RuntimeError(
                "Quilt already refined with different parameters; rebuild before changing them"
            )
    changed = []
    for obj in targets:
        if obj.get("quilt_pose_v4_config") == stamp:
            continue
        world = np.array(obj.matrix_world, dtype=np.float64)
        inv = np.linalg.inv(world)

        def map_local(coordinates):
            co = np.asarray(coordinates, dtype=np.float64)
            xyz = co @ world[:3, :3].T + world[:3, 3]
            mapped = warp_points(xyz, c)
            return (mapped - world[:3, 3]) @ inv[:3, :3].T

        if obj.type == "MESH":
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            coordinates = np.empty(len(obj.data.vertices) * 3, dtype=np.float64)
            obj.data.vertices.foreach_get("co", coordinates)
            mapped = map_local(coordinates.reshape(-1, 3))
            obj.data.vertices.foreach_set("co", mapped.ravel())
            obj.data.update()
        elif obj.type == "CURVE":
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            for spline in obj.data.splines:
                if spline.type == "BEZIER":
                    for point in spline.bezier_points:
                        coordinates = [point.co[:], point.handle_left[:], point.handle_right[:]]
                        co, left, right = map_local(coordinates)
                        point.co, point.handle_left, point.handle_right = co, left, right
                else:
                    mapped = map_local([point.co[:3] for point in spline.points])
                    for point, co in zip(spline.points, mapped):
                        point.co = (*co, point.co.w)
        else:
            raise RuntimeError("Unsupported bound-edge type: " + obj.type)
        obj["quilt_pose_v4_config"] = stamp
        obj["quilt_pose_v4_status"] = (
            "Photo-constrained authored deformation; base shell locked below 0.675 m"
        )
        changed.append(obj.name)
    return {"changed_objects": changed, "config": asdict(c), "contact_lock_z": c.contact_lock_z}
