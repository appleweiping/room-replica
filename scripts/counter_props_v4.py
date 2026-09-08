"""Independent kitchen-counter detail candidate in the inherited kitchen frame.

Run ``refine_counter_props(M=None)`` AFTER layout_v3. Existing PackageV3 geometry
provides the original-to-final transform, so its scale and grounded height are
preserved. Only this counter collection is touched. No photographed room or
screen is projected onto geometry; all new shapes and neutral print are authored.
"""

from __future__ import annotations

import math
import random
from functools import lru_cache

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

VERSION = "counter_props_v4_3"
PREFIX = "CounterV4 / "
GROUP = "Props / Kitchen counter details"
BASE = 0.9411
_WHITE_SUPPORT = None
_BLACK_SUPPORT = None
OLD_PREFIXES = (
    "PackageV3 /",
    "Olive cap",
    "Cap crown",
    "Cap small",
    "Cap curved",
    "Cap visor",
    "Kitchen flattened black zip pouch",
    "Black pouch",
    "Clear water bottle",
    "Bottle water",
    "Green bottle",
    "Bottle green",
    "Bottle cap",
    "Bottle molded",
    "Cream insulated travel bottle",
    "Travel bottle",
)


def _mat(label, color, rough=0.45, metallic=0, transmission=0, vertex=False):
    mat = bpy.data.materials.new(PREFIX + label)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    bs = mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (*color, 1)
    bs.inputs["Roughness"].default_value = rough
    bs.inputs["Metallic"].default_value = metallic
    bs.inputs["Transmission Weight"].default_value = transmission
    bs.inputs["IOR"].default_value = 1.46
    if vertex:
        attr = mat.node_tree.nodes.new("ShaderNodeVertexColor")
        attr.layer_name = "SurfaceTone"
        mat.node_tree.links.new(attr.outputs["Color"], bs.inputs["Base Color"])
    return mat


def _mesh(name, verts, faces, mat, group, transform, uv=None, thickness=0, tone=None):
    data = bpy.data.meshes.new(PREFIX + name)
    data.from_pydata(verts, [], faces)
    data.update()
    data.materials.append(mat)
    ob = bpy.data.objects.new(PREFIX + name, data)
    group.objects.link(ob)
    ob.matrix_world = transform
    for p in data.polygons:
        p.use_smooth = True
    if uv is not None:
        layer = data.uv_layers.new(name="UVMap")
        for loop in data.loops:
            layer.data[loop.index].uv = uv[loop.vertex_index]
    if tone is None and any(n.type == "VERTEX_COLOR" for n in mat.node_tree.nodes):

        def tone(i, v):
            return tuple(mat.diffuse_color[:3])

    if tone:
        col = data.color_attributes.new(name="SurfaceTone", type="FLOAT_COLOR", domain="POINT")
        for i, v in enumerate(verts):
            col.data[i].color = (*tone(i, v), 1)
    if thickness:
        mod = ob.modifiers.new("Real thin material gauge", "SOLIDIFY")
        mod.thickness = thickness
        mod.offset = 0
    ob["detail_revision"] = VERSION
    return ob


def _grid(name, surface, mat, group, transform, nu=80, nv=60, thickness=0, tone=None):
    vv = [surface(i / nu, j / nv) for j in range(nv + 1) for i in range(nu + 1)]
    ff = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            ff.append((a, a + 1, a + nu + 2, a + nu + 1))
    return _mesh(
        name,
        vv,
        ff,
        mat,
        group,
        transform,
        [(i / nu, j / nv) for j in range(nv + 1) for i in range(nu + 1)],
        thickness,
        tone,
    )


def _tone(color, frequency=45, strength=0.045):
    def tone(i, v):
        x, y, z = v
        # Low-contrast pigment variation, not precomputed scene lighting.
        variation = (
            math.sin(x * frequency + y * 13.7) * 0.42
            + math.sin(y * frequency * 1.83 - z * 47.3) * 0.28
            + math.sin((x + y) * frequency * 3.1) * 0.15
        )
        return tuple(c * (1 + strength * variation) for c in color)

    return tone


def _gauss(u, v, x, y, sx, sy):
    return math.exp(-(((u - x) / sx) ** 2) - ((v - y) / sy) ** 2)


def _fold(u, v, intercept, slope, bow, width, amp, center=0.5, length=0.43):
    d = v - intercept - slope * u - bow * (u - 0.5) ** 2
    envelope = math.exp(-(((u - center) / length) ** 4))
    return (
        amp
        * (
            math.exp(-((d / width) ** 2))
            - 0.36 * math.exp(-(((d + 1.5 * width) / (width * 0.7)) ** 2))
        )
        * envelope
    )


