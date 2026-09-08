"""Photograph-informed everyday objects for the Yudof room reconstruction.

All geometry and graphic treatments in this module are authored procedurally.
Dimensions are metres. Personal screen contents and product labels are replaced
with neutral authored graphics; no external asset files are required.
"""

from __future__ import annotations

import math
import random

import bpy
from mathutils import Matrix, Vector


def build(ctx):
    """Populate a room using the shared primitive/material helper context."""
    B, E, C, Q = (ctx[k] for k in ("box", "uvball", "cyl", "curve"))
    M = ctx["M"]
    random.seed(521)
    created_before = len(bpy.data.objects)
    prop_collection = None

    def group(name):
        nonlocal prop_collection
        prop_collection = ctx["collection"](name)
        if prop_collection is None:
            prop_collection = bpy.data.collections.get(name) or bpy.context.collection

    def material(
        name, color, roughness=0.5, metallic=0, transmission=0, bump=0, scale=150, emission=0
    ):
        m = bpy.data.materials.new("PROP / " + name)
        m.diffuse_color = (*color, 1)
        m.use_nodes = True
        n, links = m.node_tree.nodes, m.node_tree.links
        p = n.get("Principled BSDF")
        p.inputs["Base Color"].default_value = (*color, 1)
        p.inputs["Roughness"].default_value = roughness
        p.inputs["Metallic"].default_value = metallic
        p.inputs["Transmission Weight"].default_value = transmission
        p.inputs["IOR"].default_value = 1.46
        if emission:
            p.inputs["Emission Color"].default_value = (*color, 1)
            p.inputs["Emission Strength"].default_value = emission
        if bump:
            tex = n.new("ShaderNodeTexNoise")
            tex.inputs["Scale"].default_value = scale
            tex.inputs["Detail"].default_value = 3
            tex.inputs["Roughness"].default_value = 0.72
            bn = n.new("ShaderNodeBump")
            bn.inputs["Strength"].default_value = 0.28
            bn.inputs["Distance"].default_value = bump
            links.new(tex.outputs["Fac"], bn.inputs["Height"])
            links.new(bn.outputs["Normal"], p.inputs["Normal"])
        return m

    rubber = material("rubber / warm charcoal", (0.017, 0.019, 0.022), 0.72, bump=0.0004)
    keymat = material("keycaps", (0.036, 0.040, 0.047), 0.42)
    silver = material("anodized silver", (0.38, 0.40, 0.42), 0.3, 0.72, bump=0.00008)
    shellmetal = material(
        "suitcase brushed graphite", (0.27, 0.31, 0.35), 0.28, 0.65, bump=0.00025, scale=320
    )
    shellrim = material("luggage edge plastic", (0.11, 0.13, 0.15), 0.4)
    paper = material("uncoated paper", (0.87, 0.86, 0.80), 0.87, bump=0.0007, scale=310)
    tissue = material("soft white tissue", (0.93, 0.93, 0.88), 0.94, bump=0.0006)
    navy = material(
        "violet navy ripstop puffer", (0.019, 0.013, 0.067), 0.29, bump=0.0007, scale=290
    )
    navy_seam = material("puffer stitched seams", (0.010, 0.009, 0.032), 0.55)
    cotton = material("grey marl knit", (0.32, 0.35, 0.37), 0.92, bump=0.0012, scale=380)
    ivory_fabric = material("cream canvas", (0.68, 0.65, 0.53), 0.88, bump=0.001, scale=300)
    backpack = material("dusty periwinkle nylon", (0.17, 0.22, 0.35), 0.67, bump=0.0006)
    backpack_piping = material("bag cream piping", (0.68, 0.66, 0.47), 0.61, bump=0.0003)
    sky = material("wipes turquoise wrapper", (0.24, 0.57, 0.69), 0.33, bump=0.0003)
    green = material("green bottle label", (0.014, 0.26, 0.11), 0.35)
    bottleplastic = material("translucent bottle PET", (0.7, 0.79, 0.73), 0.12, transmission=0.84)
    water = material("water", (0.62, 0.72, 0.67), 0.05, transmission=1)
    clearplastic = material(
        "storage translucent polypropylene",
        (0.59, 0.67, 0.71),
        0.24,
        transmission=0.72,
        bump=0.0002,
    )
    teal = material("storage latch turquoise", (0.15, 0.44, 0.47), 0.33)
    gold = material("snack foil / ochre", (0.64, 0.33, 0.065), 0.3, 0.38)
    scarlet = material("snack graphic red", (0.53, 0.024, 0.018), 0.43)
    yellow = material("recycling bin yellow", (1, 0.46, 0.006), 0.37)
    pink = material("chair pillow pale mauve", (0.54, 0.40, 0.43), 0.82, bump=0.0009)
    pink_seam = material("pillow embroidery", (0.21, 0.13, 0.16), 0.91)
    sole = material("sneaker sole off white", (0.71, 0.70, 0.65), 0.8, bump=0.0005)
    shoeupper = material("sneaker knitted grey", (0.32, 0.31, 0.29), 0.85, bump=0.001, scale=300)
    screen = material("laptop dark screen", (0.011, 0.016, 0.025), 0.24, emission=0.17)
    blue_screen = material("tablet note paper blue", (0.18, 0.33, 0.47), 0.32, emission=0.3)
    code_colors = [
        material("screen syntax " + str(i), col, 0.7, emission=0.8)
        for i, col in enumerate(
            [(0.36, 0.56, 0.69), (0.61, 0.54, 0.37), (0.46, 0.56, 0.45), (0.52, 0.48, 0.63)]
        )
    ]

    def mesh(name, vertices, faces, mat, smooth=True):
        me = bpy.data.meshes.new(name)
        me.from_pydata(vertices, [], faces)
        me.update()
        ob = bpy.data.objects.new(name, me)
        (prop_collection or bpy.context.collection).objects.link(ob)
        ob.data.materials.append(mat)
        for p in me.polygons:
            p.use_smooth = smooth
        return ob

    def transform_group(before, origin, rotation):
        """Rotate recently added geometry about a local pivot."""
        # matrix_world is lazily evaluated after location/scale edits. Flush once
        # before multiplying it, or recently scaled UV spheres regain unit size.
        bpy.context.view_layer.update()
        pivot = Vector(origin)
        rot = Matrix.Rotation(rotation, 4, "Z")
        xform = Matrix.Translation(pivot) @ rot @ Matrix.Translation(-pivot)
        for ob in [o for o in bpy.data.objects if o.name not in before]:
            ob.matrix_world = xform @ ob.matrix_world

    def tube(name, points, radius, mat):
        # Dense paths are already sampled from analytic rings or textile meshes.
        # Adding Bezier subdivisions between every sample needlessly inflates GLB.
        if len(points) < 16:
            return Q(name, points, radius, mat)
        data = bpy.data.curves.new(name, "CURVE")
        data.dimensions = "3D"
        data.resolution_u = 1
        data.bevel_depth = radius
        data.bevel_resolution = 2
        spline = data.splines.new("POLY")
        spline.points.add(len(points) - 1)
        for point, co in zip(spline.points, points):
            point.co = (*co, 1)
        ob = bpy.data.objects.new(name, data)
        (prop_collection or bpy.context.scene.collection).objects.link(ob)
        ob.data.materials.append(mat)
        return ob

    def polyloop(name, points, radius, mat):
        return tube(name, points + [points[0]], radius, mat)

    def ring(name, center, radius, tube_radius, mat, axis="Z", segments=48):
        x, y, z = center
        pts = []
        for i in range(segments + 1):
            a = 2 * math.pi * i / segments
            if axis == "X":
                pts.append((x, y + radius * math.cos(a), z + radius * math.sin(a)))
            elif axis == "Y":
                pts.append((x + radius * math.cos(a), y, z + radius * math.sin(a)))
            else:
                pts.append((x + radius * math.cos(a), y + radius * math.sin(a), z))
        return tube(name, pts, tube_radius, mat)

    def lathe(name, center, profile, mat, segments=48):
        verts, faces = [], []
        for z, r in profile:
            for j in range(segments):
                a = j * 2 * math.pi / segments
                verts.append(
                    (center[0] + r * math.cos(a), center[1] + r * math.sin(a), center[2] + z)
                )
        for i in range(len(profile) - 1):
            for j in range(segments):
                k = i * segments + j
                faces.append(
                    (
                        k,
                        i * segments + (j + 1) % segments,
                        (i + 1) * segments + (j + 1) % segments,
                        k + segments,
                    )
                )
        if profile[0] != profile[-1]:
            faces += [
                tuple(range(segments - 1, -1, -1)),
                tuple((len(profile) - 1) * segments + j for j in range(segments)),
            ]
        return mesh(name, verts, faces, mat)

    def text(name, body, loc, size, mat, right=(0, -1, 0), up=(0, 0, 1), align="LEFT"):
        data = bpy.data.curves.new(name, "FONT")
        data.body = body
        data.size = size
        data.align_x = align
        data.extrude = 0
        ob = bpy.data.objects.new(name, data)
        (prop_collection or bpy.context.collection).objects.link(ob)
        ob.data.materials.append(mat)
        right, up = Vector(right).normalized(), Vector(up).normalized()
        normal = right.cross(up)
        ob.matrix_world = Matrix(
            (
                (right.x, up.x, normal.x, loc[0]),
                (right.y, up.y, normal.y, loc[1]),
                (right.z, up.z, normal.z, loc[2]),
                (0, 0, 0, 1),
            )
        )
        return ob

    def softbox(name, loc, dims, mat, n=24, rings=16, wrinkle=0.0015):
        """Rounded, slightly asymmetrical sewn volume without boxy silhouettes."""
        verts, faces = [], []
        for i in range(rings + 1):
            v = math.pi * i / rings
            sv, cv = math.sin(v), math.cos(v)
            cross = max(sv, 0.002) ** 0.45
            for j in range(n):
                a = 2 * math.pi * j / n
                ca, sa = math.cos(a), math.sin(a)
                x = math.copysign(abs(ca) ** 0.53, ca) * cross
                y = math.copysign(abs(sa) ** 0.53, sa) * cross
                fuzz = wrinkle * (math.sin(13 * a + 9 * v) + 0.4 * math.sin(29 * a - 11 * v)) * sv
                verts.append(
                    (
                        loc[0] + dims[0] * x / 2 + fuzz,
                        loc[1] + dims[1] * y / 2 + fuzz * 0.6,
                        loc[2] + dims[2] * math.copysign(abs(cv) ** 0.65, cv) / 2 + fuzz,
                    )
                )
        for i in range(rings):
            for j in range(n):
                k = i * n + j
                faces.append((k, k + n, (i + 1) * n + (j + 1) % n, i * n + (j + 1) % n))
        faces.extend([tuple(range(n)), tuple(rings * n + j for j in range(n - 1, -1, -1))])
        return mesh(name, verts, faces, mat)

    def cloth(name, loc, size, mat, drop=0, waves=0.007, res=(34, 32), angle=0):
        """A thin, draped textile patch with large folds and fine wrinkles."""
        nx, ny = res
        vertices, faces = [], []
        for iy in range(ny + 1):
            v = iy / ny
            for ix in range(nx + 1):
                u = ix / nx
                x, y = (u - 0.5) * size[0], (v - 0.5) * size[1]
                edge = max(0, (abs(u - 0.5) - 0.30) / 0.2)
                z = -0.5 * drop * edge**1.3
                z += waves * (
                    math.sin(17 * u + 6 * v)
                    + 0.46 * math.sin(39 * u - 23 * v)
                    + 0.23 * math.sin(79 * u + 11 * v)
                )
                y += waves * 0.35 * math.sin(20 * u + 10 * v)
                vertices.append(
                    (
                        loc[0] + x * math.cos(angle) - y * math.sin(angle),
                        loc[1] + x * math.sin(angle) + y * math.cos(angle),
                        loc[2] + z,
                    )
                )
        for iy in range(ny):
            for ix in range(nx):
                a = iy * (nx + 1) + ix
                faces.append((a, a + 1, a + nx + 2, a + nx + 1))
        ob = mesh(name, vertices, faces, mat)
        sol = ob.modifiers.new("fabric thickness", "SOLIDIFY")
        sol.thickness = 0.0009
        return ob

    def crushed_paper(name, loc, size=0.045):
        ob = E(name, loc, (size, size * 0.8, size * 0.6), tissue)
        for v in ob.data.vertices:
            if v.co.length:
                v.co *= 1 + 0.13 * math.sin(v.co.x * 43 + v.co.y * 51 + v.co.z * 37)
        return ob

    # ------------------------------------------------------------------ desk
    group("Props / Study desk electronics")
    B("Laptop aluminium lower shell", (1.145, 1.83, 0.788), (0.268, 0.383, 0.015), silver, 0.009)
    B("Laptop black keyboard recess", (1.171, 1.83, 0.797), (0.175, 0.351, 0.002), rubber, 0.004)
    B("Laptop touchpad inset", (1.042, 1.83, 0.797), (0.071, 0.107, 0.0016), silver, 0.003)
    polyloop(
        "Touchpad engraved border",
        [
            (1.007, 1.777, 0.798),
            (1.077, 1.777, 0.798),
            (1.077, 1.883, 0.798),
            (1.007, 1.883, 0.798),
        ],
        0.00045,
        shellrim,
    )
    for row in range(6):
        for key in range(15):
            x, y = 1.092 + row * 0.026, 1.674 + key * 0.0223
            B(
                "Laptop key %02d %02d" % (row, key),
                (x, y, 0.800),
                (0.020, 0.0187, 0.003),
                keymat,
                0.002,
            )
            if row < 5:
                # Tiny diffuse legend strokes remain light enough to read as key printing.
                B("Key legend", (x - 0.003, y, 0.8016), (0.006, 0.004, 0.00025), paper, 0.0001)
    # Spacebar spans the central keys in the front row.
    B("Long spacebar", (1.092, 1.833, 0.802), (0.019, 0.11, 0.003), keymat, 0.002)
    for yy in (1.684, 1.977):
        hinge = C(
            "Laptop hinge barrel", (1.283, yy, 0.799), 0.006, 0.055, silver, (math.pi / 2, 0, 0)
        )
    # Screen is physically tilted away from the user, with independently set lettering.
    before = {o.name for o in bpy.data.objects}
    B("Laptop screen lid", (1.297, 1.83, 0.927), (0.012, 0.383, 0.246), silver, 0.008)
    B("Laptop screen bezel", (1.289, 1.83, 0.927), (0.002, 0.369, 0.231), rubber, 0.004)
    B("Laptop active display", (1.2875, 1.83, 0.929), (0.001, 0.350, 0.210), screen, 0.0001)
    # Authored editor interface: side rail, document pane, syntax-colored line strips.
    B("Editor side panel", (1.2866, 1.958, 0.929), (0.0005, 0.074, 0.208), keymat, 0)
    for i in range(24):
        z = 1.022 - i * 0.0075
        y = 1.914 - (0.010 if i % 5 else 0.027)
        width = random.uniform(0.045, 0.19)
        B(
            "Editor authored syntax line %02d" % i,
            (1.2862, y - width / 2, z),
            (0.0003, width, 0.00115),
            code_colors[i % 4],
            0,
        )
    text("Screen neutral heading", "ROOM / SCENE", (1.2858, 1.901, 1.03), 0.008, paper)
    E("Laptop camera lens", (1.286, 1.83, 1.039), (0.001, 0.0015, 0.0015), rubber)
    pivot = Vector((1.29, 1.83, 0.806))
    tilt = (
        Matrix.Translation(pivot)
        @ Matrix.Rotation(math.radians(13), 4, "Y")
        @ Matrix.Translation(-pivot)
    )
    bpy.context.view_layer.update()
    for ob in [o for o in bpy.data.objects if o.name not in before]:
        ob.matrix_world = tilt @ ob.matrix_world
    B("Laptop status LED", (1.005, 1.67, 0.789), (0.001, 0.006, 0.0015), code_colors[0], 0.0003)
    for y in (1.67, 1.72, 1.91, 1.94):
        B("Laptop edge port", (1.14, y, 0.786), (0.016, 0.004, 0.003), rubber, 0.0008)

    B("Tablet folio rim", (1.015, 1.410, 0.791), (0.236, 0.170, 0.013), rubber, 0.009)
    B("Tablet dark glass border", (1.013, 1.410, 0.799), (0.226, 0.160, 0.002), M["black"], 0.008)
    B("Tablet note display", (1.013, 1.410, 0.8005), (0.210, 0.143, 0.001), blue_screen, 0.006)
    for i in range(9):
        B(
            "Tablet ruled paper line",
            (0.923 + i * 0.022, 1.41, 0.8012),
            (0.0008, 0.135, 0.0002),
            code_colors[0],
            0,
        )
    text(
        "Tablet authored title",
        "scene notes",
        (1.095, 1.47, 0.8018),
        0.011,
        keymat,
        right=(0, -1, 0),
        up=(1, 0, 0),
    )
    E("Mouse rounded shell", (0.981, 1.582, 0.81), (0.047, 0.030, 0.025), rubber)
    tube(
        "Mouse split line",
        [(0.944, 1.582, 0.823), (0.965, 1.582, 0.834), (0.983, 1.582, 0.835)],
        0.0006,
        keymat,
    )
    C("Mouse scroll wheel", (0.958, 1.582, 0.836), 0.007, 0.005, shellrim, (math.pi / 2, 0, 0))
    tube(
        "Mouse USB lead",
        [
            (0.947, 1.582, 0.818),
            (0.920, 1.615, 0.787),
            (1.013, 1.66, 0.781),
            (1.071, 1.659, 0.791),
            (1.15, 1.65, 0.788),
        ],
        0.0014,
        rubber,
    )
    phone = B("Phone metal frame", (0.982, 1.171, 0.79), (0.15, 0.073, 0.010), silver, 0.010)
    B("Phone glass", (0.982, 1.171, 0.796), (0.143, 0.066, 0.001), M["black"], 0.008)
    B("Phone earpiece", (1.043, 1.171, 0.797), (0.002, 0.019, 0.0004), shellrim, 0.0008)
    E("Phone selfie lens", (1.043, 1.188, 0.797), (0.002, 0.002, 0.0005), screen)
    # White charging cables naturally spill past the front edge, keeping true thickness.
    tube(
        "Phone charging cable drape",
        [
            (0.905, 1.171, 0.789),
            (0.866, 1.17, 0.80),
            (0.807, 1.21, 0.68),
            (0.795, 1.28, 0.56),
            (0.822, 1.34, 0.59),
            (0.861, 1.43, 0.79),
            (1.00, 1.53, 0.782),
            (1.36, 1.61, 0.788),
        ],
        0.002,
        tissue,
    )
    B("Desk charging strip", (1.378, 1.52, 0.80), (0.066, 0.234, 0.029), tissue, 0.006)
    for yy in (1.455, 1.52, 1.585):
        for xx in (1.369, 1.386):
            B("Power strip socket", (xx, yy, 0.815), (0.005, 0.009, 0.0008), rubber, 0.001)
    B("USB-C power brick", (1.368, 1.555, 0.848), (0.052, 0.051, 0.062), tissue, 0.007)
    B("Dark laptop charger", (1.351, 1.44, 0.841), (0.055, 0.062, 0.057), rubber, 0.005)
    tube(
        "White charger loop",
        [
            (1.365, 1.554, 0.88),
            (1.322, 1.55, 0.931),
            (1.254, 1.51, 0.912),
            (1.277, 1.449, 0.8),
            (1.311, 1.32, 0.786),
        ],
        0.002,
        tissue,
    )
    tube(
        "Laptop power cord to wall",
        [
            (1.347, 1.44, 0.87),
            (1.426, 1.43, 0.851),
            (1.475, 1.45, 0.811),
            (1.476, 1.66, 0.788),
            (1.398, 1.685, 0.782),
            (1.14, 1.65, 0.783),
        ],
        0.0025,
        rubber,
    )
    B("Black stylus", (0.985, 1.314, 0.781), (0.185, 0.006, 0.006), rubber, 0.003)

    group("Props / Paper and food packaging")
    # Hollow kitchen-paper roll lies parallel to the edge of the desk.
    roll_center = (1.272, 1.19, 0.850)
    before = {o.name for o in bpy.data.objects}
    roll = lathe(
        "Embossed paper towel roll",
        (0, 0, 0),
        [(0, 0.022), (0, 0.057), (0.205, 0.057), (0.205, 0.022), (0.0, 0.022)],
        tissue,
        64,
    )
    roll.rotation_euler[1] = math.pi / 2
    roll.location = (1.17, 1.19, 0.85)
    for xx in (1.171, 1.374):
        ring("Paper roll cardboard core", (xx, 1.19, 0.85), 0.021, 0.002, ivory_fabric, "X")
        for r in (0.029, 0.036, 0.044, 0.052):
            ring("Visible rolled paper layers", (xx, 1.19, 0.85), r, 0.0003, paper, "X")
    cloth(
        "Unrolled paper towel",
        (1.125, 2.07, 0.783),
        (0.37, 0.15),
        tissue,
        waves=0.0017,
        res=(32, 18),
        angle=0.14,
    )
    for x, y in [(1.345, 2.08), (1.301, 2.123), (1.366, 1.990)]:
        crushed_paper("Crumpled desk tissue", (x, y, 0.80), 0.024)
    # Thin foil packet with the pinched edge and a simple graphic band.
    softbox(
        "Open snack bag foil body", (1.09, 1.11, 0.834), (0.148, 0.135, 0.080), gold, wrinkle=0.007
    )
    cloth(
        "Snack bag crimped open silver mouth",
        (1.015, 1.125, 0.857),
        (0.07, 0.15),
        silver,
        waves=0.005,
        res=(18, 22),
    )
    B("Snack bag red printed badge", (1.078, 1.11, 0.876), (0.074, 0.065, 0.0007), scarlet, 0.01)
    text(
        "Snack neutral package title",
        "CRISPS",
        (1.105, 1.132, 0.877),
        0.016,
        tissue,
        right=(0, -1, 0),
        up=(1, 0, 0),
    )
    softbox(
        "Seed packet", (1.017, 1.662, 0.783), (0.12, 0.048, 0.012), code_colors[0], wrinkle=0.0015
    )
    B("Seed packet cream label", (1.017, 1.662, 0.791), (0.070, 0.040, 0.0003), paper, 0.001)
    text(
        "Seed packet neutral print",
        "SEEDS",
        (1.041, 1.678, 0.792),
        0.009,
        keymat,
        right=(0, -1, 0),
        up=(1, 0, 0),
    )
    cloth(
        "Cream shopping tote",
        (1.372, 1.191, 0.802),
        (0.21, 0.22),
        ivory_fabric,
        waves=0.010,
        res=(26, 26),
        angle=0.12,
    )
    tube(
        "Canvas tote handle one",
        [
            (1.363, 1.107, 0.815),
            (1.40, 1.068, 0.80),
            (1.439, 1.077, 0.784),
            (1.456, 1.153, 0.784),
            (1.409, 1.191, 0.816),
        ],
        0.005,
        ivory_fabric,
    )

    # ------------------------------------------------------------ dresser bag
    group("Props / Dresser travel bag")
    softbox(
        "Backpack padded main body",
        (-1.263, 2.805, 1.105),
        (0.232, 0.322, 0.443),
        backpack,
        n=44,
        rings=28,
        wrinkle=0.0026,
    )
    softbox(
        "Backpack cream crown panel",
        (-1.265, 2.805, 1.265),
        (0.225, 0.30, 0.114),
        ivory_fabric,
        n=40,
        rings=20,
        wrinkle=0.002,
    )
    softbox(
        "Backpack front pocket",
        (-1.119, 2.805, 1.073),
        (0.100, 0.265, 0.287),
        backpack,
        n=40,
        rings=24,
        wrinkle=0.0018,
    )
    # Two arched zipper paths, their running chain and two independently modelled pulls.
    for n, (x, w, zbase, h) in enumerate(
        [(-1.060, 0.253, 0.963, 0.238), (-1.133, 0.303, 1.065, 0.215)]
    ):
        pts = []
        for i in range(45):
            a = math.pi * i / 44
            pts.append(
                (x + 0.007 * math.sin(a), 2.805 + w / 2 * math.cos(a), zbase + h * math.sin(a))
            )
        tube("Backpack cream zipper piping %d" % n, pts, 0.0033, backpack_piping)
        tube(
            "Backpack metal zip chain %d" % n,
            [(p[0] + 0.001, p[1], p[2] + 0.003) for p in pts],
            0.0009,
            silver,
        )
        for side in (0, -1):
            px, py, pz = pts[side]
            pull = B(
                "Backpack zipper pull",
                (px + 0.004, py, pz - 0.011),
                (0.006, 0.010, 0.025),
                silver,
                0.002,
            )
    tube(
        "Backpack top carry handle",
        [
            (-1.263, 2.702, 1.315),
            (-1.267, 2.72, 1.365),
            (-1.268, 2.78, 1.382),
            (-1.266, 2.849, 1.365),
            (-1.263, 2.869, 1.321),
        ],
        0.012,
        backpack,
    )
    for yy in (2.690, 2.918):
        tube(
            "Backpack padded shoulder strap",
            [(-1.365, yy, 1.279), (-1.436, yy, 1.17), (-1.438, yy, 0.988), (-1.351, yy, 0.918)],
            0.021,
            backpack,
        )
        B("Backpack strap adjuster", (-1.418, yy, 0.999), (0.017, 0.039, 0.028), shellrim, 0.004)
    B(
        "Backpack fabric identity patch",
        (-1.059, 2.805, 1.085),
        (0.001, 0.073, 0.029),
        tissue,
        0.003,
    )
    text(
        "Backpack neutral woven label",
        "TRAVEL",
        (-1.0575, 2.776, 1.079),
        0.011,
        backpack,
        right=(0, 1, 0),
        up=(0, 0, 1),
    )
    for yy in (2.628, 2.982):
        softbox(
            "Backpack mesh side pocket",
            (-1.25, yy, 1.038),
            (0.12, 0.028, 0.133),
            backpack,
            wrinkle=0.001,
        )
    # White narrow shopping bag, hollow opening and rope handles.
    for dx, dy, dz, wx, wy, wz in [
        (0, 0, 0, 0.13, 0.096, 0.003),
        (-0.064, 0, 0.103, 0.002, 0.096, 0.206),
        (0.064, 0, 0.103, 0.002, 0.096, 0.206),
        (0, -0.047, 0.103, 0.13, 0.002, 0.206),
        (0, 0.047, 0.103, 0.13, 0.002, 0.206),
    ]:
        B(
            "Dresser paper shopping bag",
            (-1.22 + dx, 2.382 + dy, 0.89 + dz),
            (wx, wy, wz),
            paper,
            0.0008,
        )
    for xx in (-1.285, -1.155):
        tube(
            "Paper bag twisted handle",
            [
                (xx, 2.35, 1.064),
                (xx - 0.006, 2.344, 1.155),
                (xx - 0.006, 2.410, 1.155),
                (xx, 2.417, 1.064),
            ],
            0.002,
            ivory_fabric,
        )
    # Wipes flexible packet on the front corner of dresser.
    softbox(
        "Turquoise wipes pack",
        (-1.004, 2.790, 0.913),
        (0.16, 0.105, 0.055),
        sky,
        n=32,
        rings=20,
        wrinkle=0.002,
    )
    B("Wipes white opening label", (-1.004, 2.790, 0.942), (0.105, 0.064, 0.001), tissue, 0.012)
    B("Wipes resealable flap", (-1.004, 2.790, 0.943), (0.071, 0.043, 0.001), sky, 0.008)
    text(
        "Wipes pack neutral print",
        "PURE",
        (-0.984, 2.812, 0.944),
        0.015,
        paper,
        right=(0, -1, 0),
        up=(1, 0, 0),
    )
    softbox(
        "Small yellow snack packet",
        (-1.000, 2.602, 0.891),
        (0.13, 0.083, 0.013),
        yellow,
        wrinkle=0.002,
    )
    B("Yellow packet label", (-1.000, 2.602, 0.899), (0.065, 0.066, 0.0004), tissue, 0.002)
    text(
        "Yellow packet neutral print",
        "CITRUS",
        (-0.979, 2.630, 0.900),
        0.011,
        green,
        right=(0, -1, 0),
        up=(1, 0, 0),
    )
    # Carefully coiled white data lead.
    pts = []
    for i in range(260):
        a = i * 2 * math.pi / 45
        r = 0.026 + 0.00018 * i / 6
        pts.append((-0.969 + r * math.cos(a), 2.944 + r * math.sin(a), 0.886 + 0.00011 * i))
    tube("Coiled white cable on dresser", pts, 0.0017, tissue)
    B("Coiled cable USB connector", (-0.949, 2.917, 0.887), (0.012, 0.006, 0.004), tissue, 0.001)
    B("Dresser extension strip", (-0.952, 2.294, 0.904), (0.053, 0.226, 0.036), tissue, 0.005)
    for yy in (2.215, 2.272, 2.329, 2.386):
        for xx in (-0.965, -0.946):
            B("Extension strip plug hole", (xx, yy, 0.923), (0.006, 0.003, 0.0003), rubber, 0.0005)
    B("Power plug", (-0.952, 2.225, 0.938), (0.035, 0.037, 0.041), paper, 0.007)
    tube(
        "Dresser cable to floor",
        [
            (-0.934, 2.223, 0.947),
            (-0.87, 2.208, 0.911),
            (-0.84, 2.178, 0.753),
            (-0.845, 2.128, 0.531),
            (-0.80, 2.114, 0.32),
            (-0.84, 2.097, 0.10),
            (-0.74, 2.098, 0.016),
            (-0.51, 2.184, 0.013),
            (-0.41, 2.22, 0.058),
        ],
        0.0025,
        tissue,
    )

    # --------------------------------------------------------- upright luggage
    group("Props / Upright silver suitcase")
    softbox(
        "Silver suitcase rounded shell",
        (-0.995, 0.725, 0.443),
        (0.491, 0.267, 0.692),
        shellmetal,
        n=44,
        rings=26,
        wrinkle=0,
    )
    # The casing has two shells, a raised zipper belt and sculpted vertical flutes.
    for yy in (0.704, 0.717):
        points = []
        for i in range(100):
            a = 2 * math.pi * i / 100
            ca, sa = math.cos(a), math.sin(a)
            points.append(
                (
                    -0.995 + 0.25 * math.copysign(abs(ca) ** 0.30, ca),
                    yy,
                    0.443 + 0.348 * math.copysign(abs(sa) ** 0.30, sa),
                )
            )
        polyloop("Suitcase zipper perimeter", points, 0.0037, shellrim)
    for i in range(15):
        x = -1.204 + i * 0.0298
        length = 0.548 - 0.05 * (abs(i - 7) / 7) ** 5
        tube(
            "Suitcase raised flute %02d" % i,
            [
                (x, 0.846, 0.443 - length / 2),
                (x, 0.864, 0.443 - length / 2 + 0.025),
                (x, 0.867, 0.443 + length / 2 - 0.025),
                (x, 0.846, 0.443 + length / 2),
            ],
            0.0048,
            shellmetal,
        )
    for xx in (-1.174, -0.816):
        for yy in (0.635, 0.812):
            B("Spinner wheel fork", (xx, yy, 0.080), (0.029, 0.039, 0.060), shellrim, 0.008)
            for dx in (-0.013, 0.013):
                C(
                    "Twin luggage caster",
                    (xx + dx, yy, 0.045),
                    0.025,
                    0.014,
                    rubber,
                    (0, math.pi / 2, 0),
                )
    for xx in (-1.11, -0.88):
        B("Recessed telescopic rail", (xx, 0.665, 0.684), (0.017, 0.018, 0.176), shellrim, 0.004)
        B("Handle bracket", (xx, 0.717, 0.791), (0.042, 0.070, 0.025), shellrim, 0.009)
    B(
        "Suitcase padded carrying handle",
        (-0.995, 0.716, 0.815),
        (0.21, 0.030, 0.027),
        shellrim,
        0.01,
    )
    for zz in (0.33, 0.58):
        B("Suitcase side bumper", (-1.243, 0.727, zz), (0.014, 0.059, 0.053), shellrim, 0.008)
    B("Small suitcase luggage tag", (-0.851, 0.872, 0.300), (0.072, 0.001, 0.038), teal, 0.002)
    text(
        "Luggage tag neutral lettering",
        "521",
        (-0.827, 0.874, 0.291),
        0.014,
        tissue,
        right=(-1, 0, 0),
        up=(0, 0, 1),
    )
    for zz in (0.633, 0.677):
        B("Suitcase metal zip pull", (-1.22, 0.738, zz), (0.015, 0.011, 0.046), silver, 0.004)

    # ----------------------------------------------------------- open luggage
    group("Props / Open suitcase and puffer jacket")
    for x, w in [(-0.49, 0.44), (-0.04, 0.44)]:
        softbox(
            "Open case shell half",
            (x, 2.52, 0.075),
            (w, 1.00, 0.128),
            rubber,
            n=36,
            rings=16,
            wrinkle=0,
        )
        B(
            "Open luggage fabric interior",
            (x, 2.52, 0.141),
            (w - 0.040, 0.935, 0.012),
            backpack,
            0.022,
        )
        polyloop(
            "Open suitcase zipper edge",
            [
                (x - w / 2 + 0.02, 2.04, 0.148),
                (x + w / 2 - 0.02, 2.04, 0.148),
                (x + w / 2 - 0.02, 3.0, 0.148),
                (x - w / 2 + 0.02, 3.0, 0.148),
            ],
            0.004,
            shellrim,
        )
    for x in (-0.69, 0.17):
        for y in (2.080, 2.94):
            C("Open case small caster", (x, y, 0.054), 0.024, 0.019, rubber, (math.pi / 2, 0, 0))
    for yy in (2.21, 2.76):
        B(
            "Suitcase internal compression strap",
            (-0.12, yy, 0.167),
            (0.38, 0.022, 0.005),
            shellrim,
            0.002,
        )
        B("Suitcase compression buckle", (-0.10, yy, 0.171), (0.038, 0.032, 0.008), rubber, 0.004)
    # Folded clothes establish layered thickness under the rumpled jacket.
    for i, (x, y, w, h, mat) in enumerate(
        [
            (-0.08, 2.62, 0.34, 0.37, ivory_fabric),
            (-0.12, 2.57, 0.38, 0.41, backpack),
            (-0.38, 2.39, 0.38, 0.45, ivory_fabric),
            (-0.36, 2.63, 0.38, 0.45, rubber),
        ]
    ):
        z = 0.166 + i * 0.027
        softbox("Folded clothing %02d" % i, (x, y, z), (w, h, 0.047), mat, wrinkle=0.003)
        cloth(
            "Folded clothing soft top %02d" % i,
            (x, y, z + 0.027),
            (w * 0.96, h * 0.96),
            mat,
            waves=0.004,
            res=(24, 24),
            angle=0.05 * (i - 2),
        )
    cloth(
        "Grey shirt spills over open case",
        (-0.48, 2.79, 0.255),
        (0.44, 0.31),
        cotton,
        drop=0.12,
        waves=0.012,
        res=(42, 32),
        angle=0.23,
    )
    cloth(
        "Light blue loose garment",
        (-0.51, 2.35, 0.226),
        (0.35, 0.31),
        sky,
        waves=0.011,
        res=(34, 28),
        angle=-0.22,
    )

    # Jacket torso: quilt channels are actual inflated geometry, not dark stripes.
    verts, faces = [], []
    nx, ny = 62, 75
    for j in range(ny + 1):
        v = j / ny
        y = 2.30 + v * 0.59
        width = 0.37 + 0.072 * math.sin(v * math.pi) - 0.045 * math.exp(-(((v - 0.95) / 0.10) ** 2))
        for i in range(nx + 1):
            u = i / nx
            x = -0.26 + (u - 0.5) * width + 0.020 * math.sin(8 * v)
            edge = math.sin(math.pi * u) ** 0.6
            puff = (0.013 + 0.024 * math.sin(v * math.pi * 8) ** 2) * edge
            macro = 0.030 * math.sin(5 * u + 9 * v) + 0.014 * math.sin(13 * u - 7 * v)
            wrinkle = 0.0035 * math.sin(95 * u + 40 * v) * math.sin(math.pi * u)
            z = 0.294 + 0.10 * edge + puff + macro + wrinkle
            verts.append((x, y, z))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    jacket = mesh("Navy puffer wrinkled quilted torso", verts, faces, navy)
    solid = jacket.modifiers.new("Jacket padded shell", "SOLIDIFY")
    solid.thickness = 0.019
    for j in range(1, 8):
        row = round(j * ny / 8)
        pts = [
            (
                verts[row * (nx + 1) + i][0],
                verts[row * (nx + 1) + i][1],
                verts[row * (nx + 1) + i][2] + 0.0008,
            )
            for i in range(nx + 1)
        ]
        tube("Puffer transverse sewn channel %02d" % j, pts, 0.0011, navy_seam)
    zipper = []
    for j in range(ny + 1):
        p = verts[j * (nx + 1) + nx // 2]
        zipper.append((p[0] + 0.023, p[1], p[2] + 0.0018))
    tube("Puffer center zip tape", zipper, 0.004, navy_seam)
    tube(
        "Puffer center metal zipper", [(p[0], p[1], p[2] + 0.001) for p in zipper], 0.00085, silver
    )
    B(
        "Puffer zipper slider",
        (zipper[10][0], zipper[10][1], zipper[10][2] + 0.005),
        (0.010, 0.021, 0.004),
        silver,
        0.002,
    )

    def sleeve(name, centers, radii):
        vv, ff = [], []
        sides = 32
        path = []
        # Smoothly interpolate the control path, preserving independently bent arms.
        for k in range(len(centers) - 1):
            for step in range(12):
                t = step / 12
                p = Vector(centers[k]).lerp(Vector(centers[k + 1]), t)
                r = radii[k] * (1 - t) + radii[k + 1] * t
                path.append((p, r))
        path.append((Vector(centers[-1]), radii[-1]))
        for i, (p, r) in enumerate(path):
            tangent = (path[min(i + 1, len(path) - 1)][0] - path[max(i - 1, 0)][0]).normalized()
            side = tangent.cross(Vector((0, 0, 1))).normalized()
            up = side.cross(tangent).normalized()
            puff = 0.88 + 0.12 * math.sin(i * math.pi / 5) ** 2
            for k in range(sides):
                a = 2 * math.pi * k / sides
                cr = math.cos(a) * r * puff
                sr = math.sin(a) * r * 0.68 * puff
                q = p + side * cr + up * sr
                q.z += 0.0018 * math.sin(a * 12 + i * 1.5)
                vv.append(tuple(q))
        for i in range(len(path) - 1):
            for k in range(sides):
                a = i * sides + k
                ff.append(
                    (a, a + sides, (i + 1) * sides + (k + 1) % sides, i * sides + (k + 1) % sides)
                )
        ff += [
            tuple(range(sides)),
            tuple((len(path) - 1) * sides + k for k in range(sides - 1, -1, -1)),
        ]
        mesh(name, vv, ff, navy)
        for i in range(3, len(path) - 1, 5):
            polyloop(
                name + " quilt seam", [vv[i * sides + k] for k in range(sides)], 0.001, navy_seam
            )
        polyloop(
            name + " elastic cuff",
            [vv[(len(path) - 1) * sides + k] for k in range(sides)],
            0.004,
            navy_seam,
        )

    sleeve(
        "Puffer left bent sleeve",
        [
            (-0.42, 2.76, 0.37),
            (-0.55, 2.72, 0.36),
            (-0.62, 2.55, 0.32),
            (-0.54, 2.37, 0.33),
            (-0.41, 2.45, 0.43),
        ],
        [0.078, 0.071, 0.063, 0.054, 0.044],
    )
    sleeve(
        "Puffer right bent sleeve",
        [
            (-0.08, 2.80, 0.38),
            (0.075, 2.79, 0.35),
            (0.12, 2.60, 0.33),
            (0.01, 2.51, 0.44),
            (-0.08, 2.64, 0.46),
        ],
        [0.075, 0.070, 0.06, 0.052, 0.039],
    )
    softbox(
        "Puffer rumpled collar", (-0.254, 2.871, 0.373), (0.205, 0.102, 0.109), navy, wrinkle=0.005
    )
    E("Puffer collar dark opening", (-0.247, 2.872, 0.418), (0.066, 0.030, 0.005), navy_seam)
    for x, y in [(-0.57, 2.16), (-0.52, 2.23), (-0.63, 2.29)]:
        B("Small travel carton", (x, y, 0.195), (0.092, 0.053, 0.065), paper, 0.001)
        B(
            "Travel carton colored stripe",
            (x, y - 0.027, 0.196),
            (0.083, 0.001, 0.017),
            green,
            0.0001,
        )

    # --------------------------------------------------------- molded chair
    group("Props / Black desk chair")
    # seat points +x; the curved back is toward the room at x=.15.
    chairx, chairy = 0.38, 1.78
    # The reference seat has small through-holes; keep them as one coherent mesh.
    seat_verts, seat_faces = [], []

    def seat_height(x, y):
        return 0.46 + 0.11 * (x - chairx) ** 2 + 0.12 * (y - chairy) ** 2

    def add_seat_annulus(cx, cy, inner, outer_square, segments=16):
        start = len(seat_verts)
        for bottom in (False, True):
            for is_outer in (False, True):
                for k in range(segments):
                    a = k * 2 * math.pi / segments
                    ca, sa = math.cos(a), math.sin(a)
                    r = outer_square / max(abs(ca), abs(sa)) if is_outer else inner
                    xx, yy = cx + r * ca, cy + r * sa
                    seat_verts.append((xx, yy, seat_height(xx, yy) - (0.017 if bottom else 0)))
        for k in range(segments):
            j = (k + 1) % segments
            # Top and underside annuli, followed by the cylindrical hole wall.
            seat_faces.extend(
                [
                    (start + k, start + segments + k, start + segments + j, start + j),
                    (
                        start + 2 * segments + k,
                        start + 2 * segments + j,
                        start + 3 * segments + j,
                        start + 3 * segments + k,
                    ),
                    (start + k, start + j, start + 2 * segments + j, start + 2 * segments + k),
                ]
            )

    for i in range(15):
        for j in range(15):
            add_seat_annulus(chairx + (i - 7) * 0.023, chairy + (j - 7) * 0.023, 0.0032, 0.0115)
    start = len(seat_verts)
    sides = 64
    for bottom in (False, True):
        for outer in (False, True):
            for k in range(sides):
                a = k * 2 * math.pi / sides
                ca, sa = math.cos(a), math.sin(a)
                if outer:
                    dx = 0.213 * math.copysign(abs(ca) ** 0.39, ca)
                    dy = 0.213 * math.copysign(abs(sa) ** 0.39, sa)
                else:
                    r = 0.1725 / max(abs(ca), abs(sa))
                    dx, dy = r * ca, r * sa
                xx, yy = chairx + dx, chairy + dy
                seat_verts.append((xx, yy, seat_height(xx, yy) - (0.017 if bottom else 0)))
    for k in range(sides):
        j = (k + 1) % sides
        seat_faces.extend(
            [
                (start + k, start + sides + k, start + sides + j, start + j),
                (
                    start + 2 * sides + k,
                    start + 2 * sides + j,
                    start + 3 * sides + j,
                    start + 3 * sides + k,
                ),
                (
                    start + sides + k,
                    start + 3 * sides + k,
                    start + 3 * sides + j,
                    start + sides + j,
                ),
            ]
        )
    mesh("Chair perforated molded seat / 225 actual holes", seat_verts, seat_faces, rubber)
    for xx in (0.22, 0.54):
        for yy in (1.61, 1.95):
            ox = -0.045 if xx < 0.3 else 0.045
            oy = -0.038 if yy < 1.78 else 0.038
            tube(
                "Chair tubular steel leg",
                [(xx, yy, 0.442), (xx + ox * 0.30, yy + oy * 0.35, 0.35), (xx + ox, yy + oy, 0.04)],
                0.012,
                shellrim,
            )
            E("Chair rubber foot", (xx + ox, yy + oy, 0.025), (0.018, 0.018, 0.022), rubber)
    for yy in (1.61, 1.95):
        tube(
            "Chair back supporting tube",
            [(0.205, yy, 0.40), (0.163, yy, 0.58), (0.140, yy, 0.82)],
            0.011,
            shellrim,
        )
    softbox(
        "Chair curved molded back",
        (0.15, 1.78, 0.716),
        (0.047, 0.436, 0.378),
        rubber,
        n=40,
        rings=22,
        wrinkle=0,
    )
    for yy in (1.616, 1.944):
        C("Chair back hardware", (0.178, yy, 0.621), 0.005, 0.003, silver, (0, math.pi / 2, 0))
    # Pillow tipped over the back, with gathered fabric and embroidered piping.
    softbox(
        "Pink patterned pillow on chair",
        (0.128, 1.782, 0.805),
        (0.175, 0.472, 0.258),
        pink,
        n=44,
        rings=24,
        wrinkle=0.004,
    )
    for zz in (0.708, 0.902):
        pts = []
        for i in range(81):
            y = 1.573 + 0.414 * i / 80
            pts.append((0.224 + 0.004 * math.sin(i * 0.8), y, zz + 0.006 * math.sin(i * 0.37)))
        tube("Pillow ornamental border", pts, 0.0016, pink_seam)
    for j in range(13):
        center_y = 1.592 + j * 0.032
        pts = []
        for i in range(35):
            a = i * 2 * math.pi / 34
            r = 0.009 * (1 + 0.23 * math.cos(5 * a))
            pts.append((0.22, center_y + r * math.cos(a), 0.875 + r * math.sin(a)))
        tube("Pillow paisley stitch motif", pts, 0.0008, pink_seam)

    # ------------------------------------------------------------ storage bin
    group("Props / Transparent storage box")
    x, y = 0.665, 0.82
    for dx, dy, dz, wx, wy, wz in [
        (0, 0, 0.022, 0.40, 0.51, 0.010),
        (-0.208, 0, 0.179, 0.010, 0.51, 0.318),
        (0.208, 0, 0.179, 0.010, 0.51, 0.318),
        (0, -0.26, 0.179, 0.426, 0.010, 0.318),
        (0, 0.26, 0.179, 0.426, 0.010, 0.318),
    ]:
        B("Storage bin translucent body", (x + dx, y + dy, dz), (wx, wy, wz), clearplastic, 0.006)
    B("Storage bin lid", (x, y, 0.349), (0.450, 0.557, 0.021), clearplastic, 0.015)
    polyloop(
        "Storage lid raised lip",
        [
            (x - 0.205, y - 0.25, 0.362),
            (x + 0.205, y - 0.25, 0.362),
            (x + 0.205, y + 0.25, 0.362),
            (x - 0.205, y + 0.25, 0.362),
        ],
        0.005,
        clearplastic,
    )
    for yy in (y - 0.273, y + 0.273):
        B("Storage box teal latch", (x, yy, 0.329), (0.151, 0.021, 0.062), teal, 0.006)
    # Six visible toilet rolls have genuinely hollow cores.
    for ix in range(2):
        for iy in range(3):
            xx = x - 0.097 + ix * 0.187
            yy = y - 0.156 + iy * 0.147
            lathe(
                "Toilet roll inside storage",
                (xx, yy, 0.085),
                [(0, 0.020), (0, 0.057), (0.230, 0.057), (0.230, 0.020), (0, 0.020)],
                tissue,
                40,
            )
            ring("Toilet roll cardboard core", (xx, yy, 0.316), 0.020, 0.002, ivory_fabric)
    cloth(
        "Grey socks on storage lid",
        (0.632, 0.820, 0.378),
        (0.20, 0.13),
        cotton,
        waves=0.006,
        res=(30, 24),
        angle=0.28,
    )
    softbox(
        "Folded sock cuff", (0.56, 0.823, 0.386), (0.076, 0.094, 0.023), backpack, wrinkle=0.002
    )
    # Scissors: metal crossing blades, elliptical molded finger holes.
    tube(
        "Scissor blade one",
        [(0.79, 0.974, 0.369), (0.767, 0.892, 0.369), (0.744, 0.865, 0.369)],
        0.003,
        silver,
    )
    tube(
        "Scissor blade two",
        [(0.747, 0.971, 0.370), (0.767, 0.892, 0.370), (0.788, 0.865, 0.370)],
        0.003,
        silver,
    )
    C("Scissor pivot", (0.767, 0.918, 0.373), 0.004, 0.003, silver)
    for xx in (0.742, 0.791):
        points = [
            (
                xx + 0.013 * math.cos(i * 2 * math.pi / 40),
                0.848 + 0.021 * math.sin(i * 2 * math.pi / 40),
                0.373,
            )
            for i in range(41)
        ]
        tube("Scissor navy finger loop", points, 0.0033, navy)

    # --------------------------------------------------------------- sneakers
    group("Props / Entry sneakers")

    def sneaker(name, center, angle=0, scale=1):
        before = {o.name for o in bpy.data.objects}
        x, y, z = center
        softbox(
            name + " sculpted sole",
            (x, y, z + 0.025),
            (0.104 * scale, 0.260 * scale, 0.043 * scale),
            sole,
            n=40,
            rings=16,
            wrinkle=0.0003,
        )
        softbox(
            name + " knitted upper",
            (x, y - 0.007 * scale, z + 0.065 * scale),
            (0.095 * scale, 0.237 * scale, 0.082 * scale),
            shoeupper,
            n=40,
            rings=20,
            wrinkle=0.0015,
        )
        E(
            name + " ankle opening",
            (x, y + 0.073 * scale, z + 0.099 * scale),
            (0.032 * scale, 0.043 * scale, 0.008),
            rubber,
        )
        softbox(
            name + " tongue",
            (x, y + 0.008 * scale, z + 0.111 * scale),
            (0.039 * scale, 0.083 * scale, 0.025),
            cotton,
            n=24,
            rings=14,
            wrinkle=0.001,
        )
        for i in range(6):
            yy = y - 0.054 * scale + i * 0.020 * scale
            zz = z + 0.103 * scale + 0.009 * scale * math.sin(i / 5 * math.pi)
            tube(
                name + " crossed lace",
                [
                    (x - 0.026 * scale, yy, zz),
                    (x, yy + 0.012 * scale, zz + 0.006 * scale),
                    (x + 0.025 * scale, yy + 0.018 * scale, zz),
                ],
                0.0017,
                sole,
            )
            for xx in (x - 0.028 * scale, x + 0.028 * scale):
                E(name + " eyelet", (xx, yy, zz), (0.0035, 0.0035, 0.001), silver)
        for yy in (y - 0.086 * scale, y - 0.025 * scale, y + 0.047 * scale):
            tube(
                name + " sole relief",
                [
                    (x - 0.050 * scale, yy, z + 0.021 * scale),
                    (x + 0.050 * scale, yy, z + 0.021 * scale),
                ],
                0.001,
                shoeupper,
            )
        for side in (-1, 1):
            tube(
                name + " side stitched seam",
                [
                    (x + side * 0.046 * scale, y - 0.09 * scale, z + 0.059 * scale),
                    (x + side * 0.049 * scale, y + 0.007 * scale, z + 0.071 * scale),
                    (x + side * 0.036 * scale, y + 0.092 * scale, z + 0.096 * scale),
                ],
                0.0007,
                sole,
            )
        transform_group(before, (x, y, z), angle)

    sneaker("Entry left sneaker", (-0.36, 0.63, 0.001), -0.22)
    sneaker("Entry right sneaker", (-0.22, 0.68, 0.001), 0.16)
    sneaker("Under dresser white sneaker", (-0.83, 2.97, 0.001), -0.05, 0.88)

    # ------------------------------------------------------ kitchen incidents
    group("Props / Kitchen counter details")
    # The bottle has a petaloid base, shoulder, molded rings, water and cap flutes.
    bottle = (0.52, 0.31, 0.941)
    profile = [
        (0, 0.028),
        (0.006, 0.036),
        (0.027, 0.038),
        (0.077, 0.035),
        (0.16, 0.035),
        (0.184, 0.032),
        (0.202, 0.021),
        (0.220, 0.0125),
        (0.236, 0.0125),
    ]
    lathe("Clear water bottle PET shell", bottle, profile, bottleplastic, 56)
    lathe(
        "Bottle water volume",
        (0.52, 0.31, 0.946),
        [(0, 0.031), (0.121, 0.033), (0.126, 0.032)],
        water,
        48,
    )
    lathe(
        "Green bottle wraparound label",
        (0.52, 0.31, 0.941),
        [(0.079, 0.0356), (0.130, 0.0356)],
        green,
        56,
    )
    C("Bottle green screw cap", (0.52, 0.31, 1.184), 0.0145, 0.018, green)
    for i in range(28):
        a = i * 2 * math.pi / 28
        tube(
            "Bottle cap flute",
            [
                (0.52 + 0.0147 * math.cos(a), 0.31 + 0.0147 * math.sin(a), 1.177),
                (0.52 + 0.0147 * math.cos(a), 0.31 + 0.0147 * math.sin(a), 1.191),
            ],
            0.0005,
            green,
        )
    for zz in (0.965, 0.978, 1.093):
        ring("Bottle molded grip ring", (0.52, 0.31, zz), 0.036, 0.0008, bottleplastic)
    C("Cream insulated travel bottle", (0.69, 0.37, 1.025), 0.026, 0.175, paper)
    C("Travel bottle cap", (0.69, 0.37, 1.119), 0.027, 0.025, tissue)
    ring("Travel bottle steel rim", (0.69, 0.37, 1.105), 0.0265, 0.0012, silver)
    cloth(
        "Kitchen white bag",
        (0.91, 0.34, 0.943),
        (0.34, 0.26),
        paper,
        waves=0.012,
        res=(34, 30),
        angle=0.17,
    )
    tube(
        "Kitchen shopping bag handle",
        [(0.80, 0.30, 0.958), (0.84, 0.241, 1.003), (0.95, 0.267, 1.027), (1.02, 0.34, 0.96)],
        0.005,
        scarlet,
    )
    softbox("Kitchen dark pouch", (0.83, 0.54, 0.962), (0.17, 0.09, 0.037), rubber, wrinkle=0.0005)
    softbox(
        "Folded olive fabric cap",
        (0.39, 0.41, 0.970),
        (0.143, 0.124, 0.060),
        ivory_fabric,
        wrinkle=0.004,
    )
    cloth(
        "Olive cap brim", (0.35, 0.47, 0.943), (0.12, 0.12), ivory_fabric, waves=0.003, res=(20, 20)
    )

    # Open yellow recycling bin, corresponding to the bright object beside the desk.
    group("Props / Utility objects")
    x, y = 1.25, 0.91
    for dx, dy, dz, wx, wy, wz in [
        (0, 0, 0.01, 0.24, 0.19, 0.02),
        (-0.126, 0, 0.139, 0.014, 0.216, 0.264),
        (0.126, 0, 0.139, 0.014, 0.216, 0.264),
        (0, -0.102, 0.139, 0.264, 0.014, 0.264),
        (0, 0.102, 0.139, 0.264, 0.014, 0.264),
    ]:
        B("Yellow recycling bin", (x + dx, y + dy, dz), (wx, wy, wz), yellow, 0.006)
    polyloop(
        "Yellow bin thick top rim",
        [
            (x - 0.132, y - 0.11, 0.275),
            (x + 0.132, y - 0.11, 0.275),
            (x + 0.132, y + 0.11, 0.275),
            (x - 0.132, y + 0.11, 0.275),
        ],
        0.008,
        yellow,
    )

    return {
        "objects_added": len(bpy.data.objects) - created_before,
        "seed": 521,
        "authorship": "procedural geometry and neutral labels",
    }
