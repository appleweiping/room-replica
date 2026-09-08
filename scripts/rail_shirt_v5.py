"""Reference-constrained right-rail shirt and clip lamp, after final room layout.

Only the two right lower/middle rail elevations, old white-shirt objects, and old
clip-lamp objects are changed. Reference 2/3 registered-camera triangulation is
stronger evidence than approximate reference 15. Garment is an authored double
panel with continuous rounded support return, not a claimed simulation/scanned
asset. Normal texture is analytic fine knit data; macro folds are nonperiodic.
"""

from __future__ import annotations
import math
from dataclasses import dataclass
import bpy
from mathutils import Vector, Matrix

PREFIX = "RailShirtV5_"
LAMP = "RailLampV5_"


@dataclass(frozen=True)
class RailShirtConfig:
    middle_rail_top: float = 1.2619
    lower_rail_top: float = 0.9184
    shirt_near_offset: float = -0.418
    shirt_top_width: float = 0.368
    shirt_front_drop: float = 0.374
    shirt_rear_drop: float = 0.409
    thickness: float = 0.00065
    detail_u: int = 104
    detail_v: int = 190


def _g(x, c, w):
    return math.exp(-(((x - c) / w) ** 2))


def _smooth(x):
    x = max(0, min(1, x))
    return x * x * (3 - 2 * x)


def _noise(x, y):
    ix = math.floor(x)
    iy = math.floor(y)
    u = _smooth(x - ix)
    v = _smooth(y - iy)

    def h(a, b):
        return ((a * 73856093 ^ b * 19349663 ^ 521123) % 100003) / 100003 - 0.5

    return ((1 - u) * h(ix, iy) + u * h(ix + 1, iy)) * (1 - v) + (
        (1 - u) * h(ix, iy + 1) + u * h(ix + 1, iy + 1)
    ) * v


def _material(name, color, roughness=0.8, metal=0):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    p = mat.node_tree.nodes.get("Principled BSDF")
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = roughness
    p.inputs["Metallic"].default_value = metal
    return mat


def _knit():
    import numpy as np

    name = PREFIX + "Analytic_cotton_knit_normal"
    im = bpy.data.images.get(name)
    if im is None:
        size = 256
        y, x = np.mgrid[0:size, 0:size] / size * 8
        # Interlocking yarn arcs at sub-millimetre relief. This fine textile
        # periodicity is distinct from the individually placed large drape folds.
        phase = (x + 0.18 * np.sin(2 * np.pi * y)) % 1
        yarn = np.exp(-(((phase - 0.3) / 0.11) ** 2)) + 0.75 * np.exp(
            -(((phase - 0.69) / 0.105) ** 2)
        )
        h = yarn * (0.6 + 0.4 * np.cos(2 * np.pi * y))
        dy, dx = np.gradient(h)
        n = np.stack([-dx * 0.7, -dy * 0.7, np.ones_like(dx)], axis=-1)
        n /= np.linalg.norm(n, axis=-1, keepdims=True)
        rgba = np.ones((size, size, 4), dtype=np.float32)
        rgba[:, :, :3] = n * 0.5 + 0.5
        im = bpy.data.images.new(name, width=size, height=size, alpha=True)
        im.colorspace_settings.name = "Non-Color"
        im.pixels.foreach_set(rgba.ravel())
        im.pack()
        im["provenance"] = (
            "Authored analytic knit normal data, 8 by 8 interlocking yarn loops; not a source-photo scan."
        )
    mat = _material(PREFIX + "Warm_white_cotton", (0.81, 0.805, 0.78), 0.82)
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    p = nodes.get("Principled BSDF")
    p.inputs["Sheen Weight"].default_value = 0.14
    p.inputs["Sheen Roughness"].default_value = 0.72
    if nodes.get("Knit normal image") is None:
        t = nodes.new("ShaderNodeTexImage")
        t.name = "Knit normal image"
        t.image = im
        n = nodes.new("ShaderNodeNormalMap")
        n.inputs["Strength"].default_value = 0.33
        links.new(t.outputs["Color"], n.inputs["Color"])
        links.new(n.outputs["Normal"], p.inputs["Normal"])
    return mat


def _mesh(col, name, verts, faces, material, uv=None, thickness=0):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    me.materials.append(material)
    for p in me.polygons:
        p.use_smooth = True
    if uv is not None:
        layer = me.uv_layers.new(name="UVMap")
        for loop in me.loops:
            layer.data[loop.index].uv = uv[loop.vertex_index]
    if thickness:
        m = ob.modifiers.new("Sub-millimetre cotton wall", "SOLIDIFY")
        m.thickness = thickness
        m.offset = 0
    return ob