def _paper_crease(u, v, intercept, slope, width, amp, center=0.5, length=0.5):
    d = v - intercept - slope * u
    # Narrow radiused fold with planar-looking flanks, not a rounded air tube.
    profile = math.exp(-math.sqrt(d * d + 0.000018) / width)
    valley = 0.32 * math.exp(-math.sqrt((d + width * 1.6) ** 2 + 0.000008) / (width * 0.7))
    return amp * (profile - valley) * math.exp(-(((u - center) / length) ** 4))


@lru_cache(maxsize=16)
def _tri_grid(seed, cols, rows):
    rng = random.Random(seed)
    return tuple(tuple(rng.uniform(-1, 1) for i in range(cols + 1)) for j in range(rows + 1))


def _tri_field(u, v, seed, cols=8, rows=6):
    data = _tri_grid(seed, cols, rows)
    x = min(cols - 1e-6, max(0, u * cols))
    y = min(rows - 1e-6, max(0, v * rows))
    i, j = int(x), int(y)
    a, b = x - i, y - j
    p00, p10, p01, p11 = data[j][i], data[j][i + 1], data[j + 1][i], data[j + 1][i + 1]
    if a + b <= 1:
        return p00 + (p10 - p00) * a + (p01 - p00) * b
    return p11 + (p01 - p11) * (1 - a) + (p10 - p11) * (1 - b)


def _white_xy(u, v):
    a, b = 2 * u - 1, 2 * v - 1
    gather = min(1, max(0, (u - 0.72) / 0.28))
    gather = gather * gather * (3 - 2 * gather)
    x = 0.323 * a * (1 - 0.062 * b**8) - 0.007 * gather * (0.5 + math.cos(v * 16))
    y = 0.202 * b * (1 - 0.15 * a**8) * (1 - 0.24 * gather)
    x += 0.032 * max(0, 1 - u / 0.23) ** 2 * (0.7 + 0.3 * math.sin(math.pi * v))
    x += 0.007 * math.sin(v * 8 + 0.9) * abs(a) ** 6
    y += 0.011 * math.sin(u * 7 + 0.4) * abs(b) ** 6
    angle = -0.25
    xx = 0.080 + math.cos(angle) * x - math.sin(angle) * y
    yy = 0.350 + math.sin(angle) * x + math.cos(angle) * y
    return xx, yy


def _white_surface(u, v, bottom=False):
    xx, yy = _white_xy(u, v)
    gather = min(1, max(0, (u - 0.72) / 0.28))
    gather = gather * gather * (3 - 2 * gather)
    edge = max(0, math.sin(math.pi * u) * math.sin(math.pi * v))
    bottomz = BASE + 0.00035 + 0.014 * _gauss(u, v, 0.045, 0.96, 0.13, 0.17)
    bottomz += 0.029 * _gauss(u, v, 0.018, 0.12, 0.13, 0.20)
    bottomz += 0.006 * gather * (0.3 + 0.7 * math.sin(math.pi * v))
    if bottom:
        return xx, yy, bottomz
    relief = 0.003 + 0.030 * edge**0.75
    relief += 0.042 * _gauss(u, v, 0.33, 0.23, 0.24, 0.22) * edge
    relief += 0.008 * _gauss(u, v, 0.78, 0.73, 0.18, 0.24) * edge
    for params in (
        (0.17, 0.42, 0.017, 0.025, 0.55, 0.48),
        (0.75, -0.44, 0.012, 0.020, 0.55, 0.40),
        (0.54, 0.29, 0.008, 0.013, 0.40, 0.33),
        (0.91, -0.05, 0.009, 0.016, 0.27, 0.25),
        (0.09, 0.71, 0.010, 0.022, 0.77, 0.25),
        (0.44, -0.3, 0.007, 0.012, 0.39, 0.31),
    ):
        relief += _paper_crease(u, v, *params) * edge
    relief += _paper_crease(v, u, 0.13, 0.24, 0.018, 0.027, 0.5, 0.47) * edge
    relief += 0.006 * _tri_field(u, v, 81, 13, 9) * edge
    relief += 0.019 * gather * (0.3 + 0.7 * math.sin(math.pi * v))
    return xx, yy, bottomz + max(0.0015, relief)


def _support_cache(body):
    count = len(body.data.vertices) // 2
    vv = [v.co.copy() for v in body.data.vertices[:count]]
    faces = []
    for poly in body.data.polygons:
        f = list(poly.vertices)
        if max(f) >= count:
            continue
        for j in range(1, len(f) - 1):
            faces.append((f[0], f[j], f[j + 1]))
    flat = [Vector((p.x, p.y, 0)) for p in vv]
    return BVHTree.FromPolygons(flat, faces, all_triangles=True), vv, faces


