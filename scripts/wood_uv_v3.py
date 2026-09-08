"""Post-layout physical oak UVs; no geometry, shader, or image changes.

Call ``refine_wood_uvs()`` after all furniture transforms, before glTF export.
Existing authored grain-U directions are retained. Independent hash phases are
encoded in UVMap, so native and exported image maps remain registered.

Material properties: wood_uv_period_m (default oak_scan_period_m or 1.8),
wood_uv_no_wrap (default False), wood_uv_padding_texels (default 1).
An explicit object wood_board_id joins split pieces of the same board; those
pieces must have compatible image-map settings and grain axes.
Otherwise parent/semantic-part/spatial-rank IDs distinguish adjacent boards.
Cuboid long faces wrap coherently around the board; end caps have deliberate
chart seams. Separate cabinet rails, stiles and fields remain separate boards.
"""

import hashlib
import math
import re

import bpy
from mathutils import Vector

VERSION = "3.0.0"
DEFAULT_SHADER_SCALE = (1.15 / 1.8, 0.72 / 1.8)


def _fraction(key, axis):
    digest = hashlib.sha256((key + "/phase/" + axis).encode("utf8")).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _semantic(name):
    return re.sub(r"\s+", " ", re.sub(r"\.\d{3,}$", "", name)).strip()


def _oak(mat):
    return mat is not None and ("oak" in mat.name.lower() or mat.get("wood_uv_enabled", False))


def _settings(mat):
    scale = tuple(mat.get("oak_shader_uv_scale", DEFAULT_SHADER_SCALE))[:2]
    mapping = []
    images = []
    if mat.use_nodes:
        for node in mat.node_tree.nodes:
            if node.bl_idname == "ShaderNodeTexImage" and node.image:
                images.append(node.image)
                if node.inputs["Vector"].is_linked:
                    source = node.inputs["Vector"].links[0].from_node
                    if source.bl_idname == "ShaderNodeMapping" and source not in mapping:
                        mapping.append(source)
    if len(mapping) > 1:
        raise ValueError(f"{mat.name}: wood maps must share one Mapping node")
    if mapping:
        node = mapping[0]
        if any(
            abs(v) > 1e-8
            for key in ("Location", "Rotation")
            for v in node.inputs[key].default_value
        ):
            raise ValueError(
                f"{mat.name}: UV refinement expects unrotated, untranslated shader Mapping"
            )
        scale = tuple(node.inputs["Scale"].default_value)[:2]
    period = float(mat.get("wood_uv_period_m", mat.get("oak_scan_period_m", 1.8)))
    if (
        not math.isfinite(period)
        or period <= 0
        or any(not math.isfinite(v) or v <= 0 for v in scale)
    ):
        raise ValueError(f"{mat.name}: invalid wood period or shader scale")
    no_wrap = bool(mat.get("wood_uv_no_wrap", False))
    smallest = min((min(image.size) for image in images if min(image.size) > 0), default=2048)
    padding = float(mat.get("wood_uv_padding_texels", 1.0)) / smallest if no_wrap else 0.0
    if not 0 <= padding < 0.5:
        raise ValueError(f"{mat.name}: invalid wood UV padding")
    return {"scale": scale, "period": period, "no_wrap": no_wrap, "padding": padding}


def _axes(obj, layer):
    """Cache the initial local grain directions so a second call is idempotent."""
    cached = obj.get("wood_uv_v3_face_axes")
    if cached is not None and len(cached) == len(obj.data.polygons) * 6:
        return [
            (Vector(cached[i : i + 3]), Vector(cached[i + 3 : i + 6]))
            for i in range(0, len(cached), 6)
        ]
    result = []
    for poly in obj.data.polygons:
        indices = list(poly.loop_indices)
        p0 = obj.data.vertices[obj.data.loops[indices[0]].vertex_index].co
        uv0 = layer.data[indices[0]].uv
        found = None
        for k in range(1, len(indices) - 1):
            a, b = indices[k], indices[k + 1]
            du1, dv1 = layer.data[a].uv - uv0
            du2, dv2 = layer.data[b].uv - uv0
            determinant = du1 * dv2 - du2 * dv1
            if abs(determinant) < 1e-12:
                continue
            e1 = obj.data.vertices[obj.data.loops[a].vertex_index].co - p0
            e2 = obj.data.vertices[obj.data.loops[b].vertex_index].co - p0
            g = (e1 * dv2 - e2 * dv1) / determinant
            c = (e2 * du1 - e1 * du2) / determinant
            if g.length > 1e-9 and c.length > 1e-9:
                found = (g.normalized(), c.normalized())
                break
        if found is None:
            raise ValueError(f"{obj.name}: face {poly.index} has no usable authored UV frame")
        result.append(found)
    return result


