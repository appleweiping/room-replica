"""Independent chair-back / draped pillowcase candidate, in final room coordinates.

Call ``refine_chair_pillow(M=None)`` AFTER layout_v3.  The calibrated chair seat,
legs and pose are deliberately left untouched.  Only the existing back, its two
support tubes, side fasteners and the four pillowcase objects are replaced or
deformed.  This is a reference-informed shape hypothesis, not measured cloth.
"""

import math

import bpy
import bmesh
from mathutils import Matrix, Vector


ORIGIN = Vector((0.48, 2.22, 0.0))
YAW = math.radians(-11.0)
ROT = Matrix.Rotation(YAW, 3, "Z")
INV = ROT.transposed()
BODY = "Pink patterned pillow on chair / thin sewn rectangular case"
BACK = "Chair curved molded back"
VERSION = "chair_pillow_v4_candidate_2"


def _local(p):
    return INV @ (Vector(p) - ORIGIN)


def _world(p):
    return ORIGIN + ROT @ Vector(p)


def _replace_mesh(ob, vertices, faces, uv=None):
    old = ob.data
    materials = list(old.materials)
    data = bpy.data.meshes.new(ob.name + " / v4 geometry")
    data.from_pydata(vertices, [], faces)
    data.update()
    for mat in materials:
        data.materials.append(mat)
    if uv is not None:
        layer = data.uv_layers.new(name="UVMap")
        for poly in data.polygons:
            for li in poly.loop_indices:
                layer.data[li].uv = uv[data.loops[li].vertex_index]
    for poly in data.polygons:
        poly.use_smooth = True
    ob.modifiers.clear()
    ob.data = data
    ob.matrix_world = Matrix.Identity(4)
    if old.users == 0:
        bpy.data.meshes.remove(old)


def _replace_curve(ob, points, radius, cyclic=False):
    old = ob.data
    data = bpy.data.curves.new(ob.name + " / v4 geometry", "CURVE")
    data.dimensions = "3D"
    data.bevel_depth = radius
    data.bevel_resolution = 2
    data.resolution_u = 1
    for mat in old.materials:
        data.materials.append(mat)
    sp = data.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for p, co in zip(sp.points, points):
        p.co = (*co, 1.0)
    sp.use_cyclic_u = cyclic
    ob.data = data
    ob.matrix_world = Matrix.Identity(4)
    if old.users == 0:
        bpy.data.curves.remove(old)


def _molded_back(ob):
    """Thin curved perforated polypropylene shell, rather than a padded slab."""
    vertices, faces, edge_points = [], [], set()
    half_t = 0.0032

    def pt(s, z, side):
        t = (z - 0.515) / 0.375
        d = -0.122 - 0.121 * t - 0.015 * (s / 0.218) ** 2
        return tuple(_world((d + side * half_t, s, z)))

    cols, rows, step, seg = 14, 10, 0.024, 16
    for j in range(rows):
        for i in range(cols):
            s, z = (i - (cols - 1) / 2) * step, 0.705 + (j - (rows - 1) / 2) * step
            outer, inner = [], []
            for k in range(seg):
                a = 2 * math.pi * k / seg
                ca, sa = math.cos(a), math.sin(a)
                r = step / 2 / max(abs(ca), abs(sa))
                q = (s + r * ca, z + r * sa)
                outer.append(q)
                inner.append((s + 0.00245 * ca, z + 0.00245 * sa))
                if (
                    abs(abs(q[0]) - cols * step / 2) < 1e-7
                    or abs(abs(q[1] - 0.705) - rows * step / 2) < 1e-7
                ):
                    edge_points.add((round(q[0], 9), round(q[1], 9)))
            start = len(vertices)
            for side in (1, -1):
                vertices.extend(pt(*p, side) for p in outer + inner)
            for k in range(seg):
                next_index = (k + 1) % seg
                faces += [
                    (start + k, start + next_index, start + seg + next_index, start + seg + k),
                    (
                        start + 2 * seg + k,
                        start + 3 * seg + k,
                        start + 3 * seg + next_index,
                        start + 2 * seg + next_index,
                    ),
                    (
                        start + seg + k,
                        start + seg + next_index,
                        start + 3 * seg + next_index,
                        start + 3 * seg + k,
                    ),
                ]
    loop = sorted(edge_points, key=lambda p: math.atan2(p[1] - 0.705, p[0]))
    outline = []
    for s, z in loop:
        dz = z - 0.7025
        # Superellipse creates the manufactured rounded corners and retains a
        # broad central face; the unsupported corners must not be pillowy.
        r = ((abs(s) / 0.218) ** 4.5 + (abs(dz) / 0.1875) ** 4.5) ** (-1 / 4.5)
        outline.append((s * r, 0.7025 + dz * r))
    start, count = len(vertices), len(loop)
    for side in (1, -1):
        vertices.extend(pt(*p, side) for p in loop + outline)
    for k in range(count):
        next_index = (k + 1) % count
        faces += [
            (start + k, start + count + k, start + count + next_index, start + next_index),
            (
                start + 2 * count + k,
                start + 2 * count + next_index,
                start + 3 * count + next_index,
                start + 3 * count + k,
            ),
            (
                start + count + k,
                start + 3 * count + k,
                start + 3 * count + next_index,
                start + count + next_index,
            ),
        ]
    uv = [((_local(p).y + 0.218) / 0.436, (_local(p).z - 0.515) / 0.375) for p in vertices]
    _replace_mesh(ob, vertices, faces, uv)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    # World coordinates are float32 in Blender; at Y≈2.2 m neighbouring cells
    # may round by one 0.24 micrometre ULP.  Weld above that representational gap.
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    ob["molded_thickness_m"] = 0.0064
    ob["real_perforations"] = cols * rows