def _support_height(cache, x, y, floor):
    if cache is None:
        return floor
    tree, points, faces = cache
    q, normal, index, distance = tree.find_nearest(Vector((x, y, 0)))
    if index is None:
        return floor
    a, b, c = (points[i] for i in faces[index])
    denom = (b.y - c.y) * (a.x - c.x) + (c.x - b.x) * (a.y - c.y)
    if abs(denom) < 1e-14:
        return floor
    wa = ((b.y - c.y) * (q.x - c.x) + (c.x - b.x) * (q.y - c.y)) / denom
    wb = ((c.y - a.y) * (q.x - c.x) + (a.x - c.x) * (q.y - c.y)) / denom
    z = wa * a.z + wb * b.z + (1 - wa - wb) * c.z
    # A 10 mm feather continues the physical edge to its support without a
    # height discontinuity. Interior queries use the actual triangle surface.
    return floor + (z - floor) * math.exp(-((distance / 0.010) ** 2))


def _white_height(x, y):
    return _support_height(_WHITE_SUPPORT, x, y, BASE)


def _black_surface(u, v, bottom=False):
    a, b = 2 * u - 1, 2 * v - 1
    x = 0.172 * a * (1 - 0.15 * b**6) + 0.007 * math.sin(v * 9 + 0.8) * abs(a) ** 4
    y = 0.112 * b * (1 - 0.19 * a**6) + 0.005 * math.sin(u * 12 + 0.3) * abs(b) ** 4
    xx = 0.289 + math.cos(0.12) * x - math.sin(0.12) * y
    yy = 0.153 + math.sin(0.12) * x + math.cos(0.12) * y
    support = max(BASE + 0.0007, _white_height(xx, yy) + 0.001)
    if bottom:
        return xx, yy, support
    edge = max(0, math.sin(math.pi * u) * math.sin(math.pi * v))
    z = 0.002 + 0.023 * edge**0.7
    z += 0.034 * _gauss(u, v, 0.29, 0.54, 0.32, 0.25) * edge
    z += 0.024 * _gauss(u, v, 0.76, 0.27, 0.22, 0.30) * edge
    z += _paper_crease(u, v, 0.17, 0.44, 0.040, 0.039, 0.5, 0.55) * edge
    z += _paper_crease(u, v, 0.72, -0.33, 0.021, 0.035, 0.4, 0.33) * edge
    z += _paper_crease(v, u, 0.18, 0.45, 0.017, 0.024, 0.54, 0.5) * edge
    z += 0.017 * _tri_field(u, v, 521, 9, 6) * edge
    z += 0.004 * _tri_field(u, v, 942, 23, 15) * edge
    return xx, yy, support + max(0.002, z)


def _black_height(x, y):
    return _support_height(_BLACK_SUPPORT, x, y, _white_height(x, y))


