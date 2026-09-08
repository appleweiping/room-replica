"""Editable desktop roll, open wrapper and net tote after desktop_surface_v4.

Coordinates are photograph-informed estimates in the calibrated r08 room.
The original three groups are replaced; the decorative handset *carton* and
separate silver sachet move rigidly onto their supports. Devices are untouched.
"""

from pathlib import Path
import json
import math

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

VERSION = "5.0.0"
PREFIX = "DesktopPackagesV5_"
COLLECTION = "Props / Desktop packages v5"
DESK_Z = 0.7412


def _clearance_under_roll(p):
    """Lower flexible packaging beneath the fitted rigid roll's underside."""
    front = Vector((1.328, 1.7164, 0.8315))
    axis = Vector((0.2937, -0.1268, -0.0024)).normalized()
    horizontal = Vector((axis.x, axis.y, 0)).normalized()
    side = Vector((-horizontal.y, horizontal.x, 0))
    delta = p - front
    along = delta.dot(horizontal)
    across = delta.dot(side)
    if -0.010 < along < 0.328 and abs(across) < 0.0674:
        bottom = front.z + along * axis.z - min(0.0655, math.sqrt(max(0, 0.0675**2 - across**2)))
        p.z = min(p.z, bottom - 0.0007)
    return p


def _material(name, color, roughness=0.7, metallic=0):
    mat = bpy.data.materials.new(PREFIX + name)
    mat.use_nodes = True
    mat.diffuse_color = (*color, 1)
    bs = mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (*color, 1)
    bs.inputs["Roughness"].default_value = roughness
    bs.inputs["Metallic"].default_value = metallic
    bs.inputs["Specular IOR Level"].default_value = 0.3
    return mat


def _texture(mat, directory, name, socket="Base Color", normal_strength=None):
    im = bpy.data.images.load(str(directory / name), check_existing=True)
    im.colorspace_settings.name = "sRGB" if socket == "Base Color" else "Non-Color"
    im.pack()
    tree = mat.node_tree
    node = tree.nodes.new("ShaderNodeTexImage")
    node.image = im
    bs = tree.nodes.get("Principled BSDF")
    if normal_strength is not None:
        normal = tree.nodes.new("ShaderNodeNormalMap")
        normal.inputs["Strength"].default_value = normal_strength
        tree.links.new(node.outputs["Color"], normal.inputs["Color"])
        tree.links.new(normal.outputs["Normal"], bs.inputs["Normal"])
    else:
        tree.links.new(node.outputs["Color"], bs.inputs[socket])


def _mesh(name, verts, faces, mat, col, uvs=None, smooth=True):
    mesh = bpy.data.meshes.new(PREFIX + name)
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    ob = bpy.data.objects.new(PREFIX + name, mesh)
    col.objects.link(ob)
    mesh.materials.append(mat)
    for poly in mesh.polygons:
        poly.use_smooth = smooth
    uv = mesh.uv_layers.new(name="Surface UV")
    if uvs is None:
        uvs = [(v[0], v[1]) for v in verts]
    for poly in mesh.polygons:
        for li in poly.loop_indices:
            uv.data[li].uv = uvs[mesh.loops[li].vertex_index]
    return ob


def _curve(name, points, radius, mat, col, cyclic=False):
    data = bpy.data.curves.new(PREFIX + name, "CURVE")
    data.dimensions = "3D"
    data.bevel_depth = radius
    data.bevel_resolution = 2
    spline = data.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for point, value in zip(spline.points, points):
        point.co = (*value, 1)
    spline.use_cyclic_u = cyclic
    ob = bpy.data.objects.new(PREFIX + name, data)
    col.objects.link(ob)
    data.materials.append(mat)
    return ob


