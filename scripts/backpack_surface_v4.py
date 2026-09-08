"""Local textile/hardware refinement AFTER backpack_shape_v3, metres / Z up.

Does not move or rescale the calibrated pack, fit cameras, save, or render.
Only Backpack* objects are edited. The fitted label is left untouched.
Microtexture is authored plain weave, not recovered photographic albedo.
"""

from __future__ import annotations

import math
from pathlib import Path

VERSION = "4.0.2-candidate"
MARKER = "backpack_surface_version"
PITCH = 0.064


def _mesh(name, vertices, faces, material, uvs=None):
    import bpy

    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    data.materials.append(material)
    ob = bpy.data.objects.new(name, data)
    bpy.data.objects["Backpack continuous shaped nylon shell"].users_collection[0].objects.link(ob)
    for face in data.polygons:
        face.use_smooth = True
    if uvs is not None:
        layer = data.uv_layers.new(name="BackpackWeave")
        for face in data.polygons:
            for li in face.loop_indices:
                layer.data[li].uv = uvs[data.loops[li].vertex_index]
    return ob


def _material(name, color, roughness, texture_dir=None, metal=0, weave_strength=0.36):
    import bpy

    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nodes = m.node_tree.nodes
    nodes.clear()
    links = m.node_tree.links
    out = nodes.new("ShaderNodeOutputMaterial")
    p = nodes.new("ShaderNodeBsdfPrincipled")
    p.inputs["Base Color"].default_value = (*color, 1)
    p.inputs["Roughness"].default_value = roughness
    p.inputs["Metallic"].default_value = metal
    p.inputs["Specular IOR Level"].default_value = 0.32
    if not metal:
        p.inputs["Sheen Weight"].default_value = 0.16
    links.new(p.outputs["BSDF"], out.inputs["Surface"])
    m.diffuse_color = (*color, 1)
    m.roughness = roughness
    m.metallic = metal
    if texture_dir:
        uv = nodes.new("ShaderNodeUVMap")
        uv.uv_map = "BackpackWeave"
        normal = nodes.new("ShaderNodeTexImage")
        normal.image = bpy.data.images.load(
            str(texture_dir / "plain_weave_normal.png"), check_existing=True
        )
        normal.image.colorspace_settings.name = "Non-Color"
        nm = nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = weave_strength
        links.new(uv.outputs["UV"], normal.inputs["Vector"])
        links.new(normal.outputs["Color"], nm.inputs["Color"])
        links.new(nm.outputs["Normal"], p.inputs["Normal"])
        # Both normal and pre-baked roughness connect directly to Principled,
        # retaining this subtle microvariation through standard glTF export.
        r = nodes.new("ShaderNodeTexImage")
        r.image = bpy.data.images.load(
            str(texture_dir / f"plain_weave_roughness_{round(roughness * 100):02d}.png"),
            check_existing=True,
        )
        r.image.colorspace_settings.name = "Non-Color"
        links.new(uv.outputs["UV"], r.inputs["Vector"])
        links.new(r.outputs["Color"], p.inputs["Roughness"])
    return m


def _polyline(name, paths, radius, material):
    import bpy

    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.resolution_u = 1
    cu.bevel_resolution = 1
    cu.bevel_depth = radius
    for path in paths:
        sp = cu.splines.new("POLY")
        sp.points.add(len(path) - 1)
        for p, v in zip(sp.points, path):
            p.co = (*v, 1)
    ob = bpy.data.objects.new(name, cu)
    bpy.data.objects["Backpack continuous shaped nylon shell"].users_collection[0].objects.link(ob)
    cu.materials.append(material)
    return ob


def _resample(path, step):
    from mathutils import Vector

    path = [Vector(p) for p in path]
    lengths = [0.0]
    for a, b in zip(path, path[1:]):
        lengths.append(lengths[-1] + (b - a).length)
    count = max(2, round(lengths[-1] / step) + 1)
    j = 0
    points = []
    for i in range(count):
        s = lengths[-1] * i / (count - 1)
        while j < len(path) - 2 and lengths[j + 1] < s:
            j += 1
        t = (s - lengths[j]) / max(1e-10, lengths[j + 1] - lengths[j])
        points.append(path[j].lerp(path[j + 1], t))
    return points