def _bag(name, surface, mat, group, transform, nu=96, nv=72, tone=None, open_mouth=True):
    count = (nu + 1) * (nv + 1)
    vv = [
        surface(i / nu, j / nv, bottom)
        for bottom in (False, True)
        for j in range(nv + 1)
        for i in range(nu + 1)
    ]
    uv = [(i / nu, j / nv) for j in range(nv + 1) for i in range(nu + 1)] * 2
    ff = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            ff.extend(
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
    for k, a in enumerate(boundary):
        b = boundary[(k + 1) % len(boundary)]
        if open_mouth and a % (nu + 1) == nu and b % (nu + 1) == nu:
            continue  # Open mouth, then real sub-millimetre film solidify.
        ff.append((a, a + count, b + count, b))
    return _mesh(name, vv, ff, mat, group, transform, uv, 0.00018 if open_mouth else 0, tone)


def _tube(name, points, radius, mat, group, transform, closed=False):
    data = bpy.data.curves.new(PREFIX + name, "CURVE")
    data.dimensions = "3D"
    data.bevel_depth = radius
    data.bevel_resolution = 2
    data.use_fill_caps = True
    sp = data.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for p, co in zip(sp.points, points):
        p.co = (*co, 1)
    sp.use_cyclic_u = closed
    data.materials.append(mat)
    ob = bpy.data.objects.new(PREFIX + name, data)
    group.objects.link(ob)
    ob.matrix_world = transform
    ob["detail_revision"] = VERSION
    return ob


def _ribbon(name, path, width, mat, group, transform, floor, twist=0.3):
    pts = [Vector(p) for p in path]

    def center(t):
        return (
            (1 - t) ** 3 * pts[0]
            + 3 * (1 - t) ** 2 * t * pts[1]
            + 3 * (1 - t) * t * t * pts[2]
            + t**3 * pts[3]
        )

    def surface(u, v):
        p = center(u)
        tangent = center(min(1, u + 0.001)) - center(max(0, u - 0.001))
        across = tangent.cross(Vector((0, 0, 1))).normalized()
        angle = twist * math.sin(math.pi * u)
        p += (across * math.cos(angle) + Vector((0, 0, math.sin(angle)))) * (v - 0.5) * width
        p.z = max(p.z, floor(p.x, p.y) + 0.0013)
        return tuple(p)

    return _grid(name, surface, mat, group, transform, 100, 6, 0.0007)


def _cord(name, path, mat, group, transform, floor):
    pts = [Vector(p) for p in path]
    points = []
    for i in range(161):
        t = i / 160
        p = (
            (1 - t) ** 3 * pts[0]
            + 3 * (1 - t) ** 2 * t * pts[1]
            + 3 * (1 - t) * t * t * pts[2]
            + t**3 * pts[3]
        )
        p.z = max(p.z, floor(p.x, p.y) + 0.003)
        points.append(tuple(p))
    _tube(name, points, 0.0025, mat, group, transform)


def _lathe(name, center, profile, mat, group, transform, n=96, radius_offset=None, closed=True):
    # Dense authored profile preserves bottle shoulder/rolled seam transitions.
    vv = []
    uv = []
    for i, (z, r) in enumerate(profile):
        for j in range(n):
            a = 2 * math.pi * j / n
            rr = r + (radius_offset(z, a) if radius_offset else 0)
            vv.append((center[0] + rr * math.cos(a), center[1] + rr * math.sin(a), center[2] + z))
            uv.append((j / n, z / (profile[-1][0] or 1)))
    ff = []
    for i in range(len(profile) - 1):
        for j in range(n):
            a = i * n + j
            b = i * n + (j + 1) % n
            ff.append((a, b, b + n, a + n))
    if closed:
        ff.extend((0, j + 1, j) for j in range(1, n - 1))
        off = (len(profile) - 1) * n
        ff.extend((off, off + j, off + j + 1) for j in range(1, n - 1))
    return _mesh(name, vv, ff, mat, group, transform, uv)


def _profile_smooth(knots, per=5):
    # Cubic Hermite with centred slopes gives smooth, non-stepped shoulder slopes.
    result = []
    for i in range(len(knots) - 1):
        z0, r0 = knots[i]
        z1, r1 = knots[i + 1]
        dz = z1 - z0
        a = knots[max(0, i - 1)]
        b = knots[min(len(knots) - 1, i + 1)]
        m0 = (b[1] - a[1]) / (b[0] - a[0])
        a = knots[i]
        b = knots[min(len(knots) - 1, i + 2)]
        m1 = (b[1] - a[1]) / (b[0] - a[0])
        for j in range(per):
            t = j / per
            r = (
                (2 * t**3 - 3 * t * t + 1) * r0
                + (t**3 - 2 * t * t + t) * dz * m0
                + (-2 * t**3 + 3 * t * t) * r1
                + (t**3 - t * t) * dz * m1
            )
            result.append((z0 + dz * t, max(0.0002, r)))
    return result + [knots[-1]]


def _print(name, text, origin, size, surface, mat, group, transform):
    data = bpy.data.curves.new(PREFIX + name, "FONT")
    data.body = text
    data.size = size
    data.resolution_u = 4
    tmp = bpy.data.objects.new(PREFIX + "temporary glyph", data)
    group.objects.link(tmp)
    bpy.context.view_layer.update()
    mesh = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.triangulate(bm, faces=list(bm.faces))
    for i in range(5):
        edges = [e for e in bm.edges if e.calc_length() > 0.005]
        if not edges:
            break
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=list(bm.faces))
    bm.to_mesh(mesh)
    bm.free()
    vv = []
    for v in mesh.vertices:
        p = Vector(surface(origin[0] + v.co.x, origin[1] + v.co.y))
        p.z += 0.0003
        vv.append(tuple(p))
    seen = set()
    ff = []
    for p in mesh.polygons:
        key = tuple(sorted(p.vertices))
        if key not in seen:
            seen.add(key)
            ff.append(tuple(p.vertices))
    _mesh(name, vv, ff, mat, group, transform)
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(data)
    bpy.data.meshes.remove(mesh)