def _roll(col, mats):
    # A roll-end center is the same identifiable static feature in refs 2/9.
    # Rear end and radius are less certain because of foreshortening/occlusion.
    front = Vector((1.328, 1.7164, 0.8315))
    axis = Vector((0.2937, -0.1268, -0.0024)).normalized()
    lateral = Vector((-axis.y, axis.x, 0)).normalized()
    up = axis.cross(lateral)
    length = 0.318
    n = 192

    def radial(theta, radius, t):
        r = radius * (1 + 0.010 * math.cos(theta * 3 + 0.3) + 0.006 * math.cos(theta * 7 + 1.8))
        z = max(-0.0655, r * math.sin(theta))
        return lateral * (r * math.cos(theta)) + up * z

    def coord(t, theta, radius=0.0675):
        edge = (0.00052 * math.sin(theta * 7 + 0.8) + 0.00023 * math.sin(theta * 19 + 1.4)) * (
            math.exp(-t * 70) - math.exp(-(1 - t) * 70)
        )
        return front + axis * (t * length + edge) + radial(theta, radius, t)

    verts = []
    uv = []
    longitudinal = 40
    for i in range(longitudinal + 1):
        t = i / longitudinal
        for j in range(n + 1):
            theta = 2 * math.pi * j / n
            verts.append(coord(t, theta))
            uv.append((t * 3.0, j / n * 4))
    faces = []
    for i in range(longitudinal):
        for j in range(n):
            a = i * (n + 1) + j
            faces.append((a, a + 1, a + n + 2, a + n + 1))
    _mesh("Paper_roll_embossed_outer", verts, faces, mats["paper"], col, uv)

    for end in (0, 1):
        verts, uv, faces = [], [], []
        radial_steps = 44
        for ring in range(radial_steps + 1):
            r = 0.0260 + (0.0675 - 0.0260) * ring / radial_steps
            for j in range(n + 1):
                theta = 2 * math.pi * j / n
                p = coord(end, theta, r)
                p += axis * (
                    (-1 if end == 0 else 1) * (0.00012 * math.cos(r * 19200 + theta * 0.4))
                )
                verts.append(p)
                uv.append(
                    (
                        0.5 + 0.5 * r / 0.069 * math.cos(theta),
                        0.5 + 0.5 * r / 0.069 * math.sin(theta),
                    )
                )
        for ring in range(radial_steps):
            for j in range(n):
                a = ring * (n + 1) + j
                face = (a, a + n + 1, a + n + 2, a + 1)
                faces.append(face if end == 0 else tuple(reversed(face)))
        _mesh(f"Paper_roll_layered_end_{end}", verts, faces, mats["paper_end"], col, uv)
    # The brown core is a tube, with actual annular wall thickness and no caps.
    verts, uv, faces = [], [], []
    for t, r in ((0.002, 0.02595), (0.998, 0.02595), (0.998, 0.02475), (0.002, 0.02475)):
        for j in range(n + 1):
            theta = 2 * math.pi * j / n
            verts.append(
                front
                + axis * (length * t)
                + lateral * (r * math.cos(theta))
                + up * (r * math.sin(theta))
            )
            uv.append((j / n, t))
    for ring in range(4):
        for j in range(n):
            a = ring * (n + 1) + j
            b = ((ring + 1) % 4) * (n + 1) + j
            faces.append((a, a + 1, b + 1, b))
    _mesh("Paper_roll_hollow_cardboard_core", verts, faces, mats["cardboard"], col, uv)
    # One almost flush paper edge follows the underside and curls away slightly.
    edge = [
        coord(
            0.05 + 0.89 * i / 90, 4.35 + 0.09 * math.exp(-(((i / 90 - 0.68) / 0.20) ** 2)), 0.0677
        )
        for i in range(91)
    ]
    _curve("Paper_roll_loose_sheet_edge", edge, 0.00016, mats["paper_edge"], col)
    return {
        "front_core_center": list(front),
        "rear_core_center": list(front + axis * length),
        "length_m": length,
        "outer_radius_m": 0.0675,
        "core_inner_radius_m": 0.02475,
        "core_wall_m": 0.0012,
    }


