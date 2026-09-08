"""Independent open-front puffer candidate; call after frozen puffer_shape_v5.

The back, folded front panels and sleeves are closed padded surfaces, joined by
a deterministic volume union. The front opening is actual negative space above
the existing black garment. This is authored geometry, not a cloth simulation.
No photographs, camera changes or network access are used at build time.
"""

from __future__ import annotations

import math
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import puffer_shape_v5 as base

TAG = "puffer_shape_v6_candidate"
COLLECTION = base.COLLECTION
BODY_NAME = base.BODY_NAME
TAU = math.tau

# World-space pose stays anchored to v5. The broad back is visible in reference
# 16; the two unequal front panels turn aside in reference 10 rather than making
# a zipped, complete chest rectangle. Hidden panel ownership is an inference.
SECTIONS = (
    (
        "collapsed back",
        (
            (0.205, 3.205, 0.275),
            (0.184, 3.158, 0.380),
            (0.178, 3.080, 0.484),
            (0.204, 2.973, 0.540),
            (0.185, 2.926, 0.479),
        ),
        ((0.204, 0.020), (0.243, 0.037), (0.236, 0.051), (0.205, 0.049), (0.164, 0.025)),
        1.7,
        False,
        0.07,
    ),
    (
        "left descending sleeve",
        base.LEFT_PATH,
        (
            (0.081, 0.068),
            (0.079, 0.060),
            (0.078, 0.042),
            (0.068, 0.039),
            (0.051, 0.037),
            (0.038, 0.024),
        ),
        2.9,
        True,
        -0.12,
    ),
    (
        "right folded sleeve",
        base.RIGHT_PATH,
        (
            (0.082, 0.068),
            (0.086, 0.053),
            (0.081, 0.035),
            (0.071, 0.037),
            (0.050, 0.032),
            (0.042, 0.025),
        ),
        5.6,
        True,
        0.18,
    ),
    (
        "right open front",
        (
            (0.340, 2.994, 0.520),
            (0.372, 2.932, 0.448),
            (0.345, 2.862, 0.364),
            (0.274, 2.813, 0.307),
            (0.230, 2.828, 0.292),
        ),
        ((0.068, 0.030), (0.081, 0.025), (0.080, 0.021), (0.068, 0.020), (0.045, 0.012)),
        7.3,
        False,
        -0.67,
    ),
    (
        "left folded front",
        (
            (0.090, 2.987, 0.532),
            (0.104, 3.023, 0.555),
            (0.155, 3.072, 0.519),
            (0.218, 3.095, 0.481),
        ),
        ((0.060, 0.027), (0.069, 0.029), (0.065, 0.026), (0.038, 0.014)),
        9.1,
        False,
        0.46,
    ),
)