def _frame(matrix, axes):
    g = (matrix @ axes[0]).normalized()
    cross = matrix @ axes[1]
    c = (cross - g * cross.dot(g)).normalized()
    if c.length < 0.99:
        raise ValueError("Degenerate physical wood frame")
    return g, c, g.cross(c).normalized()


def _ids(objects):
    families = {}
    for obj in objects:
        parent = obj.parent.name if obj.parent else "scene"
        key = _semantic(parent) + "/" + _semantic(obj.name)
        families.setdefault(key, []).append(obj)
    result = {}
    for key, members in families.items():
        # Rank in assembly coordinates: moving/yawing a parented assembly does
        # not rename its boards, and Blender .001 creation suffixes are ignored.
        # Unparented repeated parts should supply explicit semantic IDs when
        # later rotations could change their spatial ordering.
        members.sort(key=lambda o: (*[round(v, 7) for v in o.matrix_local.translation], o.name))
        for i, obj in enumerate(members):
            explicit = obj.get("wood_board_id")
            result[obj] = str(explicit) if explicit else f"{key}/board:{i:02d}"
    return result


def refine_wood_uvs():
    """Refine all scene oak mesh UVs and return a JSON-serializable audit.

    Planning/validation completes before mutation. Oversize no-wrap boards,
    incompatible shared-board mappings or missing authored UVs fail explicitly.
    Only UV data and namespaced object metadata change. Shared meshes are copied
    when needed so differently placed linked instances can have different UVs.
    """
    bpy.context.view_layer.update()
    objects = sorted(
        (
            o
            for o in bpy.context.scene.objects
            if o.type == "MESH" and any(_oak(m) for m in o.data.materials)
        ),
        key=lambda o: o.name,
    )
    ids = _ids(objects)
    cached_axes = {}
    groups = {}
    for obj in objects:
        layer = obj.data.uv_layers.get("UVMap") or obj.data.uv_layers.active
        if layer is None:
            raise ValueError(f"{obj.name}: authored UVs required to preserve grain direction")
        cached_axes[obj] = _axes(obj, layer)
        for poly in obj.data.polygons:
            mat = obj.data.materials[poly.material_index]
            if not _oak(mat):
                continue
            key = ids[obj]
            setting = _settings(mat)
            group = groups.setdefault(key, {"settings": setting, "faces": [], "members": set()})
            if group["settings"] != setting:
                raise ValueError(f"{key}: connected board pieces have incompatible UV settings")
            group["members"].add(obj)
            group["faces"].append((obj, poly))

    plans = {}
    report = {
        "version": VERSION,
        "objects": len(objects),
        "boards": len(groups),
        "faces": 0,
        "linked_mesh_copies": [],
        "board_details": [],
    }
    for board_id, group in sorted(groups.items()):
        settings = group["settings"]
        members = group["members"]
        representative = max(members, key=lambda o: (sum(p.area for p in o.data.polygons), o.name))
        poly = max(representative.data.polygons, key=lambda p: p.area)
        g, c, n = _frame(
            representative.matrix_world.to_3x3(), cached_axes[representative][poly.index]
        )
        origin = representative.matrix_world.translation
        points = [o.matrix_world @ v.co - origin for o in members for v in o.data.vertices]
        a0, a1 = min(p.dot(c) for p in points), max(p.dot(c) for p in points)
        b0, b1 = min(p.dot(n) for p in points), max(p.dot(n) for p in points)
        width, thickness = a1 - a0, b1 - b0
        # Only a single rectangular board gets a perimeter chart. Explicitly
        # joined planar pieces instead share one physical frame and origin.
        cuboid = (
            len(members) == 1
            and len(representative.data.vertices) == 8
            and len(representative.data.polygons) == 6
        )
        assignments = []
        for obj, face in group["faces"]:
            fg, fc, fn = _frame(obj.matrix_world.to_3x3(), cached_axes[obj][face.index])
            aligned = abs(fg.dot(g)) > 0.99999
            for li in face.loop_indices:
                point = (
                    obj.matrix_world @ obj.data.vertices[obj.data.loops[li].vertex_index].co
                    - origin
                )
                if aligned:
                    along = point.dot(g)
                    # Coplanar pieces share the representative cross axis. A
                    # perpendicular return needs its own tangent, otherwise a
                    # shared-board projection would collapse that face's UVs.
                    across = point.dot(c if abs(fc.dot(c)) > 0.99999 else fc)
                    if cuboid:
                        # Unfold consecutive long faces around the cross section;
                        # one perimeter seam and end-cap seams remain deliberate.
                        a, b = point.dot(c), point.dot(n)
                        center = obj.matrix_world @ face.center - origin
                        ca, cb = center.dot(c), center.dot(n)
                        nearest = min(
                            (
                                (abs(cb - b0), 0),
                                (abs(ca - a1), 1),
                                (abs(cb - b1), 2),
                                (abs(ca - a0), 3),
                            )
                        )[1]
                        across = (
                            (a - a0),
                            width + (b - b0),
                            width + thickness + (a1 - a),
                            2 * width + thickness + (b1 - b),
                        )[nearest] - width / 2
                else:
                    # Existing end/carcass-face orientation is intentional.
                    along, across = point.dot(fg), point.dot(fc)
                assignments.append(
                    (obj, li, along / settings["period"], across / settings["period"])
                )
        mins = [min(v[2 + i] for v in assignments) for i in range(2)]
        maxs = [max(v[2 + i] for v in assignments) for i in range(2)]
        hashes = [_fraction(board_id, axis) for axis in ("u", "v")]
        phase = hashes[:]
        if settings["no_wrap"]:
            usable = 1 - 2 * settings["padding"]
            spans = [maxs[i] - mins[i] for i in range(2)]
            if any(span > usable + 1e-8 for span in spans):
                required = max(spans) * settings["period"] / usable
                raise ValueError(
                    f"{board_id}: no-wrap chart exceeds {settings['period']:.6g} m period; requires at least {required:.6g} m including perimeter/end charts and image padding"
                )
            phase = [
                settings["padding"] - mins[i] + hashes[i] * max(0, usable - spans[i])
                for i in range(2)
            ]
        for obj, li, u, v in assignments:
            plans.setdefault(obj, {})[li] = (
                (u + phase[0]) / settings["scale"][0],
                (v + phase[1]) / settings["scale"][1],
            )
        bounds = [[mins[i] + phase[i], maxs[i] + phase[i]] for i in range(2)]
        if not all(math.isfinite(v) for bound in bounds for v in bound):
            raise ValueError(f"{board_id}: non-finite UV result")
        report["faces"] += len(group["faces"])
        report["board_details"].append(
            {
                "id": board_id,
                "members": sorted(o.name for o in members),
                "period_m": settings["period"],
                "no_wrap": settings["no_wrap"],
                "hash_fractions": hashes,
                "phase": phase,
                "image_uv_bounds": bounds,
                "perimeter_chart": cuboid,
            }
        )

    for obj, values in plans.items():
        if obj.data.users > 1:
            obj.data = obj.data.copy()
            report["linked_mesh_copies"].append(obj.name)
        layer = obj.data.uv_layers.get("UVMap") or obj.data.uv_layers.active
        for li, uv in values.items():
            layer.data[li].uv = uv
        obj["wood_uv_v3_face_axes"] = [
            v for pair in cached_axes[obj] for axis in pair for v in axis
        ]
        obj["wood_uv_v3_board_id"] = ids[obj]
        obj["wood_uv_v3_version"] = VERSION
        obj.data.update()
    return report
