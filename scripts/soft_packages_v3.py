"""Low-profile kitchen carrier bags reconstructed from reference photograph 1.

Call ``refine_soft_packages(M)`` immediately after ``props.build`` and before
``fittings_v2.refine_fittings``. Coordinates are the original kitchen-prop
coordinates; the existing kitchen collection owns subsequent layout transforms.
Only the old white/black carrier bags are replaced. The cap, bottles and zipped
pouch remain separate. All lettering is original, generic geometric artwork.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Vector

PREFIX = "PackageV3 / "
COLLECTION = "Props / Kitchen counter details"
LEGACY_PREFIXES = (
    "Kitchen large white crumpled shopping bag",
    "White shopping bag sealed edge",
    "Shopping bag burgundy authored store print",
    "Shopping bag small authored lettering",
    "Shopping bag burgundy flattened handle",
    "Kitchen crushed dark plastic carrier bag",
    "Dark bag folded loop handle",
    "Dark bag gathered upper mouth",
)


def _material(name, color, roughness):
    name = PREFIX + name
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    nodes = mat.node_tree.nodes
    nodes.clear()
    bs = nodes.new("ShaderNodeBsdfPrincipled")
    bs.inputs["Base Color"].default_value = (*color, 1)
    bs.inputs["Roughness"].default_value = roughness
    bs.inputs["IOR"].default_value = 1.47
    bs.inputs["Specular IOR Level"].default_value = 0.35
    bs.inputs["Coat Weight"].default_value = 0.065
    bs.inputs["Coat Roughness"].default_value = 0.32
    out = nodes.new("ShaderNodeOutputMaterial")
    mat.node_tree.links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 340
    noise.inputs["Detail"].default_value = 2
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.13
    bump.inputs["Distance"].default_value = 0.00005
    mat.node_tree.links.new(noise.outputs["Fac"], bump.inputs["Height"])
    mat.node_tree.links.new(bump.outputs["Normal"], bs.inputs["Normal"])
    return mat


def _mesh(name, vertices, faces, mat, group, uv=None, thickness=0):
    data = bpy.data.meshes.new(PREFIX + name)
    data.from_pydata(vertices, [], faces)
    data.update()
    data.materials.append(mat)
    obj = bpy.data.objects.new(PREFIX + name, data)
    group.objects.link(obj)
    for poly in data.polygons:
        poly.use_smooth = True
    if uv:
        layer = data.uv_layers.new(name="UVMap")
        for poly in data.polygons:
            for loop in poly.loop_indices:
                layer.data[loop].uv = uv[data.loops[loop].vertex_index]
    if thickness:
        mod = obj.modifiers.new("Thin film gauge", "SOLIDIFY")
        mod.thickness = thickness
        mod.offset = 0
    obj["authorship"] = "Reference-informed procedural carrier-bag geometry v3"
    return obj


def _grid(name, surface, mat, group, nu=96, nv=72, thickness=0.00012):
    verts = [surface(i / nu, j / nv) for j in range(nv + 1) for i in range(nu + 1)]
    uv = [(i / nu, j / nv) for j in range(nv + 1) for i in range(nu + 1)]
    faces = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
    return _mesh(name, verts, faces, mat, group, uv, thickness)


def _gauss(x, y, cx, cy, sx, sy):
    return math.exp(-(((x - cx) / sx) ** 2) - ((y - cy) / sy) ** 2)


def _white_surface(u, v, bottom=False):
    # A full-sized thin bag lies on a diagonal. Two compressed broad folds are
    # much shallower than the previous narrow high ridges. The mouth is +u.
    a, b = 2 * u - 1, 2 * v - 1
    gather = min(1, max(0, (u - 0.72) / 0.28))
    gather = gather * gather * (3 - 2 * gather)
    xx = a * 0.323 * (1 - 0.038 * b**8)
    yy = b * 0.205 * (1 - 0.10 * a**8) * (1 - 0.25 * gather)
    xx -= 0.006 * gather * math.sin(v * 17 + 0.3)
    xx += 0.0038 * math.sin(v * 8 + 0.8) * abs(a) ** 5
    yy += 0.0030 * math.sin(u * 12 + 0.4) * abs(b) ** 5
    angle = -0.25
    x = 0.080 + math.cos(angle) * xx - math.sin(angle) * yy
    y = 0.350 + math.sin(angle) * xx + math.cos(angle) * yy
    edge = max(0, math.sin(math.pi * u) * math.sin(math.pi * v))
    # Shallow corner curls give the separated films a readable edge thickness.
    edge_lift = 0.004 * _gauss(u, v, 0.04, 0.12, 0.18, 0.21)
    edge_lift += 0.023 * _gauss(u, v, 0.04, 0.97, 0.16, 0.14)
    mouth = 0.003 * gather * (0.55 + 0.45 * math.cos(v * 14))
    z = 0.9411 + edge_lift + mouth
    if not bottom:
        z += 0.0013 + 0.010 * edge
        z += 0.033 * math.exp(-(((v - 0.24 - 0.29 * u) / 0.052) ** 2)) * edge
        z += 0.021 * math.exp(-(((u - 0.23 + 0.16 * v) / 0.048) ** 2)) * edge
        z += 0.0040 * math.sin(u * 21 + v * 12) * edge
        z += 0.0020 * math.sin(u * 61 - v * 29) * edge
        z += 0.020 * gather * (0.38 + 0.62 * math.sin(math.pi * v))
        z += 0.007 * gather * math.sin(v * 26 + 1.3) ** 2
    return (x, y, z)


def _white_height(x, y):
    # The XY deformation is <=4 mm; a conservative 1.8 mm clearance is retained
    # by the handles when using this inverse nominal surface mapping.
    xx, yy = x - 0.080, y - 0.350
    a = -0.25
    u = (math.cos(a) * xx + math.sin(a) * yy) / 0.646 + 0.5
    v = (-math.sin(a) * xx + math.cos(a) * yy) / 0.410 + 0.5
    du, dv = max(0, -u, u - 1) * 0.646, max(0, -v, v - 1) * 0.410
    z = _white_surface(min(1, max(0, u)), min(1, max(0, v)))[2]
    # Taper a conservative support envelope over a centimetre beyond the edge;
    # a hard inside/outside test produces a visible vertical cliff in black film.
    return 0.9411 + (z - 0.9411) * math.exp(-(du * du + dv * dv) / 0.012**2)


def _black_surface(u, v, bottom=False):
    # Compressed bag has a 34 x 23 cm footprint and roughly 5 cm total relief.
    # Rounded low-frequency pleats establish its folds without isolated spikes.
    a, b = 2 * u - 1, 2 * v - 1
    xx = a * 0.169 * (1 - 0.105 * b**6)
    yy = b * 0.110 * (1 - 0.16 * a**6)
    xx += 0.003 * math.sin(v * 10 + 0.5) * abs(a) ** 4
    yy += 0.004 * math.sin(u * 13) * abs(b) ** 4
    x = 0.284 + math.cos(0.10) * xx - math.sin(0.10) * yy
    y = 0.159 + math.sin(0.10) * xx + math.cos(0.10) * yy
    edge = max(0, math.sin(math.pi * u) * math.sin(math.pi * v))
    # Support follows the white bag wherever the two overlap, without a step.
    support = _white_height(x, y)
    z = max(0.942, support + 0.0012)
    if not bottom:
        z += 0.0016 + 0.016 * edge
        z += 0.026 * _gauss(u, v, 0.32, 0.60, 0.31, 0.23) * edge
        z += 0.017 * _gauss(u, v, 0.78, 0.28, 0.22, 0.30) * edge
        z += 0.011 * math.exp(-(((v - 0.23 - u * 0.32) / 0.09) ** 2)) * edge
        z += 0.0023 * math.sin(u * 31 + v * 19) * edge
        z += 0.0010 * math.sin(v * 47 - u * 11) * edge
    return x, y, z


def _black_height(x, y):
    xx, yy = x - 0.284, y - 0.159
    u = (math.cos(0.1) * xx + math.sin(0.1) * yy) / 0.338 + 0.5
    v = (-math.sin(0.1) * xx + math.cos(0.1) * yy) / 0.220 + 0.5
    if not (0 <= u <= 1 and 0 <= v <= 1):
        return _white_height(x, y)
    return _black_surface(u, v)[2]


def _closed_sheets(name, surface, mat, group, nu, nv, open_mouth=False):
    # Two continuous films are joined at their boundary. Their enclosed relief
    # is compressed air/creased folds rather than an arbitrary thick solid slab.
    top = [surface(i / nu, j / nv) for j in range(nv + 1) for i in range(nu + 1)]
    bottom = [surface(i / nu, j / nv, True) for j in range(nv + 1) for i in range(nu + 1)]
    verts = top + bottom
    count = len(top)
    uv = [(i / nu, j / nv) for j in range(nv + 1) for i in range(nu + 1)] * 2
    faces = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.extend(
                (
                    (a, a + 1, a + nu + 2, a + nu + 1),
                    (a + count, a + count + nu + 1, a + count + nu + 2, a + count + 1),
                )
            )
    boundary = (
        list(range(nu + 1))
        + [j * (nu + 1) + nu for j in range(1, nv + 1)]
        + [nv * (nu + 1) + i for i in range(nu - 1, -1, -1)]
        + [j * (nu + 1) for j in range(nv - 1, 0, -1)]
    )
    for i, a in enumerate(boundary):
        b = boundary[(i + 1) % len(boundary)]
        if open_mouth and a % (nu + 1) == nu and b % (nu + 1) == nu:
            continue
        faces.append((a, a + count, b + count, b))
    return _mesh(name, verts, faces, mat, group, uv, 0.00010 if open_mouth else 0)


def _ribbon(name, path, width, mat, group, floor, twist=0, count=120):
    # Cubic Bezier path avoids interpolation overshoot at flattened handles.
    points = [Vector(p) for p in path]

    def center(t):
        s = 1 - t
        return (
            s**3 * points[0]
            + 3 * s * s * t * points[1]
            + 3 * s * t * t * points[2]
            + t**3 * points[3]
        )

    def surface(u, v):
        p = center(u)
        tangent = center(min(1, u + 0.0005)) - center(max(0, u - 0.0005))
        across = tangent.cross(Vector((0, 0, 1))).normalized()
        angle = twist * math.sin(math.pi * u)
        across = across * math.cos(angle) + Vector((0, 0, math.sin(angle)))
        p += across * (v - 0.5) * width
        p.z = max(p.z, floor(p.x, p.y) + 0.0020)
        p.z += 0.0008 * math.sin(u * 27) * math.sin(math.pi * v)
        return tuple(p)

    return _grid(name, surface, mat, group, count, 8, 0.00030)


def _print(name, body, origin, size, mat, group):
    # Convert editable font curves, subdivide once to limit triangles bridging
    # folds, then conform to exactly the same white upper-film surface.
    data = bpy.data.curves.new(PREFIX + name + " font", "FONT")
    data.body = body
    data.size = size
    data.space_character = 1.08
    data.resolution_u = 8
    obj = bpy.data.objects.new(PREFIX + name + " font", data)
    group.objects.link(obj)
    bpy.context.view_layer.update()
    temp = bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(temp)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    for _ in range(7):
        edges = [e for e in bm.edges if e.calc_length() > 0.004]
        if not edges:
            break
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bm.to_mesh(temp)
    bm.free()
    vertices = []
    for vert in temp.vertices:
        u = origin[0] + vert.co.x
        v = origin[1] + vert.co.y
        x, y, z = _white_surface(u, v)
        vertices.append((x, y, z + 0.00025))
    faces, seen = [], set()
    # Font triangulation followed by partial edge subdivision can emit duplicate
    # coplanar triangles around glyph junctions. Keep one winding per triangle.
    for poly in temp.polygons:
        face = tuple(poly.vertices)
        key = tuple(sorted(face))
        if key not in seen:
            seen.add(key)
            faces.append(face)
    _mesh(name, vertices, faces, mat, group)
    bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.curves.remove(data)
    bpy.data.meshes.remove(temp)


def refine_soft_packages(M):
    """Replace old carriers only; return an audit summary. Safe to call again."""
    del M  # Materials are independent to avoid mutating other room plastics.
    group = bpy.data.collections.get(COLLECTION)
    if group is None:
        group = bpy.data.collections.new(COLLECTION)
        bpy.context.scene.collection.children.link(group)
    removed = []
    for obj in list(bpy.data.objects):
        if obj.name.startswith(LEGACY_PREFIXES + (PREFIX,)):
            removed.append(obj.name)
            old_data = obj.data
            old_type = obj.type
            bpy.data.objects.remove(obj, do_unlink=True)
            if old_data and old_data.users == 0:
                if old_type == "MESH":
                    bpy.data.meshes.remove(old_data)
                elif old_type in {"CURVE", "FONT", "SURFACE"}:
                    bpy.data.curves.remove(old_data)
    white = _material("white polyethylene", (0.78, 0.782, 0.753), 0.32)
    black = _material("soft charcoal polyethylene", (0.018, 0.019, 0.0195), 0.40)
    burgundy = _material("burgundy print and handles", (0.105, 0.012, 0.023), 0.57)
    _closed_sheets(
        "White carrier flattened body", _white_surface, white, group, 112, 80, open_mouth=True
    )
    _closed_sheets("Black carrier compressed folds", _black_surface, black, group, 96, 72)

    # Heat-sealed outer margin is a film strip rather than a raised rope border.
    for v, suffix in ((0.010, "near"), (0.990, "far")):

        def seam(u, w, v=v):
            x, y, z = _white_surface(u, v + (w - 0.5) * 0.009)
            return x, y, z + 0.00016

        _grid("White heat seal " + suffix, seam, white, group, 112, 3, 0.00009)

    _print("White carrier maroon monogram", "U", (0.21, 0.27), 0.38, burgundy, group)
    _print("White carrier store lettering", "UNIVERSITY", (0.19, 0.64), 0.075, burgundy, group)
    _print(
        "White carrier books lettering", "BOOKS & SUPPLIES", (0.20, 0.18), 0.048, burgundy, group
    )

    # Handles run from the gathered (+X) mouth and collapse back toward the
    # foreground. Wide thin ribbons carry a small torsion, never cable loops.
    a, b = _white_surface(0.996, 0.20), _white_surface(0.996, 0.77)
    _ribbon(
        "White carrier relaxed burgundy handle near",
        [a, (0.260, 0.568, 0.974), (0.120, 0.505, 0.957), b],
        0.0085,
        burgundy,
        group,
        _white_height,
        twist=0.31,
    )
    a, b = _white_surface(0.996, 0.24), _white_surface(0.996, 0.73)
    _ribbon(
        "White carrier relaxed burgundy handle far",
        [a, (0.293, 0.522, 0.969), (0.175, 0.467, 0.982), b],
        0.0080,
        burgundy,
        group,
        _white_height,
        twist=-0.24,
    )

    # A loose fold at the black bag mouth exposes a thin doubled lip. The flap
    # follows the existing body so no vertex is pushed into its carrier sheet.
    def lip(u, v):
        x = 0.155 + 0.227 * u
        y = 0.142 + 0.022 * math.sin(u * math.pi) + (v - 0.5) * 0.032
        z = (
            _black_height(x, y)
            + 0.0021
            + 0.015 * math.sin(math.pi * v) ** 2 * math.sin(math.pi * u)
        )
        z += 0.0015 * math.sin(u * 21 + v * 5) * math.sin(math.pi * u)
        return x, y, z

    _grid("Black carrier loose doubled mouth", lip, black, group, 96, 20, 0.00015)
    _ribbon(
        "Black carrier slack handle one",
        [
            (0.190, 0.173, 0.976),
            (0.177, 0.262, 1.020),
            (0.354, 0.283, 1.000),
            (0.332, 0.174, 0.979),
        ],
        0.017,
        black,
        group,
        _black_height,
        twist=0.4,
    )
    _ribbon(
        "Black carrier slack handle two",
        [
            (0.180, 0.145, 0.974),
            (0.107, 0.216, 1.006),
            (0.276, 0.263, 0.995),
            (0.308, 0.155, 0.979),
        ],
        0.014,
        black,
        group,
        _black_height,
        twist=-0.3,
    )

    created = [o for o in group.objects if o.name.startswith(PREFIX)]
    return {
        "version": 3,
        "collection": COLLECTION,
        "removed_names": removed,
        "created_names": [o.name for o in created],
        "object_count": len(created),
        "base_vertices": sum(len(o.data.vertices) for o in created if o.type == "MESH"),
        "coordinates": "Original kitchen props; run before fittings_v2 and layout_v3",
    }
