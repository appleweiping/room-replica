"""Photo-constrained T-shaped bed guard, after layout and bed_support_v4.

The photographs show two broad uprights around one central opening, a flared
lower connection, and an oak-backed black header. Narrow 30 mm legacy rods and
an outward-positioned mattress support rail were incorrectly visible through
the cover. No textile is cut or otherwise changed by this refinement.
"""

from dataclasses import dataclass, asdict
import json
import math


@dataclass(frozen=True)
class BedGuardConfig:
    top_z: float = 0.754
    header_width: float = 0.747
    header_bottom_z: float = 0.612
    header_depth: float = 0.052
    black_inset_width: float = 0.715
    black_inset_top_z: float = 0.728
    black_inset_bottom_z: float = 0.616
    opening_width: float = 0.155
    opening_bottom_z: float = 0.405
    upright_width: float = 0.052
    lower_base_width: float = 0.460
    lower_base_bottom_z: float = 0.326
    front_support_inset_m: float = 0.035
    mount_under_hem_z: float = 0.194


def _rounded_rectangle(width, bottom, top, radius, steps=7):
    points = []
    for cx, cz, start in [
        (width / 2 - radius, top - radius, 0),
        (-width / 2 + radius, top - radius, 90),
        (-width / 2 + radius, bottom + radius, 180),
        (width / 2 - radius, bottom + radius, 270),
    ]:
        for i in range(steps + 1):
            angle = math.radians(start + 90 * i / steps)
            points.append((cx + radius * math.cos(angle), cz + radius * math.sin(angle)))
    return points