def _basis(path, i, normal):
    if callable(normal):
        normal = normal(path[i])
    tangent = (path[min(i + 1, len(path) - 1)] - path[max(0, i - 1)]).normalized()
    across = normal.cross(tangent).normalized()
    return tangent, across, tangent.cross(across).normalized()


def _ribbon(name, path, width, normal, material):
    vv = []
    ff = []
    uv = []
    distance = 0
    for i, p in enumerate(path):
        if i:
            distance += (p - path[i - 1]).length
        _, a, n = _basis(path, i, normal)
        for j in range(5):
            u = j / 4 - 0.5
            vv.append(tuple(p + a * u * width + n * (0.00014 * (1 - 4 * u * u))))
            uv.append((distance / PITCH, (u + 0.5) * width / PITCH))
        if i:
            for j in range(4):
                v = (i - 1) * 5 + j
                ff.append((v, v + 5, v + 6, v + 1))
    ob = _mesh(name, vv, ff, material, uv)
    mod = ob.modifiers.new("Woven tape thickness", "SOLIDIFY")
    mod.thickness = 0.0003
    mod.offset = -1
    return ob


def _stitches(name, path, normal, material, offset=0, radius=0.000075):
    path = _resample(path, 0.00105)
    segments = []
    for i in range(0, len(path) - 2, 3):
        seg = []
        for j in (i, i + 1):
            _, a, n = _basis(path, j, normal)
            seg.append(path[j] + a * offset + n * 0.00032)
        segments.append(seg)
    return _polyline(name, segments, radius, material)


def _zipper(name, source, normal, materials, width=0.006):
    from mathutils import Vector

    path = _resample(source, 0.0009)
    if not callable(normal):
        normal = Vector(normal).normalized()
    _ribbon(name + " woven tape", path, width, normal, materials["tape"])
    _stitches(name + " left lockstitch", path, normal, materials["thread"], -width * 0.40)
    _stitches(name + " right lockstitch", path, normal, materials["thread"], width * 0.40)
    # Small separate interlocking elements are one mesh, avoiding a polished
    # continuous tube. Their staggered pitch is 0.9 mm, not centimetric ridges.
    vv = []
    ff = []
    for i, p in enumerate(path[2:-2], 2):
        t, a, n = _basis(path, i, normal)
        for side in (-1, 1):
            center = p + a * side * 0.00040 + n * 0.00037 + t * (0.00018 if side > 0 else -0.00018)
            start = len(vv)
            for z in (-1, 1):
                for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    vv.append(tuple(center + t * x * 0.00030 + a * y * 0.00042 + n * z * 0.00017))
            ff.extend(
                tuple(start + k for k in f)
                for f in (
                    (0, 3, 2, 1),
                    (4, 5, 6, 7),
                    (0, 1, 5, 4),
                    (1, 2, 6, 5),
                    (2, 3, 7, 6),
                    (3, 0, 4, 7),
                )
            )
    teeth = _mesh(name + " interlocking coil teeth", vv, ff, materials["metal"])
    bevel = teeth.modifiers.new("Rounded coil edges", "BEVEL")
    bevel.width = 0.00007
    bevel.segments = 2
    for index, ratio in enumerate((0.20, 0.78)):
        i = int((len(path) - 1) * ratio)
        p = path[i]
        t, a, n = _basis(path, i, normal)
        # Open pull loop, curved in the fabric plane and lifted slightly by the
        # slider. The hole is actual negative space, not a painted rectangle.
        direction = Vector((0, 0, -1))
        direction -= n * direction.dot(n)
        direction.normalize()
        cross = n.cross(direction).normalized()
        center = p + n * 0.00115 + direction * 0.006
        loop = [
            center
            + direction * (0.0047 * math.cos(j * 2 * math.pi / 36))
            + cross * (0.00155 * math.sin(j * 2 * math.pi / 36))
            for j in range(37)
        ]
        _polyline(name + f" hollow pull {index}", [loop], 0.00043, materials["metal"])
        slider = [p + n * 0.0009 + t * 0.002, p + n * 0.0012, p + n * 0.0009 - t * 0.002]
        _polyline(name + f" slider {index}", [slider], 0.0013, materials["metal"])
    return len(path) * 2