def _section(label, path, radii, seed, cuff, twist, material, collection):
    """Closed ellipses with parallel-transport frames and local compression."""
    rings, sides = 180, 88
    centres = np.array([base._spline(path, i / rings) for i in range(rings + 1)])
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(centres, axis=0), axis=1))]
    angles = np.linspace(0, TAU, sides, endpoint=False)
    vertices, faces, samples, rows = [], [], [], []
    previous = None
    # More closely spaced channels, perturbed independently around each section.
    count = max(5, round(arc[-1] / 0.055))
    cuts = np.linspace(0, 1, count + 1)
    cuts[1:-1] += np.array([0.012 * math.sin(k * 2.79 + seed) for k in range(1, count)])
    for i, centre in enumerate(centres):
        t = i / rings
        tangent = centres[min(i + 1, rings)] - centres[max(0, i - 1)]
        tangent /= np.linalg.norm(tangent)
        reference = np.array([1.0, 0.0, 0.0]) if previous is None else previous
        side = reference - tangent * np.dot(reference, tangent)
        if np.linalg.norm(side) < 0.01:
            side = np.cross(tangent, np.array([0.0, 0.0, 1.0]))
        side /= np.linalg.norm(side)
        if previous is None and np.cross(tangent, side)[2] < 0:
            side *= -1
        previous = side.copy()
        normal = np.cross(tangent, side)
        turn = twist * math.sin(math.pi * t) + 0.09 * math.sin(5.2 * t + seed) * math.sin(
            math.pi * t
        )
        s = side * math.cos(turn) + normal * math.sin(turn)
        n = normal * math.cos(turn) - side * math.sin(turn)
        width, depth = base._spline(radii, t)
        skew = (0.025 * np.sin(angles * 2 + seed) + 0.014 * np.sin(angles * 5 + seed)) * math.sin(
            math.pi * t
        )
        phase = t + skew
        channel = np.zeros(sides)
        loft = np.zeros(sides)
        for k, (lo, hi) in enumerate(zip(cuts[:-1], cuts[1:])):
            fraction = np.clip((phase - lo) / (hi - lo), 0, 1)
            loft += (
                0.0035
                * np.sin(np.pi * fraction) ** 0.8
                * (0.65 + 0.35 * np.sin(angles * 3.2 + seed + k) ** 2)
            )
        for k, c in enumerate(cuts[1:-1]):
            local = c + 0.012 * np.sin(3 * angles + k * 1.41) * math.sin(math.pi * c)
            channel += np.exp(-(((phase - local) / 0.0045) ** 2))
        crease = np.zeros(sides)
        # Local pinch pairs vary in orientation, extent and depth; no regular
        # sine-strip displacement spans the whole garment.
        for k in range(57):
            u = 0.025 + 0.95 * ((k * 0.61803398875 + seed * 0.19) % 1)
            phi = TAU * ((k * 0.38196601125 + seed * 0.17) % 1)
            a = np.arctan2(np.sin(angles - phi), np.cos(angles - phi))
            line = u + 0.032 * math.sin(k + seed) * a + 0.014 * np.sin(2.5 * a + k)
            w = 0.008 + 0.010 * ((k * 0.173 + seed) % 1)
            d = 0.0012 + 0.0022 * ((k * 0.713 + seed * 0.31) % 1)
            env = np.exp(-((a / (0.32 + 0.5 * ((k * 0.419) % 1))) ** 2))
            crease -= d * np.exp(-(((t - line) / w) ** 2)) * env
            crease += d * 0.3 * np.exp(-(((t - line - w * 1.5) / (w * 0.6)) ** 2)) * env
        crease *= math.sqrt(max(0, math.sin(math.pi * t)))
        q = centre + np.outer((width * (1 - 0.015 * channel) + crease) * np.cos(angles), s)
        q += np.outer((depth + loft - 0.0025 * channel + crease) * np.sin(angles), n)
        rows.append(q)
        vertices.extend(q.tolist())
        samples.extend((tuple(p), t, a, seed) for p, a in zip(q, angles))
    sample_faces = []
    for i in range(rings):
        for j in range(sides):
            a = i * sides + j
            b = i * sides + (j + 1) % sides
            faces.append((a, b, b + sides, a + sides))
            sample_faces.extend(((a, b, b + sides), (a, b + sides, a + sides)))
    faces.append(tuple(range(sides - 1, -1, -1)))
    last = rings * sides
    if cuff:
        start = len(vertices)
        direction = centres[-1] - centres[-2]
        direction /= np.linalg.norm(direction)
        inside = centres[-1] + (rows[-1] - centres[-1]) * 0.72 - direction * 0.019
        vertices.extend(inside.tolist())
        for j in range(sides):
            faces.append((last + j, last + (j + 1) % sides, start + (j + 1) % sides, start + j))
        faces.append(tuple(start + j for j in range(sides)))
    else:
        faces.append(tuple(last + j for j in range(sides)))
    ob = base._mesh("Puffer V6 " + label, vertices, faces, material, collection)
    seams = []
    # Follow the actual perturbed stitch valley, avoiding straight parallel
    # rings pasted across a warped sleeve.
    for k, c in enumerate(cuts[1:-1]):
        line = []
        for j, a in enumerate(angles):
            u = c + 0.012 * math.sin(3 * a + k * 1.41) * math.sin(math.pi * c)
            u -= (0.025 * math.sin(2 * a + seed) + 0.014 * math.sin(5 * a + seed)) * math.sin(
                math.pi * u
            )
            r = np.clip(u * rings, 0, rings - 0.001)
            ri = int(r)
            f = r - ri
            line.append(rows[ri][j] * (1 - f) + rows[ri + 1][j] * f)
        seams.append((label + " quilt %02d" % k, line + line[:1], 0.00026))
    if cuff:
        seams.append((label + " folded cuff edge", list(rows[-1]) + [rows[-1][0]], 0.0009))
    if "front" in label:
        # Bound free edge, deliberately away from the centre opening.
        j = round(sides * 0.25)
        seams.append((label + " exposed zip binding", [row[j] for row in rows], 0.0014))
    widths = np.array(radii).mean(0)
    perimeter = math.pi * (
        3 * sum(widths) - math.sqrt((3 * widths[0] + widths[1]) * (widths[0] + 3 * widths[1]))
    )
    return (
        ob,
        seams,
        samples,
        sample_faces,
        {
            "axis_length_m": float(arc[-1]),
            "chart_perimeter_m": perimeter,
            "sections": rings + 1,
            "radial_samples": sides,
            "quilt_channels": count,
            "seed": seed,
        },
    )