def _curve(col, name, points, radius, material):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = 12
    cu.bevel_depth = radius
    cu.bevel_resolution = 2
    typ = "POLY" if len(points) > 15 else "BEZIER"
    s = cu.splines.new(typ)
    if typ == "POLY":
        s.points.add(len(points) - 1)
        for p, co in zip(s.points, points):
            p.co = (*co, 1)
    else:
        s.bezier_points.add(len(points) - 1)
        for p, co in zip(s.bezier_points, points):
            p.co = co
            p.handle_left_type = p.handle_right_type = "AUTO"
    ob = bpy.data.objects.new(name, cu)
    col.objects.link(ob)
    cu.materials.append(material)
    return ob


def _box(col, name, loc, dims, mat, basis=None, bevel=0.004):
    from itertools import product

    vs = [tuple(sign[i] * dims[i] / 2 for i in range(3)) for sign in product((-1, 1), repeat=3)]
    fs = [(0, 4, 6, 2), (1, 3, 7, 5), (0, 1, 5, 4), (2, 6, 7, 3), (0, 2, 3, 1), (4, 5, 7, 6)]
    ob = _mesh(col, name, vs, fs, mat)
    if basis is not None:
        ob.matrix_world = basis.to_4x4()
    ob.location = loc
    m = ob.modifiers.new("Injection moulded rounded edge", "BEVEL")
    m.width = bevel
    m.segments = 4
    ob.modifiers.new("Manufactured face normals", "WEIGHTED_NORMAL")
    return ob