def _surface_normal(ob):
    from mathutils.bvhtree import BVHTree
    from mathutils import Vector

    tree = BVHTree.FromPolygons(
        [ob.matrix_world @ v.co for v in ob.data.vertices],
        [tuple(p.vertices) for p in ob.data.polygons],
    )

    def normal(p):
        nearest = tree.find_nearest(p)
        return nearest[1] if nearest and nearest[0] is not None else Vector((1, 0, 0))

    return normal


def _curved_uv_path():
    from mathutils import Vector

    # Rounded transitions at the shoulders of each sewn pocket. The zipper
    # follows its arched fabric surface; the old right-angle path is absent.
    control = [
        (0.034, 0.07),
        (0.031, 0.27),
        (0.030, 0.53),
        (0.035, 0.76),
        (0.065, 0.87),
        (0.17, 0.908),
        (0.36, 0.920),
        (0.59, 0.918),
        (0.82, 0.900),
        (0.935, 0.857),
        (0.969, 0.750),
        (0.973, 0.51),
        (0.969, 0.27),
        (0.963, 0.10),
    ]
    pp = [Vector(v) for v in control]
    result = []
    for i in range(len(pp) - 1):
        a = pp[max(0, i - 1)]
        b = pp[i]
        c = pp[i + 1]
        d = pp[min(len(pp) - 1, i + 2)]
        for j in range(12):
            t = j / 12
            result.append(
                0.5
                * (
                    (2 * b)
                    + (-a + c) * t
                    + (2 * a - 5 * b + 4 * c - d) * t * t
                    + (-a + 3 * b - 3 * c + d) * t * t * t
                )
            )
    return result + [pp[-1]]


def _grid_sample(ob, u, v, nx, ny):
    u = max(0, min(1, u)) * nx
    v = max(0, min(1, v)) * ny
    x = min(nx - 1, int(u))
    y = min(ny - 1, int(v))
    a = u - x
    b = v - y
    ids = (
        y * (nx + 1) + x,
        y * (nx + 1) + x + 1,
        (y + 1) * (nx + 1) + x,
        (y + 1) * (nx + 1) + x + 1,
    )
    points = [ob.matrix_world @ ob.data.vertices[i].co for i in ids]
    return points[0].lerp(points[1], a).lerp(points[2].lerp(points[3], a), b)


def _curve_points(ob):
    values = []
    for sp in ob.data.splines:
        if sp.type == "BEZIER":
            values.extend(ob.matrix_world @ p.co for p in sp.bezier_points)
        else:
            values.extend(ob.matrix_world @ p.co.xyz for p in sp.points)
    return values


