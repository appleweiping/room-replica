"""Photo-guided, meter-based bedding and rail-draped garments.

Integration: keep the existing mattress, bed frame, guard and reading lamp;
replace the old sheet/duvet/pillow/towel blocks with ``build_bedding(M)``.
No scene files are loaded, saved, rendered or deleted by this module.

The quilt's loose lower casing starts from a baked Blender cloth solve.
Four uneven filled return folds are art-directed into a connected volume,
with voxel union resolving compressed contact regions. This is not a
pressure simulation or a metrically recovered scan.
"""

import math
import base64
import struct
import zlib
from array import array
from dataclasses import dataclass

import bpy
from mathutils import Vector

from common import collection, curve, mesh


LEGACY_PREFIXES = (
    "Bed_rose_sheet_draped",
    "Bed_blue_floral_duvet",
    "Bed_floral_pillow_",
    "Bed_right_white_tshirt",
    "Bed_left_black_trousers",
    "Bed_left_white_checked_towel",
    "Towel_woven_check_",
)


@dataclass
class BeddingConfig:
    center_x: float = 0.0
    center_y: float = 3.586
    mattress_top: float = 0.643
    length: float = 2.032
    width: float = 0.9144
    detail: float = 1.0
    pillows: bool = False
    hanging_fabrics: bool = True
    seams: bool = True


def _clamp(x, a=0.0, b=1.0):
    return min(b, max(a, x))


def _smooth(x):
    x = _clamp(x)
    return x * x * (3 - 2 * x)


def _gauss(x, center, width):
    return math.exp(-(((x - center) / width) ** 2))


def _noise2(x, y, seed=17):
    """Small deterministic non-periodic cloth variation, with no RNG state."""
    ix, iy = math.floor(x), math.floor(y)
    fx, fy = _smooth(x - ix), _smooth(y - iy)

    def value(a, b):
        n = (a * 374761393 + b * 668265263 + seed * 1274126177) & 0xFFFFFFFF
        n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
        return ((n ^ (n >> 16)) & 65535) / 32767.5 - 1

    a = value(ix, iy) * (1 - fx) + value(ix + 1, iy) * fx
    b = value(ix, iy + 1) * (1 - fx) + value(ix + 1, iy + 1) * fx
    return a * (1 - fy) + b * fy


def _catmull(points, t):
    """Smooth through a short authored cloth cross-section, including returns."""
    k = min(len(points) - 2, int(_clamp(t) * (len(points) - 1)))
    f = _clamp(t) * (len(points) - 1) - k
    a, b, c, d = [Vector(points[max(0, min(len(points) - 1, i))]) for i in (k - 1, k, k + 1, k + 2)]
    return 0.5 * (
        (2 * b)
        + (-a + c) * f
        + (2 * a - 5 * b + 4 * c - d) * f * f
        + (-a + 3 * b - 3 * c + d) * f * f * f
    )


def _textile_mesh(name, vertices, faces, mat, uvs=None, smooth=False):
    """Bulk UV assignment avoids a slow RNA round trip for every cloth loop."""
    obj = mesh(name, vertices, faces, mat, None, False)
    data = obj.data
    if uvs:
        indices = array("i", [0]) * len(data.loops)
        data.loops.foreach_get("vertex_index", indices)
        values = array("f", (value for index in indices for value in uvs[index]))
        layer = data.uv_layers.new(name="UVMap")
        layer.data.foreach_set("uv", values)
    if smooth:
        data.polygons.foreach_set("use_smooth", [True] * len(data.polygons))
    return obj


def _restore_cloth_uv(obj, source):
    """Project a resolved casing to its donor once per vertex, in bulk.

    The dense donor is triangulated and a nearest surface point is evaluated
    with barycentric UV interpolation. Shared UVs at each remeshed vertex
    avoid millions of repeated per-corner Data Transfer queries.
    """
    import numpy as np
    from mathutils.bvhtree import BVHTree

    data, donor = obj.data, source.data
    donor.calc_loop_triangles()
    coords = np.empty(len(donor.vertices) * 3, dtype=np.float32)
    donor.vertices.foreach_get("co", coords)
    coords = coords.reshape((-1, 3))
    indices = np.empty(len(donor.loop_triangles) * 3, dtype=np.int32)
    donor.loop_triangles.foreach_get("vertices", indices)
    indices = indices.reshape((-1, 3))
    uv_loops = np.empty(len(donor.loops) * 2, dtype=np.float32)
    donor.uv_layers.active.data.foreach_get("uv", uv_loops)
    uv_loops = uv_loops.reshape((-1, 2))
    triangle_loops = np.empty(len(donor.loop_triangles) * 3, dtype=np.int32)
    donor.loop_triangles.foreach_get("loops", triangle_loops)
    triangle_loops = triangle_loops.reshape((-1, 3))
    tree = BVHTree.FromPolygons(coords.tolist(), indices.tolist(), all_triangles=True)
    positions = np.empty(len(data.vertices) * 3, dtype=np.float32)
    data.vertices.foreach_get("co", positions)
    positions = positions.reshape((-1, 3))
    nearest = np.empty_like(positions)
    triangles = np.empty(len(positions), dtype=np.int32)
    for i, position in enumerate(positions.tolist()):
        point, _, triangle, _ = tree.find_nearest(position)
        nearest[i] = point
        triangles[i] = triangle
    geometry = coords[indices[triangles]].astype(np.float64)
    texcoords = uv_loops[triangle_loops[triangles]]
    a, b = geometry[:, 1] - geometry[:, 0], geometry[:, 2] - geometry[:, 0]
    offset = nearest - geometry[:, 0]
    aa, ab, bb = (
        np.einsum("ij,ij->i", a, a),
        np.einsum("ij,ij->i", a, b),
        np.einsum("ij,ij->i", b, b),
    )
    da, db = np.einsum("ij,ij->i", offset, a), np.einsum("ij,ij->i", offset, b)
    denominator = aa * bb - ab * ab
    safe = np.abs(denominator) > 1e-24
    v = np.divide(bb * da - ab * db, denominator, out=np.zeros_like(denominator), where=safe)
    w = np.divide(aa * db - ab * da, denominator, out=np.zeros_like(denominator), where=safe)
    uv = (
        texcoords[:, 0]
        + v[:, None] * (texcoords[:, 1] - texcoords[:, 0])
        + w[:, None] * (texcoords[:, 2] - texcoords[:, 0])
    )
    loops = np.empty(len(data.loops), dtype=np.int32)
    data.loops.foreach_get("vertex_index", loops)
    layer = data.uv_layers.active or data.uv_layers.new(name="UVMap")
    layer.data.foreach_set("uv", np.asarray(uv[loops], dtype=np.float32).reshape(-1))


def _grid(name, fn, mat, nu, nv, thickness=0.0012, solid=True, omit=None):
    vertices, uvs, faces = [], [], []
    for j in range(nv + 1):
        for i in range(nu + 1):
            u, v = i / nu, j / nv
            vertices.append(fn(u, v))
            uvs.append((u, v))
    for j in range(nv):
        for i in range(nu):
            if omit and omit((i + 0.5) / nu, (j + 0.5) / nv):
                continue
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
    obj = _textile_mesh(name, vertices, faces, mat, uvs, True)
    if solid:
        mod = obj.modifiers.new("Woven fabric thickness", "SOLIDIFY")
        mod.thickness = thickness
        mod.offset = 0
        mod.use_even_offset = True
    obj["construction"] = "Continuous authored textile surface; meters"
    return obj


def _padded(name, fn, mat, nu, nv, loft):
    """Closed two-sided padded shell, compressed continuously to a sewn edge."""
    centers = [Vector(fn(i / nu, j / nv)) for j in range(nv + 1) for i in range(nu + 1)]
    vertices, uvs, faces = [], [], []
    # Batting follows the broad cloth bend, not every millimeter-scale casing
    # wrinkle. A local secant frame prevents thick inward offsets from folding
    # over themselves at narrow decorative creases.
    span = max(2, round(min(nu, nv) / 28))
    for side in (1, -1):
        for j in range(nv + 1):
            for i in range(nu + 1):
                left = centers[j * (nu + 1) + max(0, i - span)]
                right = centers[j * (nu + 1) + min(nu, i + span)]
                before = centers[max(0, j - span) * (nu + 1) + i]
                after = centers[min(nv, j + span) * (nu + 1) + i]
                normal = (right - left).cross(after - before).normalized()
                u, v = i / nu, j / nv
                edge = min(u, 1 - u, v, 1 - v)
                puff = 0.0016 + loft(u, v) * _smooth(edge / 0.055)
                vertices.append(centers[j * (nu + 1) + i] + side * puff * normal)
                uvs.append((u, v))
    size = len(centers)
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            face = (a, a + 1, a + nu + 2, a + nu + 1)
            faces.append(face)
            faces.append(tuple(k + size for k in reversed(face)))
    edge = list(range(nu + 1))
    edge += [j * (nu + 1) + nu for j in range(1, nv + 1)]
    edge += [nv * (nu + 1) + i for i in range(nu - 1, -1, -1)]
    edge += [j * (nu + 1) for j in range(nv - 1, 0, -1)]
    for a, b in zip(edge, edge[1:] + edge[:1]):
        faces.append((a, a + size, b + size, b))
    obj = _textile_mesh(name, vertices, faces, mat, uvs, True)
    obj["construction"] = "Closed upper/lower cloth shell with compressed sewn perimeter"
    obj["fold_geometry"] = "Non-monotonic cross-section; true return fold and contact underside"
    return obj


def _seam(name, points, mat, radius=0.00075):
    return curve(name, points, radius, mat)


def _edge_points(fn, inset=0.003, count=180):
    pts = [fn(inset + (1 - 2 * inset) * i / count, inset) for i in range(count)]
    pts += [fn(1 - inset, inset + (1 - 2 * inset) * i / count) for i in range(count)]
    pts += [fn(1 - inset - (1 - 2 * inset) * i / count, 1 - inset) for i in range(count)]
    pts += [fn(inset, 1 - inset - (1 - 2 * inset) * i / count) for i in range(count)]
    return pts + [pts[0]]


def _sheet(c, M):
    # Rest coordinates continue around a rounded mattress shoulder and then
    # downward. The front hem varies in length; corner material gathers rather
    # than stretching a planar top into a flat vertical skirt.
    lx, wy = c.length / 2, c.width / 2
    radius = 0.055

    def bend(distance, bound):
        extra = max(0, abs(distance) - (bound - radius + 0.010))
        if not extra:
            return distance, 0.0, 0.0
        angle = min(extra / radius, math.pi / 2)
        outward = (bound - radius + 0.010) + radius * math.sin(angle)
        drop = radius * (1 - math.cos(angle)) + max(0, extra - math.pi * radius / 2)
        return math.copysign(outward, distance), drop, _clamp(extra / 0.14)

    def surface(u, v):
        restx = (u - 0.5) * (c.length + 0.36)
        front_extra = (
            0.335
            - 0.064 * _gauss(u, 0.24, 0.105)
            - 0.043 * _gauss(u, 0.73, 0.085)
            + 0.030 * _gauss(u, 0.48, 0.14)
            - 0.018 * _gauss(u, 0.91, 0.055)
        )
        resty = -wy - front_extra + v * (c.width + front_extra + 0.105)
        x, dx, ax = bend(restx, lx)
        y, dy, ay = bend(resty, wy)
        # Rounded maximum avoids a hard ridge at the four gathered corners.
        drop = max(dx, dy) + 0.18 * min(dx, dy)
        front = (1 if resty < 0 else 0.35) * ay
        hang = _clamp(dy / 0.30)
        fold = 0.003 * _noise2(restx * 18, resty * 13)
        # Sparse diagonal tension ridges descend from irregular tucks. Their
        # positions fan out with gravity instead of forming a curtain comb.
        for origin, slope, amplitude in [
            (-0.78, 0.11, 0.014),
            (-0.47, -0.22, 0.022),
            (-0.08, 0.16, 0.012),
            (0.31, -0.19, 0.018),
            (0.72, 0.13, 0.024),
        ]:
            d = restx - (origin + slope * hang)
            fold += amplitude * _gauss(d, 0, 0.022 + 0.011 * hang) * (0.20 + 0.80 * hang)
            fold -= 0.24 * amplitude * _gauss(d, 0.027, 0.026) * hang
        if resty < 0:
            # Clear the near steel support at y=3.10 as well as the mattress.
            y -= front * (0.065 + fold)
        if abs(restx) > lx - 0.035:
            x += math.copysign(ax * (0.003 + 0.002 * math.sin(resty * 39 + 1.3)), restx)
        top = 1 - max(ax, ay)
        wrinkles = 0.0014 * _noise2(restx * 34, resty * 31) + 0.0007 * _noise2(
            restx * 83, resty * 74, 51
        )
        for center, slope, amp in [(-0.54, 0.50, 0.008), (0.21, -0.64, 0.006), (0.76, 0.32, 0.010)]:
            d = restx - center - slope * (resty + 0.3)
            wrinkles += amp * _gauss(d, 0, 0.024) * _gauss(resty, -0.29, 0.19)
        z = c.mattress_top + 0.012 - drop + top * (0.003 + wrinkles)
        z += front * (
            0.002 * _noise2(restx * 36, resty * 18) + 0.001 * _noise2(restx * 73, resty * 22, 41)
        )
        return c.center_x + x, c.center_y + y, z

    obj = _grid("BedV2_Rose_Sheet", surface, M["rose"], int(212 * c.detail), int(138 * c.detail))
    obj["visible_front_hem"] = "Uneven gravitational drop with gathered corners and 2–12 mm folds"
    if c.seams:
        _seam(
            "BedV2_Sheet_turned_hem",
            _edge_points(surface, 0.006),
            M.get("fabric_cream", M["rose"]),
            0.00085,
        )
        _seam(
            "BedV2_Sheet_hem_stitch",
            [surface(i / 260, 0.018) for i in range(261)],
            M.get("fabric_cream", M["rose"]),
            0.00035,
        )
    return obj


def _quilt_seed_surface(c):
    # Lower layer reaches the rear, rolls up and returns toward the observer.
    # The rolling radius leaves space for the two padded layers at the turn.
    profile = [
        (-0.245, 0.035),
        (-0.055, 0.037),
        (0.165, 0.044),
        (0.338, 0.063),
        (0.398, 0.118),
        (0.343, 0.174),
        (0.163, 0.209),
        (-0.025, 0.190),
        (-0.133, 0.065),
    ]

    def surface(u, v):
        yz = _catmull(profile, v)
        x = -0.914 + 1.80 * u
        x += 0.021 * math.sin(v * 14 + u * 7) * math.sin(math.pi * u)
        y = (
            yz.x
            + 0.035 * math.sin(u * 7.8 + 0.5)
            + 0.026 * math.sin(u * 16 + v * 2) * math.sin(math.pi * v)
        )
        y += 0.04 * (u - 0.5) * _smooth((v - 0.3) / 0.5)
        y += 0.065 * math.sin(u * 9.1 + 0.45) * _smooth((v - 0.36) / 0.45)
        # Collapse the right shoulder, keep a substantial bunched roll left of
        # center, and distort the fold diagonally instead of parallel waves.
        weight = _smooth(v / 0.3)
        z = yz.y + weight * (
            0.106 * _gauss(u, 0.39, 0.19) * _gauss(v, 0.66, 0.25)
            - 0.028 * _gauss(u, 0.83, 0.14) * math.sin(math.pi * v)
        )
        z += 0.055 * _gauss(u, 0.56, 0.20) * _gauss(v, 0.69, 0.19)
        z += 0.059 * _gauss(u, 0.82, 0.13) * _gauss(v, 0.59, 0.16)
        z += 0.014 * math.sin(u * 18 + v * 8) * weight * math.sin(math.pi * v)
        diagonal = v - (0.72 - 0.18 * u + 0.04 * math.sin(u * 11))
        z -= 0.018 * _gauss(diagonal, 0, 0.025) * _gauss(u, 0.63, 0.30)
        z += 0.012 * _gauss(diagonal, 0.036, 0.037) * _gauss(u, 0.61, 0.27)
        for center, phase, amount in [(0.19, 0.6, 0.018), (0.49, 2.1, 0.021), (0.72, 4.2, 0.016)]:
            crease = u - (center + 0.045 * math.sin(v * 7 + phase))
            z += (
                amount
                * (_gauss(crease, 0.026, 0.028) - 0.72 * _gauss(crease, 0, 0.016))
                * _gauss(v, 0.67, 0.24)
            )
        # Centimeter-scale compressive wrinkles and millimeter-scale cotton
        # creasing, suppressed at mattress-contact patches on the lower layer.
        fine = 0.0026 * math.sin(u * 78 + v * 31 + 0.8 * math.sin(v * 13)) + 0.0014 * math.sin(
            u * 143 - v * 53
        )
        fine += 0.0075 * math.sin(u * 37 - v * 17) * _gauss(v, 0.72, 0.32)
        z += fine * (0.25 + 0.75 * weight)
        return c.center_x + x, c.center_y + y, c.mattress_top + z

    return surface