def _carton():
    prefixes = ("Desk white handset carton", "Desk handset carton", "Desk carton printed")
    items = [ob for ob in bpy.data.objects if ob.name.startswith(prefixes)]
    base = bpy.data.objects.get("Desk white handset carton base")
    if base is None:
        raise ValueError("Expected original decorative handset carton")
    old = base.matrix_world.translation.copy()
    destination = Vector((1.447, 1.519, 0.790))
    transform = (
        Matrix.Translation(destination) @ Matrix.Rotation(0.08, 4, "Z") @ Matrix.Translation(-old)
    )
    for ob in items:
        ob.matrix_world = transform @ ob.matrix_world
    return {
        "objects": [ob.name for ob in items],
        "old_base_center": list(old),
        "new_base_center": list(destination),
        "yaw_delta_degrees": math.degrees(0.08),
        "size_unchanged": True,
        "fit_status": "Approximate center/axis match; source carton corners are partly obscured. Camera12 is an approximate review camera.",
    }


def _tote(col, mats):
    center = Vector((1.567, 1.478, DESK_Z))
    angle = -0.07
    ex = Vector((math.cos(angle), math.sin(angle), 0))
    ey = Vector((-math.sin(angle), math.cos(angle), 0))
    hx, hy = 0.199, 0.160

    def point(u, v, layer=0):
        # Asymmetric long folds and a collapsed turnover at the near right hem.
        def g(a, b):
            return math.exp(-((a / b) ** 2))
        z = 0.002 + 0.035 * g(v - 0.50 * u - 0.22, 0.31) * g(u + 0.2, 1.5)
        z += 0.027 * g(u + 0.50, 0.21) * g(v + 0.3, 0.85)
        z += 0.026 * g(v + 0.80, 0.20) * g(u - 0.4, 0.65)
        z += 0.020 * g(v - 0.76, 0.19) * g(u - 0.36, 0.51)
        z += 0.013 * g(v + 0.17 * u + 0.15, 0.15) * g(u - 0.6, 0.5)
        xx = hx * u + 0.008 * g(v + 0.8, 0.3) * g(u - 0.5, 0.8)
        yy = hy * v + 0.006 * g(u + 0.8, 0.25) * g(v - 0.2, 0.8)
        p = center + ex * xx + ey * yy
        z *= 1 - 0.97 * g(u + 0.82, 0.28) * g(v - 0.80, 0.31)
        z *= 1 - 0.97 * g(u - 0.88, 0.23) * g(v + 0.43, 0.39)
        z = max(0.0008, z - layer * 0.013)
        # The unchanged-size carton is a physical contact constraint. Keep the
        # net beneath it, instead of drawing a mesh over a solid carton.
        if 1.357 < p.x < 1.537 and 1.467 < p.y < 1.571:
            z = min(z, 0.0316)
        # Rear half of the paper roll lies on this folded net layer.
        if p.x > 1.47 and 1.55 < p.y < 1.64:
            z = min(z, 0.020)
        p.z += z
        return _clearance_under_roll(p)

    # Diamond knot net is actual 3D open geometry, with cream tape-like cords.
    verts, faces, uv = [], [], []
    segments = 96
    for family in (-1, 1):
        for k in range(-48, 49):
            c = k / 24
            samples = []
            for i in range(segments + 1):
                u = -1 + 2 * i / segments
                v = family * u + c
                if -1 <= v <= 1:
                    samples.append((u, v))
            if len(samples) < 2:
                continue
            start = len(verts)
            for i, (u, v) in enumerate(samples):
                p = point(u, v)
                tangent = (ex + ey * family).normalized()
                side = Vector((-tangent.y, tangent.x, 0))
                width = 0.00112 * (1 + 0.14 * math.cos((u + v) * 17 + 0.7))
                # Tiny alternating interlace contact, well below silhouette scale.
                p.z += 0.00034 * math.cos((u - v) * math.pi * 24) * (1 if family == 1 else -1)
                for lateral, height in (
                    (-1, 0),
                    (-0.7, 0.00065),
                    (0.7, 0.00065),
                    (1, 0),
                    (0.7, -0.0004),
                    (-0.7, -0.0004),
                ):
                    verts.append(p + side * (lateral * width) + Vector((0, 0, height)))
                    uv.append(((u + 1) / 2, (v + 1) / 2))
            for i in range(len(samples) - 1):
                for j in range(6):
                    a = start + i * 6 + j
                    b = start + i * 6 + (j + 1) % 6
                    faces.append((a, b, b + 6, a + 6))
    _mesh("Cream_tote_open_diamond_net", verts, faces, mats["cotton"], col, uv)

    # Continuous woven hems follow the folded net perimeter. The panel stays
    # truly open; it does not become a solid cream rectangle behind the holes.
    for side in (-1, 1):
        border = []
        for i in range(101):
            border.append(point(-1 + 2 * i / 100, side))
        _ribbon("Cream_tote_bound_long_hem_" + str(side), border, 0.013, mats["cotton"], col)
    for side in (-1, 1):
        border = [point(side, -1 + 2 * i / 100) for i in range(101)]
        _ribbon("Cream_tote_bound_end_hem_" + str(side), border, 0.011, mats["cotton"], col)

    # Flattened webbing handles: loops are broad straps rather than white tubes.
    for index, coords in enumerate(
        (
            [
                (1.425, 1.330, 0.765),
                (1.385, 1.332, 0.759),
                (1.332, 1.310, 0.750),
                (1.299, 1.368, 0.749),
                (1.354, 1.416, 0.748),
                (1.421, 1.400, 0.752),
                (1.553, 1.317, 0.769),
            ],
            [
                (1.58, 1.324, 0.770),
                (1.50, 1.305, 0.758),
                (1.407, 1.270, 0.748),
                (1.320, 1.300, 0.748),
                (1.306, 1.343, 0.752),
                (1.360, 1.348, 0.754),
                (1.470, 1.328, 0.766),
            ],
        )
    ):
        smooth = []
        # Catmull-Rom interpolation through deliberately nonuniform folds.
        control = [Vector(v) for v in coords]
        for p in control:
            if p.z <= 0.7521:
                p.z = DESK_Z + 0.0010
        for end in (0, -1):
            u = max(-1, min(1, (control[end] - center).dot(ex) / hx))
            control[end] = point(u, -1) + Vector((0, 0, 0.0006))
        arr = [control[0]] + control + [control[-1]]
        for i in range(1, len(arr) - 2):
            p0, p1, p2, p3 = arr[i - 1 : i + 3]
            for j in range(16):
                t = j / 16
                p = 0.5 * (
                    (2 * p1)
                    + (-p0 + p2) * t
                    + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                    + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t
                )
                p.z = max(DESK_Z + 0.0006, p.z)
                smooth.append(p)
        _ribbon(f"Cream_tote_flat_handle_{index}", smooth, 0.015, mats["cotton"], col)
    return {
        "body_center": list(center),
        "nominal_size_xy": [hx * 2, hy * 2],
        "real_holes": True,
        "cord_width_m": 0.00224,
        "carton_contact_cap_z": DESK_Z + 0.0316,
    }