def _cloth_uv(ob, width, height):
    if ob.type != "MESH":
        return
    if not ob.data.uv_layers:
        # Existing sewn gussets are two corresponding perimeter rings with no
        # UVs. Unwrap by real seam distance and pocket depth, including the
        # closing-seam discontinuity; a constant UV would lose the cloth grain
        # and produces an invalid textured glTF primitive.
        new = ob.data.uv_layers.new(name="BackpackWeave")
        if "joined fabric gussets" in ob.name:
            count = len(ob.data.vertices) // 2
            points = [ob.matrix_world @ v.co for v in ob.data.vertices]
            cumulative = [0.0]
            for i in range(count):
                cumulative.append(cumulative[-1] + (points[(i + 1) % count] - points[i]).length)
            for face in ob.data.polygons:
                for li in face.loop_indices:
                    vi = ob.data.loops[li].vertex_index
                    index = vi % count
                    s = (
                        cumulative[count]
                        if face.index == count - 1 and index == 0
                        else cumulative[index]
                    )
                    depth = (points[index + count] - points[index]).length if vi >= count else 0.0
                    new.data[li].uv = (s / PITCH, depth / PITCH)
        else:
            for face in ob.data.polygons:
                points = [ob.matrix_world @ ob.data.vertices[i].co for i in face.vertices]
                axes = sorted(
                    range(3),
                    key=lambda a: max(p[a] for p in points) - min(p[a] for p in points),
                    reverse=True,
                )[:2]
                for li in face.loop_indices:
                    p = ob.matrix_world @ ob.data.vertices[ob.data.loops[li].vertex_index].co
                    new.data[li].uv = (p[axes[0]] / PITCH, p[axes[1]] / PITCH)
        ob.data.uv_layers.active = new
        return
    old = ob.data.uv_layers.active
    new = ob.data.uv_layers.get("BackpackWeave") or ob.data.uv_layers.new(name="BackpackWeave")
    for i, p in enumerate(old.data):
        new.data[i].uv = (p.uv.x * width / PITCH, p.uv.y * height / PITCH)
    ob.data.uv_layers.active = new


def _soften_local_geometry(objects):
    from mathutils import Vector
    from backpack_shape_v3 import _deform, LABEL_CENTER, LABEL_NORMAL

    normal = Vector(LABEL_NORMAL)
    label = Vector(LABEL_CENTER)
    # Localized asymmetric tension creases. Compact Gaussians, no repeating
    # whole-panel sine displacement and no change to scale or matrix_world.
    creases = [
        (2.772, 0.966, 0.75, 0.020, 0.006, 0.0022),
        (2.954, 0.991, -0.7, 0.023, 0.005, -0.0020),
        (2.777, 0.866, -0.25, 0.018, 0.005, -0.0017),
        (2.962, 0.867, 0.6, 0.021, 0.006, 0.0018),
        (2.817, 1.046, 0.2, 0.025, 0.006, -0.0023),
        (2.917, 1.073, -0.5, 0.019, 0.005, 0.0022),
        (2.755, 0.818, 0.3, 0.024, 0.006, -0.0021),
        (2.926, 0.791, -0.2, 0.018, 0.005, 0.0020),
    ]

    def warp(p):
        q = Vector(p)
        amp = 0.0
        for cy, cz, angle, length, width, height in creases:
            dy = q.y - cy
            dz = q.z - cz
            s = dy * math.cos(angle) + dz * math.sin(angle)
            r = -dy * math.sin(angle) + dz * math.cos(angle)
            amp += (
                height
                * math.exp(-((s / length) ** 4))
                * (
                    math.exp(-((r / width) ** 2))
                    - 0.43 * math.exp(-(((r - width * 1.8) / width) ** 2))
                )
            )
        front = max(0, min(1, (q.x + 1.30) / 0.065))
        base = max(0, min(1, (q.z - 0.747) / 0.035))
        fitted = 1 - math.exp(-(((q - label).length / 0.039) ** 6))
        q += normal * amp * front * base * fitted
        crown = math.exp(-(((q.y - 2.889) / 0.055) ** 2) - ((q.z - 1.098) / 0.027) ** 2)
        q.z -= 0.0025 * crown
        return tuple(q)

    for ob in objects:
        if "identity patch" in ob.name or "woven label" in ob.name:
            continue
        if ob.type in {"MESH", "CURVE"}:
            _deform(ob, warp)