def _maps(directory):
    """Create portable authored numeric PBR coupons; no photographic inputs."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    normal_path = directory / "puffer_v6_crumpled_nylon_normal_r3.png"
    rough_path = directory / "puffer_v6_crumpled_nylon_roughness_r3.png"
    if normal_path.exists() and rough_path.exists():
        return normal_path, rough_path
    size = 1024
    extent = 0.24
    row, col = np.mgrid[0:size, 0:size].astype(np.float32)
    x = (col + 0.5) / size * extent
    y = (row + 0.5) / size * extent
    # Wrinkled nylon is not flat between isolated incised lines. Here small
    # irregularly warped panels have different slopes, with rounded crease
    # transitions. Piecewise triangular height fields break wide reflections
    # over the whole surface, without broad smooth Noise blobs.
    xx = x + 0.0012 * np.sin(TAU * y / 0.06) + 0.0007 * np.sin(TAU * (x + y) / 0.04)
    yy = y + 0.0016 * np.sin(TAU * x / 0.08) + 0.0008 * np.cos(TAU * (y - x) / 0.12)

    def facets(cells, amplitude, seed):
        rng = np.random.default_rng(seed)
        grid = rng.normal(0, amplitude, (cells, cells)).astype(np.float32)
        flip = rng.integers(0, 2, (cells, cells)).astype(bool)
        gx = xx / extent * cells
        gy = yy / extent * cells
        ix = np.floor(gx).astype(np.int32)
        iy = np.floor(gy).astype(np.int32)
        u = gx - ix
        v = gy - iy
        ix %= cells
        iy %= cells
        a = grid[iy, ix]
        b = grid[iy, (ix + 1) % cells]
        c = grid[(iy + 1) % cells, ix]
        d = grid[(iy + 1) % cells, (ix + 1) % cells]
        first = np.where(
            u + v < 1, a * (1 - u - v) + b * u + c * v, b * (1 - v) + c * (1 - u) + d * (u + v - 1)
        )
        second = np.where(
            u > v, a * (1 - u) + b * (u - v) + d * v, a * (1 - v) + c * (v - u) + d * u
        )
        return np.where(flip[iy, ix], first, second)

    height = facets(48, 0.00042, 6019) + facets(24, 0.00050, 6020) + facets(16, 0.00038, 6021)
    # Round the slope transitions over about 0.4 mm while retaining the tilted
    # regions on both sides. Periodic padding keeps the coupon seamless.
    for _ in range(3):
        height = (
            4 * height
            + np.roll(height, 1, 0)
            + np.roll(height, -1, 0)
            + np.roll(height, 1, 1)
            + np.roll(height, -1, 1)
        ) / 8
    dx = (np.roll(height, -1, 1) - np.roll(height, 1, 1)) / (2 * extent / size)
    dy = (np.roll(height, -1, 0) - np.roll(height, 1, 0)) / (2 * extent / size)
    normals = np.stack((-dx, dy, np.ones_like(dx)), axis=-1)
    normals /= np.linalg.norm(normals, axis=-1)[..., None]
    rgba = np.ones((size, size, 4), dtype=np.float32)
    rgba[:, :, :3] = normals * 0.5 + 0.5

    # Blender pixels are bottom-up; image row derivative above used top-down.
    def save(name, path, values):
        im = bpy.data.images.new(name, width=size, height=size, alpha=False)
        im.colorspace_settings.name = "Non-Color"
        im.pixels.foreach_set(values[::-1].ravel())
        im.filepath_raw = str(path)
        im.file_format = "PNG"
        im.save()
        bpy.data.images.remove(im)

    save("V6 authored clustered crease normal", normal_path, rgba)
    rough = (
        0.335
        + np.clip(-height / 0.003, -0.035, 0.075)
        + 0.008 * np.sin(x * 1700) * np.sin(y * 1930)
    )
    rgba[:, :, :3] = rough[:, :, None]
    save("V6 authored nylon roughness", rough_path, rgba)
    return normal_path, rough_path


def _material(old, directory):
    material = old.copy()
    material.name = "PROP / puffer V6 crumpled midnight nylon"
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    normal_path, rough_path = _maps(directory)
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "Garment metres"
    uv.label = "Physical coupon: 0.24 m repeat"
    normal = nodes.new("ShaderNodeTexImage")
    normal.image = bpy.data.images.load(str(normal_path), check_existing=True)
    normal.image.colorspace_settings.name = "Non-Color"
    normal.interpolation = "Linear"
    rough = nodes.new("ShaderNodeTexImage")
    rough.image = bpy.data.images.load(str(rough_path), check_existing=True)
    rough.image.colorspace_settings.name = "Non-Color"
    rough.interpolation = "Linear"
    mapping = nodes.new("ShaderNodeNormalMap")
    mapping.space = "TANGENT"
    mapping.uv_map = "Garment metres"
    mapping.inputs["Strength"].default_value = 0.70
    links.new(uv.outputs["UV"], normal.inputs["Vector"])
    links.new(uv.outputs["UV"], rough.inputs["Vector"])
    links.new(normal.outputs["Color"], mapping.inputs["Color"])
    for socket in (bsdf.inputs["Normal"], bsdf.inputs["Roughness"]):
        for link in list(socket.links):
            links.remove(link)
    links.new(mapping.outputs["Normal"], bsdf.inputs["Normal"])
    links.new(rough.outputs["Color"], bsdf.inputs["Roughness"])
    bsdf.inputs["Anisotropic"].default_value = 0
    material["surface_recipe"] = (
        "Authored 5/10/15 mm crumpled panels with rounded slope transitions; 0.24 m coupon"
    )
    return material, {
        "normal": str(normal_path),
        "roughness": str(rough_path),
        "coupon_size_m": 0.24,
        "normal_strength": 0.70,
        "roughness_centre": 0.335,
        "images_authored_from_numeric_fields": True,
        "base_colour_and_reflectance_retained": True,
    }


def _detail(body, samples, triangles, stats):
    """Continuous source section chart for real relief and metre-scaled UVs."""
    positions = [Vector(s[0]) for s in samples]
    attributes = np.array([(s[1], math.sin(s[2]), math.cos(s[2])) for s in samples])
    tree = BVHTree.FromPolygons(positions, triangles, all_triangles=True)
    count = len(body.data.vertices)
    parameters = np.empty((count, 4))
    points = np.empty((count, 3))
    normals = np.empty((count, 3))
    for i, v in enumerate(body.data.vertices):
        co, _, index, distance = tree.find_nearest(v.co)
        ia, ib, ic = triangles[index]
        pa, pb, pc = positions[ia], positions[ib], positions[ic]
        ab = pb - pa
        ac = pc - pa
        aq = co - pa
        aa = ab.dot(ab)
        bb = ab.dot(ac)
        cc = ac.dot(ac)
        dd = aq.dot(ab)
        ee = aq.dot(ac)
        denominator = aa * cc - bb * bb
        vv = (cc * dd - bb * ee) / denominator
        ww = (aa * ee - bb * dd) / denominator
        uu = 1 - vv - ww
        att = attributes[ia] * uu + attributes[ib] * vv + attributes[ic] * ww
        parameters[i] = (
            float(np.clip(att[0], 0, 1)),
            math.atan2(att[1], att[2]),
            samples[ia][3],
            distance,
        )
        points[i] = v.co
        normals[i] = v.normal
    edges = np.array([tuple(e.vertices) for e in body.data.edges], dtype=int)
    a, b = edges.T
    for _ in range(4):
        summed = normals * 3
        np.add.at(summed, a, normals[b])
        np.add.at(summed, b, normals[a])
        normals = summed / np.maximum(np.linalg.norm(summed, axis=1)[:, None], 1e-12)
    displacement = np.zeros(count)
    uvs = np.zeros((count, 2))
    periods = np.zeros(count)
    for item in stats.values():
        seed = item["seed"]
        mask = np.isclose(parameters[:, 2], seed)
        t = parameters[mask, 0]
        angle = parameters[mask, 1]
        height = np.zeros(len(t))
        for k in range(145):
            centre = 0.025 + 0.95 * ((k * 0.61803398875 + seed * 0.139) % 1)
            phi = TAU * ((k * 0.38196601125 + seed * 0.297) % 1)
            delta = np.arctan2(np.sin(angle - phi), np.cos(angle - phi))
            line = (
                centre
                + 0.043 * math.sin(k * 2.34 + seed) * delta
                + 0.013 * np.sin(delta * 3 + seed + k)
            )
            width = 0.007 + 0.008 * ((k * 0.236 + seed * 0.31) % 1)
            amplitude = 0.0013 + 0.0023 * ((k * 0.71 + seed * 0.13) % 1)
            envelope = np.exp(-((delta / (0.32 + 0.5 * ((k * 0.429 + seed * 0.25) % 1))) ** 2))
            height -= amplitude * np.exp(-(((t - line) / width) ** 2)) * envelope
            height += (
                amplitude
                * 0.4
                * np.exp(-(((t - line - width * 1.5) / (width * 0.64)) ** 2))
                * envelope
            )
        weight = np.sqrt(np.maximum(0, np.sin(np.pi * t))) * np.clip(
            1 - (parameters[mask, 3] - 0.002) / 0.006, 0, 1
        )
        displacement[mask] = np.clip(height, -0.0035, 0.0020) * weight
        period = item["chart_perimeter_m"] / 0.24
        uvs[mask, 0] = (angle / TAU) * period
        uvs[mask, 1] = t * item["axis_length_m"] / 0.24
        periods[mask] = period
    protected = base._protect_relief_intersections(body, points, normals, displacement)
    layer = body.data.uv_layers.new(name="Garment metres")
    values = np.empty((len(body.data.loops), 2), dtype=np.float32)
    for polygon in body.data.polygons:
        ids = np.array(polygon.vertices)
        uv = uvs[ids].copy()
        if np.ptp(parameters[ids, 1]) > math.pi and np.ptp(parameters[ids, 2]) < 1e-4:
            uv[parameters[ids, 1] < 0, 0] += periods[ids][parameters[ids, 1] < 0]
        values[np.array(polygon.loop_indices)] = uv
    layer.data.foreach_set("uv", values.ravel())
    return {
        "physical_relief_range_m": [float(displacement.min()), float(displacement.max())],
        "localized_geometry_creases_per_section": 145,
        "intersection_protection": protected,
        "uv_name": layer.name,
        "uv_coupon_repeat_m": 0.24,
        "continuous_section_parameter_transfer": True,
    }


def _black_opening(collection, body):
    """Supported closed black volume, never a hole through to the pale layers.

    A positive affine X expansion fills the observed wedge; a ray-bounded height
    field seats its underside on the already-compressed clothes. Both sheets
    retain matching XY grids, so the new volume does not turn inside out.
    """
    ob = bpy.data.objects["Folded clothing V3 central black outerwear"]
    p, refs = base._world_points(ob)
    count = 65 * 77
    if len(p) != 2 * count:
        raise ValueError("Black support topology changed")
    support_vertices = []
    support_faces = []
    for other in collection.all_objects:
        if (
            other == ob
            or other.type != "MESH"
            or not other.name.startswith(
                ("Folded clothing", "Grey shirt", "Light blue loose garment")
            )
        ):
            continue
        q, _ = base._world_points(other)
        offset = len(support_vertices)
        support_vertices.extend(q.tolist())
        support_faces.extend(tuple(offset + k for k in f.vertices) for f in other.data.polygons)
    support = BVHTree.FromPolygons(support_vertices, support_faces)
    xy = p[:count, :2].copy()
    xy[:, 0] = -0.2245 + (xy[:, 0] + 0.2245) * 1.32
    lo = xy.min(0) - 0.030
    hi = xy.max(0) + 0.030
    pitch = 0.004
    nx, ny = np.ceil((hi - lo) / pitch).astype(int) + 1
    floor_map = np.full((nx, ny), 0.157)
    for i in range(nx):
        for j in range(ny):
            x, y = lo + np.array((i, j)) * pitch
            hit = support.ray_cast(Vector((x, y, 1.0)), Vector((0, 0, -1)), 1)
            if hit[0] is not None:
                floor_map[i, j] = hit[0].z + 0.004
    # Conservative support envelope covers the finite triangles between black
    # control points. Point-only rays previously let these span sharp edges.
    padded = np.pad(floor_map, 3, mode="edge")
    floor_map = np.maximum.reduce(
        [padded[i : i + nx, j : j + ny] for i in range(7) for j in range(7)]
    )

    def floor_at(x, y):
        ij = (np.array((x, y)) - lo) / pitch
        a = np.floor(ij).astype(int)
        u, v = ij - a
        i, j = a
        return (
            (1 - u) * (1 - v) * floor_map[i, j]
            + u * (1 - v) * floor_map[i + 1, j]
            + (1 - u) * v * floor_map[i, j + 1]
            + u * v * floor_map[i + 1, j + 1]
        )

    maximum = 0.0
    minimum_thickness = 1.0
    for j in range(77):
        for i in range(65):
            k = j * 65 + i
            x, y, z = p[k]
            x = -0.2245 + (x + 0.2245) * 1.32
            interior = max(0, math.sin(math.pi * i / 64) * math.sin(math.pi * j / 76)) ** 0.62
            floor = floor_at(x, y)
            loft = (
                0.205 * math.exp(-(((x - 0.205) / 0.23) ** 2) - ((y - 2.94) / 0.25) ** 2) * interior
            )
            loft += (
                0.038
                * math.exp(
                    -(((x - 0.09 + 0.5 * (y - 2.92)) / 0.042) ** 2) - ((y - 2.91) / 0.19) ** 2
                )
                * interior
            )
            top = floor + 0.002 + loft
            p[k] = (x, y, top)
            p[k + count] = (x, y, floor)
            maximum = max(maximum, top - z)
            minimum_thickness = min(minimum_thickness, top - floor)
    base._write(ob, refs, p)
    black_tree = BVHTree.FromPolygons(
        [Vector(v) for v in p], [tuple(f.vertices) for f in ob.data.polygons]
    )
    for other in collection.all_objects:
        if other.type != "CURVE" or not other.name.startswith(ob.name):
            continue
        q, curve_refs = base._world_points(other)
        q[:, 0] = -0.2245 + (q[:, 0] + 0.2245) * 1.32
        for point in q:
            hit = black_tree.ray_cast(Vector((point[0], point[1], 1.0)), Vector((0, 0, -1)), 1)
            if hit[0] is not None:
                point[2] = hit[0].z + 0.0004
        base._write(other, curve_refs, q)
    return {
        "maximum_inner_mound_lift_m": maximum,
        "minimum_thickness_m": minimum_thickness,
        "closed_paired_height_field": True,
        "x_expansion": 1.32,
        "supported_by_actual_clothes_rays": True,
        "support_envelope_pitch_m": pitch,
        "support_dilation_radius_m": 0.012,
        "subsequent_shared_positive_height_compression": True,
    }


def _layer_clearance(collection):
    """Independent triangle interpolation needs a small final layer gap.

    The shared nonlinear height map preserves continuous point ordering, but
    separately triangulated sheets approximate it differently. The upper blue
    fold and black layer receive bounded, explicitly modelled clearance.
    """
    records = {}
    for prefix, clearance in (
        ("Folded clothing V3 blue returned trouser leg 1", 0.0015),
        ("Folded clothing V3 central black outerwear", 0.0030),
    ):
        changed = []
        for ob in collection.all_objects:
            if not ob.name.startswith(prefix):
                continue
            points, refs = base._world_points(ob)
            if not len(points):
                continue
            points[:, 2] += clearance
            base._write(ob, refs, points)
            changed.append(ob.name)
        records[prefix] = {"vertical_clearance_m": clearance, "objects": changed}
    prefix = "Folded clothing V3 cream returned trouser leg 1"
    changed = []
    for ob in collection.all_objects:
        if not ob.name.startswith(prefix):
            continue
        points, refs = base._world_points(ob)
        if not len(points):
            continue
        height = np.maximum(points[:, 2] - 0.1485, 0)
        # Derivative is at least 0.5: layer thickness and ordering remain
        # positive while the lower cream fold settles by at most 3 mm.
        points[:, 2] -= 0.003 * (1 - np.exp(-height / 0.006))
        base._write(ob, refs, points)
        changed.append(ob.name)
    records[prefix] = {
        "maximum_downward_settle_m": 0.003,
        "support_floor_m": 0.1485,
        "objects": changed,
    }
    return records


def _refine_contact_meshes(collection):
    """Resolve curved compression before sampling it on the two overlapping folds.

    Their original flattened cross sections contain 20-25 mm spans. A 6 mm
    spatial height map cannot safely be approximated by those triangles. The
    subdivision changes sampling density, not the pre-compression shape.
    """
    reports = {}
    for name in (
        "Folded clothing V3 cream returned trouser leg 1",
        "Folded clothing V3 blue returned trouser leg 1",
    ):
        ob = bpy.data.objects[name]
        before = len(ob.data.vertices)
        bm = base.bmesh.new()
        bm.from_mesh(ob.data)
        base.bmesh.ops.subdivide_edges(bm, edges=list(bm.edges), cuts=3, use_grid_fill=True)
        base.bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(ob.data)
        bm.free()
        ob.data.update()
        reports[name] = {
            "vertices_before": before,
            "vertices_after": len(ob.data.vertices),
            "edge_subdivisions": 4,
        }
    return reports


def refine_puffer_shape():
    """Replace only an already-applied v5 garment, preserving its luggage pose."""
    collection = bpy.data.collections.get(COLLECTION)
    if collection is None or not collection.get(base.TAG):
        raise ValueError("Apply frozen puffer_shape_v5.rebuild_puffer_shape() first")
    if collection.get(TAG):
        return {"status": "already_applied", "candidate": True}
    old = bpy.data.objects.get(BODY_NAME)
    if old is None:
        raise ValueError("V5 coat is missing")
    old_material = old.data.materials[0]
    seam = next(
        (m for m in bpy.data.materials if "puffer stitched seams" in m.name.lower()), old_material
    )
    material, shader = _material(
        old_material, Path(__file__).resolve().parents[1] / "assets/textures"
    )
    for ob in list(collection.all_objects):
        if ob.name.startswith("Puffer"):
            bpy.data.objects.remove(ob, do_unlink=True)
    parts = []
    seams = []
    samples = []
    triangles = []
    section_stats = {}
    for label, path, radii, seed, cuff, twist in SECTIONS:
        ob, lines, points, faces, stats = _section(
            label, path, radii, seed, cuff, twist, material, collection
        )
        offset = len(samples)
        samples.extend(points)
        triangles.extend(tuple(offset + i for i in f) for f in faces)
        parts.append(ob)
        seams.extend(lines)
        section_stats[label] = stats
    body, topology = base._union(parts, material, collection)
    detail = _detail(body, samples, triangles, section_stats)
    tree = BVHTree.FromPolygons(
        [v.co for v in body.data.vertices], [tuple(f.vertices) for f in body.data.polygons]
    )
    for name, points, radius in seams:
        line = []
        for point in points:
            hit = tree.find_nearest(Vector(point))
            if hit[0] is not None and hit[3] < 0.006:
                line.append(tuple(hit[0] + hit[1] * radius * 0.4))
            else:
                if len(line) > 3:
                    base._curve("Puffer V6 " + name, line, radius, seam, collection)
                line = []
        if len(line) > 3:
            base._curve("Puffer V6 " + name, line, radius, seam, collection)
    contact_refinement = _refine_contact_meshes(collection)
    support = base._compress_support(list(collection.all_objects), body)
    black = _black_opening(collection, body)
    black["final_common_compression"] = base._compress_support(list(collection.all_objects), body)
    black["final_layer_clearance"] = _layer_clearance(collection)
    collection[TAG] = True
    body["construction"] = (
        "Closed padded back and asymmetric open front panels with compressed sleeve sections"
    )
    return {
        "status": "applied",
        "candidate": True,
        "topology": topology,
        "sections": section_stats,
        "detail": detail,
        "material": shader,
        "black_support": black,
        "support": support,
        "contact_mesh_sampling": contact_refinement,
        "dependency": "Frozen puffer_shape_v5 applied first; no v5 files are modified",
        "limitations": [
            "Panel ownership and unseen fold geometry are inferred, not measured",
            "No cloth or pressure simulation is claimed",
            "Actual camera rendering and independent contact audit are required before adoption",
        ],
    }
