"""Refine floor-prop geometry before any room-layout transforms.

Call ``refine_floor_prop_geometry(M)`` after ``props.build`` and before
``layout_v3.refine_layout``. Construction coordinates intentionally remain the
original ones: storage at (.665, .82), chair at (.38, 1.78), metres, Z up.
The original lid, latches, stored items, chair seat/back and pillow are retained.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Vector

VERSION = "3.0.0"
BODY_NAME = "StorageV3 / tapered continuous body"
STORAGE_COLLECTION = "Props / Transparent storage box"
CHAIR_COLLECTION = "Props / Black desk chair"
LEGACY_BODY_PREFIX = "Storage bin translucent body"
MARKER = "floor_prop_geometry_version"


def _rounded_rectangle(width, length, radius, segments=12):
    """Counter-clockwise closed perimeter without duplicate end vertices."""
    points = []
    for cx, cy, start in (
        (width / 2 - radius, length / 2 - radius, 0),
        (-width / 2 + radius, length / 2 - radius, math.pi / 2),
        (-width / 2 + radius, -length / 2 + radius, math.pi),
        (width / 2 - radius, -length / 2 + radius, 3 * math.pi / 2),
    ):
        for i in range(segments + 1):
            angle = start + i * math.pi / (2 * segments)
            points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def _storage_shell(group):
    existing = bpy.data.objects.get(BODY_NAME)
    if existing and existing.get(MARKER) == VERSION:
        return existing, []
    legacy = [o for o in group.objects if o.name.startswith(LEGACY_BODY_PREFIX)]
    if len(legacy) != 5:
        raise RuntimeError("Floor-prop refinement expects the five original storage-body panels")
    material = next((o.data.materials[0] for o in legacy if o.data.materials), None)
    if material is None:
        raise RuntimeError("Original storage polypropylene material is missing")

    # Outer wall rises from a narrower base to the unchanged lid seat. The
    # profile then returns down the inside to form a real, closed plastic shell.
    # Base .385 x .465; upper lip .426 x .530; wall gauge about 3.5 mm.
    profile = (
        (0.017, 0.379, 0.459, 0.024),
        (0.020, 0.385, 0.465, 0.029),
        (0.029, 0.386, 0.466, 0.029),
        (0.329, 0.424, 0.528, 0.031),
        (0.334, 0.426, 0.530, 0.032),
        (0.338, 0.426, 0.530, 0.032),
        (0.338, 0.419, 0.523, 0.0285),
        (0.333, 0.419, 0.523, 0.0285),
        (0.030, 0.379, 0.459, 0.0255),
        (0.023, 0.377, 0.457, 0.0245),
    )
    vertices, faces = [], []
    ring_count = len(_rounded_rectangle(*profile[0][1:]))
    for z, width, length, radius in profile:
        vertices.extend(
            (0.665 + x, 0.82 + y, z) for x, y in _rounded_rectangle(width, length, radius)
        )
    for row in range(len(profile) - 1):
        for i in range(ring_count):
            j = (i + 1) % ring_count
            a, b = row * ring_count + i, row * ring_count + j
            faces.append((a, b, b + ring_count, a + ring_count))
    faces.append(tuple(range(ring_count - 1, -1, -1)))
    faces.append(tuple((len(profile) - 1) * ring_count + i for i in range(ring_count)))

    mesh = bpy.data.meshes.new(BODY_NAME)
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    mesh.update()
    uv = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        polygon.use_smooth = polygon.index < len(faces) - 2
        for loop_index in polygon.loop_indices:
            index = mesh.loops[loop_index].vertex_index
            x, y, z = vertices[index]
            if polygon.index >= len(faces) - 2:
                uv.data[loop_index].uv = ((x - 0.44) / 0.45, (y - 0.54) / 0.557)
            else:
                row, column = divmod(index, ring_count)
                # Resolve the periodic seam locally on the final perimeter quad.
                u = column / ring_count
                if polygon.index % ring_count == ring_count - 1 and column == 0:
                    u = 1
                uv.data[loop_index].uv = (u, z / 0.338)
    obj = bpy.data.objects.new(BODY_NAME, mesh)
    group.objects.link(obj)
    obj[MARKER] = VERSION
    obj["geometry_note"] = "Closed tapered polypropylene shell; original lid and contents retained"
    obj["outer_base_xy"] = [0.385, 0.465]
    obj["outer_upper_xy"] = [0.426, 0.530]
    removed = [o.name for o in legacy]
    for old in legacy:
        bpy.data.objects.remove(old, do_unlink=True)
    return obj, removed


def _chair_lower_legs(group):
    legs = [o for o in group.objects if o.name.startswith("Chair tubular steel leg")]
    feet = [o for o in group.objects if o.name.startswith("Chair rubber foot")]
    if len(legs) != 4 or len(feet) != 4:
        raise RuntimeError("Floor-prop refinement expects four chair legs and four rubber feet")
    changed = []
    for obj in legs:
        if obj.get(MARKER) == VERSION:
            continue
        if obj.type != "CURVE" or len(obj.data.splines) != 1:
            raise RuntimeError("Original chair leg must be a single spline")
        if obj.data.users > 1:
            obj.data = obj.data.copy()
        spline = obj.data.splines[0]
        points = spline.bezier_points if spline.type == "BEZIER" else spline.points
        worlds = [obj.matrix_world @ Vector(point.co[:3]) for point in points]
        lower = min(worlds, key=lambda co: co.z)
        sx = 1 if lower.x > 0.38 else -1
        sy = 1 if lower.y > 1.78 else -1
        expected = Vector((0.38 + sx * 0.205, 1.78 + sy * 0.208, 0.04))
        if (lower - expected).length > 0.0001:
            raise RuntimeError("Chair geometry must be refined before layout transforms")
        target = Vector((0.38 + sx * 0.235, 1.78 + sy * 0.260, lower.z))
        delta = target - lower
        inverse = obj.matrix_world.inverted()
        for point, world in zip(points, worlds):
            # Keep the seat attachment fixed; smoothly increase the offset down
            # the lower leg. Existing curve radius, material and topology stay.
            t = min(1.0, max(0.0, (0.442 - world.z) / (0.442 - 0.04)))
            local = inverse @ (world + delta * t * t)
            if spline.type == "BEZIER":
                point.co = local
            else:
                point.co = (*local, point.co.w)
        obj[MARKER] = VERSION
        changed.append(obj.name)
    for obj in feet:
        if obj.get(MARKER) == VERSION:
            continue
        matrix = obj.matrix_world.copy()
        origin = matrix.translation
        sx = 1 if origin.x > 0.38 else -1
        sy = 1 if origin.y > 1.78 else -1
        matrix.translation = Vector((0.38 + sx * 0.235, 1.78 + sy * 0.260, origin.z))
        obj.matrix_world = matrix
        obj[MARKER] = VERSION
        changed.append(obj.name)
    return changed


def refine_floor_prop_geometry(M):
    """Replace storage walls and widen only the chair's lower support geometry.

    ``M`` follows the other refinement interfaces. This module reuses the
    original prop materials directly and does not edit any material settings.
    Repeated calls before layout are idempotent.
    """
    storage = bpy.data.collections.get(STORAGE_COLLECTION)
    chair = bpy.data.collections.get(CHAIR_COLLECTION)
    if storage is None or chair is None:
        raise RuntimeError("Call refine_floor_prop_geometry after props.build")
    bpy.context.view_layer.update()
    body, removed = _storage_shell(storage)
    changed = _chair_lower_legs(chair)
    bpy.context.view_layer.update()
    return {
        "version": VERSION,
        "storage_body": body.name,
        "storage_removed": removed,
        "storage_vertices": len(body.data.vertices),
        "storage_faces": len(body.data.polygons),
        "chair_changed": changed,
        "chair_foot_center_span_xy": [0.47, 0.52],
    }