def _pad_strap(ob, material, thread):
    import bpy
    from mathutils import Vector

    points = [ob.matrix_world @ v.co for v in ob.data.vertices]
    if len(points) % 2:
        return
    path = [(points[i] + points[i + 1]) * 0.5 for i in range(0, len(points), 2)]
    if "top carry handle" in ob.name:
        for i, p in enumerate(path):
            f = max(0, math.sin(math.pi * i / (len(path) - 1))) ** 1.3
            # Retain the stitched endpoints, letting the loose loop slump back
            # and toward the visible side instead of standing like a rigid tab.
            p += Vector((-0.012, -0.018, -0.007)) * f
    vv = []
    ff = []
    uv = []
    s = 0
    edges = [[], []]
    for i, p in enumerate(path):
        if i:
            s += (p - path[i - 1]).length
        across = points[i * 2 + 1] - points[i * 2]
        width = across.length
        across.normalize()
        tangent = (path[min(i + 1, len(path) - 1)] - path[max(0, i - 1)]).normalized()
        normal = tangent.cross(across).normalized()
        for j in range(9):
            u = j / 8 - 0.5
            q = p + across * u * width + normal * (0.0014 * (1 - 4 * u * u))
            vv.append(tuple(q))
            uv.append((s / PITCH, (u + 0.5) * width / PITCH))
        edges[0].append(Vector(vv[-9]) + across * 0.001)
        edges[1].append(Vector(vv[-1]) - across * 0.001)
        if i:
            for j in range(8):
                a = (i - 1) * 9 + j
                ff.append((a, a + 9, a + 10, a + 1))
    replacement = _mesh("Backpack V4 " + ob.name.replace("Backpack ", ""), vv, ff, material, uv)
    solid = replacement.modifiers.new("Padded woven strap backing", "SOLIDIFY")
    solid.thickness = 0.0026
    for k, p in enumerate(edges):
        _stitches(replacement.name + f" seam {k}", p, Vector((1, 0, 0)), thread)
    bpy.data.objects.remove(ob, do_unlink=True)


def _charm(materials):
    import bpy
    from mathutils import Vector

    # Small soft taupe charm, seen beside the pink bottle. Its exact decorative
    # animal is ambiguous, so this is explicitly an inferred generic soft charm.
    center = Vector((-1.249, 2.697, 0.770))
    for name, offset, scale in [
        ("body", (0, 0, 0), (0.025, 0.027, 0.025)),
        ("head", (0.004, -0.009, 0.026), (0.019, 0.021, 0.022)),
        ("foot left", (0.014, -0.023, -0.016), (0.021, 0.014, 0.013)),
        ("foot right", (0.012, 0.019, -0.015), (0.018, 0.014, 0.014)),
    ]:
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=24, ring_count=16, location=center + Vector(offset)
        )
        ob = bpy.context.object
        ob.name = "Backpack V4 plush charm " + name
        ob.scale = scale
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        ob.data.materials.append(materials["plush"])
        for f in ob.data.polygons:
            f.use_smooth = True
        _cloth_uv(ob, 0.13, 0.10)
    cord = [(-1.228, 2.710, 0.865), (-1.235, 2.694, 0.849), (-1.244, 2.688, 0.815)]
    _polyline("Backpack V4 charm short cord", [cord], 0.00065, materials["binding"])
    for i in range(3):
        t = i / 2
        p = Vector(cord[1]).lerp(Vector(cord[2]), t)
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=8, radius=0.0031, location=p)
        ob = bpy.context.object
        ob.name = "Backpack V4 small brown charm bead"
        ob.data.materials.append(materials["bead"])
    # Only the exposed cap and small translucent shoulder are visible above
    # the gathered side cup in the photographs. No label/brand is invented.
    for label, z, radius, depth, mat in [
        ("bottle shoulder", 0.862, 0.018, 0.055, materials["bottle"]),
        ("pink cap", 0.897, 0.0158, 0.021, materials["pink"]),
    ]:
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=40, radius=radius, depth=depth, location=(-1.260, 2.743, z)
        )
        ob = bpy.context.object
        ob.name = "Backpack V4 side pocket " + label
        ob.data.materials.append(mat)
        bevel = ob.modifiers.new("Small molded rounded edge", "BEVEL")
        bevel.width = 0.003
        bevel.segments = 3
        for f in ob.data.polygons:
            f.use_smooth = True