def _cap(group, transform):
    olivecolor = (0.105, 0.108, 0.085)
    olive = _mat("washed charcoal olive cotton", olivecolor, 0.82, vertex=True)
    seam = _mat("cap dark olive seam", (0.057, 0.062, 0.047), 0.86)
    cx, cy = 0.508, 0.278

    def crown(t, a):
        r = math.sin(math.pi * 0.5 * t)
        x = cx + 0.087 * r * math.cos(a)
        y = cy + 0.081 * r * math.sin(a)
        z = BASE + 0.002 + 0.102 * math.cos(math.pi * 0.5 * t)
        edge = math.sin(math.pi * t)
        z -= 0.017 * math.exp(-(((a - 1.1) / 0.7) ** 2)) * edge
        z += 0.006 * math.exp(-(((a - 4.4) / 0.6) ** 2)) * edge
        x += 0.0028 * math.sin(a * 7.3 + t * 8) * edge
        return x, y, z

    n, rows = 96, 48
    vv = [crown(i / rows, 2 * math.pi * j / n) for i in range(rows + 1) for j in range(n)]
    ff = []
    for i in range(rows):
        for j in range(n):
            a = i * n + j
            b = i * n + (j + 1) % n
            ff.append((a, a + n, b + n, b))
    # Weld coincident top pole before validating (all panel rays meet here).
    ob = _mesh(
        "Olive cap six panel slumped crown",
        vv,
        ff,
        olive,
        group,
        transform,
        [(j / n, i / rows) for i in range(rows + 1) for j in range(n)],
        0.0014,
        _tone(olivecolor, 170, 0.09),
    )
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-7)
    bm.to_mesh(ob.data)
    bm.free()
    for j in range(6):
        a = 2 * math.pi * j / 6
        _tube(
            "Cap paired panel stitch %d" % j,
            [crown(i / 70, a) for i in range(2, 71)],
            0.00035,
            seam,
            group,
            transform,
        )

    def brim(u, v):
        xx = (u - 0.5) * 0.172
        arch = math.sqrt(max(0, 1 - (2 * u - 1) ** 2))
        yy = 0.025 + v * (0.045 + 0.077 * arch)
        z = BASE + 0.004 + 0.012 * (2 * u - 1) ** 2 - 0.002 * v + 0.003 * math.sin(u * 5 + 0.6) * v
        return cx + xx, cy + yy, z

    _grid(
        "Cap asymmetric curved visor",
        brim,
        olive,
        group,
        transform,
        80,
        38,
        0.0022,
        _tone(olivecolor, 180, 0.06),
    )
    for v in (0.68, 0.79, 0.90):
        _tube(
            "Cap visor fine stitch %.2f" % v,
            [tuple(Vector(brim(i / 120, v)) + Vector((0, 0, 0.0012))) for i in range(121)],
            0.00028,
            seam,
            group,
            transform,
        )
    _lathe(
        "Cap cloth button",
        (cx, cy, BASE + 0.102),
        [(0, 0.0045), (0.001, 0.005), (0.0035, 0.003)],
        olive,
        group,
        transform,
        n=32,
    )
    # Eyelets are small stitched rings on the actual crown surface, not black holes.
    for a in (0.58, 2.6, 4.4):
        points = [
            crown(0.39 + 0.015 * math.cos(t), a + 0.037 * math.sin(t))
            for t in [2 * math.pi * j / 32 for j in range(32)]
        ]
        _tube("Cap stitched ventilation eyelet", points, 0.00048, seam, group, transform, True)


def _wallet(group, transform):
    color = (0.010, 0.012, 0.013)
    leather = _mat("black coated zipped wallet", color, 0.47, vertex=True)
    seam = _mat("wallet dark edge and zip", (0.025, 0.027, 0.026), 0.58)
    cx, cy = 0.226, 0.562
    angle = -0.19

    def xy(u, v):
        x = (2 * u - 1) * 0.082 * (1 - 0.055 * (2 * v - 1) ** 8)
        y = (2 * v - 1) * 0.041 * (1 - 0.12 * (2 * u - 1) ** 8)
        return cx + math.cos(angle) * x - math.sin(angle) * y, cy + math.sin(angle) * x + math.cos(
            angle
        ) * y

    def face(u, v, bottom=False):
        x, y = xy(u, v)
        edge = max(0, math.sin(math.pi * u) * math.sin(math.pi * v))
        support = max(BASE, _white_height(x, y)) + 0.0007
        z = support + 0.001 if bottom else support + 0.022 + 0.003 * edge
        return x, y, z

    _bag(
        "Wallet soft rectangular case",
        face,
        leather,
        group,
        transform,
        60,
        32,
        _tone(color, 210, 0.1),
        False,
    )
    boundary = (
        [xy(i / 90, 0) for i in range(91)]
        + [xy(1, j / 40) for j in range(1, 41)]
        + [xy(i / 90, 1) for i in range(89, -1, -1)]
        + [xy(0, j / 40) for j in range(39, 0, -1)]
    )
    _tube(
        "Wallet narrow zipper band",
        [(x, y, _white_height(x, y) + 0.0127) for x, y in boundary],
        0.0008,
        seam,
        group,
        transform,
        True,
    )
    _tube(
        "Wallet double edge seam",
        [(x, y, _white_height(x, y) + 0.0222) for x, y in boundary],
        0.00042,
        seam,
        group,
        transform,
        True,
    )
    silver = _mat("wallet oxidized zip pull", (0.13, 0.14, 0.14), 0.43, 0.7)
    x, y = xy(0.13, 0.97)
    points = [
        (x + 0.013 * math.cos(t), y + 0.004 * math.sin(t), _white_height(x, y) + 0.014)
        for t in [2 * math.pi * j / 28 for j in range(28)]
    ]
    _tube("Wallet short zipper tab", points, 0.0011, silver, group, transform, True)