def _ribbon(name, points, width, mat, col):
    verts, faces, uv = [], [], []
    for i, p in enumerate(points):
        tangent = Vector(points[min(len(points) - 1, i + 1)]) - Vector(points[max(0, i - 1)])
        side = Vector((-tangent.y, tangent.x, 0)).normalized()
        for j in range(5):
            u = -1 + j / 2
            verts.append(Vector(p) + side * (u * width / 2) + Vector((0, 0, 0.0006 * (1 - u * u))))
            uv.append((i / max(1, len(points) - 1), j / 4))
    for i in range(len(points) - 1):
        for j in range(4):
            a = i * 5 + j
            faces.append((a, a + 1, a + 6, a + 5))
    ob = _mesh(name, verts, faces, mat, col, uv)
    solid = ob.modifiers.new("Cotton webbing thickness .55 mm", "SOLIDIFY")
    solid.thickness = 0.00055
    return ob


def _wrapper(col, mats):
    front = Vector((1.123, 1.563, 0.778))
    axis = Vector((0.923, 0.385, 0)).normalized()
    side = Vector((-axis.y, axis.x, 0))
    length = 0.262
    longitudinal = 100
    around = 160
    phone = bpy.data.objects["Phone glass"]
    phone_box = [phone.matrix_world @ Vector(v) for v in phone.bound_box]
    phone_low = Vector(tuple(min(p[i] for p in phone_box) for i in range(3)))
    phone_high = Vector(tuple(max(p[i] for p in phone_box) for i in range(3)))

    def support_z(p):
        # Only the small near-right corner overlaps the true, unchanged phone.
        # A smooth lift over its edge avoids driving the wrapper through glass.
        dx = max(phone_low.x - p.x, 0, p.x - phone_high.x)
        dy = max(phone_low.y - p.y, 0, p.y - phone_high.y)
        blend = math.exp(-((dx / 0.009) ** 2) - (dy / 0.009) ** 2)
        return DESK_Z + 0.0005 + (phone_high.z - DESK_Z) * blend

    # Gaussian creases are localized compression lines with independent
    # origins/directions, rather than an evenly spaced wavy mouth silhouette.
    creases = (
        (0.12, 0.5, 0.008, 0.24, 0.19),
        (0.34, 2.2, -0.021, 0.35, 0.24),
        (0.67, 0.9, 0.013, 0.18, 0.29),
        (0.83, 2.65, -0.014, 0.22, 0.23),
        (0.46, 1.56, -0.014, 0.31, 0.20),
        (0.21, 3.7, 0.005, 0.2, 0.30),
        (0.17, 1.08, -0.012, 0.13, 0.25),
        (0.72, 1.75, -0.017, 0.11, 0.41),
    )

    def surface(t, theta):
        width = 0.097 * (0.91 + 0.12 * math.exp(-(((t - 0.35) / 0.30) ** 2))) * (1 - 0.07 * t**5)
        width -= 0.012 * math.exp(-(((t - 0.28) / 0.085) ** 2)) + 0.006 * math.exp(
            -(((t - 0.67) / 0.13) ** 2)
        )
        height = 0.023 + 0.027 * math.exp(-(((t - 0.45) / 0.32) ** 2))
        height *= 1 - 0.79 * t**7
        center = front + axis * (length * t)
        center.z = DESK_Z + 0.002 + height + 0.004 * math.exp(-(((t - 0.45) / 0.4) ** 2))
        center += side * (0.014 * math.exp(-(((t - 0.61) / 0.18) ** 2)) - 0.008 * t)
        across = math.cos(theta)
        vertical = math.sin(theta)
        displacement = 0
        for at, ang, depth, spread, angular_width in creases:
            dtheta = math.atan2(
                math.sin(theta - ang - 0.7 * (t - at)), math.cos(theta - ang - 0.7 * (t - at))
            )
            displacement += (
                depth
                * math.exp(-(((t - at) / spread) ** 2))
                * math.exp(-((dtheta / angular_width) ** 2))
            )
        displacement += (
            0.0011 * math.sin(theta * 11 + t * 19 + 0.7) * math.exp(-(((t - 0.10) / 0.24) ** 2))
        )
        displacement += (
            0.0008 * math.sin(theta * 19 - t * 27) * math.exp(-(((t - 0.83) / 0.19) ** 2))
        )
        # A asymmetric tipped corner and a gently pinched front opening.
        flap = 0.010 * math.exp(-(((theta - 0.53) / 0.33) ** 2)) * math.exp(-((t / 0.17) ** 2))
        p = center + side * ((width + displacement) * across)
        p.z += (height + displacement) * vertical + flap
        p.z += (
            0.007
            * math.exp(-(((t - 0.21) / 0.19) ** 2))
            * math.exp(-(((theta - 2.05) / 0.38) ** 2))
        )
        p += axis * (
            (0.009 * math.cos(theta * 3 + 0.5) + 0.003 * math.cos(theta * 7 + 1.3))
            * math.exp(-((t / 0.09) ** 2))
        )
        if vertical < -0.70:
            p.z = min(p.z, support_z(p) + 0.025 * ((vertical + 1) / 0.30) ** 2)
        p.z = max(support_z(p), p.z)
        return _clearance_under_roll(p)

    verts, faces, uv = [], [], []
    for i in range(longitudinal + 1):
        t = i / longitudinal
        for j in range(around + 1):
            theta = 2 * math.pi * j / around
            verts.append(surface(t, theta))
            uv.append((j / around, t))
    for i in range(longitudinal):
        for j in range(around):
            a = i * (around + 1) + j
            faces.append((a, a + 1, a + around + 2, a + around + 1))
    ob = _mesh("Open_crisps_laminate_shell", verts, faces, mats["wrapper"], col, uv)
    ob.data.materials.append(mats["silver"])
    solid = ob.modifiers.new("Thin metallized package wall .14 mm", "SOLIDIFY")
    solid.thickness = 0.00014
    solid.offset = -1
    solid.material_offset = 1
    solid.material_offset_rim = 1
    _curve(
        "Open_crisps_fine_cut_rim",
        [surface(0, 2 * math.pi * j / around) for j in range(around)],
        0.00023,
        mats["silver"],
        col,
        True,
    )
    # Turned-out lower silver lip: no cap closes the actual opening.
    verts, uv, faces = [], [], []
    for i in range(15):
        s = i / 14
        for j in range(81):
            theta = math.pi + math.pi * j / 80
            p = surface(0, theta) - axis * (0.043 * s)
            p.z += 0.011 * math.sin(math.pi * s) * (1 + 0.24 * math.cos(theta * 3 + 0.6))
            p += side * (0.004 * s * math.cos(theta * 5))
            p.z = max(support_z(p), p.z)
            verts.append(p)
            uv.append((j / 80, s))
    for i in range(14):
        for j in range(80):
            a = i * 81 + j
            faces.append((a, a + 1, a + 82, a + 81))
    ob = _mesh("Open_crisps_outturned_silver_lip", verts, faces, mats["silver"], col, uv)
    solid = ob.modifiers.new("Silver film thickness", "SOLIDIFY")
    solid.thickness = 0.00014
    # Rear heat-seal joins both collapsed layers; fine transverse crimps.
    seal = [surface(1, 2 * math.pi * j / around) for j in range(around)]
    _curve("Open_crisps_rear_heat_seal", seal, 0.0006, mats["seal"], col, True)
    return {
        "open_end_axis_center": list(front),
        "rear_center_xy": list((front + axis * length)[:2]),
        "length_m": length,
        "maximum_width_m": 0.20,
        "laminate_thickness_m": 0.00014,
        "neutral_original_print": True,
    }