def refine_backpack_surface(texture_dir=None):
    """Apply once to a current v3 backpack. Returns exact local change metadata."""
    import bpy
    from mathutils import Vector

    body = bpy.data.objects.get("Backpack continuous shaped nylon shell")
    if body is None:
        raise RuntimeError("Backpack shell is missing")
    if body.get(MARKER):
        return {"already_applied": True, "version": body[MARKER]}
    if not body.get("backpack_shape_version"):
        raise RuntimeError("Run backpack_shape_v3 after calibrated layout first")
    texture_dir = Path(
        texture_dir or Path(__file__).resolve().parents[1] / "assets/textures/backpack_v4"
    )
    if not (texture_dir / "plain_weave_normal.png").exists():
        raise FileNotFoundError(texture_dir)
    old = [o for o in bpy.context.scene.objects if o.name.startswith("Backpack")]
    before = [body.matrix_world @ v.co for v in body.data.vertices]
    mats = {
        "blue": _material(
            "Backpack V4 / periwinkle woven polyester", (0.098, 0.112, 0.166), 0.62, texture_dir
        ),
        "cream": _material(
            "Backpack V4 / warm cream canvas",
            (0.53, 0.505, 0.395),
            0.81,
            texture_dir,
            weave_strength=0.48,
        ),
        "tape": _material(
            "Backpack V4 / ivory zipper webbing", (0.54, 0.51, 0.367), 0.76, texture_dir
        ),
        "binding": _material(
            "Backpack V4 / folded blue fabric binding", (0.065, 0.081, 0.131), 0.68, texture_dir
        ),
        "thread": _material("Backpack V4 / ecru lockstitch thread", (0.43, 0.414, 0.31), 0.8),
        "metal": _material(
            "Backpack V4 / aged warm nickel coil", (0.36, 0.35, 0.285), 0.36, metal=0.78
        ),
        "plush": _material(
            "Backpack V4 / taupe plush charm",
            (0.265, 0.222, 0.175),
            0.89,
            texture_dir,
            weave_strength=0.7,
        ),
        "bead": _material("Backpack V4 / dark brown charm beads", (0.057, 0.029, 0.014), 0.33),
        "bottle": _material("Backpack V4 / frosted side bottle", (0.51, 0.48, 0.43), 0.45),
        "pink": _material("Backpack V4 / dusty rose bottle cap", (0.59, 0.255, 0.315), 0.44),
    }
    _soften_local_geometry(old)
    for ob in old:
        if ob.type not in {"MESH", "CURVE"} or "identity patch" in ob.name:
            continue
        for i, mat in enumerate(ob.data.materials):
            if not mat:
                continue
            if "cream canvas" in mat.name:
                ob.data.materials[i] = mats["cream"]
            elif "nylon" in mat.name:
                ob.data.materials[i] = mats["blue"]
            elif "binding" in mat.name or "piping" in mat.name:
                ob.data.materials[i] = mats["binding"]
        if ob.type == "MESH":
            if ob == body:
                _cloth_uv(ob, 0.72, 0.38)
            elif "side mesh pocket" in ob.name:
                _cloth_uv(ob, 0.12, 0.115)
            else:
                _cloth_uv(ob, 0.255, 0.22)
    normal = Vector((0.96, -0.05, 0.26)).normalized()
    teeth = 0
    for prefix in ("Backpack middle compartment", "Backpack front pocket"):
        panel = bpy.data.objects[prefix + " sewn front panel"]
        uvpath = _curved_uv_path()
        surface_normal = _surface_normal(panel)
        path = []
        for u, v in uvpath:
            p = _grid_sample(panel, u, v, 64, 42)
            path.append(p + surface_normal(p) * 0.00070)
        teeth += _zipper(
            "Backpack V4 " + prefix.replace("Backpack ", "") + " arch zipper",
            path,
            surface_normal,
            mats,
        )
        for ob in list(bpy.data.objects):
            if ob.name.startswith(prefix) and any(
                s in ob.name for s in ("cream zip tape", "metal zip chain", "narrow zipper pull")
            ):
                bpy.data.objects.remove(ob, do_unlink=True)
        binding = bpy.data.objects.get(prefix + " perimeter binding")
        if binding:
            binding.data.bevel_depth = 0.00050
            _stitches(
                "Backpack V4 " + prefix.replace("Backpack ", "") + " perimeter seam",
                _curve_points(binding),
                normal,
                mats["thread"],
                0.0015,
            )
    # Main compartment arc sampled on the existing closed shell, preserving
    # its silhouette. This is the previously absent third zipper visible in 11.
    path = []
    surface_normal = _surface_normal(body)
    for k in range(201):
        a = -math.pi / 2 + math.pi * k / 200
        t = 0.16 + 0.78 * max(0, math.cos(a)) ** 0.65
        row = t * 48
        i = min(47, int(row))
        j = (a % (2 * math.pi)) / (2 * math.pi) * 64
        lo = int(j) % 64
        hi = (lo + 1) % 64
        f = j - int(j)
        va = body.data.vertices[i * 64 + lo].co.lerp(body.data.vertices[i * 64 + hi].co, f)
        vb = body.data.vertices[(i + 1) * 64 + lo].co.lerp(
            body.data.vertices[(i + 1) * 64 + hi].co, f
        )
        p = body.matrix_world @ va.lerp(vb, row - i)
        path.append(p + surface_normal(p) * 0.00075)
    # Suppress triangle-scale kinks in the traced centreline. Projection back
    # to the actual shell below keeps smoothing from floating above the cloth.
    for iteration in range(3):
        path = (
            [path[0]]
            + [path[i] * 0.5 + (path[i - 1] + path[i + 1]) * 0.25 for i in range(1, len(path) - 1)]
            + [path[-1]]
        )
    from mathutils.bvhtree import BVHTree

    tree = BVHTree.FromPolygons(
        [body.matrix_world @ v.co for v in body.data.vertices],
        [tuple(p.vertices) for p in body.data.polygons],
    )
    path = [tree.find_nearest(p)[0] + tree.find_nearest(p)[1] * 0.00065 for p in path]
    teeth += _zipper("Backpack V4 main compartment arch zipper", path, surface_normal, mats, 0.0065)
    crown = bpy.data.objects.get("Backpack crown panel seam")
    if crown:
        crown.data.bevel_depth = 0.00047
        _stitches(
            "Backpack V4 crown panel topstitch",
            _curve_points(crown),
            normal,
            mats["thread"],
            0.0012,
        )
    for ob in list(bpy.data.objects):
        if ob.type == "MESH" and any(
            ob.name.startswith(s)
            for s in ("Backpack folded top carry handle", "Backpack padded shoulder strap")
        ):
            _pad_strap(ob, mats["blue"], mats["thread"])
        elif ob.type == "CURVE" and "edge stitching" in ob.name and ob.name.startswith("Backpack "):
            bpy.data.objects.remove(ob, do_unlink=True)
    _charm(mats)
    # Blender's tangent calculation rejects n-gons. Triangulate only end caps
    # for portable normal-map export; the cloth's quad surface stays editable.
    for ob in bpy.context.scene.objects:
        if (
            ob.name.startswith("Backpack")
            and ob.type == "MESH"
            and any(len(p.vertices) > 4 for p in ob.data.polygons)
        ):
            mod = ob.modifiers.new("Backpack V4 export-safe cap triangulation", "TRIANGULATE")
            mod.min_vertices = 5
    body[MARKER] = VERSION
    bpy.context.view_layer.update()
    shifts = [(body.matrix_world @ v.co - p).length for v, p in zip(body.data.vertices, before)]
    return {
        "version": VERSION,
        "shell_max_local_displacement_m": max(shifts),
        "shell_vertex_count_unchanged": len(before) == len(body.data.vertices),
        "main_pose_and_scale_changed": False,
        "label_mesh_edited": False,
        "coil_elements_approx": teeth,
        "texture_tile_m": PITCH,
        "texture_source": "authored generic plain weave; not scanned backpack",
        "shape_status": "Local inferred millimetric tension creases; existing v3 shell/pocket layout retained",
        "material_status": "Relightable Principled cloth with authored tangent normal. No baked capture illumination.",
    }
