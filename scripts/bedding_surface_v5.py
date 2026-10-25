"""Localized pressure folds for the already calibrated blue quilt.

This is a fixed surface refinement, not another macro pose or cloth
solve. Curved, branching crease fans redistribute the outer filling by a few
millimetres. A monotonic vertical map leaves the contact casing untouched and
cannot reverse the ordering of surfaces above the same XY point. The printed
albedo, UVs, shell topology, sheet, mattress, frame and calibrated pose are kept.
"""

from dataclasses import asdict, dataclass
import json
import numpy as np


@dataclass(frozen=True)
class BeddingSurfaceConfig:
    amplitude: float = 1.35
    displacement_limit_m: float = 0.020
    contact_lock_z: float = 0.680
    release_height_m: float = 0.080
    seed: int = 52105


def _smooth(t):
    t = np.clip(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _creases(seed):
    """Authored pressure centres with reproducible unequal branching folds."""
    rng = np.random.default_rng(seed)
    paths = []
    # Position, fan direction/spread, number, length and vertical amplitude.
    # The centres follow the existing major valleys; directions are deliberately
    # unrelated between neighbouring patches instead of one global wave field.
    fans = [
        ((-0.29, 4.04), 1.45, 2.30, 9, 0.23, 0.010),
        ((0.31, 4.12), 0.95, 2.90, 8, 0.22, 0.009),
        ((-0.68, 3.98), 2.00, 2.35, 7, 0.20, 0.009),
        ((0.12, 3.79), 1.65, 2.55, 7, 0.18, 0.008),
        ((-0.55, 4.25), 3.60, 1.60, 6, 0.19, 0.007),
        ((0.47, 3.87), 2.50, 2.00, 5, 0.15, 0.006),
    ]
    for centre, direction, spread, count, length, height in fans:
        for i in range(count):
            angle = direction + spread * ((i + rng.uniform(0.05, 0.95)) / count - 0.5)
            along = np.array([np.cos(angle), np.sin(angle)])
            across = np.array([-along[1], along[0]])
            start = np.array(centre) + rng.normal(0, 0.012, 2)
            run = length * rng.uniform(0.60, 1.23)
            end = start + along * run
            control = (
                start + along * run * rng.uniform(0.35, 0.70) + across * rng.uniform(-0.028, 0.028)
            )
            width = rng.uniform(0.0045, 0.011)
            paths.append((start, control, end, width, height * rng.uniform(0.65, 1.15)))
    # Sparse independent diagonal compression folds break the long front roll.
    for start, control, end, width, height in [
        ((-0.50, 3.70), (-0.47, 3.81), (-0.36, 3.86), 0.009, 0.011),
        ((-0.09, 3.72), (-0.18, 3.78), (-0.17, 3.89), 0.010, 0.010),
        ((-0.02, 4.15), (-0.13, 4.24), (-0.29, 4.22), 0.012, 0.012),
        ((0.47, 4.03), (0.49, 4.12), (0.60, 4.18), 0.008, 0.009),
    ]:
        paths.append((np.array(start), np.array(control), np.array(end), width, height))
    return paths


def fold_field(xy, config=None):
    """Signed displacement before vertical release; metres in world XY."""
    c = (
        config
        if isinstance(config, BeddingSurfaceConfig)
        else BeddingSurfaceConfig(**(config or {}))
    )
    xy = np.asarray(xy, dtype=np.float64)
    displacement = np.zeros(len(xy))
    for start, control, end, width, height in _creases(c.seed):
        t = np.linspace(0, 1, 15)
        curve = (
            (1 - t[:, None]) ** 2 * start
            + 2 * (1 - t[:, None]) * t[:, None] * control
            + t[:, None] ** 2 * end
        )
        lo, hi = curve.min(0) - width * 4, curve.max(0) + width * 4
        ids = np.flatnonzero(((xy >= lo) & (xy <= hi)).all(1))
        if not len(ids):
            continue
        q = xy[ids]
        best = np.full(len(q), np.inf)
        signed, progress = np.zeros(len(q)), np.zeros(len(q))
        for j, (a, b) in enumerate(zip(curve[:-1], curve[1:])):
            tangent = b - a
            u = np.clip((q - a) @ tangent / np.dot(tangent, tangent), 0, 1)
            delta = q - (a + u[:, None] * tangent)
            distance = np.linalg.norm(delta, axis=1)
            chosen = distance < best
            sign = np.sign(tangent[0] * delta[:, 1] - tangent[1] * delta[:, 0])
            signed[chosen] = distance[chosen] * sign[chosen]
            progress[chosen] = (j + u[chosen]) / (len(curve) - 1)
            best[chosen] = distance[chosen]
        d = signed / width
        # A compressed sharp valley beside two unequal soft shoulders. These
        # are not cylindrical tubes: the crease tapers and bends along its run.
        profile = 0.85 * np.exp(-(((d - 0.88) / 1.32) ** 2)) + 0.35 * np.exp(
            -(((d + 1.22) / 1.60) ** 2)
        )
        profile -= 1.65 * np.exp(-((d / 0.43) ** 2))
        taper = _smooth(progress / 0.17) * (1 - _smooth((progress - 0.69) / 0.31))
        displacement[ids] += height * profile * taper
    # Do not modify the registered left rear floral roll or the free rear edge.
    x, y = xy.T
    mask = _smooth((x + 0.98) / 0.10) * (1 - _smooth((x - 0.62) / 0.10))
    mask *= _smooth((y - 3.65) / 0.09) * (1 - _smooth((y - 4.28) / 0.11))
    preserve = (1 - _smooth((x + 0.70) / 0.18)) * _smooth((y - 4.16) / 0.13)
    mask *= 1 - preserve
    return (
        c.displacement_limit_m * np.tanh(c.amplitude * displacement / c.displacement_limit_m) * mask
    )


def warp_surface_points(points, config=None):
    """Return the warped points (displacement capped, never folding over itself); inputs are not modified."""
    c = (
        config
        if isinstance(config, BeddingSurfaceConfig)
        else BeddingSurfaceConfig(**(config or {}))
    )
    if not 0 < c.displacement_limit_m <= 0.020 or c.release_height_m <= 0:
        raise ValueError("Use a positive displacement limit (at most 20 mm) and release height")
    if c.displacement_limit_m * 1.5 >= c.release_height_m:
        raise ValueError("Vertical derivative could reverse; increase release height")
    if c.contact_lock_z + c.release_height_m > 0.825:
        raise ValueError("Contact release and crown preservation must not overlap")
    if not 0 <= c.amplitude <= 2.0:
        raise ValueError("Surface amplitude must be between zero and two")
    p = np.array(points, dtype=np.float64, copy=True)
    if p.ndim != 2 or p.shape[1] != 3 or not np.isfinite(p).all():
        raise ValueError("Expected finite N x 3 world coordinates")
    release = _smooth((p[:, 2] - c.contact_lock_z) / c.release_height_m)
    # Fade above the original high crown rather than lifting the old maximum.
    crown = 1 - _smooth((p[:, 2] - 0.825) / 0.033)
    p[:, 2] += fold_field(p[:, :2], c) * release * crown
    return p


def refine_bedding_surface(config=None):
    """Apply after bed_support_v4, once; retain direct image albedo and all UVs."""
    import bpy

    c = (
        config
        if isinstance(config, BeddingSurfaceConfig)
        else BeddingSurfaceConfig(**(config or {}))
    )
    scene = bpy.context.scene
    if not scene.get("bed_support_v4_config"):
        raise RuntimeError("Surface refinement requires the resolved bed support")
    stamp = json.dumps(asdict(c), sort_keys=True)
    previous = scene.get("bedding_surface_v5_config")
    if previous:
        if previous != stamp:
            raise RuntimeError("Rebuild before changing applied surface parameters")
        return {"changed_objects": [], "config": asdict(c), "already_applied": True}
    quilt = bpy.data.objects.get("BedV2_Blue_Quilt_Folded")
    if quilt is None or quilt.type != "MESH":
        raise RuntimeError("Expected the calibrated blue quilt mesh")
    targets = [quilt] + [o for o in bpy.data.objects if o.name.startswith("BedV2_Quilt_bound_edge")]
    changed = []
    bounds = []
    for obj in targets:
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        matrix = np.array(obj.matrix_world)
        inverse = np.linalg.inv(matrix)

        def mapped(local):
            world = np.asarray(local) @ matrix[:3, :3].T + matrix[:3, 3]
            after = warp_surface_points(world, c)
            if obj == quilt:
                delta = after - world
                bounds.append(
                    {
                        "min_dz_m": float(delta[:, 2].min()),
                        "max_dz_m": float(delta[:, 2].max()),
                        "before_bounds": [world.min(0).tolist(), world.max(0).tolist()],
                        "after_bounds": [after.min(0).tolist(), after.max(0).tolist()],
                    }
                )
            return (after - matrix[:3, 3]) @ inverse[:3, :3].T

        if obj.type == "MESH":
            coordinates = np.empty(len(obj.data.vertices) * 3)
            obj.data.vertices.foreach_get("co", coordinates)
            obj.data.vertices.foreach_set("co", mapped(coordinates.reshape(-1, 3)).ravel())
            obj.data.update()
        elif obj.type == "CURVE":
            for spline in obj.data.splines:
                if spline.type == "BEZIER":
                    for point in spline.bezier_points:
                        co, left, right = mapped(
                            [point.co[:], point.handle_left[:], point.handle_right[:]]
                        )
                        point.co, point.handle_left, point.handle_right = co, left, right
                else:
                    for point, co in zip(spline.points, mapped([p.co[:3] for p in spline.points])):
                        point.co = (*co, point.co.w)
        else:
            raise RuntimeError("Unsupported bound seam type: " + obj.type)
        obj["bedding_surface_v5_config"] = stamp
        changed.append(obj.name)
    scene["bedding_surface_v5_config"] = stamp
    return {
        "changed_objects": changed,
        "config": asdict(c),
        "bounds": bounds,
        "crease_paths": len(_creases(c.seed)),
        "albedo_and_uv_unchanged": True,
    }