def _small_foil_packet():
    """Rigid contact correction of the separate silver sachet, as authorized."""
    packet = bpy.data.objects["Desk small torn foil packet on crisps"]
    items = [
        ob
        for ob in bpy.data.objects
        if ob.name.startswith(
            ("Desk small torn foil packet on crisps", "Foil packet pressed crimp")
        )
    ]
    points = [packet.matrix_world @ v.co for v in packet.data.vertices]
    old = Vector(
        tuple((min(p[i] for p in points) + max(p[i] for p in points)) / 2 for i in range(3))
    )
    target = Vector((1.303, 1.612, old.z))
    transform = (
        Matrix.Translation(target) @ Matrix.Rotation(-0.18, 4, "Z") @ Matrix.Translation(-old)
    )
    for ob in items:
        ob.matrix_world = transform @ ob.matrix_world
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    supports = []
    names = (
        PREFIX + "Open_crisps_laminate_shell",
        "Desk handset carton fitted lid",
        PREFIX + "Cream_tote_open_diamond_net",
    )
    for name in names:
        ob = bpy.data.objects[name]
        ev = ob.evaluated_get(dg)
        mesh = ev.to_mesh()
        supports.append(
            BVHTree.FromPolygons(
                [ev.matrix_world @ v.co for v in mesh.vertices],
                [tuple(p.vertices) for p in mesh.polygons],
                all_triangles=False,
            )
        )
        ev.to_mesh_clear()
    correction = -1e6
    support_count = 0
    for v in packet.data.vertices:
        p = packet.matrix_world @ v.co
        top = DESK_Z
        for bvh in supports:
            hit, normal, index, distance = bvh.ray_cast(
                Vector((p.x, p.y, 1.5)), Vector((0, 0, -1)), 1
            )
            if hit is not None:
                top = max(top, hit.z)
                support_count += 1
        correction = max(correction, top + 0.00045 - p.z)
    for ob in items:
        ob.matrix_world = Matrix.Translation((0, 0, correction)) @ ob.matrix_world
    return {
        "objects": [ob.name for ob in items],
        "old_bbox_center": list(old),
        "new_bbox_center": [target.x, target.y, target.z + correction],
        "yaw_delta_degrees": math.degrees(-0.18),
        "vertical_contact_adjustment_m": correction,
        "ray_support_hits": support_count,
        "geometry_unchanged": True,
        "placement_status": "Rigid estimate from broad sachet silhouette in references2/9/12; final height determined against the actual wrapper/tote/carton support geometry.",
    }