def _filled_quilt_points(c):
    """Calibrate solved folds, keeping the lower casing on the mattress."""
    values = struct.unpack("<12213f", zlib.decompress(base64.b85decode(_SOLVED_CLOTH_B85)))
    nu, nv = 68, 58
    upper, lower = [], []

    def place(x, y, z):
        return (
            c.center_x + x * c.length / 2.032,
            c.center_y + (y - 3.586) * c.width / 0.9144,
            c.mattress_top + (z - 0.643),
        )

    def filling(x, y):
        y -= 3.6
        h = 0.310 * math.exp(-(((x + 0.16) / 0.30) ** 2) - ((y - 0.015) / 0.19) ** 2)
        h += 0.245 * math.exp(-(((x - 0.48) / 0.25) ** 2) - ((y + 0.06) / 0.18) ** 2)
        h += 0.069 * math.exp(-(((x + 0.61) / 0.22) ** 2) - ((y - 0.15) / 0.13) ** 2)
        h -= 0.062 * math.exp(-(((x + 0.14 - 1.6 * y) / 0.026) ** 2) - (y / 0.17) ** 2)
        h -= 0.065 * math.exp(-(((x - 0.55 + 0.8 * y) / 0.024) ** 2) - ((y - 0.1) / 0.13) ** 2)
        return max(0, h)

    for k in range((nu + 1) * (nv + 1)):
        x, y, z = values[k * 3 : k * 3 + 3]
        x *= 1.51
        y = 3.28 + (y - 3.4911256) * 0.658
        d = z - 0.65
        z = 0.669 + 0.74 * 0.5 * (d + math.sqrt(d * d + 0.000035))
        lower.append(place(x, y, max(0.667, z - 0.012)))
        u = (k % (nu + 1)) / nu
        v = (k // (nu + 1)) / nv
        z += 0.010 + filling(x, y) * math.exp(-(((z - 0.69) / 0.2) ** 2)) * _smooth(
            min(u, 1 - u, v, 1 - v) / 0.12
        )
        upper.append(place(x, y, z))
    return upper, lower, nu, nv


def _quilt_return_patch(c, M, name, center, length, profile, angle, puff, seed, shape, uv_region):
    """One continuous padded return, attached inside hidden contact regions."""
    co, si = math.cos(angle), math.sin(angle)

    def surface(u, v):
        cross = _catmull(profile, v)
        q = (u - 0.5) * length
        end = math.sin(math.pi * u) ** 0.45
        r = cross.x * (0.50 + 0.5 * end)
        z = cross.y * (0.48 + 0.52 * end)
        r += shape[0] * _noise2(u * 3.8, v * 0.8, seed)
        q += shape[1] * _noise2(u * 2.2, v * 3.6, seed + 7) * end
        z += shape[2] * _noise2(u * 3.3, v * 2.4, seed + 9) * end
        free = _smooth((z - 0.025) / 0.09)
        z += free * (
            0.0045 * _noise2(u * 18, v * 15, seed + 11) + 0.0017 * _noise2(u * 43, v * 34, seed + 4)
        )
        for uc, sl, amp in [
            (0.12, -0.19, 0.008),
            (0.20, 0.28, 0.018),
            (0.32, 0.39, 0.009),
            (0.49, -0.31, 0.024),
            (0.56, -0.13, 0.010),
            (0.72, 0.20, 0.020),
            (0.83, 0.32, 0.008),
            (0.88, -0.36, 0.010),
        ]:
            d = u - uc - sl * (v - 0.55) - 0.06 * (v - 0.55) ** 2
            z += (
                amp
                * (0.28 * _gauss(d, 0.029, 0.025) - _gauss(d, 0, 0.017))
                * _gauss(v, 0.52, 0.30)
                * free
            )
        if name == "Front rolled hem":
            # Two diagonal crushes interrupt the roll, with opposite sideways
            # kinks. The turn's cross-section is physically flattened locally.
            d1 = u - 0.29 - 0.21 * (v - 0.5)
            d2 = u - 0.66 + 0.25 * (v - 0.5)
            squeeze = 1 - 0.62 * _gauss(d1, 0, 0.050) - 0.59 * _gauss(d2, 0, 0.055)
            z = 0.025 + (z - 0.025) * squeeze
            z -= 0.013 * (_gauss(d1, 0, 0.012) + _gauss(d2, 0, 0.014)) * free
            r += 0.047 * _gauss(u, 0.66, 0.068) - 0.036 * _gauss(u, 0.29, 0.057)
            q += 0.020 * _gauss(d1, 0.022, 0.030) * free
        x = center[0] + q * co - r * si
        y = center[1] + q * si + r * co
        return (
            c.center_x + x * c.length / 2.032,
            c.center_y + (y - 3.586) * c.width / 0.9144,
            c.mattress_top + (center[2] + z - 0.643),
        )

    obj = _padded(
        "BedV2_Quilt_piece_" + name,
        surface,
        M["floral"],
        int(112 * c.detail),
        int(96 * c.detail),
        lambda u, v: puff * (0.8 + 0.25 * _noise2(u * 4, v * 3, seed + 5)),
    )
    import numpy as np

    layer = obj.data.uv_layers.active
    uv = np.empty(len(obj.data.loops) * 2, dtype=np.float32)
    layer.data.foreach_get("uv", uv)
    uv = uv.reshape((-1, 2))
    uv[:, 0] = uv_region[0] + uv[:, 0] * uv_region[2]
    uv[:, 1] = uv_region[1] + uv[:, 1] * uv_region[3]
    layer.data.foreach_set("uv", uv.reshape(-1))
    return obj


def _remove_voxel_crumbs(obj):
    """Discard detached submillimetre remnants of thin compressed casing."""
    import bmesh

    bm = bmesh.new()
    try:
        bm.from_mesh(obj.data)
        for vertex in bm.verts:
            vertex.tag = False
        groups = []
        for vertex in bm.verts:
            if vertex.tag:
                continue
            vertex.tag = True
            stack = [vertex]
            group = []
            while stack:
                item = stack.pop()
                group.append(item)
                for edge in item.link_edges:
                    other = edge.other_vert(item)
                    if not other.tag:
                        other.tag = True
                        stack.append(other)
            groups.append(group)
        if len(groups) > 1:
            groups.sort(key=len, reverse=True)
            # A detached major fold indicates a placement error; do not silently
            # remove it. Only very small voxel remnants may be discarded.
            if any(len(group) > 128 for group in groups[1:]):
                raise ValueError("Quilt return became detached from the lower casing")
            bmesh.ops.delete(bm, geom=[v for group in groups[1:] for v in group], context="VERTS")
            bm.to_mesh(obj.data)
    finally:
        bm.free()


def _quilt(c, M):
    upper, lower, nu, nv = _filled_quilt_points(c)
    # The gravity-solved casing supplies loose peripheral folds, rather than
    # filling the whole middle with a single broad height-field mound.
    upper = [
        Vector(b) + (Vector(a) - Vector(b)) * 0.12 + Vector((0, 0, 0.008))
        for a, b in zip(upper, lower)
    ]
    size = len(upper)
    faces = []
    uv = [(i / nu, j / nv) for j in range(nv + 1) for i in range(nu + 1)]
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
    faces += [tuple(k + size for k in reversed(f)) for f in faces.copy()]
    edge = list(range(nu + 1)) + [j * (nu + 1) + nu for j in range(1, nv + 1)]
    edge += [nv * (nu + 1) + i for i in range(nu - 1, -1, -1)]
    edge += [j * (nu + 1) for j in range(nv - 1, 0, -1)]
    for a, b in zip(edge, edge[1:] + edge[:1]):
        faces.append((a, a + size, b + size, b))
    ob = _textile_mesh("BedV2_Blue_Quilt_Folded", upper + lower, faces, M["floral"], uv + uv, True)
    pieces = [ob]
    specifications = [
        (
            "Central overturned lap",
            (-0.20, 3.69, 0.688),
            1.04,
            [
                (-0.17, 0.024),
                (0.04, 0.025),
                (0.25, 0.034),
                (0.28, 0.095),
                (0.20, 0.205),
                (0.03, 0.236),
                (-0.12, 0.176),
                (-0.13, 0.087),
                (0.02, 0.065),
                (0.10, 0.11),
            ],
            0.14,
            0.026,
            21,
            (0.047, 0.075, 0.042),
            (0.36, 0.54, 0.38, 0.27),
        ),
        (
            "Right deep return",
            (0.53, 3.70, 0.690),
            0.59,
            [
                (-0.17, 0.035),
                (0.04, 0.035),
                (0.22, 0.06),
                (0.245, 0.15),
                (0.15, 0.267),
                (-0.025, 0.280),
                (-0.15, 0.187),
                (-0.09, 0.103),
                (0.07, 0.119),
                (0.13, 0.205),
            ],
            -0.36,
            0.031,
            47,
            (0.065, 0.055, 0.045),
            (0.40, 0.36, 0.36, 0.32),
        ),
        (
            "Front rolled hem",
            (-0.24, 3.415, 0.683),
            1.20,
            [
                (-0.052, 0.035),
                (0.024, 0.035),
                (0.112, 0.065),
                (0.127, 0.122),
                (0.056, 0.167),
                (-0.045, 0.124),
                (-0.061, 0.059),
                (0.020, 0.063),
                (0.040, 0.103),
            ],
            -0.10,
            0.022,
            79,
            (0.058, 0.035, 0.027),
            (0.36, 0.49, 0.30, 0.20),
        ),
        (
            "Left crushed return",
            (-0.69, 3.70, 0.692),
            0.55,
            [
                (-0.19, 0.025),
                (-0.025, 0.04),
                (0.20, 0.053),
                (0.245, 0.096),
                (0.135, 0.155),
                (-0.010, 0.155),
                (-0.105, 0.07),
                (0.03, 0.081),
                (0.075, 0.122),
            ],
            0.44,
            0.018,
            33,
            (0.046, 0.049, 0.040),
            (0, 0, 1, 1),
        ),
    ]
    for spec in specifications:
        pieces.append(_quilt_return_patch(c, M, *spec))
    previous_active = bpy.context.view_layer.objects.active
    previous_selected = list(bpy.context.selected_objects)
    source = None
    try:
        for item in previous_selected:
            item.select_set(False)
        for piece in pieces:
            piece.select_set(True)
            bpy.context.view_layer.objects.active = piece
            sub = piece.modifiers.new("Smooth cotton casing", "SUBSURF")
            sub.levels = 2 if piece == ob else 1
            bpy.ops.object.modifier_apply(modifier=sub.name)
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.join()
        source = bpy.data.objects.new("Temporary quilt UV donor", ob.data.copy())
        bpy.context.scene.collection.objects.link(source)
        source.hide_render = True
        source.hide_set(True)
        # Reprojecting a union into the old compressed layers would restore
        # their self-intersections. Keep the resolved volume's own surface.
        ob.data.remesh_voxel_size = 0.0035 / c.detail
        ob.data.use_remesh_preserve_volume = False
        bpy.ops.object.voxel_remesh()
        smooth = ob.modifiers.new("Relax union surface", "SMOOTH")
        smooth.factor = 0.30
        smooth.iterations = 3
        bpy.ops.object.modifier_apply(modifier=smooth.name)
        bpy.ops.object.voxel_remesh()
        _remove_voxel_crumbs(ob)
        ob.data.polygons.foreach_set("use_smooth", [True] * len(ob.data.polygons))
        _restore_cloth_uv(ob, source)
        if not ob.data.materials:
            ob.data.materials.append(M["floral"])
        # Close the deliberate collision clearance left in the baked casing.
        # Isolated sheet/casing distance checks leave approximately 1 mm after
        # this placement adjustment, with no surface intersections.
        import numpy as np

        coordinates = np.empty(len(ob.data.vertices) * 3, dtype=np.float32)
        ob.data.vertices.foreach_get("co", coordinates)
        coordinates = coordinates.reshape((-1, 3))
        coordinates[:, 2] -= 0.0055
        ob.data.vertices.foreach_set("co", coordinates.reshape(-1))
        ob.data.update()
        if c.seams:
            from mathutils.bvhtree import BVHTree

            seam_surface = BVHTree.FromObject(ob, bpy.context.evaluated_depsgraph_get())
            points = []
            for k in edge + edge[:1]:
                mid = (Vector(upper[k]) + Vector(lower[k])) * 0.5
                co, normal, face, _ = seam_surface.find_nearest(mid)
                points.append(co + normal * 0.00065 if face is not None else mid)
            _seam("BedV2_Quilt_bound_edge", points, M.get("fabric_blue", M["floral"]), 0.0008)
    finally:
        if source is not None:
            donor = source.data
            bpy.data.objects.remove(source, do_unlink=True)
            if donor.users == 0:
                bpy.data.meshes.remove(donor)
        ob.select_set(False)
        for item in previous_selected:
            if item.name in bpy.context.view_layer.objects:
                item.select_set(True)
        bpy.context.view_layer.objects.active = previous_active
    ob["construction"] = "Baked lower casing; four uneven filled returns; connected contact union"
    ob["simulation"] = "Lower casing only: Blender 4.5.13, 85 frames, 68 x 58 quads"
    ob["upper_folds"] = (
        "Deterministic authored padding; two diagonal front crushes; no build-time simulation"
    )
    ob["print_placement"] = (
        "Quiet blue central/front return; flower print concentrated at left and perimeter"
    )
    return ob


def resimulate_quilt_points(frame_count=85):
    """Reproduce the r02 cloth solve in a temporary scene, without file I/O.

    Blender 4.5.13 was used for the delivered bake. A flat 1.85 x 1.42 m
    rest-shape key preserves the cloth's uncompressed spring lengths while the
    initial positions are predraped and asymmetric. The final geometry comes
    from gravity, mattress collision and self-contact, not the initial seed.
    API reference: https://docs.blender.org/manual/en/4.3/physics/cloth/settings/shape.html
    Returns control-grid points suitable for explicit, reviewable rebaking.
    """
    old_scene = bpy.context.window.scene
    sim = bpy.data.scenes.new("Temporary quilt relaxation")
    bpy.context.window.scene = sim
    made = []
    try:
        nu, nv = 68, 58
        fn = _quilt_seed_surface(BeddingConfig(seams=False))
        vs, fs = [], []
        for j in range(nv + 1):
            for i in range(nu + 1):
                u, v = i / nu, j / nv
                x, y, z = fn(u, v)
                y -= 0.105 * _gauss(u, 0.52, 0.20) * _gauss(v, 0.8, 0.30)
                y += 0.035 * _gauss(u, 0.18, 0.16) * _gauss(v, 0.6, 0.4)
                z += 0.105 + 0.09 * _gauss(u, 0.50, 0.24) * _gauss(v, 0.68, 0.3)
                z += 0.07 * _gauss(u, 0.85, 0.12) * _gauss(v, 0.56, 0.25)
                vs.append((x, y, z))
        for j in range(nv):
            for i in range(nu):
                a = j * (nu + 1) + i
                fs.append((a, a + 1, a + nu + 2, a + nu + 1))
        data = bpy.data.meshes.new("Quilt solve control grid")
        data.from_pydata(vs, [], fs)
        data.update()
        ob = bpy.data.objects.new("Quilt solve", data)
        sim.collection.objects.link(ob)
        made.append(ob)
        ob.shape_key_add(name="Basis")
        rest = ob.shape_key_add(name="Unfolded cotton rest")
        for j in range(nv + 1):
            for i in range(nu + 1):
                rest.data[j * (nu + 1) + i].co = (
                    (i / nu - 0.5) * 1.85,
                    3.55 + (j / nv - 0.5) * 1.42,
                    0.8,
                )
        rest.value = 0
        cloth = ob.modifiers.new("Gravity and self-contact relaxation", "CLOTH")
        s = cloth.settings
        s.rest_shape_key = rest
        s.quality = 7
        s.mass = 0.38
        s.air_damping = 4
        s.tension_stiffness = 18
        s.compression_stiffness = 18
        s.shear_stiffness = 12
        s.bending_stiffness = 0.32
        s.tension_damping = 9
        s.compression_damping = 9
        s.shear_damping = 8
        s.bending_damping = 2
        s.time_scale = 0.6
        cs = cloth.collision_settings
        cs.use_self_collision = True
        cs.self_distance_min = 0.014
        cs.self_friction = 8
        cs.distance_min = 0.008
        cs.collision_quality = 4
        # Beveled mattress identical to the reconstruction, isolated from other
        # room objects so changing a lamp or cabinet cannot change this bake.
        x, y, z = 1.016, 0.4572, 0.104
        mvs = [
            (a * x, 3.586 + b * y, 0.539 + d * z)
            for a, b, d in [
                (-1, -1, -1),
                (-1, -1, 1),
                (-1, 1, -1),
                (-1, 1, 1),
                (1, -1, -1),
                (1, -1, 1),
                (1, 1, -1),
                (1, 1, 1),
            ]
        ]
        mfs = [(0, 2, 6, 4), (1, 5, 7, 3), (0, 4, 5, 1), (2, 3, 7, 6), (0, 1, 3, 2), (4, 6, 7, 5)]
        md = bpy.data.meshes.new("Quilt mattress collider")
        md.from_pydata(mvs, [], mfs)
        md.update()
        mo = bpy.data.objects.new("Quilt mattress collider", md)
        sim.collection.objects.link(mo)
        made.append(mo)
        bevel = mo.modifiers.new("Mattress edge", "BEVEL")
        bevel.width = 0.065
        bevel.segments = 3
        mo.modifiers.new("Cloth support", "COLLISION")
        mo.collision.thickness_outer = 0.006
        mo.collision.cloth_friction = 12
        sim.frame_start = 1
        sim.frame_end = frame_count
        cloth.point_cache.frame_start = 1
        cloth.point_cache.frame_end = frame_count
        for frame in range(1, frame_count + 1):
            sim.frame_set(frame)
            bpy.context.view_layer.update()
            ob.evaluated_get(bpy.context.evaluated_depsgraph_get())
        dep = bpy.context.evaluated_depsgraph_get()
        result = ob.evaluated_get(dep).to_mesh()
        points = [tuple(v.co) for v in result.vertices]
        ob.evaluated_get(dep).to_mesh_clear()
        return {
            "nu": nu,
            "nv": nv,
            "points": points,
            "frames": frame_count,
            "blender": bpy.app.version_string,
        }
    finally:
        bpy.context.window.scene = old_scene
        for ob in made:
            bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.scenes.remove(sim)


def _pillow(c, M, index, x, y, angle):
    def fn(u, v):
        a, b = 2 * u - 1, 2 * v - 1
        xx = a * 0.275 * (1 - 0.085 * abs(b) ** 6)
        yy = b * 0.166 * (1 - 0.085 * abs(a) ** 6)
        bulge = max(0, math.sin(math.pi * u) * math.sin(math.pi * v)) ** 0.48
        z = 0.704 + 0.002 * math.sin(u * 41 + v * 35) * bulge
        # A dented seam and biased filling break the inflated-sphere look.
        z -= 0.009 * _gauss(u, 0.27, 0.085) * _gauss(v, 0.75, 0.25)
        xx += 0.006 * math.sin(v * 19) * abs(a) ** 5
        yy += 0.004 * math.sin(u * 23) * abs(b) ** 5
        return (
            c.center_x + x + xx * math.cos(angle) - yy * math.sin(angle),
            c.center_y + y + xx * math.sin(angle) + yy * math.cos(angle),
            c.mattress_top - 0.643 + z,
        )

    def loft(u, v):
        return 0.047 * (max(0, math.sin(math.pi * u) * math.sin(math.pi * v)) ** 0.48)

    ob = _padded(
        f"BedV2_Pillow_{index}", fn, M["floral"], int(86 * c.detail), int(62 * c.detail), loft
    )
    if c.seams:
        _seam(
            f"BedV2_Pillow_{index}_piping",
            _edge_points(fn, 0.003, 90),
            M.get("fabric_blue", M["floral"]),
            0.0012,
        )
    return ob


def _hanging(c, M, kind):
    # A single arc-length coordinate moves up the near panel, around the rail
    # and down the far panel. Position AND tangent are continuous at the joins.
    side = 1 if kind == "shirt" else -1
    front_length = {"shirt": 0.47, "towel": 0.405, "pants": 0.64}[kind]
    back_length = {"shirt": 0.245, "towel": 0.22, "pants": 0.30}[kind]
    # Reference 4/14: trousers occupy the door-side half, checked towel the
    # window-side half of the same left end rail.
    ycenter = {"shirt": 3.685, "towel": 3.725, "pants": 3.335}[kind]
    width = {"shirt": 0.43, "towel": 0.415, "pants": 0.40}[kind]
    rail_z, rx, rz = 1.157, 0.035, 0.046
    arc_length = 0.127
    total = front_length + arc_length + back_length

    def surface(u, v):
        s = v * total
        if s < front_length:
            x, z, nx, nz = side * (1.07 - rx), rail_z - front_length + s, -side, 0
            gather = 1 - 0.68 * _smooth(s / front_length)
        elif s <= front_length + arc_length:
            t = (s - front_length) / arc_length * math.pi
            x, z = side * (1.07 - rx * math.cos(t)), rail_z + rz * math.sin(t)
            nx, nz = -side * math.cos(t), math.sin(t)
            gather = 0.24
        else:
            x, z, nx, nz = side * (1.07 + rx), rail_z - (s - front_length - arc_length), side, 0
            gather = 0.30 + 0.35 * _smooth((s - front_length - arc_length) / back_length)
        # More material gathers lower down, with an uneven sewn hem. The
        # displacement always points away from the wooden support.
        folds = 0.0065 * (1 + math.sin(u * 23 + 0.8)) + 0.003 * (1 + math.sin(u * 49 + v * 3))
        folds *= gather
        x += nx * folds
        z += nz * folds + 0.004 * math.sin(u * 17 + 1.7) * (1 - _smooth(v / 0.15))
        w = width
        if kind == "shirt" and s < front_length:
            w += 0.075 * _gauss(s / front_length, 0.73, 0.16)  # folded short sleeve shoulders
        y = ycenter + (u - 0.5) * w + 0.003 * math.sin(v * 19 + u * 8)
        return c.center_x + x, c.center_y - 3.586 + y, c.mattress_top - 0.643 + z

    material = M["black"] if kind == "pants" else M["towel"]
    # The open split below the crotch is part of the silhouette, not a dark
    # stripe painted across an unbroken towel rectangle.
    omit = (lambda u, v: 0.465 < u < 0.535 and v * total < 0.245) if kind == "pants" else None
    obj = _grid(
        "BedV2_Rail_" + kind,
        surface,
        material,
        int(96 * c.detail),
        int(150 * c.detail),
        0.0015,
        omit=omit,
    )
    if c.seams:
        seam_mat = M.get("fabric_cream", material) if kind != "pants" else material
        if kind != "pants":
            _seam(
                "BedV2_" + kind + "_double_hem",
                [surface(i / 160, 0.016) for i in range(161)],
                seam_mat,
                0.00055,
            )
        else:
            for a, b in [(0, 0.45), (0.55, 1)]:
                _seam(
                    "BedV2_pants_leg_hem",
                    [surface(a + (b - a) * i / 75, 0.013) for i in range(76)],
                    material,
                    0.0007,
                )
    if kind == "towel":

        def out(u, v):
            # Follow the cloth normal around the rail so the woven stripes
            # remain visible on the near panel, rounded top and far panel.
            du = Vector(surface(min(1, u + 0.001), v)) - Vector(surface(max(0, u - 0.001), v))
            dv = Vector(surface(u, min(1, v + 0.001))) - Vector(surface(u, max(0, v - 0.001)))
            return Vector(surface(u, v)) + 0.0012 * du.cross(dv).normalized()

        for u in [0.045, 0.072, 0.19, 0.22, 0.71, 0.735, 0.915, 0.945]:
            _seam(
                "BedV2_Towel_woven_stripe",
                [out(u, j / 180) for j in range(181)],
                M["navy"],
                0.00070,
            )
        for v in [0.03, 0.062, 0.20, 0.22, 0.40, 0.42, 0.73, 0.752, 0.94, 0.969]:
            _seam(
                "BedV2_Towel_cross_stripe",
                [out(j / 150, v) for j in range(151)],
                M["navy"],
                0.00065,
            )
    return obj


def build_bedding(M, config=None):
    """Build replacement textiles and return new objects grouped by role.

    Required materials: rose, floral, towel, black, navy. Optional seam colors:
    fabric_cream, fabric_blue. All locations are world-space Blender Z-up meters.
    ``config`` may be a BeddingConfig or a dictionary. No old objects are removed.
    Default mattress bounds: x ±1.016, y 3.1288–4.0432, top z .643.
    """
    c = config if isinstance(config, BeddingConfig) else BeddingConfig(**(config or {}))
    if not 0.4 <= c.detail <= 2:
        raise ValueError("detail must be between .4 and 2")
    for key in ("rose", "floral", "towel", "black", "navy"):
        if key not in M:
            raise KeyError(f"Missing textile material: {key}")
    collection("07 / Bed and textiles V2")
    before = set(bpy.data.objects)
    roles = {"sheet": _sheet(c, M), "quilt": _quilt(c, M), "pillows": [], "hanging": []}
    if c.pillows:
        roles["pillows"] = [
            _pillow(c, M, 0, -0.63, 0.247, 0.10),
            _pillow(c, M, 1, 0.66, 0.225, -0.13),
        ]
    if c.hanging_fabrics:
        roles["hanging"] = [_hanging(c, M, kind) for kind in ("shirt", "pants", "towel")]
    roles["objects"] = sorted(set(bpy.data.objects) - before, key=lambda o: o.name)
    for ob in roles["objects"]:
        ob["reconstruction_version"] = "textiles-v2"
    return roles


# Lossless float32 control-grid bake from resimulate_quilt_points(), Blender 4.5.13.
# Embedded so scene rebuilds need neither an external cache nor a fresh solve.
_SOLVED_CLOTH_B85 = (
    "c-j<PbyyW&8?-S9MX>-uk?uygd)^nMq@<DV6r{UufekhmsMwgOASipT*qw-h9oUKOPyNpK-#+^+%U$lynR#dCP~+7@AFh=k<^{os"
    "nmhDXt`sE#UpV7@iO#o|;(*b<koDmVotH1c_84#IuhL01Y$X__8~~=xS83ocF}^$y0yl<Sr&+JXm|qqNHY+aBwnbvx+8PflX7cpG"
    "3Nh9!NrbOA4$!-&ML1qA8SMJEQC(9J-hUhicbgAVy;vc3U5bKl>P^(oSBU4ggu{%1n`w_?C2l?z3Nv$8(i@TrG_($dh`tr{xpz7G"
    "cm)7Fuct+0D^NMo2PR+HKpS)`v2e8;eEDw|ece`xDu3M|vvxa;dR2iZM>|3F@ojXir~((6JHS7u6|_&T0_Q~o{OP}%ww9IQ<>wC2"
    "f8bWyvaAeya_qoewu74fF2SL{tzhQQ270lt7^^;*LsiF0dT>oK`kNcWon`ZA+mK>BA~b|eI*X}zO(EWxVFda{B0Al(5UY>rL(GzS"
    "bkNUyEVya}whyZ4ZCM^3@zjG$#>I4PbuQlS(}j%uG`hwu7rU%XAbdp#HS5d9Ljgu$VheO0JMP?~2XX_g=+$Lem{@BF%jG7}>+7@7"
    "?SL-i&m2Mpcd}9QwjS&=y3239l#O%O7(m~rgM9kK9JJRlfpfAd-f4FZYTq=1bvbFg+m9@qea#qN_3rIZEzUywEF<t8W7VPeVh*Mp"
    "Glq<H-A8Yq$-r?tEZ|PoEx{a(416hX0lOo+1X@wEF?fIt?2%t4I5227whiQ9(%yDKCQZfG9!FR;Z<|2hDGi?<o&l4yTLn&!Qqa@M"
    "2cCa4=h}y+;J;oE=-#@5+j27*2Y+{ma)UPR^4uhR7Vin$?)~5@)RHm#pF5nMqe!M6OGI@C4=B7gf&6Mtz>V*Gz~qe;QHe>wYiqpV"
    "h3`x<wlf~dbZ-cJHI2CY#^ZH|02t~+NUm8NKFgm4BPwSQ;l?-|uqFl`H~5oS)mRK!9|z-%qlln3231E#fQn@%>GX)js`L=3JzPen"
    "+>OTC(m*hin@`rxVaJA{uvBpg`I8od-J2p{Vc&gv&|89@mwcgW(OvrWi3Bs(20=%AH_cI&Vs(`#kYQJ7bhQNK=lO$+=V=;qLX0`L"
    "eBk<@PMUQ^jJ3Bz!29TRdTpi{Z9PNbm%?e9%ZqW?`AAqA+eu%26`@l9c$huBnVQZPqr6-^WK=iN@LUn{^J8IwMKj$kC&KXV2$*}M"
    "na<V};{5Vps6Nm@2e=8bwl@?8MKsWn!z!`SIS|%bFQfy~D)8HgAh_MVlz#Y7jt|~>f$lYiqotMjxY`?}_qS31G9h*<%z&KtP1H0%"
    "i03MuK!5iRTK=gLRmTdT`rdk)kXnIyst)k#Z7nS*E61}#?V;mO9evAi^i$0SqIYhmUtP*D=CwJ53|mj{4k$&XGgdHu@d~<gYcVQS"
    "T7krFAyrf_!5LB$;AM;Hgc(IB*l!Md){Cg({z6RqVgkw?1@!lv0))#(5Y{E4`zrHLPRj%|+_UKs&3wF2rwe;;#L(8fTwFUy55AoC"
    "qmuGmJTb`>4qZSh{gjQW5vHIOtxHFZ%E6VB44~)mBsw}M3;Q~a;qAhHRNFZV!?W~3rS?5PU{N-%{%Z;c6`J`Ye%Ux{v@s|})bh61"
    "bI`EN0?h9j^7-*O*ra6&d-|F31G_SD7@EN9(-)2wXJz5LgXZvDAwbY>n~7a>&7tl1Ifts#>G)CE8um_6<96Rk#}PWVAnhE_)t*el"
    "d3yE$L$3>_jG2uc-<-gFp&EDJI~Bh^aRL9Wa@_gpX_##>6J9##bD0_`IF0iMP?^U)Tat`0c_wHcIK{2ANWm|oJz<&gQ*Lf-5_-Py"
    "29dThvB*fqnr&Wim*^5pmn3}o))N{VOvw3?1nd{!54ShDlOs-vxaFre)EfH}6P<YMY4-<Z0TR3wkN<XrLipl9@@8ZldTE4#Q&%*Z"
    "J}V9-^W&iXVj5{Jk3m~;99TsclQ97?D0~_Y7lXy5`$Q}*Gzo&LD+|cS<Iy<AB>-O4*AVT@XncMl3=S8+qC?{uUM2<rR`<~OZZVGD"
    ";S0;xJ*EFOOYq-Z4{%TKqUD1n7%|opUKw4dTQbF{{o4<YEIUQJhKTXFo<AJ&I72VI7GZYQEEr&MnNGeS!V_a-K(IhY|9lYPx2gzu"
    "zw$8MEfwQir${Ip*+dPE#rR@k1SENGrN4X_A6bUNOXofG=5--{)eC?f{dQ0fbs=tg>Ic}inm#WP;+gY7(5$wI?obtC^|BBMX<I^D"
    "n=5hGTwiE<xs)au2=U@u4_J_~h6*J@%pL0vhEp~%z7wLG*L1l2emx!2QHj>Zju6prB{eLr#C<pIVM^dqs&KjjukEph%+7k6f4m%j"
    "ffYPSY@mZDmZSV_6WE|oPyd@;ig&#k*SIaE*43qW`kXmbch98@?w8<-a%+$VR@1lo#rP@I8aDlrQnl5E2xtRVLLpr@ssP`sTSCIw"
    "3|g#~kCXK*Vfm1F`sI2aW*#<zR}%xNlX*U7JL*CR=SrIw=AxuR7sjo&r4RPy;-MB}u<_QXRvUBh#Cvn-KCDdhdb6?Pr3p9;8BRM2"
    "v+%<ubJ(%yE-!eNiIX0gL1fTbe)ZC9tS_*F*yHtl#D^^OUuzD;W){D@BO5R5w}waiUw63bX5(WID_Az@S%+Wu9Mtf%fV>Cm?DI!v"
    "Vv@Bj+#S;?_?I#Vl_%T5{+7)G{gQO_-{}Ab>5g1kWIBFG<CrFi=A?~jn1KlA9cFON_ZaW!yF)@lF?S^)6&nN|ApbCrgL$bqc$Yuy"
    "S-XV0w=Wq>Mg@bpX(#t$OEPBt^Mmute{(KIDVY6cCT!g@nEW1@gcDc!L)_d+<oTsU++Pp~b4NRns8vbm-R=huGmzB$PC)UsAjnpV"
    "A~kx6xU$zD40__pyM^)CJs<?qp3NeGZ{l(4qe!r<&mgZ8;_y*nI4nI?Oakx6qS~_<sH?3aO;It}P!S6yE(=J^+E{eD9R_zbmXN_q"
    "VsY4lKv2|MO%#tr;~Q}>q|=vFJ5GYN(omTE;2}M_T#PC!gP}3?6_vX$#%tHSp}gn;P4O4w4nGeFHoQtl{1xGy22c3!^CfyHON8~N"
    "{?P7shW^$Pq4&37_@Z%{s(%)u$(=|TWpRuy(h%XZRZ-w=*Frz;6yc_Yq40dhVVV&l#&7z;aPz`;dXnKNbaoKjJiMD$OBe^0`awj_"
    "M!IIS2o+2Gp=a|N+L|Q9``$Cb?{y8$Wmq_J$`6h`l2RuS;*;!|5U{<9?o+MA^Fut~^~Ytj!MPG+rm}T!-7+c-6XLWfPT(?RBW-;w"
    "M8_Hd6zy)HCgDQ78D$IOG#aRTQYGRVOGq}UqZbxephb%bEKaVWzm&@HQ@%MQd{|DWTq?tnTMeL4QcDGHrFeY1K8Uy~>Y7)I`!<@u"
    "^NnTHZBhwdePaguhUHR~r$uNOW(h<4XV8MQLe!gJ4Wm_K=yjz6Y-zE9b4P>eky!<}PsJ4eeRZV<_w&$MXbjub?dbAR`KVs12T2hI"
    "v~5E!evs3JBP%CTt#!F*6lw(D9F%BnZ7zP@WdT3F52tklb8yr!Yv}y*n@^NvVfh1Fm@vPSSO1)ewn?_|CSyH+WmGmE0Xwi=S<Sm`"
    "$Yi{11#SaP`83~5tn0M_r>Mmp#l4xB(`W|`znVG@51fO(@zWsM*VBGkat0di7Qm`oe+3%9GqAG^;OMJ20+og7c;kx`*lkSV3}VtT"
    "Tsj>l!D=q_cpBdQ<qU&{&E@{Pn})JlZ)iQaljCz!Q89#R1K)kz=z>(7UKa$mIcK?4{S<7jp9N{nf4FB+$#^U<1e8<8lXdTtao-<*"
    "aJ{8QwwEU%T{8<#OtmI{uM^QdF%0H=co6l=Nw`2a7{d1Xl4g%Y{96(RS6Va3QujoZOqm7wTt2b>5|4%u25zf!$QNlmmi5KJg|iZ3"
    "eLoJ>UWdcg5%Y<!WgIS#U|LSFf+X9-V)ejS(44-W+!Vy(5XM<Qs_MxS+gS7}4}b^TzS3{~BzW~uFuZ^9mTuAzqpo`hEHL;$P4&h2"
    "Z=f%z-+x3$-WFlo5I?Y=c#DdMi*TKv54a0@Xk3m6U)u)5yFuMl+A2hcU7=v{{yfbdEyNxF!oZ?}(o!cO?ztTbC%oDz|C*gY6bK=<"
    "N9p}7B3$0+2YT^`=-L@f`<c!JxyUWFmTAB2Tp#FOwS)e%7NHfx>4FvY)M2m)pBH#S*0!ZIW`qa@fu0bwNJ^(q6yg5Qo=`tXM2#bb"
    "I74X$%vY0ArG1t7>g;qlIB5}GTu_Pm)dU>BFQHA<Lc})?;GeaMj{70RfQ>friSdrAvk*_7w}CM#%juuNLcDHZ3RC0e(TW`vSd(iG"
    "qwXxAXS6Hu&?N)7IA9*lyv?-SGF{l`SW0(vl;Yw;x?s4!n3j<eY)#Pzhp-|#_E-^CzcT;@+eF&2vJh*38bb2mK-%)D5S!90U|*FZ"
    "UHq~D$A(ye+$?*#sxBXop0R{;Tc^@ld>(E*W(s(8JbmY$k2*K?K(b;G-7_f<*ShG!g<D_w0h4o4ug4IYG+*)+mvZo{yd~tQzU8yy"
    "a_~*UG;lb5g+JwxjXs(jOr5)x|7wwiYZh@J=bptop2@@}4+m)19Lj&{&cd?_4iM-%k`K_!MBhdZ)c#B8m_K?BzTJ;7&%i`rIXM$`"
    "%n8^G{p#?@BLnx{m<~@5j^_$@W?;X8uHZ7(hV#-&#|zCfz%pwMr<|FNa?NgV#gTIP;j?k}yBRQoZ{~)6O~d>Hez1N?5BIb+6@N7Q"
    "K#kxlx5zmaPbvn%^N3;OvqCCX_JzUj1CxkIDFus;hrz*zRzzbE<D<Ah7(UaEY*?O*H?<<5ajh5W_mE+#ClYdxB#><%86VvYfp-qk"
    "WdDgoTyQN4!hd9upQ97e$T0>wg;L_tlz=HKBcNnx6*+%19{m&I;9L6=va2*6Lq<eHkxc_x5Fdww<6<EtuZ}30#iNIRD73q8CP&%%"
    "&J`gbck~zSVmvauWEPBpUv&6k5x%?Z3%0A?(GJEVpCbH0{`@N{Y!u=2UmkGU{t2DcCq!{Ed!K8c(aTInoqXd5PLjKHz~4%&+ZhO+"
    "nwRMx<w_hP7YN7iAEPrKRARiFA8ZwzrgI($QR($ea5~mXudwxh`Z+I9x^jdjwu<np;|$oCy_?pzh|u<v8@Qd`Lc_eoxaPGR>|{Pb"
    "S-A+K)LdX^R2_9@T2a4Y1_XH2Q1{g$oXERClglFd<Ot)Y?JjW6s*FB)%jTwPXLzxrnqDpy;@%AavvVZ0iecnex;<n?&ZXUBMYu8F"
    "4lX`jK;vHsapQS&7_p;@h71tm&m~sy{E3hnPZr`OPZP*{T1bm}*nE^>1pnz}Q{#2z=<!7#HpnXIr6XmibI}x<^X5=<?@}D5V+twh"
    "3DoaoF-~_jgKIOxXi9i7>MI(+zswm_^s5k`E-(Q7Gv@S<RS|xvGKCAl*6djrAK4f|^Cb;>;XnbpjIe<2DtYRemyaXd%^}qMJ+FK?"
    "AE!zTVVuPYzAi2gpU*df?&B|b-3@v8DcJ&6>rkF^&BYg2t)T&y@$;*4(ENoxJPuyXNAAzYNsAppNzRMEcQYHeC2{b0p(;PLCJTG_"
    "J3{Jk^Nt-=S!l5qV7tC$$M&F1JgwjgV=f*OsI1P!pJ~qEx_P-kxo!?Fd@_T12z>&1EvC{8e8AE=m%DT*1J_s1fTIRg+_aE%)YqR0"
    "o&`MDH#`G(obZOC?ibvUv$N44$Okkp+~*ozq~TecAW)vANLHUtLz`HCxcF}}$-9z@#%@9IG*ge9ib%!9BckAND<MUEDn7~%2D?B%"
    "GFy~_E$4#a*tkH_e_skV+>QbwNhQ(~$!IH#f|K7Xh#k{){oKM}!-i5~up<cry5nFt%q8=;C!#4k7E~@Jwfz$@r+*Ygsw^cJ<|Uwt"
    "ToTN1Uq|eY#N&)}iI5z+iEJ@VK$pNM__=#4dFqvb+iGV)<AnjT@L&;M2o41KFF$DL4j~R$9|$M+{HB)w*n6(w1x=qm(j11DJy~wh"
    "|HOOx+g^x6=Xt{?*QeC|VkIW3d&2Km_h{w13jFHr1IKS)r+J^*%)Y@JYTlft&c7=#=;91$(!M}TMMAXJbcY97o%AyE2R??o!qRmI"
    ">B2KYJecYNhWGZ-3#B4VyNa;pK{I_GE5?I4)8SgmHrn(<giAFMW`12qPt}Q0DaZ+4+N_~}dPKPL89@BaWz^1GgbQuh_da$Wy~@0Z"
    "2YV291Xj=nC&rJ89Hcv>)4WYWtl3PU(<ql_^kW)QWCtnHLi%Bm2xHYO;nn9tdf*V_FQ&WJi*o4#_Pl1QHqbsYht}Syz=4CTVb8{B"
    "dTB`o*6lKdnaYXu<eM^7Dz<`+?z3p|rZW8V*$8HD38t?`m*TMk3wZt8m8LW?>@=B!`))#82bG|Oxgm4~nbVs4MW{AX7nY{0Q_1o|"
    "T-u-u|0&8-_rC@BD4ls<e+E;&x)3iswgAhFUjCqE0bV?837%K>@Gsux<HiqW5a7F+|GFs;mpEI4WXcWRb!Q$v{p$czM;+lGW#wYe"
    "1_Vx!$Cvu$;-g%~BMUru_{@B{<Ib?x<8VifAO}y*b_9o8D>`%@WZ|fTuAqH%tl;stEHs?y0%<+jf^Ana@zOO<IBsRk^^46!XQ>B_"
    "T5Z8SIzI==WPh;IS;K{1n1g}L^E@+sF=vpPft8(s@YLrBXBe1{n=u&N?LTmqNf{`A%^&>V%aM)K((%ZbV3@5mj@*8gh8>^7;JJeh"
    "QRZjkDT846)!&wY{cL;~6AgPm&mi@q(lBdvG&~#`PNs;`@bR%(@Xs!rs0F2>L(MFRewI&0MyBGW3o#HXS4G|~PQhCj!=N`|A&K=*"
    "M&-wm@Z#tq;-i&}!bOQ-&95T8gOl;W@hC{JSVub7Bw|cy96V`lBx9yC&KjKxHCK0%I|Ye&%r6e69^FfRX(!<A^HFdO2FWhH6yh#z"
    "Z-|{ZP_{`!h%XELVA$MWv|&Rfrs#SDH}V%%nkmFNk6odp{Vh#17b3my0+*k?qrR~fcxI|QwEuZP+vZnbhPo?+;vKp|Ux=lnTp>#P"
    "I{nBz;ft%M!@^Z(=&t%oJk;k138zj|tIcdqSwTR5e=E(*65_(G1g^?aTH_}|RTTnurbp<9iDGn#=3v{wy|l4ZjK2%)f$!HyzbzEw"
    "7!3zlb7Cb;7K_o|(E%E6)zb81BK-Z?4qP`bq=hc*nr8&UmsZf}%3}2Y!2E$bb7)bA2({J`@ZCI%wuXuDg*yk+y^?6{HWA+BZQ$Ry"
    "cpB<1LQQWoXzPijIW0nzJ+cPZ_(=LlQHWD*rh(j~VA{T`0)K3_1)Yno^nOV>Ms(SL>ozC)Yh@V*=vhFumNRWGC`G3^hOj!ql0LF8"
    "#hZUDpkwxAT0f)&544zp_gHP}R#k$zgV|iOdNj40QjB)fjR1<j@NP?rFi=w;1`T|`_tq9-_%>rGF6!c)zZasShBd?oo#9uC3($tz"
    "fnsbGU-md3^IN9D-<vJ`*D(b++y$V1W-YJ%Bo93XIYQdWTHgM4E{-j9gC7NYyxpE$ywT+hb0_`kSVnTty^*bH;u%LTC+Fbw@viV<"
    "-pL~Yld`e<u_rimei3AOXJe452h=WA;MO{1VUedVj5jXkR$6D_(IOu>=Qf{fnwp6*{evNL^)XIGGzXX8@&~VG%JqECz_ySuXx#ap"
    "OC6bkPsc_uJvo-#Kc0a@*M!3BTuoxxl#Z=?V<6~^4N;28K;zsn=0A9mEtct6>l_9)dxD7mzu9<GBNpln(#Yy_X}I}S3>f?>AjfTI"
    "<GrcOL#~@gq;Y8&eJC6P9?mDtv8niBODtr!uObtFrJzMj1WaAGiahE~!P~Wo;69+9+}@syuNEah$=GdV{5j_D^+my{1x@6dYBH+n"
    "roiK@gXGf1L~PefhAaB5B;rmYHV=z|gpy&hceX-I9O(&(-v`L#qJ^li-yL-P2g-t1SK#nP?l3UwCzYRFft!Myq38M!ddxwHS49Ye"
    "B=6{{&`PXdiLm0wW9nzkt{Fz)%kL-jpn&nnGsYbb-E_<IO1xT6V3Fq~I*PBrecSD!`s^`!(5n)s{jrD4DQ)yI^QHCDY~e&kD-HW5"
    "#Q4#6AX`OgEYos>-dh8@?5F<@ig3hd8?Y5@rSF%B@a^(xkfFAg9(XCju@|jj%f}@&!H0Qwt1O`N%3SJFEk@^eHgI8^h@N^VMuo#1"
    "_|GY)(eh$6Dwqa!W8<lRx)_gyI6z&j2W=Q8M%Sm)VDE5G`YBn2+M8`)>myG(=CBY?JvD>8Yff}yl@KG$?O<7s7ft_Hi8~k<gf>p6"
    "Nh>Pw?`u=AX)>V))|6w<J#(<XC!n`ymgCkX2Jr2*J~jJYioe-xa@&6b%WF#UPlN?<{_=G3qf+eCF@&drKfH1d!x8hD+aCAvL3zbE"
    "^tu^v8OQi*!Nr)!{DJioxAF7N72<IXQwaE8!)K5})RMP`IZL<jZyO5H$3g(t6*75^Ed|)yAK|y$dS1t_0GIf<!iOebK0hHJ&Ffv@"
    "QLrQbRXGnI*?Ga+<lP;*S8_2a#2xZyC3RG=45-M?8}=Cr1wBi1FmjM5boEFDF4Al~=jRV{@dECLZVqOv&xA4mV!82mv#@1FAY4<~"
    "$vw!;!ZR2Ap|+)+`?x0)r_Tz7c&+!`?5A_^npH6Tarnix{hfnZ+alq^xRJzo!W>LAiUpaU2}$ytgAq&P!L!?yBu&r2LajIm-yA^R"
    "|IEPS-@+jLK{8QnO~(v2`*^&}B{4hFajR7v^gOR7mWd2s|3!d-W;OXQU^bfWkB1|pR*+0S4KHs_gr1}|M71vsjh{rqqScLL;92HT"
    "_{V_4m>s0*Z3?FGNwE7T<CnE5IL9jr%3=<ZvY=$_4U7fRnRXI$EEzM8C&Q#2GIC2d3H$#}1pmduWS{?4U|EGTIQ=IlyRuS<|8$%o"
    "wqby*t)~*hnU_1)y}xXS2g@Jb1)!$?otAo6V$>Q3_%VTDCtrw%t~$Uz=F3fZUxE6;HgJB=L+WlR#GUQ7(C_vw`uL6z)6MOn_rVRi"
    "l-+Xz^Kuna&d^~@A68zsg&vzzbnNd+oPNk0e3u-iN0^^>y2%Vw%3A1L2NCY6H3RE$2WXs}7}H;x!ur&$w6~DyF*9>mIBGjRktoIz"
    "4-0r7T~9~65@XL#E4XF5lqL!!xGUEN$Qvo0S|mZG-?k6~+0<gB1g8$OgOIX(x-nafzcyGv-<e=Kai19Lj#)$boNyZOLWF0BS%AhT"
    "pk8-GXvXG_cd3^2g$~n)r!C=rkTDem3Q=ReCG0R0(2>SMv}rMdqPyDE5i9ZEcr!RRO`GO!tHAvi^}wV-h5E&p<GqP`pjJJKu4^jC"
    "^-oNp`o@3!ss&~EXq7oQIo;vQSeBG}$`Cpa-sT(KOYuOD1>9JEgfIGDjIV}TL(klK{4eif{2Xlx>lQEP-wZ0ofho4o{?3oz{vXSd"
    "*t|b)$UMF&tq9|GIYQ00H2%=}Le$7{hqcKwdBxNMyj9}`-OpZjP*3JdXwHD)lbSmU_vhj2+L@3xs=q^;PaZCB@qkGO8r%Ll<)X8e"
    "KYaUrTJUUaE=os)KwQjB&O0>+=Pe2Wr_yEIH^@QTcs~fAxt+_a$;Q_wX2JdV9&Wmf<+f)7VamWi+|4;GhxH1BSFK~o;ANS3e(Nlt"
    "K3Zg}2J-{!V_;kBG@?2*6Zbw3hm&otWWbC}6f4DpT3!_S(>w=vSI5I?l^mj@Gzaf}i~?DGH94U<2Vp}btU0`Z%w|}-n-&jK_pcz%"
    "e(89OMnSu69qDXI$D|ucU}D)w!kcH~@wh~oMs^dk+}Rkb69Z$u?k9idrs0n#N${YtmAryfRI-VO<$v0VvM>b=8BYbPA1C_aWK_Bx"
    "14CY)C5{`D@fqWwd9Q}bHuqIv$zlf>r#VbEoz2w74;>(Ga(~&yW+6^;ae$i#`pdF5RbpJ9HJEPxMgtkw*fIaV_uMynp3Mb%{cK>x"
    "m)Ep6QHT%cTR`;O2lT-NAx^$-0=2*H)0Y3(Jv&%lP<@3uFK4rZo(a6KyG&OXi13H4C3xLEPRB5>%(U1Hj3#%|l-0~bXx0aH)<f9O"
    "KEud5eRw`)H$5FI!jqf<)HrUXrsKt!x5xlC8?T`!dqw!y#{`7)*Hg(oF-D9rf^+AW)3xCe+&j<|qEf19z)A^fHJQR*KA(PVk>LGz"
    "7H~5%k|w!G@bL<BsO(9g7nu$W8*2=YVqIt|J8mCh274R=srh*kx)~dRQIRXvQe_<X%>Y`v4e18v0XE+@g7`z@Y2r5K*I66GqHVf#"
    "3d^20_~^n4krEX@szl#PBY0^yghutN#2KZ!pxg0@x7t#UUBL#B-usUKSW|&p_01vE>n#7ssvNx?ErA=eg+F0ZhIFS1^fs>ND^8W-"
    "ykCr8#s%`~S4+@tz7?RNE`MZsF?NO70k0zDuYN4X$$<opx+?MW6pPWe58y%7y^gdqg_tnH1%~ar*b%t65CgNk*~~Su!%bL#nt85F"
    "w~LSbEGxjEf|+owO+&EyZyq`g^@FyK#{#W)|JQY1uu!PN@rUwI83W**ub8`$mxnGDA)qj5KbMi5i{>ALVM)<BPGx)!ZZPr(RsJKV"
    "U7Ujg=TLa#ph#A(%|;u!Aei)4jd(53#)Y54L3@)mIo*<lFD8USMV<?p(wl`T3DI!LB8+&iVEAIb@qllsq;hu_p4`i3{L#fEVn7yt"
    "Z-{^``BmiM(M+5l8V4uhmy+4zGqGWQJb34=CWFJ~VD7|7sC%)Agb6aRB`6x+uiHktj%DDwq9i!r)=V@Gq@$r$GN_#DAn*IJSxhq#"
    "bSIx6L#os8j#2_VpWaDkC8VKVXE<zeK2HRVDR}W=I9QxNO_~%_apUheusow6OJaH{G|>jciE=XSNkUZVvVfz12g^*@8v8HA24>&w"
    "Co|b2#9QMmV9?dSv~#EsD@qLE(EM+7*fSwo)Ea@=vNyDX>6{mJCJ=Y|6^)xO#BZPVpeOeM&5jXaFRu@~+`H+GCYG}}>4JOV6>5|y"
    "!YvX5IJ<>$kOJ!@oHhalgQHY;hX^|>4MFy#jg~Tg*{nSk90Yr4$#@YacTI)`%^PXoZ1%fuX+cf*Dw=*yght<VAmu;}9m-~$#9V#2"
    "AH0~xnn<vFsxG8kO6kq53{w+~z+!t2&C!zJ*FHmNDT||#w<YMc*ANsuX42ge65Q-#1g}?m(j(i%=(|Q24msM;VK!oXbl4E)>bcQd"
    "Ec3Ok)P}yXrqsYqgw=Z5uzadARTqj-Ce{Z>Zam%oT!`iFQ{j#BU^**=c`tXhAvX9G|HM^@?e#`*H?50zVS4q1xh_P0rThl<3ar|1"
    "2+C<&dD*iHJeyz+0bf?|Q3d6wS!)Fymp%D5=Q8wFw}6(JVf;>yGHiN14J<eC9furCu|Lzm_upFZFV>Wz-x7o+%g6DWB_(J*))jnx"
    "=XTr)Eyk-0Jzzui8izO4MQEw-1EcNS1lKMX;*XoIuyyrXfnIO{%A3xB)nOyJym1BC@!c1UzK-L5DCOgM=J}_M4C5Ab<>HwyUSRXM"
    "p0n>{*x_b^%9AVHN9Iv1e8BSkF#|}AYA)^rUwE7*N4A^g;ReHCrY$Ft#%z{DInRPm#b!i_c@%dS2g1QO0+M<w2S;281vg;`Sve~Q"
    "Ump#J=%Ne~J~A7Z>V?3g=h<YoR}Nb0M8YM9YGT%vjradX!F9)l<lM|GoW3Ir+SV;6SN~<<oAzj!$~Tai1GDh7dmNaR?I6`2nW&T$"
    "3qyQb$jzuZ_~KkF>^40}<R7Htj!%&gJhGEG=VjpAmRMM};{v(wn~o#h;^A)Z6|(qd8h(8f4RvpB5}li==#mu%_O3TcYCtN!{}T)4"
    "#}#Ckv_;sSZ2_w9hRdD{SqEm3A$+cplj)bRcjLMd4A1W;Q`pY5Q?L<yxZGcsd!ON}QyX6Df2B4bnQ!1V6$<GWYVc8n{<``wj(bhx"
    "MIzjGSQ}o;p3uub88_{n49_Na(;;3WJlCTM(VFMzXr{-$U7ZZwldsSgJu%w#Oobobo%GcIGo~JGkU6!`viV}{8ma?3jhm>CF3V?^"
    "YJp?d7W$QS6^{H;gA(Uew21lDv3n;$-OM_A_LLY+w6tJu^?a(&Ji1`LDex?#gq~O{#_~;CF!e<#{kTGcdVjUy%#dh$ZIT2heb)xH"
    "yS{YKCkY;@&<6T(8dZ}@aQIzaa85U*w?B$;+a+D_*kwRN-B>qot0s(HH-Q#9Gp+bg2MRhz(LY@xG+(X>uU7r#9|%O)Wu^&lhri>a"
    "JVbagSr-(xT;cO;ST9Ih8{~gA^B+=#n7PFe2F_~WJ<}_(^FJLpmMr0G%q!5V)BqNlc<>GT%TeX72}rKG@;PHFSl`124&^=UAZ=yX"
    "m~RE6R=n$2Wmt{|+5$+`7IkbdEJIh`5xV7EI{s@e!Ki}>Yl9E8$4x568rG@!Xun2q_H;204w(Tr)+%#1YKzb=+6&xQ>Tw-0h4|%;"
    "3%tD<!(GrUL<iP~nI){?(pKf;6KzkJIARfJZJdV&KV2a8MH6>$W-e++dB7a;6E3En;UdfvteyIiROU<ES?vS+ttXO<?Rhw++83mp"
    "2KjO?2Zd$6kp9}1+`F8MMCb=O)-y?vkj+`w0wG{b3>o}{`F=tEa3nE<7<%O5mgT`P{g9NXM>6gUp9Kj9^NIXI#$SrTu*_lw8Ii{P"
    "jl*H^!gw`lY0bh<pF$w@;CAvyAsZdmg~Q#$J4n4Q<1e33@a=0MFAim*G&%ytm$nfDtvUGS$1G64e1hmOkNxxLP}t&kl_Va_z?}wB"
    "uxrN+l3<dKb6Fp(+u<>pM3~<52#53U9}^8p8nzvbg?alGWPkpM&~l_P?2cEIEeDqMu<tRlbBN5&R)q1&Q=#kXAXzwy(R{uh_|*QR"
    "*O@2WsW=tva(+^C#x*1J)uG|RXZnwI4;0cgVd;Qg`ZHCGEsLhWr`G3Gv`>WPwrWr~@(%s!F2(_GHQ_`0HQIDmggR-eU}ArY{!<j="
    "=594uzWxL~^InW<mXkr@Xe*8M6XSy@b*LM%mj<#7H+P68-1Xf^Yk!E*##RG9Tw6=0uVk}-;CPrgr-l|j5#vlxHR$)fnrhFMAkEf<"
    "Me>zYYm*r7JXVGCe==yKjs%}y(ST`x66u9uQgpdA8LoNHr1RK(6n{h=9@p5@I@Uq@7N7|~^>nG<DG5%n)B@+mNwkQ~N~`MCKxe1|"
    "{Ww~J^Nh9N-_YN@PMR1eG);w=>Ak!z!~U|tlc34*1iz8#Owr)UuzlfSUM_^K6$<*Gd~iMAaz%*6|7pR8G%^1ySBT5*>%(@D2mg05"
    "<0HnQL55EJUe?V!EHQzoTNgVN1QpoZYX%;nk30M~RbXR{9gMecKYH7ebsm@>q6N_o+Xj~5oG%XWAVp75!m`@GTGPQVBww)1p#&Ry"
    "3A{S<T%hu@2(3z;AkxK^+cduz<vLu!VTFX-R=_eQ*2gdiui>^_EI?&@H@K<7bG6J5um8^zo=n-zx$nxyPyd`?;KyrRw0j=*y>*6B"
    "@!vSomXDRh6D|*tBVTUi;^570aQM{(QmdYe6I5rw)8l63!-_oodC?2(a~#R7XE_+J<^gdIvq)JD({;1F;bdMCDZZbJd&5{3|3XCI"
    "cP<9*^M!dm^GM3P9JGn@g+bew5#_D9ICMx5m{zPJmj>nF^=*F8SHF?;t;)eGD?=bJw~;)P&&GqT0dU-7H#ycX3rj}(!}Z&3<k99#"
    "9MKa18WT>E<5rot%9rJ^`_GZ#-{;^~rVnpPuaXfKjGK&DmvYMk@~1Nc>mdYAFYhJm-lSvqiEuEH>m|uijI-{?0l!aKHg%vF`&xBi"
    "!Pen2FMBa2HBN=5rlB$+(@x`R)!@|eL9(-R#rS=h29%%rkA__qqwta@Tr>Sk_ps}~G>?b8lOJg}dw(3mCcs7Imvpg}1Y4;({GIch"
    "niPt0quN-w_Ns^Weqrx<r7CRdx=bJ3WSkPI3LcZr(udQ;Slprl_MyjVhdk3!#pB_!Rx2&^mtg*2Rah3bi%wb3?h`T&#?9GE7cG=v"
    "MfwC76kJEEwo34f-$bZgvWT`DOVBbw1(dE;(^Fq1xLR`}XciUHwj~m5d@unDjl*fxI0<_E83z_F5!A?BibMBIfEn+QR{h6tv0oKN"
    "4Yr~tW7z$Fj)Pm7+VlbI#4ZX^1+{ENs`*yJI=3278`qy&kC))k*Q#I_@RXkyBEj2{Q=qZ&7|%1Deh$)t!CQCmK7+(K(sB~`8aML8"
    "#)|QyPzUO^2>D8>2t$|Z!~UCIyeiAia@-k?)@kz->Y0x>#{lZa-|1)(R-$K=9t>S{zGF7i(lyp*aJ<f>qvlm5@|UgQqrTPAPZulD"
    "xZ56P@U?=4C(7~1IRWHf`yzO{y9}?gjLd8E7%p;TDTaS{0%b*gF8c$^YP~o(KQEe#N-e_ku?Szd_1s-7Mw1WD5PWbKx51+jRWCTg"
    "(w+;P-ljtAPgy7J$0M%EqyXEWxq#E&KCa|r9$tD3pm<$@JRDSj{i9vr(EUl|+`l|L&HRV<jao!}I2Xe-oZx=01Nk#K4+l<mg^O1M"
    "Nqt)$27AnaShHj@a7ZrN$XwxiWidJEk%!$no*+{dlWqHQFnEgxT-mUY=pV_&4QgH>I8jHY8nOG#_JPE@4WyOk;&oqt*zLQOgb&Wa"
    "{y{S#Yv~^HdSwpo-w^~d?l94tla1UfKe*u0LVQ`jB78|GM6%ic+wv?7wGW5w|1J^Pq%2%+5&}lA?-HewOguI;1iAw55&14QH=T-v"
    "t4rS!<K=U3YB<B!g-=9{%}~k@qM?Z&Eo*9K`D6MNxY0IBRyRV7E88Z)0;}P&0fAzyFc}Z^=7VH8tmk&UX&gkj4v>}SNYH$vI@}oZ"
    "o1U<gV2Aodh!*tGo>6R$Xc`Sq&%dMJ&Pwp;u!(TW`vvt0X6t{%7*JE`p<#?K)N7SN^zk}v-yp#N_i^BT@FF#TE5;`qM*$bhQ;zw`"
    "U2jLi*U269!zI@7zODk(PVA$-OkXueD?`wYMyjF0@O69?oLat;#;;=6G>nG9%NEg<22$LmF&Zqph16>q+c)uhG{k0R)7fcKZ1)=r"
    "l1+)!C0l}vT1UZ<P2P0iJqgP4$3XbDX>>xP6tj)S!mf8_bQ9Z`@rB+0TiOJ=j&)@Rx{rm(Ve<5avlR8Ojbq=-JAS2t6b~1wK}YsQ"
    "Ug#`Ap{pu*U)#oOhe@!Q>C!PRMf{XKV)T@s4C~ACc~jOw8YY+wA>j`E5(hCZAEpbrKSuKX(is0P(t}2q8y){PvR;J6R7e`VzT>P+"
    "h~Kvwf<fehqpw$0;)T-&AdJy%8^5svPbHdx$(I0uTy`bCX|(~xea(WcPUU!Gt~HbzeH6&9mf~ud29BQtIE9I2c&i@ZY>J4xy|M&*"
    "BOSqU<XrAxaxp&Dasb=*t=!>|BINdSFk<I*4%>^c>(F%g@vetEJ-!eN)EvRbd>~mTEW~C<H;|h$l>8_yz@~Qu)Y``r`^bD`aTQ$e"
    "FeK;JGtRPegW%P+BrQ1~b!Q;x`?`?}>Up@knZTc}D6;x^E-szv1c@bir1f_m=H7Jy?x~3EotBG>k4%TJIt$5N-#jc`<OWegmXT){"
    "bMPqh)!#I(Atp&VSR?j;E%H0a)PcG9Da`{`IPWI-G8Ywe{J>xH5b0*Vx<-RHoGWi5gA;PG?N}fbc^)H&*5zOwodwRPPmxTIY>c}X"
    "00Tx`CT5#iXX$)641Cm0`ekI{=F&(An*W?^)Xc)L1Cii5`2`uZdk*5!ILOQYN_v$tvCWG)wj)Q&HnfOwT<HW@dPYemWLQ{sNdwAk"
    "hRKdimEg5ulVGIkFj<MC1RoL=2%rOG+8q*{cw#IlP5VWkO^~Ae&k2xn_YW<+Ai)dbQQ#N!kwUT*Ll=&LcIBsZ8<FA?ehiooe@urp"
    "NO0i<MdribpbhO3T$`x`E7DHU=9?1SqBROkY&t1t#yZ<aheLg9E4_1Gg0t2rfT2?pT{>KfnhamAo?GbtVhO%A8Ug*?*V1n$Qv7MC"
    "1ZC!nC?1#K%5(DYDZZR0>}R^GT^=5t%%jihrRbHU1cn*m^g*B$FRLqoeu)!3dQ^hS3*{lnQ9y4TlVXRj5=^^3l~ym5;{GsYAVbE{"
    "T&CHw+?C+Uy?=a0nFN#Hj)qNj&-h~@QtZ)E0orqf-!WB+Mo%VydczX_XOjf)%vXhb3U$0(JzEp5Pk^ZR!F=#<5$aD+g)!0*ygT#N"
    "uT*HlZuOrX(<?=2)2j(h(SaRzQkajYqzfHA+D8{KE%)_=HgtHZI}qkinx8g?^?bD;zp4^@6O2H8=1D<!B<ndunL)|V(Ol!l3LKDW"
    "3pb~kaTasS@l2aN$cMyo-RDcOzP}xeiLK{;D6m<{4Is~d6Bkrpf;xT<@T;bcdpE8GnKXhIjyJe1kBZQAkO0z0edTJam`AtD0X#<!"
    "Chs;Dp>~`T+-sjma#%NS)cNTUu}hP9uPMM85dz>}Sd)vhS;hoT(A(xt-c2jOE0bK{0vA9oRp;YLeGa}vC6SU%`G_S>uu-vu*fJi8"
    "W<8L9=5t9U<E-jbConT!O75J_#Wc1(VPW=a;<qmkr?Q^I&tIEJJ)5%@Ik<q|tj&af#(vh?6Z#sPiQCg$Ou-qTbn7q~Rl)S(iJ1_%"
    "x06ihmy5OTKCtKJDbjf-7k!=w!nX-m$j(hUnADGTfp**?TkW$^cpwNY`tFfH%^bY@Edq>Ho)Fbl*=Va35Be`&kcV6rc4IPFt9~X="
    "Sa+h&H5n!(smS^>|8~*-@vt#bQKrJQP@Db)P*^G_%b6%ePh|~wE*K`OL@AopjfL;B!7`U>DPGwz3RHUg$#h!T`GAQq$mcKp%-+57"
    "(os;W{f#EgmSPqvz;C0MbYp}RGgTG9Y~@`#e7+Pn?p1_0Kf35>O)0+lJ`|q$ou||0O0nyn0tgo|zgk|3cel!c+Ju9&s850yFAf3g"
    "AG_#}HB$U`L>{b^HqjEcFK@ZqFu0hsoPL?YxS(1N>JH7P;hj?advgSQ+F3~>jivZuyBu_lNML)=q)e0zgGZnI=v<vDOt>Ns8AfjO"
    "e2^5!^$h{j1;%u$niQ{%8xDhU3Qc<_#diww5ZPaz8g6FK*gFzp`}d<CA4#zEx;$v?yTbc0&q1Z%D7dw4JHL$Sy1tIlP^h(xf5hgg"
    "#fwM7fgy4HP-~_e|Bi<TD-8MY3^6{IjfE2H?v9gpMR@o21gNzb&~ce%Nq^aTg@3mkl`t<caFQkr5-SPnf>^h3gbw^(vQePPx=aiH"
    "=|a$_Q-U>OA*x%Nfm)v)w{>+T4$3x$kVr=^!=817#AYxoA(hi$Gm%@=G<cXL;k=#8@!C-V$o<>M_3bXjFN~-9-#f#7d{c@6j~!t5"
    "lp9=kWC?OV?BQkhC+_B>Vl3A~SWx(ri~3Q7+gNAmozh5hXn7GjWeec>PgUZ}`VZINIKhR<x}?*r2(Lb#22B!sGVgN%7L0R%;9MWF"
    "M86PG2cd9YI=O$k02e0!*q+QKHH?q`8!dqN772MYr2xGc4=&ocfUNkMhl5``K($~M>D<otXk<A;(dY(pd`uqheFIP(xr_KW=3#)A"
    "BX|cik@TSjC|u_XPdg8g110%r+wKV;{V53z%fpMxtQ(ngirjd}=CVCAA@#~-(iNMF4rhJf)5&f!Unvh)EeV3wKle#ya1PGC=ntA+"
    "FUWzt+32Yl0?%H&Cx0enW8khxup9r8h#8IslqW(|-Vb8zmWBJ*rNGxgV`SylQZ!tm4tgp|vXAT78eTLGM(WDT3Y(-j<efS!Yab%3"
    "doIOI^Cp7zYdKj^S{0Um91UJC`^hdZuEIad$Ah`yH_AI!;lKwfAo2W8n;fbz)kJ~u+8erUVioo`83hfwkEx?-6%MHx4(CF<Y2805"
    "-cXeT<z;8-t9=X?@k3zxf+KVaTl1H#9RaatT50+&DSo{(03u)q{l>79HDVCh-djtLC{|%}@lco~T~2Q=W!Q8d0Iho@^h&!Fz26Ol"
    "mc%)<cUTo(ua$#-u@Uqx!*U@EfUoYpbYEB%4tE;@qDnieqFIFlHVg&r6-IQ{94We&4}^pTW2p5s_Pqb(AnEB)I+1<;@m<4V)_*T}"
    "DZ{2=pc1$@T;My^rKmGx1ng4Y%v-OQU=ybRf&M=H+$srv+^Yod$LRCLO3bg*9t}#*hVw7jep>@?RVbRjrX#aajL+VT2dl-|_8W(a"
    "vD<n)IDHNiyks1-cB~qVYCR{|ATPo{V<y8+_3MIMPnOBf)ra#18eAdcpbz;5(EXR=1}_le-L+;ACzs9*xloCs+ZM2_VHxWrSK!hN"
    "Gp0#WxLdX?OWI=v6Ph-0_s^H1z`_FJR$k(a$Cu&0WJ|cZ;T88Giuv0^Z9yyUGdGQ8vfo%|Nv(7+2~96SpB7tC{XLd!%_zo4cWt0n"
    "UWbG|Eync+IWVxWA~Mz$&-#VXIu1!gRuS%*I}NN&eaT(6XLj-uTi7g4A{TWE@OZN=EJ>G;vCs4IOpYz|y{jfEV+t`dkb`rsE6Jn{"
    "%p30&K!3JJM!7o=J#FpbTIV*hSSufQAG3#qjO}D^P62KyMc6#Kl{`P1k4{YceO=f_e(o&5r~Tbw;>8mr=UqO=vsr1xv5UkxJP#F("
    "XTYL!H^?!?d~6xx3vagFBR!SOCmikrkIG+=`uJRoGV_N)@RXEGm=0VM26kUwlSe0WaGVG0&e8AWGxH_XSeCkeQ9tO?X8RCr5}{OC"
    "S=Mkyiu-CO!`<h~vVPO6a7*I^IKN_q%rL(SH$9vPb!mfS58|qDvcCqjJRBlhp;(RC+s4D&RRd&xKdbP<Uu9T4?K^$1T8*6tRN&q4"
    "@3eDJHM-4Ggj9G%9h<7~+G%;nv%W_^G2GqRH42W5y-M#|RN=g_O3=CLJiQ%Mg$t{OLO;?$f0$NbKc?%<1NPJN+EsXY_b~V~bUV$A"
    "tU{_a5UQ-!(7uo=Tu|N*lCCVIoBXP<=;0tpyd<H{R#hn5@P~|VOQ*>~c7AVvc>FJ#;zud&)%rz#y>+Hfu1GN?p&wWbwV@>&tI*1C"
    "5cug#rd3m_@WkK2uu3|LhB7>I(*9tj`<36v^ryr6A<*S^n|EfP2Q~}`ANv-5@d+u0#VA3;n0dUO6XVd&BS5|<m|q^w@cvyHei>-<"
    ">5rKgCmRPwj@vu3<RsX4dJL4DsOk9VCc!wO4vGaMJHnVxc=WeAEb7@W&}6=1bMHi0@JWknUnjzj`RbrGjbVi42sy3He>gjhs|jG<"
    "=6OSSJW|M2EMeY)y8$HstmBrkZbr`)wqJX22N&pCiH=h(V9L}ToJm3jTCTH!*img<xJ@~ZHnnHnu<M-JA=VulZv_E~{fXaGHWMwg"
    "hE-9+h&kh<ta5vpkU5f+1hE`;I|rZMj3-xEmSj|A1BRByWYvvgtk`c0R_#d47>*pe0A>VulYaY(aOhn}FglS$&P^`D>2EoRF3BZ("
    "o)xkz)fU$GRgnhuLM*vr4S88hh{nD`{OvuB{mqvXjobp9#5y6jH*Fva1^Jk~*$N&!-9lEJDZtJz)1Xw9^<*yQqgJ&8oULpjxy(zS"
    "8bP3~vV;6vR*2abr$hUYGi2@Se6|;x^<;XwNc6gVw8?h?FU=luZ*3mlD4zkux0l>!{I!Dp4*}l)8M%Kd4<FwT24%mGBuFtAO)Wy8"
    "v*0s1@--KG^H@hT=^Hu9{5@xvByd#wOGLgo_~czGSSzx8C!h-VKF|cdOj(w`y$ZiR)PP721(`C#g7U?Quv<}1=I~z?t~)ashF%^Z"
    "duULNvvt%VZQ>x=622O}0>^@nXFpl|(rP4KBO!jrSBl4~apYPBFp7CYTQ#e(O>q>+7xvK2Hq~gkUl~rUxJ(DXtHL+KMuK+IaT;}^"
    "3O`rK!<J7+=?$pD`wBzgv(a9<>SPrf$PI&u{u`*xxhkBVGy(>WUrw*mD%6OQgPcE$sKK==yt(}^IrXW4t{hN}lHLJOu_B$OZ?3{0"
    "yS|aW!~p7Xs0t7MV^|Ber-OD?;nI`8$(ANPdapmb&w;<>o7E(G>2?*a{nZ}=4TsX_0>(#g2f<j`8-BzEDc<+!2Qn`izaU?V5qAbb"
    ">FxFWjGIzi%5>l*s~mm|<4}VgO0cz`Dql24ien}#fX43g9Y5Gicj)>^XgulI@&B3b#Gna~o}25S_Cbtt!tv0x=Hik4K1`Q3Ooo2l"
    "lJ-}5VhoXL!K|*ug3@auyuEe`*e@8yxv^f*Tti(Dr-?c3Y7sim*MSRt%eek*pU8F(L(tW2<W?RNVxY_fR8Ak^X2%IJ<DMnh)*awx"
    "Nh<N#3tO<5xtUwb_L$F{#=)M~JzQg11*RXggPmEuocH}QCaxTy_rDRunspmiv7Sld%2A|fG27F34Z$&bGFi;_`uQ9ZfYty@V&Pwk"
    "D$i`-&)DhY&Vgb)Ho*ptbqA8BxMGyDxn|jk*(8Q_ha&zW{Cy-Qy>UfYa-0KC&$%RXTM<qiZVi_MYRNIy!TXkO0mFa)kE833r~3c?"
    "$lkjmB$8}d#eKid(N>Wb(bCY~%ii3D_FgKbsiD$xU$>;vCuu9~MUzrSMfE%1-+%XUANO7tuk$+RJkRs_JUiH`vvDX7=nEqk>}9#-"
    "lwW8TJg)2ndo^w)YPb4<X5BFs{U8q2dXeVng@Tp+T8WSC0zs?o3Y#WgiP8uL?^jl`l$tp7&l&`m4pg(yvn#RB&0#R+&<mEMx)M)y"
    "BW>4;7cAq!3e=As4QJe%STMzrkH#pde9*>J2@mWZ836^>|CmbDGIaVL1<^ZHVLj<MYD1>LP^J!JY6%<fIU9B*7%HDw<lv$8J;C6t"
    "fztD14(k1}2ai?8O4R}}dIZ_RtOjl6iXCFy|Fjz{KBl6)ykCqOYTaRRT01Yy5aZZbE4YyGhcEDv;Mk{TFgl=#w;U4V`dTxX*!+<<"
    "(tGoa_2JL**WBDejO(PjP+wfb@7&A5ZryZXU`Zvv`7DQeVRhKuMBX6u{I_sbc;4kG&uh)WS(GC#&)dn1O~m-%tQsuby_)Y!6{B!i"
    "3+`6r@L^VB{MAVdto$<h+hJl<*Za*bjh@1H&k!RYssan=4B=Zxh%wXg59|1jJTQ&&*YQSXd(DAYP|Y^8?klTOH{#<1a<HPIgDGq^"
    "_yLNe97}a5{rpO?C^QFyzpKOSb^8?Nf3nf>_CNNkVyR-@mTVk<r4zjG9IQBcj&hBk4m|1KToy`s+^@zM){NOxmNP6Hb2ZIjL+8;K"
    "CdN@+x6BMC7l=f0gqd6#)D;{p7K#qqXJPM+HjrZPDO&t16Hn}QfT|1H!U&3^1B&j@dBh??Al^lwO%Et29wo#QC){<cD@0k$5`-fe"
    "*nHCy<fE4eKS&Swfw&)wW~B=b@#&}{_Jf@%Il@um;(oZ<7aVSG6AFnN?@M}5X;`@sbRiWBh+kb>_DFb19EM1}U?|mZ7h)olG5T45"
    "7*lA)R*X!>4Oaw6In$dh>Y9XgCjFuOKOc6|C<zCk2nLsrVNF{Sv4aOfd%q~=d?OwQZS#i)!$mBxdjk5dp&n{R27A<yfD7ChTsgUl"
    "1zRWJ_?95jysu~aCJAW0(+9?ix3iCpak%h+7YvCwz;evuu`$LMqz6v0P^#+;iF4lhObHu6{nxDX{vb9v&+a~mN4q!y&R@93Dh|Y<"
    "ktTyR!d=$y)=Io~A7OX#L$>@+9RATB3W>cQvk^n$unT!6lsSK7F}<lTTNnx+P9NC?gO%8uW;!O%ezWr-q<KF(1}=zxvBz!8vCouA"
    "5dBC6vidE@*hkZ#bdV+p$Cl#iEz@9snUPX^Rt_%NL^{XwCd%{9Vw5!Xgjdgvl|J1i*yVE%m~=&7c`8hT?Umgi{E51<sEY)>1Z#+!"
    "_LEPsmSAB+HyB#*jlVaRU_@zGC~9fqWwRxixYZa^T<f@^T8w9cOkw7=*ZlcIF?QXo1!b<ayvuYk{_xg>oqohII3-3a9jZ9{UF7_N"
    "7`y$~3EB=E<H^s(c=fajuuZ%9qGMv5yy*|?|70CsxRCPQhJUQnk{sT~#n>-H9TK-M<yWtXaiL)+_;hR@_Zlxo%K=Sn!kE$gKIOiS"
    "rY|g}-G?vN6BDngg~crH!I$07!A-88*xc)u{KbPDYzS#%<<q_@?k48ouCzAxX5tma_N_TM?VKuP?<!O*3Clr)3JthhJxNh9onlS9"
    "6XeIVl?|f&Rkv6jv@dKg(^&LBj7}Rinb%*`am~i0Z~DOg4iI@=Al$pkh~_EJMJa^an|qtXL{oFYMLP>`sae6Z8>)f{&0dqgc83cO"
    "Pl~SY&crP802yN&Bp67^U&Y)B{&;K`%;Ga~dsip$oP1O$d6t2%5?w$&?SOE~gD{8fUJ&(brx4wijy;a}L&}d8LSbq;>JcXJIPZku"
    "y&xSuTLPiW*{6b2Z5l3*4TMc)jl#C`sTh;YK%+>L`CU%I#}8@lGuo0Z*q4l&4ujww)oD*|C*wiVbkq&#&wBPx!XCj0yF!PvciKtV"
    "cG3^@onqKr$3#3y{9EzHIM(?u>5}&O!t)*3Y|M=W>^ieAjIvtG3a2Jw-b)d^eg|{umVnV-{UG(q4mLPC0Xw|Bpf$gU&H6{&h6C=f"
    "`Pf-DdrCaseC`g%Efh>lI;P)FzA$`dB{N(RkLHW}!Wp~kEL|@F)qf&PXsc!86>(_$LjVo87c8%H9DbZM5bpka!+tD}Lyfh=;fZcN"
    "TedO|V`%PUdjAJ|(RC%NEguE3=|7lz%L*(T77eLg)u8eIa&%uB1&Z++;7Zs+pWI0>RYwO-omhsliPK^9I1^>Rk{ler%?+Bj>MHx*"
    "%E6K?&X74yS9xx`7)$LPNK-(wp0g6HKTrIbSZ$@_PYDjvw+5@Ps>+m938wGv44YmwbG0%FE?Qs#+YLYQS&<SPGTH(b-u}SfOq5XV"
    "tq)iE6CO`zdv}dKMEl?8^S_C4K&2+MZMw!&BE>lIxDHIsKg+WN#Tc+(8z%V_^GdlG-!^E#@9gco+d(njl+fen8+jJRZ|C7EP;ZyV"
    "f6(VV?E8~-&QIYFK8evGy_t>PIFnE5B*EG7jcm7kBoE#y#?8B$+0CjzzIc%s^>%z_Q%>6O=aa;^O{J9;=xOi)-NYy|`^r*Bs&N<~"
    "#;tq)vf9;8NYNw4_D$+AZp>Ll+q)bL?W+S1T~{e`b8~RiUOo7$Hb60PLJqb)(uSw2H5K=${|Z@QKzHEK^98lpxOc5Clx)ou&0d_1"
    "JJuRPpv4Q(sLt8=v&{@b4YdTd=UHf`VFd?!xeNYBvM^`19rPM35>)>;!#dLg=2e;r+m4Wr1o7_D)iQ<2Td3a4afOXTj|<aRXX5OE"
    "r1$x`Q#etVfvZJ*;JZ$uFn1$ypDz1D4kQb6iThOUBf!YHyM;G2Kbkm<v>|X^7~+slcz7@zl&P~BjcK^?xd?W6nlQc1shDabf+jy3"
    "c0DfzmlAfZ*5S#VrYEDz%RzAMi-;}Apg5XE9EPwFEOdM_@wEcrL2(SLj7`Fp-F+Y}Wid-slIO`OPk41x#ySYQ3)Av}-{Us0eT3;P"
    "|LqUUP8G5pQHfYn-VYk<53thdRO9vbg~HYYtZGgIVvs95n|6l%cP|0gY4(Aw-dC8E>b=ctykSzMk}bWJfU`)e^``h9v;P{81#yA!"
    "Q1>32`#2uYU+oXmD&DY4im&-EgJGKE7j|()9G+f6SoisFtQX}nhrm!c!@jYD&V<9KMZn6QDsb9&B{68mk;d~68%>W_&z%fglU1Rf"
    "xJh0u)8XA=O{kYI$6kGB!Tt~<<xpcWh6$dek1$jkED&Qxj0@P-XegWMj2-;p1Zo<ZO4n`@d~(hnwl{QAuBwq>n5rGfWva?zCdC%-"
    "u5i)5ov)lA#bLUppf|OV_h^!!{YE2D8}y1>=Sfiav=IbWKH>ev61<YF1G}%?<+paz&(bx7^STv$8pY1fbtbUh{R|g%5##-JMsW4R"
    "K7Kn<j0MMZVd$X(UOZTW|J~4l`FnEt7f*_dNDc5@lfi?6=x3>_z$r-*FW)LbH{TzuIy{1hX-n{cRR`m9LixN7`uv}tnX!dGze{<o"
    "LA{MRJhmduf*9B6H8Yd%27E{r#p$aK_RZv}B9T%2u5M)=1*MASe>u2{wKG%GEsCL3TW+xL1c__Y6;BBdnfZe1#{Ho9^ppCd=X%h&"
    "Q+nB@gd9Bmje4=v$z|<?H@b8+fv}y@i!<*K<}a9m%Am#Pe-6pUim=XLy51<LmgZAsTDIW6XQZfmbr!DrXAeJux#$;pusm*Yf})XA"
    "g)2R?(DOns`r8Hz<H>`??}sN;nl2Zfl3vM<yrc}Zs)YYoCQkb31%u995t3x&yAt6?bNSW6=eHT?5-fr}n&rYMgADv!76^w8UJC&W"
    "Ntg662;MB!U~fs!Xxa>Ls6(HX$E4y#;uvf_*qt%bP?T2&gY8Ym$_TIX(jE+Z)`qc>Cz5bwzk#s-STsA`l8Dht216e#V^h-;Q7^PF"
    "*uF_-5xtXe;e1bU*_g*(kgwfae|O-dWj<1ph!=l(!@Nto*|*(EXmBL}{OgXekQ(yAv+#wGZ%3K)^+cTE<qAO`F0jq^iC8ev6>hA("
    "&U(}1gUz1ME$AkjOFG<NoBiM;-el3ni737aAbI|n1s_Ym|HcCBF@3_ijZMI*_lCgz<FA>~HJbl^8xBhiT39sIa_{qp!H&KiY=>PO"
    "ZX&OYMe^Tljc*)gXGTHHA$1seWd*7kM8QJ?El^8Yfo>&Jpq{W-kMk>V&yQK~-q2i`FkFmNyLiGLKV9XS(PA8S&>aR*jPxuK<BAUA"
    "4_E%<z3+=r8RP`+y;PJbizV2J`kkKxfAi&y5<C)Y4T~l=^Sp2=W|?&coptZI);=kIzGX!GpI7`%PbnsS(ubJv$9!ii)mleQz;^Ui"
    "?x!X}2+#$S=jVB7nHYDv=|VqgG2cx1Lu@}|NIkrhJafbt^UMfVPu##c<*Zpby72VEdfxrG1oe{DL1Vp)Kc!e6_wg^Yk<H=97fG-r"
    "Mg^8;PUij3NHG6!6FUI{Ul1a}-CNq&v7tWv`(H7-rqr`718n%XJ@oiXJ!_R{@Ix=e*!uM=^+8`03+OdVv^&`B>Gu@Z%f%RZN)>k7"
    "XDhByzjnH=gDto$D3S=5h;mbfYU|f!gL;T@)i4dHdVHtst*RIojMW3<SF?jWHxf>mr3cqkhl$#I<)GmMBRKDJQ*@NDzR4jLuzvVi"
    "(U6&h(T%l+r01(e>+-Wvx~vDJKf5XF>XVH&f-}q*s4eW7orP<@yTbJy*@8U~cWAmB6jf~!oXAh|$5L-_Da{ewi7UAKkRMz$eI%$6"
    "r*7(Ge{j=N3e6`n&^a^+E@l)7lV*_j*Qj7{F#jkVZ%#+w`2hEA>V#gN>8SsE5EQ$1Vv2=nIAi)C_<GWb6^%^A(qTivxw8+OK|Xj3"
    "%*ZEX#$Z;`kc?-Z0hrszupGN&^qtoaTIMWb!h<B7HP9a-f99}*UlVb?tuG9WTg&#RC!uqU2fP@&i-{`}@iU#PQtcwP*P66TtGwaf"
    "#1fWnl#EK!LoIk!!oCD0<B9t&F#6*~W_~salQw%o&Q%4w8<m71*ZjayxXP*{DDG5)z+>+%mbNMh?@U0@I(LuBssDOrItUh@f5{>b"
    "B;c3A0pRxPGaLOm9zC>%z!=#lR=znN-yIqSV&fld{@{2V^<^CNe53}=ZgIFXaSZhB&;t9{D{-ze67)an0c=@;fmRb>#4ZC!IJq1H"
    "pG<|--^`WyO=5gSTAO{UrpgFI2_7qQh5?Ipl{$2{TMi&zC~2`jPL|-|TaHi?)yfC&l;Fa<j-cM{3zuAzVAD1`fc_1<wp4;<E3II%"
    "#Yg_vM2a&^ETH+`3*L7D<qKVNC=GhZN9>cJ=2SySD!I<fDVJT?VFYW+F7V$yCHUou0XQ5f=4oFEm$<6~NA~RG>b4RbsiF_bFY|bv"
    "n*^h|A-ro$=Pi!(-Z~xdJD$J?P_F46t_}@rCvw}z5`68X3QB_!T<wqqMRWc!p9{f!#{miQ{-4>CG$$SrCBdO<zp<5ry6`soy_8>G"
    "v+nPHE3Q!<{B`vmbKiJZarr6X5@VZKpxa5s(pzFo+VPv+y}nyvR3S#q2kJ0AEKc$29K{#SXZ5{o73q{8KkMjIPH`wpa}}fg9UX|&"
    "*j}ddJ_j?E#?a;Kn|=jVIk@*T^*Gft1BW~2pyja6a7h{~TIE79Mf}yXI(>vqgg<<YwgKN*dm%R{n`)jOP`P8cFqC?wylp*UmQg?9"
    "GwCL*9X-Ho!Ze|g@CPsQdCNb$Qh3#ri6*gqAx*tN_>@i>^Rz&?alb)GB%SO@MG)+@ekq*DB#f>dp_6mDV9wKV@1;SoPWDsKBHjJU"
    "jsY<9ygqYtO~<1+6c!zJVr%2mu;TVmz@T8}FeMc~J`aX{_QTk)w<)*+0^vdLMXW=agc=6Kf0L%Mzde%hT}cqk`H{gi33Esp<qMTd"
    "rR-*9GENBbfbX}qumh3*d+ZASWku`=c}RXZ=nAdRPO!GD6s(T+hV-b5%uj_re~|}FJ#&Q#+mkT9$OTUBxyI}glTb6<8`{FE*vk(|"
    "$RGe(a~`sB$%*LSKL~Pu5hhSUUMpMrL&vn|Oy4UB#eN~+82*+G_)WE+Pbk2MW;V(^0rN9Mf%WWQ%@OgWe+-9^!N1wZ*;M1TO`!Tv"
    "4Mq)(!>le-;L1}?2->?6KX023QO!nRxS!@kBS?ebYplFSz5JKPKG5!?r(E-o?s+Xw*wRA!opcEnYq-E9H8tfXD=C(5A&mfZaMSKm"
    "T-0g@4;MD`>XlOTs_q6$wLkG?X;L)()*0G<zvhvbCAhb?3#1%+!ejNMxbBKE?7VY_pPeVce=-wzHm{0XpOawSI~_<nSjNqwB^X<z"
    "31+8`@_*YUI4?vOR@^J#VcR4)*TM+?25;m6bp9(2>O$S%O#VwL!JI;EsCYb&2YjaZ8m9@WgO>4^f)pd%f3iJZqqz1MDeA5H#k5NM"
    "^7HQ~#|>;}I+?CKlHyC-<`ZktHslTk5|rI+VDcN^6d5uJ%`4xs2NTI!<D?iLjeO5;+}@*@8Ab6TZ(@@&lNC#@P~Mr;!Aus7QyA5W"
    "G1^rf4u-oas=Xw5)lU~v3W~}SUW)O~2m?4>*T1ZR@W87Jh<otplxWu@nw@nwf+7Fai>#9g->Wf$>N$48Px~CYi@Lz##ZN^t_Z)Ou"
    "*B!Qun=M$<9QH!GJzVM|5gJBjqw=I9)Sg@?=$+2Or6-+X?ByLoMp_n5s&<F%m1~7Q`B~U6J^;QYmk9;r-5NKJbm-kK2>%FM@Sz@m"
    "dB8<sD`9l1mj{3`uNJmVBaBWM3UPgY33U`lgB!?yPi(=i9wU9$ON8thHf+hMG<-5L7@A{-vQ_cqMQkzz%)KTu)4&w0HyQ{#*UV?R"
    "<h6BSiU^8VNLc5RBs}<quIaGVtRo`{owEF4&!#o(<ujVY{zux|qZ^prlN3C7$px}AidgcF6ui_<-dSf)GZ*qk?xg7kF;SOUE2N@c"
    "H>%AND_GY%)LT`NUb6fS^SYLZp@bV$mOo(Y<|d-YbYHO5e#A`YB%#-|zOXaz6|0<+h<{ZD7@P8uB}Y?^iy8=hEE`zgz(lMq8wN>>"
    "8<;kEt+a5`_Z79Um+KNR>dH7sUaJPLmdE3egX7_Apc;HkiASCJQy^-FF3cTAoY+rOpsS4`WRbVtgx56dQ8826E|s7V<PE)Q4V8s!"
    "C8$5a6}*gfl+iCFxU$$8tUGBb^#i5ofDX`QP$%W0n^K%R&xYm&9emqwDSlOUflE$bd7QZnrPXF|WbPY2YmF48ly|E7J>n<mY>z0g"
    "0MXED?$cL_#~KabMB61k<Cp}!FX=(Wy)wSmQHq!CHQ`U_LEinM1ke3b2Q80XyvSIJRW*7re(Nf(+bls}xgq!r%j3{niph?ep#C+J"
    "uS=HVIX4yPo4$m%-k0K@s1`OuIhnUCpzk*QD_fD!pS!zDF`%`9U9)rKX9(+P_5aPjl$&t#d<pI={l(1NzAKKUNpSzbW;RG&p$MSo"
    "eIh=ws|C4=rr%;z^!UtFo}og2G1abPzq4(Rf0iYS#b`c41v*y!EPF~h^iHrkyqNa%VkG6SS7Dl9($!Pcnfkb4hjiieuh*j1I59fC"
    "H3FGV7a>DOj9Q<}V0zphQQMsy?AmAr?|zIF@{Z?_wxS!T$!SPJnBD?aCor4oCuC4Q(%R+>hZm#>ezDoanREsAAXiwcMsw|^J}`Yc"
    "7oukpciqh!^iMw$3dUq%d4M0h+4oJjQksdksHU1<_f{B19Mo`?{t%_{T)3i}i5gQwAo_+1>o-3Ghb|lj-*kJh_i5?qP&^oFdwR2H"
    ")CYyVN9bPc%go28p}|A}j5bHIpLbHQ;DP|!Q{!1oZ8EC$BW?b2IUCX`1>O4r6g6yQ3*IN;IRg>=^V-hNPfJEq(zfR{>|m{g;~kkr"
    "{=kR#v7?r0Xm-mP{+>R?93xWEU&je9=5ux@It6bJa0XugA5%Y(jDHh)!>T9MtlQ>foI1w~G`c@$)g~017rfxnxz|kXaU$l11VF;R"
    "XKc>iBz*r~1Xo6WVs)vBn6Ze#l9unRQ%eH!szESp>Th;pVgf!n9s;Yzs)12sJkALi2@kt#z&)pUeE(n!YzomNomd>Y<dU|I_+DdO"
    "<I#BU47jS$1Eo9;SB;$w0ke#i72^m)Tj>YaKNu>#J0v*yoIALF(pPSuF2&#EceFl2OBwQBimf*sfd3-zsWK@Rx7$PihfO@(S%$k("
    "tf5&^&sCPou+6^<Oxf_1KkFmIoxRP$D&;<p+APH;Ra2Pt`x^H<EkT`mW?*A<g?|_z#iR9x@MPRMzBr!ZF;5RF-xl)=sZ#t_tpO`f"
    "Z|99>Qf#J}3c9+M_e_!Ejb*yP3sZO#<(DqEDW)vq`FoiZZ6h?`QrCst_LCGxpZv!X{m1jDo-%y?qKUoV?!#RVO7YX0W|sNMj=xHj"
    ";!mxwtg>34@3WAi$Kn?D>)Qv#bc)l3YrnHV=PQasQVHIC(aIk3b&5fBw-nYjvpVfyg$mW5E%D!3;m(?}9_|v1ll*1_JDt9mYCsr8"
    "s47fRt|_yRp<H=M8|0V6MHUoy8t%H_`fEy1<WIuPpP0cDD<4sMs2GdRSVHH?PQoI}YuB!Jg=X0oQOOsY^FHnl?%$UQBMCn*TWb$c"
    "nkjT8KEufpCop)rOz>#W#?_NOz<1v<VJ2xP^6lMW?v=a3?Uz{?)#3$Nf#(F(<HRi|-@@6q&kKi%-y0-iuy&~$vm+fx#7=||KUMaW"
    "=B@pY4}?V;`fLbsx%0-7zsGSqR<Jo8N0V=-UPKVP)rGuYW`w}}JE833-Zb2>Y!JjRoW}|#q~Zqi{;(o$K0CNBg?z>W;Mn2}R$r8i"
    "U&&K(Pq)?Vcp-Uuzvv6g#D&a8F9p+!13<_2FzZR4FwQD{;KJdPEM7>%)@`n!*7-bJQc2z~*Ls4q`YJoSfPBfsPH;+kiybo|+)wNV"
    "qSH0Z!7mw~7rTI({{zB+lJT}a`5s%>voH&Kew!~$8~&N;tw_RKK7nv#<vX@KI|-lf>JL9WJ~FTPBwQvB0kelKY|!FFyk!;&A13}`"
    "UVlh`5f}zvo^^s7qZ4qc$yi8Tpbr<D<Ir7;yx?*SVR!vX{O|k($hI+oZS&($TYEO-57AZTJ4kRHd9E70(o!~#rkPGpFSwMeq5Seo"
    "f|E#_{Nb9KvihtPbHDclhnK3#^V4K#lxPpXh%bHUi4<QRu>-A&dj2&|iuwC(z#{!AHy$g+@ONEcPHr{Nqx!1PWJ|c^QpFV-RHvP="
    "gvwcEyqNIq8%CyJ{p}QA_fmp0`WwK1tp|B9#hT+=Jy_p=H&=Tp#YVz8EJm;AE?cFz*Haxjtq^mlq`0ovg7g<t`S&SO9Q9cTv>Ybz"
    "eG(~NP*;W3X(2p8Pli?X?d(Yxf#(d75#~nmV$hj~K9u5Bt!B2kSdXhMk>W*~8I{cXqlo!Oc_&f@j5Hr97UW8B@d*_eGxf0Ie6R%f"
    ">{S7q#t8~{!XkE${l`KN87p2qkYLS_4i?>Y_Qe7BCFq!>0y)B`AQ!m=XT@m3oz`g=PbWxF`pFQ|swzZ*y{HyFVg%JMItfP`2}|UZ"
    "mzOOPWo!{+NlzQ--t&d1YNr^#O>=+%X)i&nN%i5DUeGLACp@H?waesQAhRtN9Em$LO5PhPrd0@%)7kiay*tdfcv484nvEJd0r2zo"
    "H(}AyEc|_haN`HxgnOi+uul`fdh$JC+%@txX&wl&V`^+Tae-br4}}L!rtBzr1Z^Pyz5R{mEQNd+epL>Fu0sVjhcxmXLJ0Vo4`oF!"
    ")379vf%}aJHdH?iTh0VRp;`tjc$0!+@`3qnox{|prr@XX<X^XG1M{WYO#Mp`EG;f%YUD+>Bq|W%6H3@Zii?qh{9)tfi_B(P8isxG"
    "gv&oKv$l#foM`U?+oxAEt=Kda-E@S^<_E0vjTBr<c<)@xS~g}u3hvwO1}px1$@Wf6#xF<dy`@iCuT8{@7}*cTWWHgG4ku$&GlRMD"
    "RA*B!mRrnVyK5_3(?~VmoB>et{RbN!o`m0aheKFN8#8;Eh+b<Vpf>Rzi+z@WCPmSZ?Wql0e-Z9o9Suh;4Iq+udMlnxfiBxk!P6xU"
    "hm=hPk)fe7PECrnu>r6E)s<(dj+#H&7vB4-C@*A5&_e7E#<7369@R)4HBO-6_lsMNm*LqN4zNDDg}2?7;Y@W~@~*GrA(}GOkF){L"
    "KTr8(s?GYXwt?!(2mH_$36lF9Ov}E)#}oI!e|%TClwHc5372@-Vga{C6!TpaM{PTd;r+ZqE>J$IB8*P)W*c8du_M~04_5uw@yCJ;"
    "%O7jP=hYIv%|M0=KB~c^+&TQ!7b&J|X~K!4L%1>3mH~P+Gg1rU7E7ggzn2R6iTU#Ry<|A6=r@}_x+mZ5D#MGxA6cTECRc7GOvAW="
    "{my!;P+XJZ*)b|$Qe3WR1}SdZuLA4ttXEikkzlf&3dBX_D%6uD_~(QMc$Zl#-rS(yrBxjywIj>2MoAHf!*ld$vgk#BDTZy;fIBP7"
    "L{iGLZq|CRWWI~Y@0J9c`<TIjg<hgf5fZ#kyn+w6uZZ5$+*z+5ai@322y(&_tygx3k%4|fN4*&T892ky?HR(Ge3~7vbA!#@HVch3"
    "gL{A769$Tp33EHL@$z>cFbsMxl+DjZ(MVq~GW{cT8J&&Y>iR+9&MHCuZWewz7z|x{Toq=AXW`maq-D#l6ABA6aj`5E{*5tVHl&Y8"
    "wF-wMa~HN}I{6qs9}XJ*J=nO)bR3~enwqo-c9XnZLUPHs?b8%iJ}M2XiHA^oY98C>M!bcJ0Px(C%jS_s->RW~p~-nG)3Hv)=xe^<"
    "rCrEeYtrybEqN1pm9Q}K=kIvs4_IB!z$qO&Tl&Jx>gy~fEe#jH_Jsc7)y#Qc8rG6~v~x)fD=kRHj0QItxB4~P6_<j0ecfR1p9gI5"
    "!4$OGPyWM$>zP@23iUPq5LNVrRXs??vF^kjUHgfxicZE)cL&0bmp@o{($#9M41uHR|CrkPL_F;>6i!1YxS5rRuDeIUi)?kmQxY+="
    "H4+B@R)^J<3Fu6II}Kfke|an(FP)o6`vS~h=UD2AGGf3-X{-#6m14?M^3@-&t6b+LMepn0@M@)s66pC_?g8I=wep@+I~8<tg$u90"
    "^YJ63c<QYKxPJM>GYe&C{=ptBs$TP1T!z;UTEne3kNM(yDOTHB!<#>McuS-d|E5^MrMPl_v{iyheqG_w@zeZ%71f8`N&C}Q#E<Q!"
    "e&K~BT({rC{XSCP?P3nC|2FWCRLh<3Y6SLydEBv!49{)ShYo2LADt(|$;q0amA0Js$dTcv396v~a4aA7LW<fd>Tm|VxQt?<w!RaX"
    "m^<*u5{d=-n?+c4=ljmcaBc7J%;l;ESEYQkx#|OZ*!D#6c01u7Yd^4gua7Bg?4|g<tbwJe?ND6JmtydEiYd*likE$)=)O)9MygI!"
    "tgj%9;*>7D(5x)8{3=0Xu`XCeI|RiBNby-$eRx!%E~G4$;`R%KSAVw^N(eLe>~9KQThEHF=}U2Sr>;=2I!NeBv9tBK6-4Y53A*bg"
    "nDUVN%GqKehUQj}hxLND9S4QAd&SsCqbIoTz9KxNc~eZBD{R{JSjY;@!K9_0;Pl^5;pFpd>|*2xJG$H!LN8>KKZyuJhO`Jn+Ou#f"
    "-NTbAT7(AjKhdPw&7pPwgzKcqdOtM`Zsu7r>48jK^D-P__c^nl*GUIqHV76(y0d+RX|H?;;G!GI{^#Q@R0?pwd@-9ub5*P4fw1|0"
    "It!-VF0-#7SiQ<%y_Dn)yUPdm1g>KHR;S{M`<}2wXCIRgr%ram3&P%?WQF8E_GYjrY~G?^Av9yEDDi;!wKrLOTsofF;|<TX@3Z#z"
    "X=qdA3C~@gvhI#)c&4xy<PEN4)9EwAM!Le&h&RltH3e^V_l6_UHLO~ef^p=pb;SJ*dr4kiUf&rE>-2+p)FtEls{kI>?M%-x8K?9d"
    "0L2BJKs=rDj_DBCBiDrLzqC8aY6R)dbf6_a0d*p2H^Fm#IF*)wMV}&}nd-L@G`H=3YC5>2na~W0Fob=v&_tS@=n5&G`RN1I2lSO="
    "RAl&KpF1dmwUu+POL6x+SGW}Lhp#(B{SNu>xtM+9L+DH%|K$Xo4%GAbPBP3gae(t@p76*S6g#fnL1*X#ek)yuhKIXA<f3Z+y-<p8"
    "A6USN$g8}F?&RJ5&B3&$lq)r)_`HB>wn<0$<>6ACH{2W^T-(kQsisQbY6dkedAyS9z#|Ffa6L1JkJ&3l-#SBBu_>N6e~@Cs5k0uL"
    "e*wRmFT>V!O&DF<pG&CE@*J)S;q!v|%UsGet#rqHu;CI98P?gW!AyNke$7vYW>Zzc%kq!nkckY{9NJiu;*w&$z6`q#Y-QK0)+^5b"
    "M=?VA=wjteMH1!EivwF&+mLCB@s!Ih=BPnKY>c98ofO}1(S<Y*6GhZe>a*;PAv)iwY@?+VjbEEWuuYyQk-q<mT_%LX3>VTfq<BS2"
    "JlL&cgbEcYuA<&B*-cH@OSR(6-FDDj$Q2l2HKmlV11on35mYmGa&Us4-LDCz)LTtRa)PjKUj@%(;zf+=4RbA8g{j1e9T)Bi2Hl<s"
    "*Ei+hZFQQnU-~MP{>{cuJppcdJ`>(hU3VX-PV4bn`1F%%xwxU=b=Z{MTb6~9n?hhiq6;gur1-iL29v`ASR3&Zwr>rC%-_I{({7gm"
    "gsnw{j-=X#eD-nywg=5%vE*;rp1|OzMmEc(Soq_K@NE5RrXcUW3+n{<`F9<gF)IyM2Ka)z?haP^C=G+0-N1GGVP-!o9XFLZ!>gAU"
    "*(wR`g~{y&T9>b}WYQ%)T;c+bxp&#+DAM|kaD}@AsAt(lwH)aICtQEcBG0Gcrhy(Hyn4z?Kc%9_$UgAQt%i+xo{DFww<=js%WzyO"
    "zBm;O7i-C*BQ^z%Rt$#i2b<WLwq&&9L*UntzwAlZWUPoA0WM!OU?5@O#XZ8HBwiN^b|s>j6M3*RUAQ)iusAjao)nwHQinwRv||zs"
    "dT0STq{VQ#H4TynX(^uvNm2csFH}>_mPxU&>a82d?X{GT<761<?@S&zzqx3-4CB0d!?WFuT=R+)-z;^7;TH9L+dPVk!#&~ft7rTc"
    "#n%aYdzjvKhZl87apzuJh#y_WZ&KfJwz4a{x^tbc)sW%g&L)t*>LOphONz1gP2j`1V!n~$(bvZaPAn?muc#*6ciR{SZ(YsrJIK($"
    "%nY_H&)|jhIXKk}#DVj;&vD9?CB`uFdlawGmZ8-)U07Q*o{MkEFqZf;S`R#U8^z8#V-48l)SDOlC&Q?v|5)`kLw?|t4DBm^vT1w2"
    "DrVi6(awuTcIVv%h0anLPS^Uxn*3KQ`q1}0G5!~M?|CaqTPXJtPO~;tR}n#ZFhl<jo8zXdXvreHLZ$(xd%KsNDy7$C>5_Kdr!4lJ"
    "6no^GgI-}DQD(6e54m-L*%NJr`wdd+SuDXt(@wa1jB=Tk4XipgSumvBG%mmqLRS?EDRhU_C~cth%XLAE>StvJd7Hd>Ajl}MA^E`1"
    "EWII|GNM^qtOrcoQX~8ep}H=@7d*Hw+h0UnAmSS*9x!1`ymRm|c}`j-7_(ui**JCwKx%+Cb0E#p-<UzLdX6EBChgvt2f^TCV9oBG"
    "qS?@nq0m}^Y&G>k)3*<Usuhe)B43v$I{o2P{6LoVKVO$qLGa(v(ae?nV?)wOi)x<0YRT*Vi+vy%NOPGz?Q=Qd*AG(2yXG~;m#tYp"
    "I5B1?t20PP_|XT}zC6lakzd)s*B-E6^*nPiC6A^TE)bM`jeR8!-VZJEFH(QVI!#Q+Ss{*~Ir0r#MY}DMU%J5akOt<WmyT=CyFtpP"
    "PptFVRLnZ<1!ijR*m~kW<QkLCXm1_!qWyqJ%S13E@*}%EAQgv;2E($dFHBiP*kEud?AB>!ABj`6-zFUPJFCEM@@3si`+%<R*MK7f"
    "lhC$30$%7C!C8+aJa0E1?))%>UA4r)^PB-|PMAXkCZfV?7BuzIRNkFP_0`NkaHn|jrCKX|jvs6utEQ~nC&S0fJ>aH>s`B>(8IGlX"
    "r-OEjG%l85OSfJiXusvQ)N9NnO_oM$EuTSscTu1dxEbH&R)mASQ|%6tph`Z1?%uLpRxq{YG7nUhVPs%uShui@Th5c=+aZKo>^#on"
    "BV>5`u^ycIvWwq}p?HbZrAl-IFIz7|mzjnjZO`FhyJa|1Yz$ek3%F*641EerU~Tv)et_`3x!(+7lVdQSvPy<aXY0ZpJ2(E`K#slU"
    "XhEuBXYTS{hFjXz;e)hYVfT{mgdZw!GqO_Au#sZtR6D!%p-3^^P>yOP-`Ez<nF^09^!v_fVf)Rz6}_mBTM$d!Ikn(2%{D2{zpDbf"
    "?mj7dJWhrsG=EP0*;v*ZK#vJC>{5=RQ51K5?Tuhy(InBwcp0izT0&lsuHZjKh7DQWU}Z>-aENmHlKxiEurgE7rd*lo>HvXhX9R)j"
    "#(~6XSF33x!an8q^WC9Sx*8k1it<srBh)QbWeL+IIQpqOJld(vR;?y}(ZfFQ=VhB9BHs9wz#!-t_)l;?N1Bd}!SGO}6LTl+Ud59k"
    "u((%;FpTuGE~Hy|5opi+$Rp_0j)5Srux3IPc?*9=X!`5QUQEu!y@dnegh?1%|1txU{|kZTh2g9xd5(GS><@>Wr?DjRs~ohtA1sfZ"
    "%hdd-?lSWQvsMZFL%xnr+<c(w>v}eg@<>oIdE>u1z@{}3?p@*!?Pt%h0kogO{Jt+VJh;lj$vbGwH`=$grJBw7la3R%lfU1c`>c#~"
    "e+>s5;oyk3%!GXY;i3~PcC2R$$hY>#U@xeA@|mUUr(<Q9546jg*i_0pd*Awj#<NCN)|P^%0|SB6^CN7@t9A$JOiMc0u)Qg?D=h@N"
    "P5#6F29eI<WH_9zYG*7e8O!}6L6bNl-(r&RL&!u}N?1W2aTR(jnFxk+O(E$>5{`T}5!f?Rut`b6+t+7;L6y34l&K6qX7z*8lYjZ="
    "SyJr3%@6V%J9w3`41XT-gr<{iy!0K#%M(}d`0|4{ddkTw-jViqyyNDZWtieaUTwE)_yg*}KU7goKIbOCe@cp_4vw(Y{t6FuAg<0q"
    ";=e^-;EBtq_8Zy-a;#7Db0Qf!?6ZXMeMflaRT=7zFoFAFd%3%V9DlCVgH>xc@WFJ>%a&+^|34|;ctM65A$o8ZlXx`sJFk=VA)tLS"
    "KV423g{3ZZ^$Mk!m81JVHCVqv;C5r=Xx;vYmEY{a>oer!$JN62IB4?$Gv)YW*bkOpdS7vFyd3{!(>$nctzzDEIUe8mn?2dLNwH|E"
    "3@^-3gZKv%70ttC*c_w@t36JYMb*eK{e}t@nRi^+M6qAIRts==bQ%7pc=RLxkoVU_+4LITXb3--4iSpdWH|qTDcrjrD^#n=F?xy>"
    "L_Iny45IfYE$IS1`X~jx>oV-PN}g{fjl!$0GTh+a17^Kz6kJYAaV*s~m;N(j4HQRL_w@u{T?@9`REqww?r`XLH}-Kn&3xYw|I?%!"
    "OQ%}SVm0YstgM+iX_}&ZXdlFXc5KGaZ0tq3=J`ltR(UNO|D6bh*z2}z;fpN%{B8sc+wa1rjmW}i^6^lN@6UX7$eYM&Am~q+z*duA"
    "_ve*^Vfd`6EZZ>y!!Hkkp+$4pwyWgt8iU}Ooy_9y61V4T0K67wGH=qf*4*=it14^R$KmN%^xF-hI(D&O+Pl=z*AuF57PGNAwBxTI"
    "`DJzI%;;hU<{WW{UmL5~X!6xB+U5cpPoJ^qnHjjFFYW58e#9c*rlZp#;vw{Z%F0HQAK)fW=+x~cYo#3Y`h^b!eR<D-d}{}O>kB@*"
    "Ev%n$8lEf<qP=(>th_7*wW>vsa7hich(~m&b^z3FRD*h|-_|Y~0h8<1;WH+aW??L>nxhVlImx&ta{??@Xu$ut;vcG~!R2xKAbpsG"
    "vi&in<u`|>h9or2n+oOB*9@h8KfS;gBEEF+OM_)Jqa^NneG~V;Ek)UTZ^-WTm5-yledr$Am8tcKpY1Cr?NV>>im2z(0dh<t@0Z~{"
    "YWPaZO_$g8fX{C#`Lkr|-)nn7?20SAjb<*3J?vn(;tY2dOL0P}4J?0hgo|kAVsx!D)L$>;w<R*n@wJ53q@CP@K6CMLQ}`iT$G^wO"
    "@kpaSY+9MkS51~<!4Pfu`DOvvruZE(M;{vY&EO>|avao^`ghv>^u4DXFM~FWa`fd!JL&cIsxTgn`G*B^oMfpAkL4=d>5m*mHKZ?C"
    "`ciQvRE~Bum+?NfPjR$WhEv^1?{+Xq@zz9+%up3VyeBJEKGB`<N(X*NT`QA^$?;H{CWz-u5~<IV<MK(`uvs=-WN=Q7CQ1_so&HfY"
    "-a}5DD+}nZx<H7FkfUaWF}xUkPOy~A@zekdC~EsG<Y~%LPtywc9Brm?QHHnw*g|YUlTdk2h7$i?(AC(SNe9Vj_h?V(f6j&VrF?Bv"
    "=K|XrjoBPq8U7%x!I}B`Y;}wjBP0DlJ+BLk-zC9@Z-Mafk_G#GUX0%4bJ$aE&a_%`aHRcE_+@IxjHl+HM{yXqEcIq{;<FJ{LZP5<"
    "AiMY^3-65{3Y{l-vm^bp(B?9O;>iP9-Auyb<}kQDYBrlqo?~rP`;8fv#OD7_$G@8g!Qhx2*7-5{`4kHftC`E%i6hsj;}6G2u3?5f"
    "GBDf316D+AXQNe#%S~K}VPVJEcfuc>yY_-NK}vS|DD6L*&=UfhZn1Z?!{V4tPuRDsmVGDhO6!8&;Hh}ceg<ct`&7c&e%CO`<#h7j"
    "@Bu~XL-vdMtXH%<$*<rkizfbqh%~BA>YrIbTpB)e2iSJ(H?wI<#qNc~i|`=+hd31-jtqp#liF}ZoPzR2A@EIy?qZ6UkM-ejE<+Ed"
    "45k_G=JBBUL<=IWCzH=W4EX2jK~zf;F4!{@)bdTif@W3kmQDlr+gi$#&2)#qb%$ORs>+v^a?~RKaHp9+_<stjshAJ!cCO<oRG$pq"
    "Ksz;Z$)}zE*TcvcdQH<aK8?<#o1qf~Iz8cfk#h19v4N6DxA}rgGVDRKp2LePxatDJAKrHb&6ab#ZWPr&(`{gW`yno&-s*0Q4ea>5"
    "m75sK@KRG3aGAcIcdMeaG=z9xi)4J(G&#z`OyQeT2De=!$L>E2;Of)4y#1*h&pp+FgDXbxH<RS}V7Wf@iW|Z|Hpy|$MGXl1>%d>q"
    "c~)Jo1uHgm<Hg>&SV0`~&3D=qKhDta*xU*HqAn`twa9VjnSX4E=O)G60y%CUs|8n;0~PYGa!fm<3iCGgP^h-c@%BhP7?>DQHsgRC"
    "Eo%(m@V`wW=P9{3vso9OJGlxEG;;B5Z)31KIYLlxm1AIx74%QrE~s_OMZYjhn7VJDFt1pS*K%#4d)9N|aT>+@(;iU0M4!EWAjdxg"
    ">_OOU!CdU<yA{w`dZNpo(%)f6o;&rA9t^+9&_dz{>-_q#qOmf3rso50K9($SBGm>D17Q16U3O@_6sHarpmwP`+d>>a(<K97^d&=P"
    "MLb>&`(fbtsR!#nNQ{GGM#5Lieylx{JS7$n2bcVQ%#r*eCSD!{-bKM|Swj{YkS4D5)i7pG7{UlO5p*6ul|7(1x?LrLFi2!x4Yb$H"
    "egK^Gm9c*0fmuabxvimVm_PBf_jVOQW&0*JcyI=WmHI#v>|pIY0}onyz{cjo><aNz2TgMU%V+1=9I6j3yE?<7Z8w+=d7+eB^n$&4"
    "x0pNmtj>)0gpf^-SOjUzPq%x4OU^5HgZiU68~kAG4DuGpPDjzi0Elp`V{L@d>8UYzzTpjXy-b*%%0Q@{_njTLBW*?B!SL#g3T(fd"
    "iXBUafqjG)B#;jMfb~e&TSNTa<0-h=XdJA}CXbAo6f}v5gy`RfFq3%Wg^G!Azd{FQ5_f3gqgYti%>=qJ@<0xY1-mv)<<!A)T*PPw"
    "CskEuB~v|<?gmXCTKE{L9DC09g2C<e{FX?LU_v~K_D6h@t{hLe(tg;LxA|xKpFZsC44Wt4<L~y#v0qvbc&lE`r$<pfnr#g#r!Vs{"
    "I&z#sy18BN&hh(isQ%ID48v9&;Tx&8sc`HDm+H20Z>rgzS6IU=XE}dMHB7#)71%vV=G}hCu)y6CYLaI2Zvk>txncrOb4T$^PT$AM"
    "7&=`E<Cnh3G2NbY3Zr~^HszFkBlO^xr8_sDpNlg{i@JB9Ay;+GMQ>9r2si$!kgU(e7cW)dIaDghq!mkP_WI-ETE*hHTx<?kgQidu"
    "h3S=CJU?9>$TOg9<=k8x^G6%THmxm-9i5A>{+Pj|+gYM|tvn1Cn?P@OJwcM2i;Wqb;q*_jaHS#_BTrjG`H-!`bb9{sKwGF^|3X+W"
    "E*E3Tm*7hR`JVO4#iQiQ9llJ58EfZa(UacL?}$6oJWIJu<N_;B8ZkY3Ji?XE%u6d)VJjz}8DIDy3u1G}QSQ4+UZ8cZ?A&1)K5`Mk"
    "(SXiuQ6S~+#$Xul{!i$UDaD{pLm($vo83D?oZhNX=zGGMy(PS^nEK@qe{Xi3`Xk?QLt)vZ0CrB6gU$~Iz`6(@){T6DVq~OWCjWu?"
    "#@VQ74}@j)(^**{?WNri1pRfB+4kY&-S<-jW?s3h!h*cSiC?<@<0iJ2&Ux&yU>K~kliehK>E;W8;2KiMu9JsJpLW{em35f?B~OMe"
    "a_aG)o?~sZ$@2s}A^Gi9=D#o#L%cnpxwVGHZpcJQz6Z?f_lAv9&BU*#J>iS@XQoNqq0CFfAA9qa9om{s{)c{0GrftG2dCqD{~)m6"
    "(ZG_46W%y$ASCEDuo_>QL*WRRUGt0GPD{l<H^X2#or#^am$p~qSh$w+hfO=5f*3a*HWEH-XpoA5NfROPssYpx-k#w;5e}8=KvoOw"
    "0hv4vaGoKo7NucL8u{dO)lz<>J9g<@M<^Vkq8xdI`h~ZSG;jUE7u}ZQqZiJg^W{DNOlL2@zzu%9e8R8S(El{b1!kAs<hEDjxW0=E"
    "7?xk*U#TXky6yl$=Wg&)(_B=2Y6B0)l=C-*a@>EQ3%px;hX11a>g@$<@LO_-Yf=q%E5#C?(JuJTlv6BKtRdn1YJT;k9K#lMCQLq)"
    "Z>F=o+P*VbsLkQmTyk;KFbfzJK9fJ2k&A~%7(#QOfjliC7cD;;LZLF4hZpAJ)N~E_8}7hQ(HZVGKnErSb>^R2bFtH1H5gvkp{P^j"
    "V#gS5@Op7fk$x!`w-xHaj+Lp3A!G7z&OHrC7-*w#tj)z#nLd2DT5^F&^3bMS58MiCFFstFhhZNqAfVGW(Z8l#6#wW76JWR?nv{nx"
    "`<jDOzkH#HUhmV(2L8KoL--n=hq9m6(6Zx~kOO(>aK8uScUED{J`e9%xWXW3TlVU5E>8RC1X&xsnDhBu3?xp}&8;5HEr?>R#s|WG"
    "8nWZR<isWJ3+wNAvL&9mSTdM=1BUlxt8(PnZE7&wzoE&Rt>x%9zdx+aR%7=U$<VLwFnHW%&W`ON%ya)pXqausv|A*2IyHp$F1fNk"
    "G^bv?ZxB4J_Ga}lVhpZ9sI~QHg%n2vXdi1=+fnT57t-s!U@&{zOqNf2y=Q9xMi(csDDrE)d5m~s=`yx_RVMPhe$ZRCfjNK9z*{$H"
    "kJy$%HY9=K#TFpadk5QDm4WPI0KDmWh?RI`;?Y2V*d240RV|~P>8JgmXhS(mAilTu7a!O*=QcY(gL2RvAK37vhFQPKKtI9(<h$Rp"
    "UgX<9hP>wbM>MkO6Ecv;2g1}XKiRrF<ar)W`()>JuoPd~SJ-7Byz0@$j_e@JTrZ67(l)k%V&PHQSO}V{3O4_x;r2t}uwj}CydppF"
    "6pRA9Ky|2gO2e6!Q=!{I9eA!veyu$xK;vrzh@xF=e+{O?Ty<@@OZzn6S<QxoBn{;;`X3!DvjLAgD$4N8TwFNY0dB4N!IOLB;-XWe"
    "7U^8iXAjNA)?<$3kMxv3q&s<CYcII3ap(Wf@W*mT*xsd_Ur))!;tx&`*?fU#(0eQPb%)Rq3Vw3|)ib1vR9-&CC#vV7?^X-An0kmm"
    "eJe*nqZ@p#*+V#XE*>#Ar(S72FE`3XjSEI_DmtAX56PwdKBU1+P2?NstiJDU3Zu47=BFBS(U>@LrgdZa;37JE4mtp}0o=nT4^=0V"
    "Cy%BlzmuAWo?q2rqJt6N5S@n_6fdb=UMuns<>AIh8Zf7|Sn;YV56g)ccmDDKg^6`ON>1p3%0pYl(v5kTbAkL849v@_N93bxx-soi"
    "UnQEPnvZo>769S?g2Bx^++}AApN>d`J@fLh@SO$3Z7mai`R3#F+OD7z{z<4Bl#f5+yF+%!YayZ|5BD5&hWdv_Onf&FlTHyHJIt1;"
    "l;>g7BsT~&FlECH^YB52H(2a+Vnavd;hNrk;qFU4c3*?O|AZhIa>$g`%PIFQKsYnafo&Q<F;4j<;hZX4VxCLBYJ*|^Rc+=?dH=w&"
    "P-twmV~&J9vWzfz@wgYAVdBarksfEZ6AS1}eBBcAA*}IY?<kHYkypl+x<KYXmvl@-=(IBpWm^`~9JVn4!tAH9qCMFtY3&R8I`Qlf"
    "ap$bw5k`GN#!k%1LJx62INrXVExklLjFckCez}Wzl0U!y>R?!0yPGW^OdjJW0-+I)us!5eaxE+n>XOf}1AB<e{n{UlmtA6i)rjwH"
    "6$t-*y2)b6lU9X#x79~)vGufr@95aR;9>BTjW8ll?-@aGebHO?mG)qo><2jO{gw4K&!83M13-)Tg(C@Dc>Q1qoEr0$?V6L0u4ZAN"
    "<^6-{8>M61z6dyfko2MZ(s4)9Xo&mS2@Z@&$HzwF;oi%CtkEwW@1B_gt9}zVg?1LSCQXKzXahLroPm97r-82u#m?t+?4>#f?lDbe"
    "gEsw-Hd(<g>0cguJQrQwTGK8|+G}8!hiYZrVac}ly!37^Ix}1F?On?^p3KF^v&c*5#BKh2cpjF_bbx|=*Ld%nxfuPx4zeB3^IEGs"
    "^nPOx_a~g-3y<XD7J6^5#u8q4D;KY(TfmnC2lxwme#!gJ@b=y&eu?U+aPs;KUb&XPr_XtO$OPV;mvGNVx%hgwF1+2dh+pZHhl8gR"
    "p7wqMzeVRwhvLgCbOIl@fX-xvIt)-lzTt5m9+Q*z;ME?yx*`wL$n*2rRDFIeDj)NYXhLJ(=ZcFi`Dl7W5BxuDQ&b<z$4Az>P`h2K"
    "*bVu(Vwee7mg_5&bMn#lI^h^@g@GT}=i|1DF0ih*p)lcDK7OyZBu(K^;nTi+oVwo*#w#`oFJ`R5(4|(OBdQVFN3TNvIW|!6=!S6l"
    "Zaxkg)DuqDsIk`SeBAEZ6ZTIwXW2*dQEuxB;?Pbk-76m}Nw?Ck#Gd`M%*UnueW9bh6T5gO4<DNL1+QM+SV2=B>c<FhFjJ46E28@$"
    "Y5<IV)tjZc=Akp`Zob<avqK;09&-wTf<+dr**6y#cMgZ5T303}Ov7wlD0nuzv5BRG`KS$nhWbA20AV->tAoMxUtczdu)D+p5u{d+"
    "U@ck_Oc)si(Hn*{+vXg+$QitO7|Rm3lSj&neh~0EnKhDj@A>n7aABK-Z6;5K$HZrQ7A$A1B@?es4u)g0E$lGq^4_l+0IoatvWx0j"
    "7_KeAo*u<)4DF}b*iC?`O{MH5EfD<CD!^x7&fb$(NzUUSaLT;O#!|nt>l}c-(S7#nTn1|OM%buxkF7b9j@?ZF`tWD$1bNe~yfpy+"
    "PI%9BR;Od>qoMHaOe4#rT^pr!A)vP8CyS)r&;~jq;liT^cJLh4a(d%n*^&-s>_vM$&W)ovuR8po7@RdYn&zABtdy{h^|NRf$w75^"
    "X_0|);~DU`i!N;WzlzQ~uIB%X<5rPMDs388l#yBJo^vWCl{9H+7iC0=qDWiouCh1TBYY*)eTVEVTlU_&Z2ivfzaAdf$HnKo&v~Eo"
    "I?vaeEY=lA;hCcv=x~DdeygUUa+!La>}3i4Xl069yjw)^;u89AvI&k0{4D$}ODO!iG42U}EvBC=p`jk#@bKP7VZN_~Hcn)JfyS#M"
    "cytMUwKBtU-;?6TjuPs3*&K%qR|&^HCG@P&6y0L?i7ftn;*f6WvS_Q=?N~y#%_i6$H;LP?I35q^Vv*Mh;ktlpo+Kl*t1A>|>`KUB"
    "kRe(`<%+tUCA1|}8+Z4aFIFEYq3RlSe7ZAIj504J!}l84>hn0UaYQNgQMJJyL;DM@kWxCzy~b-vJ;c(=QnLE4g)ir*iHZ58q&ue*"
    "ZVbAuvhE}$7w(T)Y^YN;94w{O;?5}X%2J)zl+r>oLwp(YyEZFON)={$xbpAEQP~P9o$6<VvFi^wYMDqWx6mAiPj{B=nkA*mPG;!!"
    "W4XjkOG-N?b;o6A4oiBf$!I}RcU(T}v!wffQo3N+1Dk?1pru4g>fLN`;Q*$m8%U`z!wxT;GlQRhO37}(AUrEIfq<W-RMnk#)-t|G"
    "o*ply`F!?1JNR2-JgJm2Ch*>UtOaacQc4rHxG>+iKg=;Mr5#$_TQ)F(29C9)0bZCqvJaGVp4zg(7qd!+gZAiR_HFUPBtHijCoQ7Y"
    "L)<X=5I}ZaA+_}))S2x8{Vp!1h;NSg;aMP5e&U^!waoN5>jf`)kE!~sGnT8x!z|vRNZs#<e_b+ReHF9pPB~)8y*$YO$_z|H!dFwW"
    "poKYF#<yKir*k<Z?#ZFmg-*EX^G2A=Tp+mMghSnS!Zh{*u>9zZ33>aWJ9}`HaP0S*xerEZWYJ@;8+GL>aGb>aVQm*2-gFvDdG51j"
    "hZA1u&;VmzvoCD~`=uJ(hlVNt_eOWc!jJdi$VINN+I!(s>o@R@^M#lBcr2~@2FdKXSutrmI$e7U1x4(SrayswH@-t?LKbcQ8G;Ji"
    "HdxHOeeYqxJWKiwovv{&v2PSEVIAa^#XMumkH=pcYPcsbo2G`vq2()0G%d=e+aIQ2#R~Phxdo;4?O_*ucd<qEiZ7+b)y7z9^F<s{"
    "FQv2fMz~<xGcjRf34L=iK-HzYV&T6MI-+KRL)<Qk%2B2CTc<1b?Rthefh9aIGsINp6W%u{CAW#DsM+Q}afM^5hqnPL8n%d)`lYnD"
    "fOAd#MlncMLT@y6Ft}uiXelotod_M&N+}T?OiF2YnIVo_Hd`FiDW%qLJ7aq20+F$a-<hEr824ndSgI<exby9BOE*^$c&L=LIgWCw"
    "hlx~2DQT_ZI_+3zp*@V>=LU7O%4{RPgh}azvNKw*JF04XMM`!~+UWMQUbSbglx`bvobJm|ZT>DLD^Golt~g!0sh^Bu7V+ODXGHDO"
    "^-_AsHEoU4BgcN)GRpPphOwQdNpAO&(FS5)p~6LyVL?**?B53m6$*(%o|J~v_Qmp_&n1WCGBT1_V~zex$(0T=`u<`drhL(bYi(qd"
    "<Yk9(`dm|8meQ)h+}CBYqvX1jC6es7d;gOpyi`gd`aHgg(Sqyz{KKPNa9phpbXAwq8WRtkSz`-(+DXad@>on>Y6)2-rDRby9@BN~"
    "A?QpAO?cvisyt_??p#8}lRZ(3oM1&lF`fF(ECQo({P`jZawUBIY7$hihRWeL;OxFZ5XN(aV?Mm6tnUKbH}kIUZx^&QOMn}F3n-_x"
    "6Q1vt0`5ce$?cmHN*ZUtV6{BzaTD>yzWJb?ol9$Z_h-;VIdo%Px5*zTyzq1d6g|zM?XTSMzk!>eHT$zHKIx9uE4RRO_EehjzzyqR"
    "2P~p2%9Og{n5EU=#-3=?7P_NxzmuTOy|w?6$KpiQ1qe}PQJYdXycK-|hH@;-|Lchz^`5}e>MUw?(F3bJAH#NLde<%W!@#3&LAYd-"
    "s*^Wv?Dz!+@jYwl>OeGz{s03xX8&;y?eH(YAF-CtcWMaUI@JcdviI4OrxECV;3u4$kWK26DL8mnJM7Ipz=z+au_viIu3#^lWi#W^"
    "(XD-51^>UCWCqmnh*ouzjiq$dstb0aFXF)aQhL<Q5VKA_6SvAsDdboed^qK{$aLbfai$*5YtO73u1V}mjWD9~Ns+dol-jaxt=pR#"
    "@p(Wg-6+(<?v|AzFt3!ZGlzNmy&ZzLgXzQi&RAKpQg{vI=f7ajg5c#M(W8{|m?J%MUWpjawN1`zU1kNRiuBWbkBI7m^eaI`=}D>W"
    "Zf$Ix>M0h@l+wP<>Nt{|MGU`7GYvcApQU}oM1J3@?rP$n>xSYOzuN<rw8vAY->4b_W#m+-iL<qLtMc~9Xx78dIP}p@6^xTn@?m4%"
    "WuB~xdm$xhLsyjNf2du5S4IJ8X1GNCTuoe@j1KDcz-*oOj>_{gI>GwA`Be@Qbpsha`eKbv>sL$u`N>$PYK`*7eUj`ZDWxy5!^njf"
    "C7q4s<TJ8Aer(~mcqyYw=EfM=w1S16GKxAgjD5!};c1<WY}?r5TupU2v_VE*eVBQ!V+iUxGAh+2jC-sD0X8z47d-|&PV@$wBF>xr"
    "*h6Y>Pq?BfqiyHCuuKdE5h^9)cptQ%?g9g4rQ}OotK4^kk{2apam^ivkMspCt|cDYjmCXGkub!xm^$oq#)C6sp?gaqU7I}`Ki>0z"
    "28Tk*_ZW@GFFJ!=;$q5na>vPcBH^HlwX9FvaN_+)n7b^WHkh&h@9z*;tjMF7sL@zqy9jnL=OpO3D`qv7LdN4<(&e1kF|-&4sdDJw"
    "$}#9Su?+H<j~evX9X)GSz>b00w4$2_M(*DXYV6Zw@WcxX)vI7lSr+}$8;3)x1T1XfUN?V#|21czE7x**?5ma8sR4E}zivj~vDn@I"
    "0T}GbrmRFS{CMXMoM1niH)R31W&Ly5{Uw_c6n?mSSQF^8H_h*jf%q-<9gKU%zD{*vn9Ce7hgHlP`WT599GF|kUK@7pBGL5cU$C~#"
    ";W<$}hO7R<<OA6>c<Brb2yKs^?0qx%L?UjU(Y`Krgp3y6W-iBrR&~FGlq9-3`1aRV5wlB5^_}%__qSK#v7MCi!kBy6qfs;tlu~=H"
    "wbn;p5~&<t$M))=cK8Wl#%FsD&om#NJ|gx!EhWW8Z7i9#UzqzyY5Yn(9Ob-8)N6B`w&8u2{Iz07D=9r)V}Lj2mWyr?92eiTaH~e1"
    "sBq!)Hcb<^%$qO99FWqmQTo{DK(P2XM@ojw<Bk0rC}d_b`smXUbv%ZPjB8SIo34lJuA2y--BNnIMGq6&wi9EI@;m>s6B_jSrds1F"
    "qyKUZP|fRts_$Sq)mL^w-II${cHd-VIob&S+T^N?`Mq^qXNlL1KGg!h&j%uVqSuR?qqe)t*{`i99(W>myt`dSPh>XC@R3NmH}dn>"
    "4#4dT)=QT0Gc%6bVh}1M{u^b?w;6(#k1t7{)yn9S@i6o#_$*03DW{O2p}6t)H_2;9IlWvk3QKhL;ok~59oue?ulw|Z2NF3Ij&a1F"
    "LI*arlT)S#GX}T!fPWl!gL$XsOx7^?;VUDzeopwRz!8q$l~U_!S2P^!4mzKu<e9<x#z;@7;xq7Y^jO>@4+ou~QrcqVg+okZAzW2L"
    "xpl6%pi3e&RdX+Nxf^cjl>kdu7SV%0W7$vE0~Yg4;Vtt$uB;1zpytIyQ^(@Z<{+qO&AU`5ys#?N8=RT(<u}Y7|9W~uY?pj$IOL8t"
    "m*e3YvzOD%J+OmuK8#{M`N=>}{BmqDj9|v&n^N{$yu29RdvIMhZyf%&svJU&WYf9p<I&l36ZGI(sOI^2%vJ4$PTT{}`{;`!&mV%4"
    "L)ny$Uc6Uw8s=AL(<@IeeCcx;en)3h^9)}sw!IEZSQk;jaW{SGZJ5s<Ol>-HZMK*h1=h^lXHUldlRm;r_OnPDHxWBdX@+6U4DZ=E"
    "3BU1PPX)8Qt~ABs&UdZxIC}>y3t?~5%WctG!M;w%<8ivqADFr&hlb5gM0aUxG~@Vs;FE+#b{*;_{gP4aAx*4^YhCwqnT#eK(8Q27"
    "O(MWUMs_}0*zWENaj=h!q-{IlipoY2uun=qcph7^=CT-Yi(_E{_lo^bh_y?kr035wM3-u@|DBZnv*%c=-6fVPr8F&46C3=u3VbG|"
    ";HmmJW9u^UP+dka#{i`(i-pq#DRmj3k1dr2B8uy!b7wo^+LlBi4dJ^(x;CnP4-)T5Mi*nd;N?FqV$^f~OpP|4xNj}KC}cGMvkoTa"
    ">Wfq-8CkKXgKL_$=o2KTUa|T(`NBKZ?Nc&p+G2{QJMU5X@ZZ;EMOO@eD_2Rc%Sm$C1gp+YRF$ujQ&?Je%;>PE){x)x5w_j&O8vCj"
    "U7m6}s%MKO)2BJENS4zK%Yk_Io`WRxgq-$&vO!0uLP>#|f|}pk;cfF3lKp8M7wehB+2ORLx0Reay0T<Mc2SbuO+k;0N1(ZJD^NHq"
    "XkGqD<~*pu#r1NU{+j)3W?RCkVG2rG#P@DTE2zCECvE2P)f^fIy_d<!YMK)UpL2(J6FIe7>Vj?cN5ZmWGU{sJfejL0sOSH?gXLWF"
    "T$=>$eCE8)bj1wMcnGwWQp8mcH0_!OvD`B`vv&;I*`>o?_Y#Vk&Wr+^1h5V-rZr~X_;{Z;lsqn?Pf4CQH7g9(R<gFd^*Ah&jf47|"
    "i%I>rH(H(@2^WqtYvq9__8IO9i<xV5`2IM&nHmqT6PS6@*ApMEn+Lm?$F<dGJj%?{U=n*|tgaZ3dzHD+<{Nvvl>6cP!%7&=o?<f+"
    "{qdB~26!EnLlGbSFwJ@owC7z3`@-=Uh({oXy~fr&^vCAvdI(|9j&V1=@xS+{!1@9A^in3^?(dgi;A_qo>HfGty%8krud$oG7w=iV"
    "fVqQNgES@>rNM7t^A(=?nnd79qb6A3%ic*jkvK-Z3Cj8V91fj|<kcEytj;A3gUNWK2haRw@XuGK;^l@m_}Dv_4p`4b$m9KF_H~MQ"
    "l87$1+Sh%$FDLg*O$;<_Q&%`mPT}z#aEx=ah|rdktW5{Zzxzu3J1L{+i5<{*c%$gGN=7@F4YhLCMG+Y;qdvJEuutM~VY8BJcsp%W"
    "-mMlVxh8319a?_%R$-GPqt!<=@Oa@SQN-u)=J~q#F@32xI9o;y3$=0csUlIgTSiy>yWrV2i^W1iIrsXsaQ5JNVr^?alZWZ!)!|`c"
    "0@pt$EOc?;2;@Ce8Sz926*=9-@-R7>8R+B6K0U?wb6o#03qAi(2jQ!dQylxg{n5Fh+O|zjySR5TXJ@_Y06+gsw;s4MeW}W4oPv4g"
    "R#>^Nmnt?>L1&w-aJibg>d6B+)!pcW?(I&GxM8lKJgeT=^zEMG)KUdKTxN^j^By|R`y{8o$wP3bZ<s{dRzd5t9T3)Rl3WT`um}1m"
    "OwX#67}d$Caj!Fmr`?zQ(NoaiSZ7q%(*St~CAHZEm^r>9d<<2v24f7q+};iFfr9jtopImXVem0SK|w>E(H4e)DSw|~<G60=;|oa!"
    "3M%G1^5;wLuy~c6UUc`u$~a#r;q#;?_hZLKPKHE(8FlOLiN<s1L(Ul~-F-U-SM<vTt#_qV2VQtSFCBKZFQw)hZ#>>15@vgsP*|`x"
    "&OYl6k<rEE>+Op<_CXMB!!u~s<Xat;fMGf7NeaBNx2YW%b1kR(HXdEiJA)4INY;P$L+v%u@Q8ceEAD$^$cHfaWzMX~5`NCd>5%A?"
    "N0zSw@UcrS9K6Y#;SGWKHlhrO_w`=Y2BK@gI!NdDxulmbMqJ(l^Vt7o<c9I+IPyPub0UY*js;>(ZaviVXI51O;L0!caJwvrzB`9v"
    "$;_*;mo?!JGea;{?+&bFw!^k}LEJxYgjT%wH@ANT9{T<iMl(C5)w2kk)9EWTF<&LmDHfYseTCfhx%Biy0!~`<7qpoJW}!75Gb7sL"
    "X7(ER@_H8Lm~_P3l3W_pDw%i0+TjT1^G6PvjrRA|>Y5iSC?i4_!!ugf6$SG7`L!b||FQpj2L(lIwa3~1uZ2OCoNCO~aXHs)Bh%&7"
    "#!?;kDXxma{pAGF9Z|#Wgt*&BPMg=YN5kd=;@4O?^$YBPdFS_v4SI6g$84x0ohyW!kDMki?TEAcm5Z&j<&<(*6V)o2MKD=TbMm=1"
    "dyp+!eU{VJ``Va>%*8z~r?d^)7~<_K^xyM2d_W(E$GM6@ayf07VTv&vJJWh7=+qb!thY54<2Wxwvrp*LhTp1X@p9TZ(*j3%-Bo?c"
    "R*?ETb9B}|s%rcyry};ho_4lC70vOb_nDc2W5=puo+#*-K_5Jvw7hmyje;^C^})#jJ8NDVb1Zn+VUg<Ss0C(9X4MWvzb!``_nlFY"
    "B-S4HrgoJ?r736|`=D)@QY1MSte_df8I6yekrdug(2LcC8*e|Cv}sV#oyG2GvhRzeYKM~DiCnN|u@;#2Qc?qZOn)o3fQtt?E`r%d"
    "=I(HKKZ-xI%MIJ#b%csk1<hA@qi)CX5UQ!9;n&^qaJwLQKS4pYgS{{-o_9HS$!WWx58umXg2ga7HJtFkUYU!aW`T^pyz#`g#}~oK"
    "6;gUR)CUJeCBdJnQVPuQ#i6N*u$+6Cby@z{{ZkxF-BwKJs{>FnA_z_&E24Hb6L4qn2)NGLlA~t+c%X3rTw)f)&oqBj{2dJ)a(VYQ"
    "(;p?xQBeP)fGo`X@a5Ma7<M_IFfb4==gfu`Zuu0i3dCzY^5GWu=#Jm=$3wIP)^J_7x{UW_eAYwV|9xsMPQb?%yI^hGJaV4ri>~2^"
    "A>tA<A$tU3ZG0`fb77wshfvfTeg@px2P$E6D1Li$88$y>FWP5O82Rfe+-a3ZAB(~<(YFykgyhl(qgb?;zJMCeM<;PIj_LRcu8hf}"
    "SFs6r)V7J2v-4=zpjo)t{tvui|BL#9B;2po7VDY)<<cq@>wjtBy2ZKVqMeQjr5&-EJps3S&A~TsTGu%o;Ch~Ce_Pali+?!^()HHG"
    "O$pyc=w3Owvgg{V%y(j(n}X7L7qYbL1F>hQf>wRhKx%bKRQFQQB<4hY>2O*o=gaA`M<?_j$6f}%<>bjR7}kB4c*H;d3}fA9X@v+}"
    "DW`*nnUiU;Qs4*$ReNh=!H7a(!e{<iTV34vI!okoz4Wx)0Dq{@6+83z&t*TjzZV0=*lP-AGjiWx<p|-&XL2L^2#oyOPZXFc=)ieP"
    "=KX4kVh06jOt8eGl})OqBspF1=#Bmlo~zDnQ&8ESUYJX}RNXJ|d7jW4%S)E3{5YqCZt9OaevVMR;d*K2k^Y!-|7dN#i;}uM8i3cg"
    "e5|#JR?xeap&0%<yC&R3Ny+<}W4Wu!amGO<*^C*92fjH;GWk8<#(OK*56LAS)=H{<>xhwuHb`zBQW90WU|ifSN#8DI<QD0Ui+{C-"
    "sYYeg?&nx+#T+O3CnYUqt>%Aq=Af0KBzqelOx)lA!S9r0xQ6e)&qjgWASG=_KYZ@v54j%|lyk@j4J8S1z(Gmvnz@HooB%2L3bNkp"
    "gI--Sp$nf6$5?qbuO%C9>&ofUSYP~+kP6d5Mtkc0F~)cXRE(8UFRuyMG9ebU{Y$BK&P1H*9|{uJ66$<yBEDMh3OB=wDLHQ<R{U~;"
    "iDQdM70$c-{d+<H?+9Nj4??3(ZlKS5g&9pjID1?qykuU)Z}#ha{W=OJFte-6++fUl$2tVt0?H2!#3j*%aE$v5+HQf^_0AGlWt~sS"
    "yZrESr_Ip*K_2zZ4#bt`_CP0QeVc~_;o+-$;41g)zQ*%2dsf3{y*%DsnuL}E>*4=?F0<Z6V4~VdaN^I5HjKfn>zBYpmwhxY#p0#w"
    "_uwn%j+V$NI6dY8Tx5?k?RL}9GV>MuV6UYUPo`sG-dphD9((7Y6fCLy2_esNiG0)W)Z(@{*n#<zCsHxIq8&bA&%yNp3o*k&3;o#x"
    "eRz)r*t=Y<&X&*f{*i{b>G3Zy{)e2}eKW+r(hp*wrh;Bi*GE11Yf&4+HB5vy_B{Sr`1MuLrbnI8o%?Jq?h4A!?u_TW>&3GG1$_(9"
    "#fP7c2%80RN?>oeC3p6Vwmu3PV6Thwqc({Qj?JH!^l-(M<>J#9In52}!ipBT*m_(+JJuTDz#Unlg=6IKSwl>$iWi+bDX28k2+j9K"
    "iH90Wy3yJU>)tzwmsUy&WnTu5HI^c+jgn$wEHHDmrbtpLs3@ox`kQnTPoHp4;7VV_rUxn=4FyehwZ-Q_=T)v>73`mGixz_mRQtGg"
    "ddnPuYv;pNhhi0Uw2C!jG0v)$3zgL2*kEkCzKg1hp_2Iq?1vjgwGO`()WEassb^L@e&Fw5?cjtKIRhlS`8_XgMvS!%mbj6U&ir%5"
    "$R#T!4IPzaRpo(WR$P+w8=$0HTqE84qXxI8Drs>mAN-fC1G@fY)RX!A{=@o0ds!J-P4>o6lYUTbT1J0N0`TZs4~Q`=qjh?I*f-t}"
    "dUz^n<h2QCvpNP|-BeQBzP{))avrpCRg#gVANHtS2=eI)GB_20Gm4X8Y8ls-&iqb3i-NIyKN@q>57+nvf;IQ*hr0Qr?+9P0JXuOQ"
    "nE^O!hb!n`WUa-OK-6ur2l1|$s@8>In>mAF^R*)Cwm1x9-}Qxz!-ce|Ivl^J_64(jyu0TYiW_#h!bH|8B&USn{UcLg3o{>%eF($h"
    "I$5xYS$vAqq4;x(6h7D#P|1T}beF7zdF-Pxhwt)N&#iz<?3XmlF9b)N+6KF_@@Vj>Fl_gGGrVV}R&={CoXho_E#EsPe-6iZ|7y6&"
    "akTw@3|7UQ0C)C8lf0dR`YW%%&S>`dt4+XGdN&{p@(8xhz;*4OK<kUS6me)4u37jBiVo$FQ(_`sYR!64AC9RXNf?^j471oz@WQur"
    "thn+Ia@Y^|*|E8Jc%vFt7Bc(JVjgZ}-qbwyan2Z;iPkIH*IjYq`sbW6O1WnHWhW;MnE`4he-rKbPI}f|5B0k-`OZyFAAI<pUU*mJ"
    "2FvO7-A?>(bwj9gk0_n>_Vt$MM1qZiUM@4jQ@;)iU9NMi8jWzhNu}7FC#T}s258W-RS3=t?e-Ys?Q1K<K|Uwn*_yI;x>(HBR*=>j"
    "W6U0$FB&g$K3dlm)hlO-Tg16$bT>?M@E20faUE>TQEiWx*waeM`mrAPW4E2SY|k~%Y|bM$EJX^xGf~<$_^e1xwB<OetLcX`UNxz#"
    "Uvp1j;vigBU#rq~Qqa@LK^X0`U!^u($vfaY)6ZF_`oVXN&He20ZEd)!ypZc6$tYwuz}h<>_|IBwkEc?W)~acg(bElxl?PfocGM{&"
    "jlV89MWd6%+@g%C`Oac#pDj6(R7ThSjK)g)EfRJ2GO|49fh}|EBr(Iv=os<&zu|-AKL6hA9|3qczBA-omeI2f6R>%tDNOlXMm+UI"
    "%eBLyre`^69}2))i948Amr;lCAk-40U=ZiB;=@7s>|qd?wJ)Qe%<8wlm<$CcI5#Z}!oF6Mq4}MHZ0`o)YV|OP`XgtCRWR-y5Cnb9"
    "<>a?En7yw2p^J%(GPVYzZ234iKb&V<Cd|WpI0ib6<U5heBoua@FmGrH>FPz|q}8r4i?xLfCef%f0N`JH)`8EB#>sOKa(N$c?e+-V"
    "m1Pg6Uzl%vI})!f2?Su?-Q0>uY~7LuU6@^&@-hnVjmd^xysy{iOBfm_$RL?Hb#Dv8FyPM`aD2`lXAP0q&tx_DJYerX&v0CAuoLFI"
    "%_Z}?XdLLa8+5+p(0{9A&}HTkSn@N6REijE>3tkRIHy=oNWjX~r=jv{E?wz9gKO6YFo|IA=Fc;6$f8Er#XW&;H<K{#_6wNLnxeZd"
    "b8yGhukgJjhqi7?Li3kjV0lpv{arpEN3Cy#)tc<%+&=^Lcz<%|E@pu9=dbqDz(l8PI(sk!mj<iXJ<*g?sIb8JH-AO>7&*OH=Y9E3"
    "pGE%xa=Kz;f>UR`5+!*uy0*FtYKPntZwh&C;-H69<1UFFclb^kql>GLoDkI>a;oZQfMc%Iig)&M3h2@mcUx47_LXw_c(f~eFWexa"
    "68PS9#t6%gm5YbjaymWO6bD_GixSRRZnG@dZzxN=sh88M30<*1W|nwyR!-e#bjP&)v0`i%$4*=ieCX*VdbY@^d44bK(#KJh#w%#e"
    "SsQG+ZYzdxJr@1W4pprTg;6^Nncf+Q6W_NNCl4rS_M#!UcH=G8^Jxk?xx^l~ZhoeU=bC34`vy8=jmrEVpW8Sbw^!$=yg3&fW={B;"
    "uU%CcSIg-68VCG%acr%*S~=O&jlzgBN5_pu<<##3;Y5k1Bztr@75#O^*znO3^$z9qdzcpntt^wcM3mDfCvTiwcS_PXw45xj_~Kya"
    "yOJ)=Wd#2wqP>GUq&k<=>u(dVVUHO+Pb(+b!d~Phy<kIH8Qs<jLD`<+(9p4*l&Wy_@*WGz0?TNkdL$06cY!R<kGC#_;rk8|@OzGu"
    "hDjsP&mk4EpD9SbCK78L7Q#F}$Hwu_W9arIQ1s&diAxwp^qvj&UfjdU3c>L1(_n`O&&zgA!qaOfgH*yj1nn@acZ`8$14^hyFAP83"
    "oCLKz4|3s{%CrjtCF@SV>PBGxjbO+yE2M*;qHv+U7w8OUZbNPy@8)>JsnN`J35&-xX$;gX;dlv&W#(`$tYqeo(d}5?IW2&Fd-5o^"
    "Lkz~UpLG^{Azd(!#!U;>gB$Zv!})Gvsj(g=a;5EYEC&B|-U-i^=F(Y<1bpdy5IkAqz2ry&_R~5Hr+L56>diD%K0gL7%<*2hbr$wY"
    "I0uzkoI4gI;u6Iz_^Zu2hrzQja^q7-d(S>c5y=?4nCGY5bAGNh7e5*Of<CMrIy@o;NB3=k$w}E1+93^BY+yed=0N^1PQhQ+8tA*0"
    "cZ+<|u!lmeZlbx2*63ScW#~V#nP(G=w7R2t+s~pk_t|!>w#4YNXCkIaMjlzF_(tu%i0jPrK{q3GnsG(kZp*#mbzM-_azeZgmeEEd"
    "Bc1^<$3rP2;}?d^DcUJ^T$j;bNA_Oqx?WW9bFQ&Zld<|Lp?y(K{|;KBX17xDUxu8rFL%S0E!o09l4Ed6ckJ3JN37zQie1_h-BYHC"
    ">75mHu~%Q5_k5zzKc%45!R!?{+)u3J{_xm;15hD#5G^~o55QW=lU7z@M6sNl=dh2)ymq1!*PrUV8#~OQy-3niQu*)^DAjzVT3w-}"
    "koBXm^N$LZ+cYH^?3dv1@vBq|r<T!|775PI1=YyWWz_jTqPIj}^{#z69qZ|gRTx$KG>qTpA!Cpi8%L$?D5vSYy-=^|y5r)z<z#ft"
    "7l&O6lC*hPPG`Rd;7<0<iPBrbcdLmQd+m%Q_IWuqs!c-qiuaO|73CB&I0FB*)qrHZaw=OGjV~5-1;wH=^0JCStKI!!_FW~-ND9XX"
    "kB5T0TN%xJ5QlxM#=xXaN?K?hhrRo_18{$%=tVU4Rfd8I$BUawB>oya560b*(~;dVIKVRx7IM#AQ5KEeTNi+<w~QXnXHOZed{B;-"
    "QrNFhd}fvdq8rD~nNU;<$%5AECG00MiP^s?;KbVa_>1A#W_|>`U&=cs*>QMvycb;Necl8`JSv>W!R;-~Yuz;+mrRI)0n9PB51)ok"
    "n`Xlj=88{DO~8@c(%}DINaGGp#bwb&@T5GCmhYR2R>8|)%MIq<yHCNlJ(n<dH<v7=(=cG{D$xDJ^O_OUP%msdsIADMQ%wojcyJH2"
    ";a=Pw*O|Drr5bWR<dW-^WL%&;19#4F4`Edb_8fQx#H$>d7dr<Z&%X|L+Hl|7Cl&o08X<_|Lhs{TjIDYJ#Iw}Gj8rt8@ev}{Wz+ew"
    "N%*VgH{9=)O(!&y@$~jq7+;b_)wXH4AW{tjhh&l0rWCyKx=q~=o;eP=X^L^Wf5b+fhwg8(L^tct;v>&YZ-48FQ3sxht=#|olhXt5"
    "d)yL>9?K}N-VA$+tKuuqB?mn)MLVMtLL)^=&b21&_g5{nZcC}r-4t&(RtoRAGS02$nBcix_<feq=QYfB>$q0vb(eGf+zZ#(mWhGQ"
    "GHOXM$Dll!=)Or#E?K?MLo-LX@8JG<6|-dJIig3Ag7*Eh#mu(Tg=QW11J4b>6OaAHR=&R==Z+eaVPbNjf(B|1$Lm7}iDle((wi^}"
    "U$5vQ>^OF6ejxrH(_Xy1qo5;tgega_s*ayj&>tx?WBZ>}#h+I)yUzu?@5xae-m4^;rVCd1%~4ftETaWO-LS9G_u5-rU;VXpMfd&j"
    "HJ3(}(dPDJ@ptC}M|ox$Eq>*NQ@37lJaLxuLMwk>cN!uwe_qD<F&G#3E|!#Wo*K6=5Y><Gm#8k5QPS=Zyi<8rqIaN-dbmbm@Q+uL"
    "7t_jU`h`iTK2ZyFnz>e7KM8w<nZj`|B}qIZ@J5g=%n4OeuWhj?eQXb3gO!w%J`MMG4}fT{ISaj}F^?q%_Hq4uH#r_PCdPq*1=r+L"
    "V{vcTB3O4sM%w1_*zrv&*zkO9a$Gc8X%s;35j>Aej>Yi65}3lV)8%h89;hjSX1x;Hd?gCo%`5=JA4RmMDiY^}&4oj(LpXLh3S&-9"
    "gBeb|+vqU`Pn?+yE?1dLDQ2Pi^$2)%lDTv9X5*DXG4P=^bL!M)qMm0qD4Cb_f$OM2ISL@=68G3J9rv7D3qilxuk(H)-d$1w=h<_%"
    "_SFouAGrzUu;0qd;91yV{x)dCo?oM%&%#~(55Xa64((N&h4XLL!2<TFymxpmc95QAAG%!X=a+%&(r&`>dAZboY8u`!dkBVed2b>&"
    "4c}xwgu~1kZd03qalhWdJ=Uxa8J&(B+`d8|-iZheNJX81PvCt&i?k#u7?AuEw3rvv+I%*?V&6@t{fkJWW-gxX*t+hios8xPBmB~-"
    "NgOJdQZvs%rgnNS#>GgfAjAqM+;}3=S#za+vllj4-WIoNSO*f>0|!K25Gffl8sF9&&)b|3i+E;gciaN&epL%i2Pw^Uu)tx)JH=@J"
    "b;Yf27<YYxSQ09u>88xDs9Yh=4r856zBNvry;z((&9ff%1YG!s_pH^pt{Y>69!sRcopY1fz<zl4{d}SIANOFb2I9g;3&rFz1zmnP"
    "1YJ@i#OslqQxb;bn*(D+pfBepHAl2_=p&|8aE%u%!J{FzLd{D-hDENJ@=QataaE8Aa>GkozN@BNDyi(WD>`Z%Q#HI&P?&`~-m}P7"
    "896HHrLhP4jBr-{<UUv{4-XtX>Uyou1HQAo@!%b?&9w&n>&d;x<M_P?Mr~cq@ADX6OrN45DdHIHo9u(`N#iB%Gs@`PXg}<pwo1}o"
    "yNtf?55(}lIg+tM%IH#M7?!y1myCF&B-b6`c>V7q$!)H?#sx%R#^`^N8?DM{=)7qB9?=HqyMlJwL}Qbu8Q82;&`pfNlX-)|e6NC@"
    "nNPtBJb%fVq@Ye`6H#s&0;*Fy7pR_zv8Sd(E1n%}yEYxyJH){&dl?n1;@RKh46sU*(u}JKXs|O80^XET3v29~A1?qk)@;kqMB}6F"
    "*>HFW>v^IQu=rCU1a~W@N!Jt5eqSMY_AjE0?s0g@I~S-8bG-&k!9w{QD2r!~mg_V;tDO!$tV8IXnSv9W6X6+q^X<2ri+jCNU@H56"
    "4eFbOue%n33Hz|Ptx968!V1{Q9!C0xbMeIZE%2ImA9C~N;M++%;3501-*`0}S8Ul1B^#J8HzO6j4;=)(*6dGoJ_TF)pMcwm?6Fdx"
    "f=%|PU=HgCqV+Rz*@)}VI4PI%GZ&$}_Y(+V{&1sa2Kq6he893Cx?{Zvm*Wp`c#%zQ?H1wg4L`v_!m*>wz?y(}Fp_u78!o0Z!|*+L"
    "vRCpSF$WuV|A1@E#R8g*?d^VxJFM4Ql&O!$`uz}NrppK)o8f$uSHhZODzDibhqc@jho(yD!47kD-FQt5*)JtqX6A(4KQ9)rE@e$z"
    "Z>)Wy;vSleY<8Ms=OG7#3F`{F74*Q>^LB^|*5r@)+6&LnIuV^Jr6g@j4C+@VN;!6h-807{#}<n<ucZ`U(+h`m$QFZHi}JZ+A3W1e"
    "D&9Sj(bwez@q>Ml2!AH0*1d*c)vaWqyF^Z3^6hc`%oK5Ly@Jl%a>RWJA>xRZlAb&og)WC3gk_wP_ORCdj9yo<b+nRPz9PCFF%t>x"
    "lvKKAEKWH2R~3ItK}Ma%;rWKgD*Xl}=`@Z-qY*1r8okQMZxqi>wtK5oZ<J&i>5I{}162j>%1OT42bVeN*Vb`P$y)1!*zlt!xN{i="
    "&X|DvR^4-4KeCL}x&~p>=W!CV3;Z3f24mf_bjdO9GY?{>gptNh$+So%HH`|!$9_u5InJBwE=J<4QB{)u>y)IK8HaTaFC--#o0lF<"
    "!KyBL@OG<`X4OpQx=s^xm+>4nZ7RkTc7uHGC4M?F1y>$%gyG-h#GAr+W`jT2rOJ8VHXes`@q<{ttE%|(3&N+vPg5D4y+0FomWIJf"
    "J{z0W6EJE+GDujrBiWdM<A+Cr*($En9z}C(&WC%ui|Kk!4DNrO46fUFzdkV@Yb`S1>%KyY=Q?V2W-<6O7scr4Ox$<A2p$D9k8asi"
    ")ES!zE7_-PmqQ{yllSAeM?FwA7yBMr1Xk?(ysT3ij_jBZokwu5>`*e=wp|W$9oXx<eKKwyy$TWp&oS-i<LID0K)-S+ZRULJ{{25_"
    ";eCe@zf&<+ts0zIpSEmi20pDm3C1<qbjdOmAHZek!gn0Sz;x{P>?%BB4(hgHS-5lPOE_<lOXZ`p@pkHCn8Wv-Kkc$GM(rcaox=WK"
    "gR}8??>}&W*>p*9S*Vx)9n9D-FZacKoYd((oMXQI=zr<V5PJ_NREy|a{%mv@+o~>n2gl0-J<QE+7Rx8ds9%r~M!kG1c5ol2=#vR9"
    "b-yptd&=m>APdZ%*dXeQrL@i23OzQQ7A+U0)WFQ`L5;`6*S9h{{fK#?dey?GKt?st3;*um*s+$;@}%B4)@H3(&UM`&NpHMQW#SS4"
    "Z2Q#$55(t-l=qz1dRXA$g?XYA>$Oz>`eJ-}mN>(Dv$g8%!_vYGYSshXWIb5+HvSCv6Na;2-YSDcv7Bf3M!ct=G$2^4;huTGeZr!i"
    "uHrNIw2yENHX(6<82q1-!n(QO^n%XfVJ^pxu`50us3ih6C@H~o9L_y*Sv6gkdj)&Eadg&x)g+$Xw3_UT11(Ba6$NGFe3_Z6CdR6l"
    "p=He555%6SHMN7gm(%j7K+L-4J8IqiGHPNUirQvf$Ftqa=!R7&j)`t`9F(l2jw!)7a>WG64enP@bPUC+POBtJj`#S+iP)G^FWJiT"
    "Q-m<Q)O<j4`KW?=N5`R-_5(>(XC<js#p6tecJP#INX^D+7@6J`5(e@tiKgL6S4;TrsG#;miJ0p&7z%j4woQ8m8YU4q@C<q>-^WjA"
    "xkJ@I8C{(_16}id!AMU=mnY7|r4M7_CQ8XvG7~E`LqM^ylrGxEV}V8-6z?vf6`$jA;NU12dAykNp2o0uNj&JW-XMB4=b+r#U_7sg"
    "Oy(yt|1TZ(1s76m#4L>aSp?sCPP(Tl3H>G%Ltpk<N<BIaje3<rVV44W<e7w{J{H5fc=iIjm4-HJiolA!Ce_={LmgciTsz2qLqn2L"
    "F=rJtF^A+%dJ5*e-w1Zr97pEq_%iH2Fy(&r<*f@aW#?fS#`&efGz05i9fLm&+0;_K0Nwm9fz^p@I^dmw9$B}bRZ0$7w_AW?$2Y=o"
    ")~8KK&qmXNr!cZPn<nqi!G8OnLSWZyx+7hLeV1^I@ZN#8Zx+s~_yfDGId(=Z!lm7RLs7~iioKbRmt)_+F6J(FI+TY01Ar<B2>"
)