def refine_rail_shirt_v5(M=None, config=None):
    """Run after layout/bed-support. Return audit facts; never edits cameras.

    Absolute rail top parameters are intentionally separate from garment shape,
    so a later calibration can adopt/reject these two supported translations.
    """
    c = config if isinstance(config, RailShirtConfig) else RailShirtConfig(**(config or {}))
    middle = bpy.data.objects.get("Bed_end_ladder_rail.006")
    lower = bpy.data.objects.get("Bed_end_ladder_rail.005")
    if middle is None or lower is None:
        raise ValueError("Final right end-frame rail objects are required")
    bpy.context.view_layer.update()
    changes = []
    for ob, target in ((middle, c.middle_rail_top), (lower, c.lower_rail_top)):
        old_top = max((ob.matrix_world @ Vector(p)).z for p in ob.bound_box)
        stamp = ob.get("rail_shirt_v5_original_top", old_top)
        ob["rail_shirt_v5_original_top"] = stamp
        mat = ob.matrix_world.copy()
        mat.translation.z += target - old_top
        ob.matrix_world = mat
        changes.append(
            {
                "object": ob.name,
                "original_top": stamp,
                "target_top": target,
                "translation_z": target - stamp,
                "cross_section_changed": False,
            }
        )
    bpy.context.view_layer.update()
    origin = middle.matrix_world.translation.copy()
    E = middle.matrix_world.to_3x3().col[0].normalized()
    A = middle.matrix_world.to_3x3().col[1].normalized()
    # Final native rails use local X outward, local Y toward the window.
    if E.x < 0:
        E = -E
    if A.y < 0:
        A = -A

    def world(x, y, z):
        return origin + E * x + A * y + Vector((0, 0, z - origin.z))

    remove = [
        o
        for o in bpy.data.objects
        if o.name.startswith(
            (
                "BedV2_Rail_shirt",
                "BedV2_shirt_",
                "Bed_right_white_tshirt",
                "Bed_clip_light_",
                PREFIX,
                LAMP,
            )
        )
    ]
    removed = [o.name for o in remove]
    for ob in remove:
        bpy.data.objects.remove(ob, do_unlink=True)
    name = "07 / Right rail garment V5"
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    cotton = _knit()
    seam = _material(PREFIX + "Cotton_sewn_hem", (0.78, 0.774, 0.75), 0.86)
    plastic = _material(LAMP + "Ivory_ABS", (0.77, 0.775, 0.748), 0.39)
    rubber = _material(LAMP + "White_flex_jacket", (0.79, 0.785, 0.75), 0.64)
    silver = _material(LAMP + "Spring_metal", (0.25, 0.27, 0.28), 0.42, 0.8)
    dark = _material(LAMP + "Recess", (0.07, 0.073, 0.068), 0.65)
    hx = 0.0195
    top = c.middle_rail_top
    # Individually placed tension folds: differing widths, amplitudes, drift and
    # termination length. No repeated sinusoidal pleat profile is used.
    folds = [
        (0.03, 0.012, 0.008, 0.070, 0.38),
        (0.14, 0.008, 0.023, 0.100, 0.82),
        (0.28, 0.018, 0.007, -0.080, 0.30),
        (0.48, 0.018, 0.030, 0.040, 1.0),
        (0.65, 0.010, 0.005, 0.150, 0.40),
        (0.81, 0.010, 0.014, -0.055, 0.75),
        (0.95, 0.015, 0.006, -0.030, 1.0),
    ]

    def face(u, d, rear=False):
        # d=0 at the rail's side tangent, d=1 at an open hem.
        far_inset = (
            0.031 * _smooth(d / 0.85) + 0.029 * _g(d, 0.39, 0.15) - 0.013 * _g(d, 0.12, 0.10)
        )
        near = c.shirt_near_offset - 0.003 * _g(d, 0.78, 0.20)
        width = c.shirt_top_width - far_inset
        y = near + u * width + 0.004 * _noise(u * 7, d * 6) * _smooth(d / 0.12)
        depth = 0.006 + 0.009 * _smooth(d / 0.3) + 0.009 * _g(u, 0.88, 0.16) * _g(d, 0.36, 0.23)
        for centre, w, amp, drift, end in folds:
            path = centre + drift * d + 0.014 * _g(d, 0.45, 0.23) * (centre - 0.45)
            alive = 1 - 0.82 * _smooth((d - end) / 0.24)
            spread = w * (1 + 2.4 * d)
            depth += amp * alive * _g(u, path, spread)
            depth -= 0.35 * amp * alive * _g(u, path + spread * 1.05, spread * 0.70)
        depth += 0.0022 * _noise(u * 22, d * 12) * _smooth(d / 0.08)
        for h, a, w in ((0.12, 0.007, 0.016), (0.25, 0.004, 0.022), (0.43, 0.003, 0.029)):
            depth += a * _g(d, h + 0.37 * (u - 0.75), w) * _g(u, 0.83, 0.20)
        if rear:
            depth = depth * 0.68 + 0.002
        # Rounded, asymmetric hem dips follow distinct drape paths.
        hem = (
            0.007
            + 0.018 * _g(u, 0.28, 0.20)
            + 0.011 * _g(u, 0.72, 0.14)
            - 0.009 * _g(u, 0.96, 0.10)
        )
        drop = c.shirt_rear_drop if rear else c.shirt_front_drop
        z = top - 0.003 - d * (drop + hem) + 0.002 * _noise(u * 12, d * 9) * _smooth(d / 0.12)
        # The left/window edge turns gently inward under its compressed sleeve.
        if not rear:
            depth += 0.014 * _g(u, 0.99, 0.09) * _g(d, 0.28, 0.19)
            z += 0.012 * _g(u, 0.99, 0.085) * _g(d, 0.32, 0.19)
        x = (hx + max(0.002, depth)) * (1 if rear else -1)
        return x, y, z

    # Front hem -> front top -> rounded support -> rear top -> rear hem.
    front_fraction = 0.455
    arc_fraction = 0.09

    def surface(u, v):
        if v < front_fraction:
            return world(*face(u, 1 - v / front_fraction))
        if v > front_fraction + arc_fraction:
            return world(
                *face(
                    u,
                    (v - front_fraction - arc_fraction) / (1 - front_fraction - arc_fraction),
                    True,
                )
            )
        t = (v - front_fraction) / arc_fraction
        f = face(u, 0)
        b = face(u, 0, True)
        x = f[0] + (b[0] - f[0]) * _smooth(t)
        # Arched cross-section joins side tangents, with a flat shallow support
        # crown above the physical wood. All crown points remain outside wood.
        gather = sum(
            0.0045 * _g(u, centre, max(0.008, w * 0.9)) for centre, w, amp, drift, end in folds
        )
        z = top + 0.0014 + gather * math.sin(math.pi * t)
        z -= 0.0044 * (abs(2 * t - 1) ** 8)
        y = f[1] + 0.0015 * _noise(u * 21, t * 3) * math.sin(math.pi * t)
        return world(x, y, z)

    verts = []
    uv = []
    nu = c.detail_u
    nv = c.detail_v
    for j in range(nv + 1):
        for i in range(nu + 1):
            u = i / nu
            v = j / nv
            verts.append(tuple(surface(u, v)))
            uv.append((u * c.shirt_top_width / 0.012, v * 0.88 / 0.012))
    faces = []
    for j in range(nv):
        for i in range(nu):
            a = j * (nu + 1) + i
            faces.append((a, a + 1, a + nu + 2, a + nu + 1))
    body = _mesh(
        col, PREFIX + "Continuous_double_panel_Tshirt", verts, faces, cotton, uv, c.thickness
    )
    body["construction"] = (
        "Continuous rounded rail drape; front and rear open hems; independently authored nonperiodic tension folds"
    )
    body["source_views"] = (
        "Registered 2 and 3 for support position; 15 for folded edges; 9 held-out outline check"
    )

    # A T-shirt is a sewn tube, so the folded garment presents two body plies
    # on the room side. The inner ply has its own longer open hem, exposed below
    # the outer hem; it is a thin surface, not a stuffed second curtain.
    def inner_surface(u, v):
        d = (1 - v / front_fraction) * (1 + 0.037 / c.shirt_front_drop)
        # Evaluate the same physical fold field at the longer arc length.
        # A shifted UV copy would cross the outer ply where folds drift.
        x, y, z = face(u, d)
        # Keep the inner cloth ply outside the physical support at the four
        # narrow crown valleys; the visible outer fold shape is unchanged.
        return world(min(x + 0.0032, -hx - 0.001), y, z)

    innerverts = []
    inneruv = []
    for j in range(99):
        for i in range(nu + 1):
            u = i / nu
            v = front_fraction * 0.98 * j / 98
            innerverts.append(tuple(inner_surface(u, v)))
            inneruv.append((u * c.shirt_top_width / 0.012, v * 0.88 / 0.012))
    innerfaces = []
    for j in range(98):
        for i in range(nu):
            a = j * (nu + 1) + i
            innerfaces.append((a, a + 1, a + nu + 2, a + nu + 1))
    _mesh(
        col,
        PREFIX + "Inner_body_ply_exposed_hem",
        innerverts,
        innerfaces,
        cotton,
        inneruv,
        c.thickness,
    )
    for k, v in enumerate((0.006, 0.011)):
        _curve(
            col,
            PREFIX + f"inner_double_needle_{k + 1}",
            [inner_surface(i / 180, v) - E * 0.0005 for i in range(181)],
            0.00024,
            seam,
        )

    # The short sleeve is pinched over and turned inward at the window-side
    # edge. Its free angled lip breaks the rectangular towel silhouette.
    def sleeve(u, v):
        d = 0.035 + 0.30 * v
        p = surface(0.84 + 0.16 * u, front_fraction * (1 - d))
        p += A * (0.033 * math.sin(math.pi * v) * u) - E * (0.002 + 0.011 * math.sin(math.pi * v))
        p.z += 0.012 * math.sin(math.pi * v) * u
        return p

    sv = []
    su = []
    for j in range(45):
        for i in range(33):
            u = i / 32
            v = j / 44
            sv.append(tuple(sleeve(u, v)))
            su.append((u * 0.09 / 0.012, v * 0.14 / 0.012))
    sf = []
    for j in range(44):
        for i in range(32):
            a = j * 33 + i
            sf.append((a, a + 1, a + 34, a + 33))
    _mesh(col, PREFIX + "Window_side_folded_short_sleeve", sv, sf, cotton, su, c.thickness)
    _curve(
        col,
        PREFIX + "Sleeve_turned_lip",
        [sleeve(1, j / 100) - E * 0.0004 for j in range(101)],
        0.0003,
        seam,
    )
    # Sewn hem allowance follows the same surface, lifting less than 1 mm;
    # separate front/rear hems expose real doubled thickness without a thick rim.
    for side, v0, sign in [("front", 0, 1), ("rear", 1, -1)]:

        def hempt(u, v):
            p = surface(u, v)
            p += E * (-0.00065 if side == "front" else 0.00065)
            return p

        for k, off in enumerate((0.006, 0.011)):
            v = v0 + sign * off
            _curve(
                col,
                PREFIX + side + f"_double_needle_{k + 1}",
                [hempt(i / 180, v) for i in range(181)],
                0.00024,
                seam,
            )
        bandverts = []
        banduv = []
        for j in range(4):
            for i in range(145):
                u = i / 144
                v = v0 + sign * (0.001 + j * 0.0045)
                bandverts.append(tuple(hempt(u, v)))
                banduv.append((u * c.shirt_top_width / 0.012, j * 0.0045 * 0.88 / 0.012))
        bandfaces = []
        for j in range(3):
            for i in range(144):
                a = j * 145 + i
                bandfaces.append((a, a + 1, a + 146, a + 145))
        _mesh(
            col,
            PREFIX + side + "_turned_hem_allowance",
            bandverts,
            bandfaces,
            cotton,
            banduv,
            0.00035,
        )
    # Subtle overlocked side seam, not a high-contrast decorative pipe.
    for u, label in ((0.008, "near"), (0.992, "window")):
        _curve(
            col,
            PREFIX + label + "_side_seam",
            [surface(u, 0.01 + 0.44 * j / 140) - E * 0.0006 for j in range(141)],
            0.00022,
            seam,
        )
    # Pinch clip across the newly supported lower rail, on the window-side half.
    lamp_y = 0.252
    lp = world(-0.013, lamp_y, c.lower_rail_top + 0.007)
    basis = Matrix((E, A, Vector((0, 0, 1)))).transposed()
    _box(
        col,
        LAMP + "Front_clamp",
        lp - E * 0.020 + Vector((0, 0, -0.014)),
        (0.020, 0.039, 0.077),
        plastic,
        basis,
        0.008,
    )
    _box(
        col,
        LAMP + "Rear_clamp",
        lp + E * 0.038 + Vector((0, 0, 0.002)),
        (0.015, 0.036, 0.054),
        plastic,
        basis,
        0.006,
    )
    _box(
        col,
        LAMP + "Upper_jaw_bridge",
        lp + E * 0.009 + Vector((0, 0, 0.032)),
        (0.066, 0.035, 0.014),
        plastic,
        basis,
        0.004,
    )
    # Jaw pads contact the broad rail faces; thin metal hinge remains recessed.
    _box(
        col,
        LAMP + "Front_grip_pad",
        world(-hx - 0.0015, lamp_y, c.lower_rail_top - 0.010),
        (0.003, 0.031, 0.018),
        rubber,
        basis,
        0.001,
    )
    _box(
        col,
        LAMP + "Rear_grip_pad",
        world(hx + 0.0015, lamp_y, c.lower_rail_top - 0.010),
        (0.003, 0.031, 0.018),
        rubber,
        basis,
        0.001,
    )
    for i in range(4):
        _curve(
            col,
            LAMP + f"Spring_loop_{i}",
            [
                lp
                + E * (0.004 + 0.008 * math.cos(t * math.pi / 10))
                + A * ((i - 1.5) * 0.003)
                + Vector((0, 0, 0.022 + 0.008 * math.sin(t * math.pi / 10)))
                for t in range(21)
            ],
            0.00075,
            silver,
        )
    for i in range(3):
        _box(
            col,
            LAMP + f"Jaw_recess_{i}",
            lp - E * 0.0301 + A * ((i - 1) * 0.008) + Vector((0, 0, 0.010)),
            (0.001, 0.003, 0.015),
            dark,
            basis,
            0.001,
        )
    start = lp - E * 0.031 + Vector((0, 0, -0.017))
    controls = [
        start,
        world(-0.10, 0.302, c.lower_rail_top - 0.06),
        world(-0.20, 0.391, 0.743),
        world(-0.205, 0.397, 0.687),
        world(-0.184, 0.388, 0.646),
    ]
    _curve(col, LAMP + "Flexible_white_gooseneck", controls, 0.0036, rubber)
    end = world(-0.177, 0.384, 0.624)
    headbasis = basis @ Matrix.Rotation(-0.24, 3, "Y")
    _box(col, LAMP + "Slim_reading_head", end, (0.017, 0.026, 0.075), plastic, headbasis, 0.011)
    diffuser = _material(LAMP + "Frosted_lens", (0.85, 0.84, 0.80), 0.58)
    _box(
        col,
        LAMP + "Unlit_diffuser",
        end - E * 0.009,
        (0.0015, 0.018, 0.060),
        diffuser,
        headbasis,
        0.006,
    )
    result = {
        "version": "rail_shirt_v5_3",
        "rail_changes": changes,
        "removed_objects": removed,
        "created_objects": [o.name for o in col.objects],
        "body_vertices": len(verts),
        "garment_thickness_m": c.thickness,
        "shirt_top_center_world": list(surface(0.5, 0.5)),
        "clip_pivot_world": list(lp),
        "normal_provenance": "analytic knit normal, not photo-derived",
        "primary_reference_constraints": [2, 3],
        "approximate_detail_reference": 15,
        "heldout_reference": 9,
    }
    body["audit_json"] = __import__("json").dumps(result)
    return result