def _seat_roll():
    """Keep the fitted axis; resolve only its small vertical support clearance."""
    dg = bpy.context.evaluated_depsgraph_get()
    supports = []
    for name in (
        PREFIX + "Open_crisps_laminate_shell",
        PREFIX + "Cream_tote_open_diamond_net",
        "Desk handset carton fitted lid",
    ):
        ob = bpy.data.objects[name]
        ev = ob.evaluated_get(dg)
        mesh = ev.to_mesh()
        supports.append(
            BVHTree.FromPolygons(
                [ev.matrix_world @ v.co for v in mesh.vertices],
                [tuple(p.vertices) for p in mesh.polygons],
                all_triangles=False,
            )
        )
        ev.to_mesh_clear()
    outer = bpy.data.objects[PREFIX + "Paper_roll_embossed_outer"]
    delta = -1e6
    witness = None
    for v in outer.data.vertices:
        p = outer.matrix_world @ v.co
        if p.z > 0.801:
            continue
        top = DESK_Z
        for bvh in supports:
            hit, normal, index, distance = bvh.ray_cast(
                Vector((p.x, p.y, 1.5)), Vector((0, 0, -1)), 1
            )
            if hit is not None:
                top = max(top, hit.z)
        candidate = top + 0.0004 - p.z
        if candidate > delta:
            delta = candidate
            witness = [p.x, p.y, top]
    # A large discrepancy is a placement error, not permission to undermine
    # the calibrated photograph correspondence by dropping the roll blindly.
    if abs(delta) > 0.012:
        raise ValueError(
            f"Paper roll support differs by {delta:.4f} m at {witness}; review placement"
        )
    for ob in bpy.data.objects:
        if ob.name.startswith(PREFIX + "Paper_roll_"):
            ob.matrix_world = Matrix.Translation((0, 0, delta)) @ ob.matrix_world
    return {"vertical_adjustment_m": delta, "support_witness_world": witness, "clearance_m": 0.0004}


