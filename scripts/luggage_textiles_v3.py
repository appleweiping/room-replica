"""Compressed, folded garments packed into the open suitcase.

All shapes are authored in metres and deterministic. Names retain the support
prefixes consumed by ``props_helpers_v2._puffer_support``. No scene is saved.
"""

from __future__ import annotations

import math

from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.noise import noise

TAU = math.tau


def _n(x, y, seed=0):
    return noise(Vector((x + 17.31, y - 9.74, seed + 3.89)))


def _cloth_material(h, name, color, knit=False, roughness=0.87):
    mat = h["material"](name, color, roughness)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    p = nodes.get("Principled BSDF")
    p.inputs["Specular IOR Level"].default_value = 0.24
    p.inputs["Sheen Weight"].default_value = 0.22 if knit else 0.11
    p.inputs["Sheen Roughness"].default_value = 0.82
    mat.diffuse_color = (*color, 1)
    co = nodes.new("ShaderNodeTexCoord")
    fibers = nodes.new("ShaderNodeTexNoise")
    fibers.inputs["Scale"].default_value = 800 if knit else 1300
    fibers.inputs["Detail"].default_value = 2
    links.new(co.outputs["Object"], fibers.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.18
    ramp.color_ramp.elements[0].color = (*([0.67 if knit else 0.9] * 3), 1)
    ramp.color_ramp.elements[1].position = 0.82
    ramp.color_ramp.elements[1].color = (*([1.20 if knit else 1.07] * 3), 1)
    links.new(fibers.outputs["Fac"], ramp.inputs["Fac"])
    # The explicit constant multiplier is recognized as baseColorFactor by
    # Blender's glTF exporter; direct procedural ColorRamp links export white.
    tint = nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.clamp_result = False
    tint.inputs[0].default_value = 1
    tint.inputs[6].default_value = (*color, 1)
    links.new(ramp.outputs["Color"], tint.inputs[7])
    links.new(tint.outputs[2], p.inputs["Base Color"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.24
    bump.inputs["Distance"].default_value = 0.00040 if knit else 0.00016
    links.new(fibers.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return mat


def _uv(ob, coordinates):
    layer = ob.data.uv_layers.new(name="UVMap")
    for polygon in ob.data.polygons:
        for i in polygon.loop_indices:
            layer.data[i].uv = coordinates[ob.data.loops[i].vertex_index]
    return ob


def _panel(h, name, fn, material, nx=64, ny=76):
    """Filled textile with soft edges; matched triangles on top and underside."""
    vertices, uv, faces = [], [], []
    for under in (False, True):
        for j in range(ny + 1):
            for i in range(nx + 1):
                vertices.append(fn(i / nx, j / ny, under))
                uv.append((i / nx, j / ny))
    count = (nx + 1) * (ny + 1)
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces += [
                (a, a + 1, a + nx + 2),
                (a, a + nx + 2, a + nx + 1),
                (a + count, a + count + nx + 2, a + count + 1),
                (a + count, a + count + nx + 1, a + count + nx + 2),
            ]
    boundary = (
        list(range(nx + 1))
        + [j * (nx + 1) + nx for j in range(1, ny + 1)]
        + [ny * (nx + 1) + i for i in range(nx - 1, -1, -1)]
        + [j * (nx + 1) for j in range(ny - 1, 0, -1)]
    )
    for i, a in enumerate(boundary):
        b = boundary[(i + 1) % len(boundary)]
        faces.append((a, a + count, b + count, b))
    return _uv(h["mesh"](name, vertices, faces, material), uv)


def _surface_support(objects, fallback=0.156):
    vertices, faces = [], []
    for ob in objects:
        offset = len(vertices)
        vertices.extend(tuple(v.co) for v in ob.data.vertices)
        faces.extend(tuple(offset + i for i in p.vertices) for p in ob.data.polygons)
    tree = BVHTree.FromPolygons(vertices, faces) if vertices else None

    def support(x, y):
        if tree:
            height = fallback
            # A small conservative footprint keeps triangles between samples
            # above an underlying crease, rather than cutting through it.
            for dx, dy in (
                (0, 0),
                (0.006, 0),
                (-0.006, 0),
                (0, 0.006),
                (0, -0.006),
                (0.0042, 0.0042),
                (-0.0042, 0.0042),
                (0.0042, -0.0042),
                (-0.0042, -0.0042),
            ):
                result = tree.ray_cast(Vector((x + dx, y + dy, 0.60)), Vector((0, 0, -1)), 0.50)
                if result[0] is not None:
                    height = max(height, result[0].z)
            return height
        return fallback

    return support


def _folded_leg(h, name, x, start_y, length, width, bottom, material, seam, phase, support=None):
    """A trouser leg travels out, turns through a soft U fold and returns above itself."""
    n, sides = 116, 48
    fold_y = start_y + length
    fold_radius = 0.014
    vertices, faces, uv = [], [], []
    points, inner_vertices = [], []
    for i in range(n + 1):
        t = i / n
        if t < 0.44:
            q = t / 0.44
            y, z = start_y + length * q, bottom + 0.010
            tangent = Vector((0, 1, 0))
        elif t < 0.62:
            a = (t - 0.44) / 0.18 * math.pi
            y = fold_y + fold_radius * math.sin(a)
            z = bottom + 0.010 + fold_radius * (1 - math.cos(a))
            tangent = Vector((0, math.cos(a), math.sin(a)))
        else:
            q = (t - 0.62) / 0.38
            y, z = fold_y - length * 0.84 * q, bottom + 0.038
            tangent = Vector((0, -1, 0))
        xx = x + 0.010 * math.sin(t * 4.7 + phase)
        z += 0.003 * _n(t * 7, phase, 1)
        across = Vector((1, 0, 0))
        up = across.cross(tangent).normalized()
        ring = []
        for j in range(sides):
            a = TAU * j / sides
            ca, sa = math.cos(a), math.sin(a)
            # Flattened, softly squared section with a slightly gathered selvedge.
            taper = 1 - 0.12 * t + 0.045 * math.sin(t * 8 + phase)
            dx = width * taper * 0.5 * math.copysign(abs(ca) ** 0.60, ca)
            dz = 0.0075 * math.copysign(abs(sa) ** 0.72, sa)
            dz += 0.0018 * _n(t * 36, ca * 5, sa * 5 + phase) * abs(sa)

            def shaped(inner=False):
                p = (
                    Vector((xx, y, z))
                    + across * dx * (0.98 if inner else 1)
                    + up * dz * (0.64 if inner else 1)
                )
                end = math.exp(-((t / 0.10) ** 2)) + math.exp(-(((1 - t) / 0.12) ** 2))
                p.y += 0.013 * math.sin(ca * 3.2 + phase) * end
                # Shared spatial drape keeps stacked legs separated while removing
                # the rigid, ruler-straight pressed-trouser silhouette.
                ridge = 0.013 * math.exp(-(((p.y - 2.30 - p.x * 0.20) / 0.025) ** 2))
                p.z += max(
                    0,
                    0.006 * math.sin(p.y * 34 + p.x * 9)
                    + 0.004 * _n(p.x * 31, p.y * 24, 3)
                    + ridge,
                )
                p.z += 0.007 * (1 + math.sin(ca * 3.1 + phase)) * end
                if support is not None:
                    p.z += max(0, support(p.x, p.y) + 0.001 - bottom)
                return p

            p = shaped()
            inner_vertices.append(tuple(shaped(True)))
            ring.append(tuple(p))
            vertices.append(tuple(p))
            uv.append((j / sides, t))
        points.append(ring)
    for i in range(n):
        for j in range(sides):
            a, b = i * sides + j, i * sides + (j + 1) % sides
            faces.append((a, a + sides, b + sides, b))
    outer_count = len(vertices)
    vertices.extend(inner_vertices)
    uv.extend(uv[:])
    # An actual thin inner tube and annular cuff replace the opaque flat end cap.
    outer_faces = faces[:]
    faces.extend(tuple(i + outer_count for i in reversed(f)) for f in outer_faces)
    for end in (0, n):
        for j in range(sides):
            a, b = end * sides + j, end * sides + (j + 1) % sides
            f = (a, b, b + outer_count, a + outer_count)
            faces.append(f if end == 0 else tuple(reversed(f)))
    ob = _uv(h["mesh"](name, vertices, faces, material), uv)
    for j in (0, sides // 2):
        h["tube"](name + " pressed side seam", [ring[j] for ring in points], 0.00030, material)
    h["tube"](name + " turned trouser cuff", points[-1] + points[-1][:1], 0.00040, material)
    return ob


def _shirt_sheet(h, name, center, size, material, seam, seed, support, raised=0.030):
    cx, cy = center
    sx, sy = size

    def surface(u, v, under=False):
        # An irregular garment outline, softened corners and an asymmetric hem.
        # This rounded-rectangle map has positive area even for the small hem.
        # A fixed centimetre corner offset inverted the earlier small panels.
        x = cx + (u - 0.5) * sx * math.sqrt(1 - 0.16 * (2 * v - 1) ** 8)
        y = cy + (v - 0.5) * sy * math.sqrt(1 - 0.16 * (2 * u - 1) ** 8)
        x += sx * 0.015 * math.sin(v * 9 + seed)
        y += sy * 0.015 * math.sin(u * 7 + seed)
        inside = max(0, math.sin(math.pi * u) * math.sin(math.pi * v)) ** 0.45
        mound = raised * (
            0.48 + 0.52 * math.exp(-(((u - 0.34) / 0.25) ** 2) - ((v - 0.66) / 0.29) ** 2)
        )
        wrinkles = 0.007 * _n(u * 9, v * 13, seed) + 0.0021 * _n(u * 28, v * 31, seed + 2)
        ridges = 0
        for cu, cv, slope, height, extent in [
            (0.23, 0.31, 0.45, 0.018, 0.27),
            (0.60, 0.65, -0.49, 0.023, 0.29),
            (0.76, 0.21, 0.73, 0.015, 0.19),
        ]:
            d = v - cv - slope * (u - cu)
            ridges += height * math.exp(-((d / 0.040) ** 2) - ((u - cu) / extent) ** 2)
        base = support(x, y) + 0.006
        # Soft edge turnover gives thickness and round folds without square boards.
        edge_lift = 0.010 * (1 + math.sin(u * 13 + v * 5 + seed)) + 0.015 * math.exp(
            -(((u - 0.27) / 0.19) ** 2) - ((v - 0.06) / 0.12) ** 2
        )
        lower = base + edge_lift * (1 - inside)
        if under:
            return (x, y, lower)
        loose_fold = 0.027 * math.exp(
            -(((v - 0.16 - 0.20 * (u - 0.5)) / 0.029) ** 2) - ((u - 0.32) / 0.25) ** 2
        ) + 0.021 * math.exp(
            -(((v - 0.23 + 0.48 * (u - 0.7)) / 0.037) ** 2) - ((u - 0.76) / 0.23) ** 2
        )
        return (x, y, lower + 0.003 + max(0.002, mound + wrinkles + ridges + loose_fold) * inside)

    ob = _panel(h, name, surface, material)
    for v in (0.025, 0.975):
        h["tube"](
            name + " soft double stitched hem",
            [surface(i / 100, v) for i in range(101)],
            0.00032,
            material,
        )
    return ob, surface


def _ribbed_opening(h, name, center, radii, material, seam, surface):
    """A compressed annular neckline above the folded knit body."""
    cx, cy = center
    rx, ry = radii
    sides = 96
    vertices, faces = [], []
    for ring in range(4):
        factor = (1.0, 1.10, 0.78, 0.75)[ring]
        height = (0.005, 0.019, 0.025, 0.006)[ring]
        for j in range(sides):
            a = TAU * j / sides
            x, y = cx + rx * math.cos(a) * factor, cy + ry * math.sin(a) * factor
            z = surface(x, y) + height + 0.0012 * math.sin(a * 24)
            vertices.append((x, y, z))
    for ring in range(4):
        for j in range(sides):
            a, b = ring * sides + j, ring * sides + (j + 1) % sides
            faces.append(
                (a, b, ((ring + 1) % 4) * sides + (j + 1) % sides, ((ring + 1) % 4) * sides + j)
            )
    ob = h["mesh"](name, vertices, faces, material)
    h["tube"](
        name + " knitted neckline stitching",
        vertices[sides : 2 * sides] + vertices[sides : sides + 1],
        0.0005,
        seam,
    )
    return ob


def build_luggage_textiles(h):
    """Replace the old flat stack, retaining the same box and puffer support footprint."""
    cream = _cloth_material(h, "LUGGAGE V3 washed ivory trouser cotton", (0.46, 0.43, 0.35))
    blue = _cloth_material(
        h, "LUGGAGE V3 pale blue rumpled cotton", (0.29, 0.49, 0.57), roughness=0.89
    )
    grey = _cloth_material(h, "LUGGAGE V3 grey marl sweater knit", (0.28, 0.30, 0.31), knit=True)
    dark = _cloth_material(
        h, "LUGGAGE V3 charcoal padded coat cotton", (0.017, 0.020, 0.025), roughness=0.72
    )
    denim = _cloth_material(h, "LUGGAGE V3 folded blue charcoal trousers", (0.065, 0.095, 0.13))
    stitch = h["material"]("LUGGAGE V3 restrained dark cotton stitching", (0.09, 0.10, 0.11), 0.94)
    created = []
    # Cream trouser legs fill the previously exposed front and right half of the case.
    for i, (x, dy, length) in enumerate([(-0.145, 0, 0.650), (0.049, 0.012, 0.604)]):
        created.append(
            _folded_leg(
                h,
                "Folded clothing V3 cream returned trouser leg %d" % i,
                x,
                2.063 + dy,
                length,
                0.168,
                0.155,
                cream,
                stitch,
                i * 1.3,
            )
        )
    # A folded blue pair, partly tucked under the black coat, compresses the right stack.
    for i, (x, dy) in enumerate([(-0.130, 0), (0.043, 0.025)]):
        created.append(
            _folded_leg(
                h,
                "Folded clothing V3 blue returned trouser leg %d" % i,
                x,
                2.135 + dy,
                0.526,
                0.148,
                0.224,
                denim,
                stitch,
                2.8 + i,
            )
        )
    base = _surface_support(created)
    ob, blue_surface = _shirt_sheet(
        h,
        "Light blue loose garment V3 gathered shirt",
        (-0.482, 2.338),
        (0.437, 0.581),
        blue,
        stitch,
        1.7,
        lambda x, y: max(0.169, base(x, y)),
        raised=0.054,
    )
    created.append(ob)
    # Grey knit is bunched at the left rear, with its neckline facing into the case.
    base = _surface_support(created)
    ob, grey_surface = _shirt_sheet(
        h,
        "Grey shirt spills V3 rumpled knit body",
        (-0.488, 2.798),
        (0.416, 0.362),
        grey,
        stitch,
        4.4,
        lambda x, y: max(0.215, base(x, y)),
        raised=0.038,
    )
    created.append(ob)
    grey_top = _surface_support([ob], 0.22)
    created.append(
        _ribbed_opening(
            h,
            "Grey shirt spills V3 folded knitted neckline",
            (-0.550, 2.945),
            (0.057, 0.034),
            grey,
            stitch,
            grey_top,
        )
    )
    # A small returned sweater sleeve gives a recognizable cuff beside the jacket.
    created.append(
        _folded_leg(
            h,
            "Grey shirt spills V3 returned sweater sleeve",
            -0.595,
            2.720,
            0.165,
            0.107,
            0.214,
            grey,
            stitch,
            5.2,
            support=grey_top,
        )
    )
    # Dark, softly inflated central clothing supports the puffer near its prior height.
    base = _surface_support(created)
    ob, black_surface = _shirt_sheet(
        h,
        "Folded clothing V3 central black outerwear",
        (-0.255, 2.565),
        (0.465, 0.635),
        dark,
        stitch,
        0.7,
        lambda x, y: max(0.217, base(x, y)),
        raised=0.024,
    )
    created.append(ob)
    return {
        "garment_meshes": len(created),
        "support_prefixes_preserved": True,
        "authorship": "deterministic modeled packed garments; no photo projection",
    }