def refine_bed_guard(config=None):
    """Rebuild the guard once, retaining the calibrated header XY and yaw.

    Call after ``refine_bed_support`` and before final oak UV refinement/export.
    Fresh geometry uses the existing black, oak, maroon and steel materials.
    Identical repeated calls do nothing; changed settings require a rebuild.
    """
    import bpy
    from mathutils import Vector
    from mathutils.geometry import tessellate_polygon

    c = config if isinstance(config, BedGuardConfig) else BedGuardConfig(**(config or {}))
    if not (
        0
        < c.opening_width
        < c.opening_width + 2 * c.upright_width
        < c.lower_base_width
        < c.header_width
    ):
        raise ValueError("Guard widths must retain a positive central opening and flared base")
    if not (
        c.mount_under_hem_z
        < c.lower_base_bottom_z
        < c.opening_bottom_z
        < c.header_bottom_z
        < c.top_z
    ):
        raise ValueError("Guard heights must retain the opening and an under-hem mounting route")
    scene = bpy.context.scene
    stamp = json.dumps(asdict(c), sort_keys=True)
    previous = scene.get("bed_guard_v4_config")
    if previous is not None:
        if previous != stamp:
            raise RuntimeError("Guard already refined differently; rebuild to change settings")
        return {"changed_objects": [], "already_applied": True, "config": asdict(c)}
    if scene.get("bed_support_v4_config") is None:
        raise RuntimeError("Apply bed_support_v4 after final layout before refining the guard")
    cap = bpy.data.objects.get("Bed_guard_oak_cap")
    panel = bpy.data.objects.get("Bed_guard_panel")
    if cap is None or panel is None:
        raise RuntimeError("Expected the original calibrated guard header")
    frame = cap.matrix_world.copy()
    frame.translation.z = 0
    oak = cap.data.materials[0]
    black = panel.data.materials[0]
    old_mark = bpy.data.objects.get("Bed_guard_maroon_mark")
    maroon = old_mark.data.materials[0] if old_mark else black
    supports = [o for o in bpy.data.objects if o.name.startswith("Bed_support_steel")]
    if len(supports) < 2:
        raise RuntimeError("Expected front and rear mattress support rails")
    front = min(supports, key=lambda obj: obj.matrix_world.translation.y)
    steel = front.data.materials[0]
    coll = bpy.data.collections.get("07 / Bed guard V4")
    if coll is None:
        coll = bpy.data.collections.new("07 / Bed guard V4")
        scene.collection.children.link(coll)
    changed = []

    def regions_object(name, regions, yfront, yback, material, existing=None, bevel=0.0015):
        # Regions share vertices and boundary edges. Internal interfaces are
        # not extruded, producing one closed, connected lower guard component.
        lookup = {}
        points = []
        triangles = []
        boundaries = {}

        def index(point):
            key = (round(float(point[0]), 8), round(float(point[1]), 8))
            if key not in lookup:
                lookup[key] = len(points)
                points.append(key)
            return lookup[key]

        for region in regions:
            signed_area = sum(
                a[0] * b[1] - b[0] * a[1] for a, b in zip(region, region[1:] + region[:1])
            )
            if signed_area < 0:
                region = list(reversed(region))
            vectors = [Vector((x, z, 0)) for x, z in region]
            ids = [index(v[:2]) for v in vectors]
            for a, b in zip(ids, ids[1:] + ids[:1]):
                key = tuple(sorted((a, b)))
                if key in boundaries:
                    boundaries[key] = None
                else:
                    boundaries[key] = (a, b)
            triangles.extend(
                tuple(ids[v] if isinstance(v, int) else index(v[:2]) for v in triangle)
                for triangle in tessellate_polygon([vectors])
            )
        n = len(points)
        verts = [(x, y, z) for y in [yfront, yback] for x, z in points]
        faces = triangles + [tuple(i + n for i in triangle[::-1]) for triangle in triangles]
        faces.extend(
            (a, a + n, b + n, b)
            for edge in boundaries.values()
            if edge is not None
            for a, b in [edge]
        )
        data = bpy.data.meshes.new(name + " / authored profile")
        data.from_pydata(verts, [], faces)
        data.materials.append(material)
        data.update()
        uv = data.uv_layers.new(name="UVMap")
        for poly in data.polygons:
            # Horizontal grain on the manufactured oak header, in physical
            # units compatible with the existing oak Mapping scale. The end
            # and top faces need separate charts: projecting them all to XZ
            # collapses their UV area and prevents physical wood refinement.
            dominant = max(range(3), key=lambda axis: abs(poly.normal[axis]))
            axes = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[dominant]
            for li in poly.loop_indices:
                co = data.vertices[data.loops[li].vertex_index].co
                uv.data[li].uv = (co[axes[0]] / 1.15 + 0.371, co[axes[1]] / 0.72 + 0.139)
        if existing:
            obj = existing
            obj.data = data
            obj.modifiers.clear()
        else:
            obj = bpy.data.objects.new(name, data)
            coll.objects.link(obj)
        obj.matrix_world = frame.copy()
        if bevel:
            modifier = obj.modifiers.new("Small manufactured edge radius", "BEVEL")
            modifier.width = bevel
            modifier.segments = 3
            obj.modifiers.new("Weighted corner normals", "WEIGHTED_NORMAL")
        obj["bed_guard_v4_config"] = stamp
        changed.append(obj.name)
        return obj

    def rectangle(width, bottom, top):
        return [(-width / 2, bottom), (width / 2, bottom), (width / 2, top), (-width / 2, top)]

    regions_object(
        "Bed_guard_oak_cap",
        [_rounded_rectangle(c.header_width, c.header_bottom_z, c.top_z, 0.018)],
        -c.header_depth / 2,
        c.header_depth / 2,
        oak,
        cap,
        0.0012,
    )
    regions_object(
        "Bed_guard_panel",
        [
            _rounded_rectangle(
                c.black_inset_width, c.black_inset_bottom_z, c.black_inset_top_z, 0.012
            )
        ],
        -c.header_depth / 2 - 0.001,
        -c.header_depth / 2 + 0.0005,
        black,
        panel,
        0.00025,
    )
    half = c.opening_width / 2
    outside = half + c.upright_width
    upper = c.header_bottom_z + 0.020
    # The base flares below the inner opening; the stems join it at shared
    # vertices instead of producing overlapping coplanar black rectangles.
    flare_z = c.opening_bottom_z + 0.013
    wing = c.lower_base_width / 2
    left = [(-outside, upper), (-outside, flare_z), (-half, c.opening_bottom_z), (-half, upper)]
    right = [(half, upper), (half, c.opening_bottom_z), (outside, flare_z), (outside, upper)]
    base = [
        (-outside, flare_z),
        (-wing * 0.74, c.opening_bottom_z - 0.025),
        (-wing, c.opening_bottom_z - 0.055),
        (-wing, c.lower_base_bottom_z),
        (wing, c.lower_base_bottom_z),
        (wing, c.opening_bottom_z - 0.055),
        (wing * 0.74, c.opening_bottom_z - 0.025),
        (outside, flare_z),
        (half, c.opening_bottom_z),
        (-half, c.opening_bottom_z),
    ]
    regions_object(
        "Bed_guard_connected_frame", [left, right, base], -0.025, 0.001, black, bevel=0.0025
    )
    for obj in list(bpy.data.objects):
        if obj.name.startswith("Bed_guard_upright"):
            bpy.data.objects.remove(obj, do_unlink=True)
    # The old single concave ngon looked like an irregular zigzag. Explicitly
    # tessellate a simple block-M silhouette instead, retaining maroon paint.
    outline = [
        (-0.055, -0.031),
        (-0.055, -0.023),
        (-0.043, -0.023),
        (-0.024, 0.026),
        (-0.036, 0.026),
        (-0.036, 0.034),
        (-0.007, 0.034),
        (0, 0.016),
        (0.007, 0.034),
        (0.036, 0.034),
        (0.036, 0.026),
        (0.024, 0.026),
        (0.043, -0.023),
        (0.055, -0.023),
        (0.055, -0.031),
        (0.016, -0.031),
        (0.016, -0.023),
        (0.024, -0.023),
        (0.012, 0.010),
        (0, -0.018),
        (-0.012, 0.010),
        (-0.024, -0.023),
        (-0.016, -0.023),
        (-0.016, -0.031),
    ]
    center_z = (c.black_inset_bottom_z + c.black_inset_top_z) / 2
    regions_object(
        "Bed_guard_maroon_mark",
        [[(x, center_z + z) for x, z in outline]],
        -c.header_depth / 2 - 0.0018,
        -c.header_depth / 2 - 0.0014,
        maroon,
        old_mark,
        0,
    )
    # Move the support into the mattress's footprint, while retaining its
    # calibrated height and end-post overlap. It previously protruded through
    # the drape as horizontal strips and a small triangular fragment.
    old_front = list(front.matrix_world.translation)
    front.matrix_world.translation += frame.to_quaternion() @ Vector(
        (0, c.front_support_inset_m, 0)
    )
    bpy.context.view_layer.update()
    rail_local = frame.inverted() @ front.matrix_world.translation
    mount_y = rail_local.y
    rail_z = rail_local.z

    def box(name, center, size):
        x, y, z = center
        w, d, h = size
        profile = [
            (x - w / 2, z - h / 2),
            (x + w / 2, z - h / 2),
            (x + w / 2, z + h / 2),
            (x - w / 2, z + h / 2),
        ]
        return regions_object(name, [profile], y - d / 2, y + d / 2, steel, bevel=0.001)

    # Unseen connection is inferred, explicitly routed below the intact hem:
    # a narrow steel U strap descends in front, passes underneath, then rises
    # behind the cover to meet the mattress support rail.
    for side in [-1, 1]:
        x = side * (half + 0.018)
        lo = c.mount_under_hem_z
        box(
            "Bed_guard_mount_front",
            (x, 0.005, (lo + c.lower_base_bottom_z + 0.009) / 2),
            (0.023, 0.012, c.lower_base_bottom_z + 0.009 - lo),
        )
        box(
            "Bed_guard_mount_under_hem",
            (x, (0.005 + mount_y) / 2, lo),
            (0.023, mount_y - 0.005 + 0.014, 0.008),
        )
        box(
            "Bed_guard_mount_rear",
            (x, mount_y, (lo + rail_z) / 2),
            (0.023, 0.012, rail_z - lo + 0.012),
        )
    front["bed_guard_v4_support_inset_m"] = c.front_support_inset_m
    changed.append(front.name)
    scene["bed_guard_v4_config"] = stamp
    return {
        "changed_objects": changed,
        "config": asdict(c),
        "header_frame_matrix": [list(row) for row in frame],
        "original_front_support_center": old_front,
        "resolved_front_support_center": list(front.matrix_world.translation),
        "observed_openings": 1,
        "mounts_status": "Inferred under-hem mechanical connection; not directly measured in photographs",
    }