def refine_desktop_packages(M=None, texture_dir=None):
    """Run once after desktop_surface_v4; native/GLB compatible materials."""
    scene = bpy.context.scene
    if scene.get("desktop_packages_refinement") == VERSION:
        return json.loads(scene["desktop_packages_audit"])
    if not scene.get("desktop_surface_v4"):
        raise ValueError("desktop_packages_v5 must run after desktop_surface_v4")
    directory = (
        Path(texture_dir)
        if texture_dir
        else Path(__file__).resolve().parents[1] / "assets/textures/desktop_packages_v5"
    )
    required = (
        "paper-emboss-normal.png",
        "paper-fiber-albedo.png",
        "paper-end-normal.png",
        "paper-end-albedo.png",
        "neutral-crisps-print.png",
        "wrapper-roughness.png",
        "wrapper-micro-normal.png",
    )
    missing = [f for f in required if not (directory / f).is_file()]
    if missing:
        raise FileNotFoundError(str(missing))
    old_prefixes = (
        "Embossed paper towel roll",
        "Paper roll cardboard core",
        "Visible rolled paper layers",
        "Cream shopping tote",
        "Canvas tote handle",
        "Open snack bag foil body",
        "Snack bag crimped open silver mouth",
        "Snack bag red printed badge",
        "Snack neutral package title",
    )
    removed = [ob.name for ob in bpy.data.objects if ob.name.startswith(old_prefixes)]
    for name in removed:
        bpy.data.objects.remove(bpy.data.objects[name], do_unlink=True)
    col = bpy.data.collections.get(COLLECTION)
    if col is None:
        col = bpy.data.collections.new(COLLECTION)
        scene.collection.children.link(col)
    mats = {
        "paper": _material("Embossed offwhite paper", (0.87, 0.86, 0.81), 0.87),
        "paper_end": _material("Rolled paper end", (0.86, 0.84, 0.76), 0.94),
        "paper_edge": _material("Thin white sheet edge", (0.85, 0.83, 0.77), 0.88),
        "cardboard": _material("Warm brown cardboard tube", (0.11, 0.070, 0.034), 0.93),
        "cotton": _material("Cream cotton net and woven tape", (0.67, 0.63, 0.50), 0.84),
        "wrapper": _material("Printed metallized laminate", (0.20, 0.16, 0.08), 0.51, 0.12),
        "silver": _material("Dull silver package interior", (0.46, 0.47, 0.46), 0.38, 0.84),
        "seal": _material("Dark heat sealed laminate", (0.025, 0.023, 0.016), 0.55, 0.10),
    }
    _texture(mats["paper"], directory, "paper-fiber-albedo.png")
    _texture(mats["paper"], directory, "paper-emboss-normal.png", "Normal", 0.85)
    _texture(mats["paper_end"], directory, "paper-end-albedo.png")
    _texture(mats["paper_end"], directory, "paper-end-normal.png", "Normal", 0.30)
    _texture(mats["wrapper"], directory, "neutral-crisps-print.png")
    _texture(mats["wrapper"], directory, "wrapper-roughness.png", "Roughness")
    _texture(mats["wrapper"], directory, "wrapper-micro-normal.png", "Normal", 0.22)
    _texture(mats["silver"], directory, "wrapper-micro-normal.png", "Normal", 0.45)
    audit = {
        "version": VERSION,
        "removed": removed,
        "desk_z_m": DESK_Z,
        "roll": _roll(col, mats),
        "carton": _carton(),
        "tote": _tote(col, mats),
        "wrapper": _wrapper(col, mats),
        "scope": "Three packages and decorative handset carton only; electronics/cameras/desk/other objects untouched.",
    }
    bpy.context.view_layer.update()
    audit["roll"]["support_contact"] = _seat_roll()
    for key in ("front_core_center", "rear_core_center"):
        audit["roll"][key][2] += audit["roll"]["support_contact"]["vertical_adjustment_m"]
    bpy.context.view_layer.update()
    audit["small_foil_packet"] = _small_foil_packet()
    audit["scope"] = (
        "Three packages, decorative handset carton and separate silver sachet only; electronics/cameras/desk/other objects untouched."
    )
    bpy.context.view_layer.update()
    audit["created"] = [ob.name for ob in col.objects]
    audit["base_vertices"] = sum(len(ob.data.vertices) for ob in col.objects if ob.type == "MESH")
    scene["desktop_packages_refinement"] = VERSION
    scene["desktop_packages_audit"] = json.dumps(audit)
    return audit