def _bottles(group, transform):
    pet = _mat("slightly misted molded PET", (0.73, 0.78, 0.735), 0.26, transmission=0.86)
    water = _mat("clear water", (0.86, 0.92, 0.88), 0.15, transmission=1)
    water.node_tree.nodes.get("Principled BSDF").inputs["IOR"].default_value = 1.333
    green = _mat("green printed soda label", (0.009, 0.30, 0.127), 0.36)
    capmat = _mat("dark green polypropylene closure", (0.007, 0.095, 0.043), 0.34)
    ink = _mat("label ivory ink", (0.80, 0.85, 0.75), 0.5)
    cx, cy = 0.64, 0.31
    knots = [
        (0, 0.028),
        (0.004, 0.040),
        (0.012, 0.0445),
        (0.028, 0.046),
        (0.045, 0.044),
        (0.075, 0.043),
        (0.10, 0.043),
        (0.167, 0.043),
        (0.207, 0.042),
        (0.229, 0.038),
        (0.246, 0.030),
        (0.266, 0.020),
        (0.279, 0.0157),
        (0.292, 0.0154),
        (0.296, 0.0157),
    ]

    def ribs(z, a):
        feet = 0.0037 * (0.5 + 0.5 * math.cos(5 * a)) * math.exp(-(((z - 0.013) / 0.018) ** 2))
        grip = -0.0011 * math.exp(-(((z - 0.052) / 0.003) ** 2)) - 0.0008 * math.exp(
            -(((z - 0.063) / 0.003) ** 2)
        )
        return feet + grip

    shell = _lathe(
        "Bottle smooth shoulder PET shell",
        (cx, cy, BASE),
        _profile_smooth(knots),
        pet,
        group,
        transform,
        96,
        ribs,
    )
    mod = shell.modifiers.new("PET wall thickness 0.35mm", "SOLIDIFY")
    mod.thickness = 0.00035
    mod.offset = -1
    # Raised water level follows the reference's hazy shoulder. The earlier low
    # horizontal closed cap caused a conspicuous dark meniscus above the label.
    _lathe(
        "Bottle actual lower water volume",
        (cx, cy, BASE + 0.006),
        _profile_smooth(
            [
                (0, 0.038),
                (0.01, 0.042),
                (0.207, 0.040),
                (0.229, 0.036),
                (0.25, 0.025),
                (0.265, 0.0185),
            ]
        ),
        water,
        group,
        transform,
        96,
    )
    _lathe(
        "Bottle emerald printed sleeve",
        (cx, cy, BASE),
        [(0.098, 0.0437), (0.163, 0.0437)],
        green,
        group,
        transform,
        96,
        closed=False,
    )
    # Fine label margins and a neutral segmented icon are physical print, not a room decal.
    for z in (0.102, 0.156):
        _lathe(
            "Bottle label narrow ivory rule",
            (cx, cy, BASE),
            [(z, 0.04386), (z + 0.0013, 0.04386)],
            ink,
            group,
            transform,
            96,
            closed=False,
        )

    def label(u, v):
        a = math.pi * 0.05 + u * math.pi * 1.90
        return cx + 0.04395 * math.cos(a), cy + 0.04395 * math.sin(a), BASE + 0.106 + 0.041 * v

    _print(
        "Bottle neutral label lettering",
        "SPARKLING",
        (0.26, 0.29),
        0.12,
        label,
        ink,
        group,
        transform,
    )
    for j in range(9):
        a = 0.5 + j * 0.075

        def icon(u, v, a=a, j=j):
            ang = a + u * 0.025
            return (
                cx + 0.04397 * math.cos(ang),
                cy + 0.04397 * math.sin(ang),
                BASE + 0.111 + v * (0.008 + (j % 3) * 0.004),
            )

        _grid("Bottle small label graphic %02d" % j, icon, ink, group, transform, 1, 1)
    _lathe(
        "Bottle distinct tamper seal",
        (cx, cy, BASE),
        [(0.288, 0.0165), (0.29, 0.0170), (0.293, 0.0170)],
        capmat,
        group,
        transform,
        64,
    )
    _lathe(
        "Bottle rounded fluted screw cap",
        (cx, cy, BASE),
        [(0.293, 0.0171), (0.294, 0.0177), (0.309, 0.0177), (0.311, 0.0169)],
        capmat,
        group,
        transform,
        96,
        lambda z, a: 0.00042 * (0.5 + 0.5 * math.cos(a * 44)) if 0.294 < z < 0.309 else 0,
    )
    _lathe(
        "Bottle support neck bead",
        (cx, cy, BASE),
        [(0.284, 0.0158), (0.285, 0.018), (0.286, 0.018), (0.287, 0.0158)],
        pet,
        group,
        transform,
        80,
    )
    # Cream vacuum flask: rounded base, body coat, collar joint, offset locking lid.
    cream = _mat("thermos pale ivory satin coat", (0.77, 0.765, 0.655), 0.42)
    lid = _mat("thermos slightly warm lid plastic", (0.82, 0.81, 0.70), 0.37)
    steel = _mat("thermos brushed steel collar", (0.5, 0.53, 0.53), 0.28, 0.86)
    dark = _mat("thermos lid recessed release", (0.33, 0.335, 0.287), 0.56)
    cx, cy = 0.465, 0.455
    _lathe(
        "Thermos rounded coated body",
        (cx, cy, BASE),
        _profile_smooth(
            [
                (0, 0.0205),
                (0.002, 0.025),
                (0.007, 0.0265),
                (0.031, 0.0267),
                (0.154, 0.0267),
                (0.164, 0.0255),
                (0.166, 0.024),
            ]
        ),
        cream,
        group,
        transform,
        80,
    )
    _lathe(
        "Thermos exposed collar seam",
        (cx, cy, BASE),
        [(0.164, 0.0245), (0.168, 0.0255), (0.170, 0.0255)],
        steel,
        group,
        transform,
        80,
    )
    _lathe(
        "Thermos stepped flip top lid",
        (cx, cy, BASE),
        _profile_smooth(
            [(0.170, 0.0257), (0.172, 0.027), (0.185, 0.027), (0.192, 0.026), (0.196, 0.0235)]
        ),
        lid,
        group,
        transform,
        80,
    )

    # Embossed lid catch, layered rectangular pieces fitted to front tangent.
    def catch(u, v):
        return cx + (u - 0.5) * 0.020, cy + 0.0269, BASE + 0.177 + v * 0.013

    _grid("Thermos inset lid release", catch, dark, group, transform, 4, 4, 0.001)

    def tongue(u, v):
        return cx + (u - 0.5) * 0.012, cy + 0.0278, BASE + 0.180 + v * 0.009

    _grid("Thermos cream release button", tongue, lid, group, transform, 4, 4, 0.0014)
    for z in (0.008, 0.034):
        _lathe(
            "Thermos subtle molded base seam",
            (cx, cy, BASE),
            [(z, 0.02683), (z + 0.0005, 0.02683)],
            lid,
            group,
            transform,
            80,
            closed=False,
        )