def _catmull(points, t):
    """C1 interpolation through a restrained sagittal drape profile."""
    f = min(1 - 1e-10, max(0.0, t)) * (len(points) - 1)
    i, u = int(f), f % 1
    p0 = Vector(points[max(0, i - 1)])
    p1 = Vector(points[i])
    p2 = Vector(points[min(len(points) - 1, i + 1)])
    p3 = Vector(points[min(len(points) - 1, i + 2)])
    return (
        (2 * p1)
        + (-p0 + p2) * u
        + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u
        + (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u
    ) * 0.5


# Front lower hem -> seat-facing cloth -> rounded crest -> short rear flange.
# d is positive toward the seat front.  Length is cloth length, not box height.
PROFILE = [
    (0.027, 0.478),
    (-0.020, 0.486),
    (-0.080, 0.535),
    (-0.122, 0.630),
    (-0.172, 0.757),
    (-0.202, 0.843),
    (-0.219, 0.879),
    (-0.244, 0.898),
    (-0.269, 0.879),
    (-0.293, 0.832),
    (-0.299, 0.807),
]


def _cloth(u, v):
    d, z = _catmull(PROFILE, v)
    s = (u - 0.5) * 0.464 + 0.004
    # The high end of the support curves down at both corners; the near edge
    # hangs lower.  The lower hem stays on the seat rather than below it.
    across = (u - 0.5) * 2
    top_weight = math.exp(-(((v - 0.72) / 0.20) ** 2))
    # The front free edge is skewed across the seat: its far end curls over the
    # far side, while its near end lies further forward.  This is visible in
    # ref9 versus ref16; those two free corners must not be paired as one point.
    free_weight = max(0.0, 1.0 - v / 0.70) ** 1.1
    s -= 0.052 * free_weight
    d += (-0.055 + 0.145 * (u - 0.5)) * free_weight
    s += 0.020 * (1 - across) * top_weight
    z -= (0.019 * abs(across) ** 5 + 0.031 * max(0.0, across) ** 4) * top_weight
    z -= 0.037 * max(0.0, across) ** 8 * max(0.0, (v - 0.85) / 0.15)
    d += 0.010 * math.sin(u * math.pi) * math.sin(v * math.pi) ** 2
    # Uneven compression and cloth tension: broad low-amplitude folds, no
    # random high-frequency spikes.  Most creases run approximately downslope.
    front = math.exp(-(((v - 0.39) / 0.28) ** 4))
    d += front * (0.0045 * math.sin(29 * u + 5 * v) + 0.0022 * math.sin(53 * u - 8 * v))
    d += 0.009 * math.exp(-(((u - 0.22) / 0.12) ** 2) - ((v - 0.45) / 0.22) ** 2)
    d += front * 0.0065 * math.sin(13 * u - 8 * v + 0.7) * math.sin(math.pi * u)
    z += 0.003 * math.sin(18 * u + 2 * v) * math.sin(math.pi * v) ** 2
    # Soft outward-turning perimeter with shallow hem curls, not a ruler edge.
    edge = math.exp(-((min(u, 1 - u) / 0.025) ** 2))
    d += edge * (0.0024 + 0.0032 * math.sin(13 * v + 0.4))
    z += 0.003 * edge * math.sin(15 * v + 2 * u)
    hem = math.exp(-((v / 0.05) ** 2))
    z += hem * (0.008 * math.sin(9 * u + 0.3) ** 2)
    d += hem * 0.011 * math.sin(7 * u + 0.6)
    # Constraint is applied only on the long front portion; the short rear
    # flange must remain behind the molded shell.
    if v < 0.625 and 0.49 < z < 0.89:
        t = max(0.0, (z - 0.515) / 0.375)
        back_front = -0.1188 - 0.121 * t - 0.015 * (s / 0.218) ** 2
        w = min(1.0, (z - 0.49) / 0.020)
        w = w * w * (3 - 2 * w)
        d += w * max(0.0, back_front + 0.019 - d)
    return _world((d, s, z))


def refine_chair_pillow(M=None):
    """Apply to the calibrated chair only. Safe to call twice; no scene saves."""
    body = bpy.data.objects.get(BODY)
    back = bpy.data.objects.get(BACK)
    if not body or not back:
        raise RuntimeError("chair_pillow_v4 requires the existing chair and pillow objects")
    if body.get("shape_revision") == VERSION:
        return {"revision": VERSION, "already_applied": True}
    # Catch accidental pre-layout calls rather than transforming unrelated data.
    seat = bpy.data.objects.get("Chair perforated molded seat / 225 actual holes")
    bbox = [seat.matrix_world @ Vector(v) for v in seat.bound_box]
    center = sum(bbox, Vector()) / len(bbox)
    basis = seat.matrix_world.to_3x3().col[0].normalized()
    if (Vector((center.x, center.y, 0)) - ORIGIN).length > 0.01 or basis.dot(ROT.col[0]) < 0.9999:
        raise RuntimeError(
            "chair_pillow_v4 must run after chair layout at (0.48, 2.22), yaw -11 deg"
        )

    _molded_back(back)
    back["shape_revision"] = VERSION

    supports = [ob for ob in bpy.data.objects if ob.name.startswith("Chair back supporting tube")]
    for ob in supports:
        for sp in ob.data.splines:
            pts = sp.bezier_points if sp.type == "BEZIER" else sp.points
            for p in pts:
                old = _local(ob.matrix_world @ Vector(p.co[:3]))
                d, s, z = old
                t = min(1.0, max(0.0, (z - 0.40) / 0.12))
                shift = (
                    0.108
                    if z < 0.527
                    else 0.108 * (1 - (z - 0.527) / 0.378) - 0.013 * (z - 0.527) / 0.378
                )
                new = ob.matrix_world.inverted() @ _world((d + shift * t, s, z - 0.012 * t))
                delta = new - Vector(p.co[:3])
                if sp.type == "BEZIER":
                    p.co += delta
                    p.handle_left += delta
                    p.handle_right += delta
                else:
                    p.co = (*new, p.co.w)
        ob["shape_revision"] = VERSION

    # Side pivots are on the lower side rails, not high on the rear fabric face.
    for ob in [o for o in bpy.data.objects if o.name.startswith("Chair back hardware")]:
        coords = [_local(ob.matrix_world @ v.co) for v in ob.data.vertices]
        old_center = sum(coords, Vector()) / len(coords)
        sign = 1 if old_center.y > 0 else -1
        target = Vector((-0.113, sign * 0.222, 0.528))
        inv = ob.matrix_world.inverted()
        for vert, p in zip(ob.data.vertices, coords):
            q = p - old_center
            # Original disk axis d -> transverse s, and correct the visible rim.
            q = Vector((q.y * 2.15, q.x * sign, q.z * 2.15))
            vert.co = inv @ _world(target + q)
        ob.data.update()
        ob["shape_revision"] = VERSION

    nx, ny = 80, 120
    vertices = [tuple(_cloth(i / nx, j / ny)) for j in range(ny + 1) for i in range(nx + 1)]
    uv = [(i / nx, j / ny) for j in range(ny + 1) for i in range(nx + 1)]
    faces = []
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    _replace_mesh(body, vertices, faces, uv)
    # The photographed front is a lightly filled/compressed case.  Its central
    # loft fades to a thin sewn flange and almost vanishes on the rear fold.
    # A weighted shell avoids both a paper surface and an ellipsoidal cushion.
    weights = body.vertex_groups.new(name="Compressed filling retained between seams")
    for j in range(ny + 1):
        v = j / ny
        front_loft = math.exp(-(((v - 0.36) / 0.31) ** 4))
        for i in range(nx + 1):
            u = i / nx
            w = math.sin(math.pi * u) ** 0.8 * front_loft
            w *= min(1.0, v / 0.05) * min(1.0, (1 - v) / 0.05)
            weights.add([j * (nx + 1) + i], max(0.0, w), "REPLACE")
    solid = body.modifiers.new("Soft compressed case with thin sewn flange", "SOLIDIFY")
    solid.thickness = 0.023
    solid.offset = 0.0
    solid.vertex_group = weights.name
    solid.thickness_vertex_group = 0.055
    # Reuse the authored damask image, keeping its provenance.  Give its muted
    # ink the contrast visible in refs2/9; this material is private to this case.
    source_mat = body.data.materials[0]
    mat = source_mat.copy()
    mat.name = "Pillowcase v4 / dusty rose woven damask"
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    shader = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    image_nodes = [n for n in nodes if n.type == "TEX_IMAGE"]
    if image_nodes:
        grey = nodes.new("ShaderNodeRGBToBW")
        contrast = nodes.new("ShaderNodeValToRGB")
        contrast.label = "Muted rose cotton field with darker printed damask ink"
        ramp = contrast.color_ramp
        ramp.interpolation = "EASE"
        ramp.elements.remove(ramp.elements[1])
        for i, (pos, color) in enumerate(
            [
                (0.22, (0.065, 0.044, 0.052, 1)),
                (0.40, (0.165, 0.103, 0.116, 1)),
                (0.55, (0.45, 0.335, 0.326, 1)),
                (0.59, (0.64, 0.53, 0.485, 1)),
            ]
        ):
            el = ramp.elements[0] if i == 0 else ramp.elements.new(pos)
            el.position = pos
            el.color = color
        links.new(image_nodes[0].outputs["Color"], grey.inputs[0])
        links.new(grey.outputs[0], contrast.inputs[0])
        links.new(contrast.outputs["Color"], shader.inputs["Base Color"])
    shader.inputs["Roughness"].default_value = 0.83
    shader.inputs["Sheen Weight"].default_value = 0.16
    body.data.materials[0] = mat
    body["shape_revision"] = VERSION
    body["shape_evidence"] = (
        "refs2/9 rear-flange feature points; ref16 front drape/seat contact; hidden support inferred"
    )

    seam = bpy.data.objects.get("Pillow perimeter seam follows cloth")
    boundary = (
        [(i / nx, 0) for i in range(nx + 1)]
        + [(1, j / ny) for j in range(1, ny + 1)]
        + [(i / nx, 1) for i in range(nx - 1, -1, -1)]
        + [(0, j / ny) for j in range(ny - 1, 0, -1)]
    )
    _replace_curve(seam, [_cloth(u, v) for u, v in boundary], 0.0005, True)
    for name, v in [("Pillow stitched hem", 0.023), ("Pillow stitched hem.001", 0.978)]:
        ob = bpy.data.objects.get(name)
        _replace_curve(ob, [_cloth(i / 100, v) for i in range(101)], 0.00024)
    bpy.context.view_layer.update()
    return {
        "revision": VERSION,
        "body_vertices": len(vertices),
        "body_quads": len(faces),
        "seat_legs_pose_unchanged": True,
        "new_objects": 0,
        "observed_back_flange_only_not_full_cloth_scan": True,
    }