def refine_counter_props(M=None):
    """Replace the counter assembly details, preserving its inherited frame."""
    del M
    global _WHITE_SUPPORT, _BLACK_SUPPORT
    group = bpy.data.collections.get(GROUP)
    if group is None:
        raise RuntimeError("Counter details collection is missing")
    stable = next((o for o in group.objects if o.get("counter_revision") == VERSION), None)
    if stable:
        return {"revision": VERSION, "already_applied": True, "new_objects": 0}
    anchor = bpy.data.objects.get("PackageV3 / White carrier flattened body")
    if anchor is None:
        raise RuntimeError("PackageV3 original-frame body is required")
    transform = anchor.matrix_world.copy()
    _WHITE_SUPPORT = None
    _BLACK_SUPPORT = None
    removed = []
    for ob in list(group.objects):
        if ob.name.startswith(OLD_PREFIXES + (PREFIX,)):
            removed.append(ob.name)
            data = ob.data
            kind = ob.type
            bpy.data.objects.remove(ob, do_unlink=True)
            if data and data.users == 0:
                if kind == "MESH":
                    bpy.data.meshes.remove(data)
                elif kind in {"CURVE", "FONT", "SURFACE"}:
                    bpy.data.curves.remove(data)
    whitecolor = (0.78, 0.790, 0.774)
    blackcolor = (0.022, 0.024, 0.023)
    white = _mat("creased white carrier film", whitecolor, 0.39, vertex=True)
    black = _mat("slack charcoal carrier film", blackcolor, 0.56, vertex=True)
    red = _mat("burgundy woven carrier handles", (0.054, 0.005, 0.014), 0.73)
    printmat = _mat("burgundy neutral shop print", (0.105, 0.018, 0.027), 0.48)
    body = _bag(
        "White carrier lofted open body",
        _white_surface,
        white,
        group,
        transform,
        160,
        112,
        _tone(whitecolor, 70, 0.025),
    )
    body["counter_revision"] = VERSION
    _WHITE_SUPPORT = _support_cache(body)
    blackbody = _bag(
        "Black carrier collapsed volume",
        _black_surface,
        black,
        group,
        transform,
        128,
        96,
        _tone(blackcolor, 66, 0.15),
    )
    _BLACK_SUPPORT = _support_cache(blackbody)
    for v, name in ((0.014, "near"), (0.986, "far")):

        def seam(u, w, v=v):
            x, y, z = _white_surface(u, v + (w - 0.5) * 0.012)
            return x, y, z + 0.00018

        _grid(
            "White doubled heat seal " + name,
            seam,
            white,
            group,
            transform,
            112,
            3,
            0.00015,
            _tone(whitecolor, 80, 0.01),
        )
    _print(
        "White carrier CAMPUS print",
        "CAMPUS",
        (0.24, 0.57),
        0.107,
        _white_surface,
        printmat,
        group,
        transform,
    )
    _print(
        "White carrier generic bookshop line",
        "BOOKS  &  SUPPLIES",
        (0.24, 0.48),
        0.050,
        _white_surface,
        printmat,
        group,
        transform,
    )
    _print(
        "White carrier square monogram",
        "U",
        (0.39, 0.26),
        0.17,
        _white_surface,
        printmat,
        group,
        transform,
    )
    for k, (va, vb, ctrl1, ctrl2) in enumerate(
        [
            (0.18, 0.78, (0.268, 0.592, 1.007), (0.115, 0.527, 0.980)),
            (0.22, 0.74, (0.290, 0.548, 1.047), (0.143, 0.470, 0.995)),
        ]
    ):
        _cord(
            "White loose burgundy cord handle %d" % k,
            [_white_surface(0.995, va), ctrl1, ctrl2, _white_surface(0.995, vb)],
            red,
            group,
            transform,
            _white_height,
        )

    # The closed edge is folded back onto the carrier, with a free thin doubled
    # edge and a soft hinge. This creates a real overlap instead of a big rectangle.
    def return_fold(u, v):
        uu = 0.034 + u * 0.17
        vv = 0.09 + v * 0.75
        x, y, z = _white_surface(uu, vv)
        z += 0.001 + 0.012 * (1 - u) ** 2 * math.sin(math.pi * v) ** 0.7
        return x, y, z

    _grid(
        "White bag returned side fold",
        return_fold,
        white,
        group,
        transform,
        32,
        90,
        0.0002,
        _tone(whitecolor, 90, 0.03),
    )
    for k in range(2):

        def doubled(u, v, k=k):
            uu = 0.66 + 0.31 * u
            vv = 0.73 + 0.24 * v
            x, y, z = _white_surface(uu, vv)
            z += 0.0015 + k * 0.0018 + 0.005 * math.sin(math.pi * u) * v
            return x, y, z

        _grid(
            "White mouth loose doubled layer %d" % k,
            doubled,
            white,
            group,
            transform,
            50,
            36,
            0.00018,
            _tone(whitecolor, 90, 0.02),
        )
    paper = _mat("loose pale paper below flask", (0.82, 0.825, 0.802), 0.78)
    for k in range(2):

        def loose(u, v, k=k):
            x = 0.39 + u * 0.16 - k * 0.012
            y = 0.498 + v * 0.103 + k * 0.005
            z = BASE + 0.0004 + k * 0.0007 + 0.009 * max(0, (u + v - 1.45) / 0.55)
            return x, y, z

        _grid("Loose folded counter paper %d" % k, loose, paper, group, transform, 32, 24, 0.00015)

    def mouth(u, v):
        x = 0.160 + 0.225 * u
        y = 0.124 + 0.021 * math.sin(math.pi * u) + (v - 0.5) * 0.045
        z = _black_height(x, y) + 0.002 + 0.014 * math.sin(math.pi * v) ** 2 * math.sin(math.pi * u)
        z += 0.003 * _tri_field(u, v, 41, 9, 3) * math.sin(math.pi * u) * math.sin(math.pi * v)
        return x, y, z

    _grid(
        "Black carrier soft folded open lip",
        mouth,
        black,
        group,
        transform,
        88,
        26,
        0.0003,
        _tone(blackcolor, 53, 0.14),
    )
    _ribbon(
        "Black bag collapsed loop one",
        [(0.19, 0.16, 1.015), (0.12, 0.235, 1.068), (0.31, 0.29, 1.049), (0.337, 0.16, 1.015)],
        0.013,
        black,
        group,
        transform,
        _black_height,
        0.7,
    )
    _ribbon(
        "Black bag collapsed loop two",
        [(0.18, 0.13, 1.015), (0.19, 0.225, 1.055), (0.35, 0.218, 1.038), (0.318, 0.147, 1.018)],
        0.014,
        black,
        group,
        transform,
        _black_height,
        -0.6,
    )
    _cap(group, transform)
    _wallet(group, transform)
    _bottles(group, transform)
    bpy.context.view_layer.update()
    created = [o for o in group.objects if o.name.startswith(PREFIX)]
    return {
        "revision": VERSION,
        "removed_names": removed,
        "created_names": [o.name for o in created],
        "removed_objects": len(removed),
        "created_objects": len(created),
        "base_vertices": sum(len(o.data.vertices) for o in created if o.type == "MESH"),
        "original_to_final_matrix": [list(row) for row in transform],
        "coordinates": "Inherited original counter frame; designed to run after layout_v3",
    }
