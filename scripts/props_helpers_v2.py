"""Reference-informed soft goods with sewn surfaces and compressed volumes.

These helpers create geometry only. They neither save nor render a scene. The
single generated pillow albedo is authored here and is packed by the room build.
All dimensions are metres, in the same coordinate system as ``props.build``.
"""

from __future__ import annotations

import math

import bpy
from mathutils import Vector

TAU = math.tau


def _uv(ob, coords):
    layer = ob.data.uv_layers.new(name="UVMap")
    for polygon in ob.data.polygons:
        for loop_index in polygon.loop_indices:
            layer.data[loop_index].uv = coords[ob.data.loops[loop_index].vertex_index]
    return ob


def _grid(h, name, fn, mat, nx=64, ny=48, thickness=0):
    vertices = [fn(i / nx, j / ny) for j in range(ny + 1) for i in range(nx + 1)]
    faces = []
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    ob = h["mesh"](name, vertices, faces, mat)
    _uv(ob, [(i / nx, j / ny) for j in range(ny + 1) for i in range(nx + 1)])
    if thickness:
        mod = ob.modifiers.new("Sewn material thickness", "SOLIDIFY")
        mod.thickness = thickness
        mod.offset = -1
    return ob


def _catmull(points, steps=10, closed=False):
    """Uniform Catmull-Rom, explicitly sampled so small folds stay smooth."""
    points = [Vector(p) for p in points]
    result = []
    count = len(points) if closed else len(points) - 1
    for i in range(count):
        p0 = points[(i - 1) % len(points)] if closed else points[max(0, i - 1)]
        p1, p2 = points[i], points[(i + 1) % len(points)]
        p3 = points[(i + 2) % len(points)] if closed else points[min(len(points) - 1, i + 2)]
        for k in range(steps):
            t = k / steps
            result.append(
                0.5
                * (
                    (2 * p1)
                    + (-p0 + p2) * t
                    + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                    + (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t
                )
            )
    result.append(points[0] if closed else points[-1])
    return result


def _pillow_print(h):
    """Muted woven damask bands, rather than separate floating 3D ornaments."""
    import numpy as np

    w, height = 768, 640
    u, v = np.meshgrid(np.linspace(0, 1, w), np.linspace(0, 1, height))
    rng = np.random.default_rng(52117)
    # Very low contrast tonal mottling and threads keep this a printed textile.
    weave = 0.005 * np.sin(u * w * math.pi) + 0.004 * np.sin(v * height * math.pi)
    weave += rng.normal(0, 0.0017, u.shape)
    rgb = np.empty((*u.shape, 3), dtype=np.float32)
    rgb[:] = (0.64, 0.545, 0.531)
    rgb += weave[:, :, None]
    edge = np.minimum.reduce((u, 1 - u, v, 1 - v))
    printed = np.zeros_like(u)
    for a in (0.030, 0.041, 0.158, 0.169):
        printed = np.maximum(printed, np.exp(-(((edge - a) / 0.0017) ** 2)) * 0.68)
    # The long edges carry joined paisley leaves, small flowers and scrolling stems.
    for row in (0.095, 0.905):
        for col in np.linspace(0.066, 0.934, 11):
            dx, dy = (u - col) / 0.034, (v - row) / 0.053
            angle = np.arctan2(dy, dx)
            radius = np.sqrt(dx * dx + dy * dy)
            outer = 0.61 + 0.13 * np.cos(5 * angle) + 0.08 * np.sin(2 * angle)
            petal = np.exp(-(((radius - outer) / 0.035) ** 2))
            inner = np.exp(-(((radius - 0.22 - 0.04 * np.cos(5 * angle)) / 0.024) ** 2))
            printed = np.maximum(printed, (petal * 0.66 + inner * 0.46).clip(0, 0.8))
        scroll = row + 0.020 * np.sin((u - 0.066) * TAU * 10)
        printed = np.maximum(printed, np.exp(-(((v - scroll) / 0.0015) ** 2)) * 0.60)
    for column in (0.095, 0.905):
        scroll = column + 0.021 * np.sin(v * TAU * 9)
        band = ((v > 0.17) & (v < 0.83)).astype(float)
        printed = np.maximum(printed, np.exp(-(((u - scroll) / 0.0015) ** 2)) * band * 0.5)
    # Faint broad woven stripes within the central field.
    center = (edge > 0.18).astype(float)
    rgb += (0.014 * np.cos(u * TAU * 8) * center)[:, :, None]
    ink = np.array((0.235, 0.207, 0.211), dtype=np.float32)
    rgb = rgb * (1 - printed[:, :, None]) + ink * printed[:, :, None]
    rgba = np.ones((height, w, 4), dtype=np.float32)
    rgba[:, :, :3] = rgb
    image = bpy.data.images.new("PROP / authored dusty rose damask albedo", width=w, height=height)
    image.colorspace_settings.name = "Linear Rec.709"
    image.pixels.foreach_set(rgba.ravel())
    image.pack()
    mat = h["material"](
        "printed grey rose cotton pillowcase", (0.64, 0.545, 0.531), 0.9, bump=0.0002, scale=420
    )
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    node.interpolation = "Linear"
    mat.node_tree.links.new(
        node.outputs["Color"], mat.node_tree.nodes.get("Principled BSDF").inputs["Base Color"]
    )
    return mat


def chair_pillow(h):
    """Thin rectangular pillowcase folded over the chair, with a true edge seam."""
    mat = _pillow_print(h)
    nx, ny = 64, 52

    def point(u, v, side=0):
        # Only the last centimetre rounds the corners; the shape remains rectangular.
        corner = (abs(u - 0.5) * 2) ** 18 * (abs(v - 0.5) * 2) ** 18
        y = 1.782 + (u - 0.5) * (0.478 - 0.013 * corner)
        z = 0.755 + (v - 0.5) * (0.389 - 0.012 * corner)
        z += 0.003 * math.sin(u * 9 + 0.8) * (0.3 + 0.7 * v)
        bend = max(0, (v - 0.78) / 0.22)
        x = 0.186 + 0.031 * (1 - v) - 0.046 * bend * bend
        interior = max(0, math.sin(math.pi * u) * math.sin(math.pi * v))
        # Compressed filling gives a 4 cm maximum thickness, tapering to sewn edges.
        loft = 0.002 + 0.019 * interior**0.6
        crease = 0.0015 * math.sin(18 * u + 7 * v) + 0.001 * math.sin(37 * u - 12 * v)
        crease *= (0.4 + 0.6 * math.exp(-(((v - 0.82) / 0.2) ** 2))) * interior**0.35
        x += side * loft + crease
        return (x, y, z)

    vv, uv = [], []
    for side in (-1, 1):
        for j in range(ny + 1):
            for i in range(nx + 1):
                vv.append(point(i / nx, j / ny, side))
                uv.append((i / nx, j / ny))
    count = (nx + 1) * (ny + 1)
    ff = []
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            ff.append((a, a + nx + 1, a + nx + 2, a + 1))
            ff.append((a + count, a + count + 1, a + count + nx + 2, a + count + nx + 1))
    boundary = (
        list(range(nx + 1))
        + [j * (nx + 1) + nx for j in range(1, ny + 1)]
        + [ny * (nx + 1) + i for i in range(nx - 1, -1, -1)]
        + [j * (nx + 1) for j in range(ny - 1, 0, -1)]
    )
    for i, a in enumerate(boundary):
        b = boundary[(i + 1) % len(boundary)]
        ff.append((a, b, b + count, a + count))
    _uv(h["mesh"]("Pink patterned pillow on chair / thin sewn rectangular case", vv, ff, mat), uv)
    path = [point(uv[i][0], uv[i][1]) for i in boundary]
    h["tube"]("Pillow perimeter seam follows cloth", path + path[:1], 0.00085, h["pink_seam"])
    # A narrow folded flange is represented in the cloth texture and by this inset seam.
    for v in (0.036, 0.964):
        h["tube"](
            "Pillow stitched hem",
            [point(i / 80, v, 1.015) for i in range(81)],
            0.00032,
            h["pink_seam"],
        )


def _puffer_noise(x, y, z=0):
    """Deterministic, non-periodic garment crumpling in physical metres."""
    from mathutils.noise import noise

    return noise(Vector((x + 13.72, y - 8.13, z + 4.51)))


def _puffer_support(h):
    """Ray support from the already built clothes; no simulation or persistent cache."""
    from mathutils.bvhtree import BVHTree

    prefixes = ("Folded clothing", "Grey shirt spills", "Light blue loose", "Open luggage fabric")
    objects = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(prefixes)]
    bpy.context.view_layer.update()
    dep = bpy.context.evaluated_depsgraph_get()
    vertices, faces = [], []
    for ob in objects:
        evaluated = ob.evaluated_get(dep)
        mesh = evaluated.to_mesh()
        offset = len(vertices)
        vertices.extend(tuple(evaluated.matrix_world @ v.co) for v in mesh.vertices)
        faces.extend(tuple(offset + i for i in p.vertices) for p in mesh.polygons)
        evaluated.to_mesh_clear()
    bvh = BVHTree.FromPolygons(vertices, faces) if vertices else None

    def support(x, y):
        if bvh:
            hit = bvh.ray_cast(Vector((x, y, 0.70)), Vector((0, 0, -1)), 0.65)
            if hit[0] is not None:
                return max(0.165, hit[0].z + 0.0025)
        return 0.167

    return support


def _puffer_nylon(h):
    """Fine nylon, with broad irregular roughness and submillimetre ripstop."""
    # This private material avoids changing the same navy used on other props.
    navy = h["navy"].copy()
    navy.name = "PROP / puffer V3 fine calendered midnight nylon"
    nodes, links = navy.node_tree.nodes, navy.node_tree.links
    p = nodes.get("Principled BSDF")
    for node in list(nodes):
        if node not in (p, nodes.get("Material Output")):
            nodes.remove(node)
    p.inputs["Base Color"].default_value = (0.018, 0.013, 0.051, 1)
    p.inputs["Specular IOR Level"].default_value = 0.36
    p.inputs["Roughness"].default_value = 0.41
    p.inputs["Sheen Weight"].default_value = 0.10
    p.inputs["Sheen Roughness"].default_value = 0.38
    p.inputs["Coat Weight"].default_value = 0.012
    p.inputs["Coat Roughness"].default_value = 0.30
    tex = nodes.new("ShaderNodeTexCoord")
    rough = nodes.new("ShaderNodeTexNoise")
    rough.inputs["Scale"].default_value = 48
    rough.inputs["Detail"].default_value = 3
    links.new(tex.outputs["Object"], rough.inputs["Vector"])
    ramp = nodes.new("ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value = 0.35
    ramp.inputs["To Max"].default_value = 0.50
    links.new(rough.outputs["Fac"], ramp.inputs["Value"])
    links.new(ramp.outputs["Result"], p.inputs["Roughness"])
    fine = nodes.new("ShaderNodeTexNoise")
    fine.inputs["Scale"].default_value = 1800
    fine.inputs["Detail"].default_value = 2
    links.new(tex.outputs["Object"], fine.inputs["Vector"])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.22
    bump.inputs["Distance"].default_value = 0.00009
    links.new(fine.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], p.inputs["Normal"])
    return navy


def _puffer_closed_panel(h, name, point, mat, nx=96, ny=112):
    """A filled, closed garment panel, with continuously joined top and underside."""
    vertices, uv, faces = [], [], []
    for underside in (False, True):
        for j in range(ny + 1):
            for i in range(nx + 1):
                vertices.append(point(i / nx, j / ny, underside))
                uv.append((i / nx, j / ny))
    count = (nx + 1) * (ny + 1)
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            # Paired diagonals avoid differing automatic quad tessellation where
            # the underside follows an abrupt boundary in the packed clothing.
            faces.extend([(a, a + 1, a + nx + 2), (a, a + nx + 2, a + nx + 1)])
            faces.extend(
                [
                    (a + count, a + count + nx + 2, a + count + 1),
                    (a + count, a + count + nx + 1, a + count + nx + 2),
                ]
            )
    boundary = (
        list(range(nx + 1))
        + [j * (nx + 1) + nx for j in range(1, ny + 1)]
        + [ny * (nx + 1) + i for i in range(nx - 1, -1, -1)]
        + [j * (nx + 1) for j in range(ny - 1, 0, -1)]
    )
    for i, a in enumerate(boundary):
        b = boundary[(i + 1) % len(boundary)]
        faces.append((a, a + count, b + count, b))
    ob = _uv(h["mesh"](name, vertices, faces, mat), uv)
    ob["construction"] = "closed padded panel with nonuniform seam channels and pressure folds"
    return ob


def _puffer_join_shells(body, parts, support):
    """Sew padded volumes with a 3.0mm signed-distance union, evaluated once.

    The union removes buried shoulder caps and internal intersections. It is a
    deterministic modeling operation, not a frame-dependent cloth simulation.
    """
    vertices, faces, face_materials, materials = [], [], [], []
    for ob in [body, *parts]:
        offset = len(vertices)
        remap = []
        for material in ob.data.materials:
            if material not in materials:
                materials.append(material)
            remap.append(materials.index(material))
        for v in ob.data.vertices:
            co = v.co.copy()
            co.z = max(co.z, support(co.x, co.y) + 0.0003)
            vertices.append(tuple(co))
        for p in ob.data.polygons:
            faces.append(tuple(offset + i for i in p.vertices))
            face_materials.append(remap[p.material_index])
    data = bpy.data.meshes.new("Puffer sewn volumes before union")
    data.from_pydata(vertices, [], faces)
    data.update()
    for material in materials:
        data.materials.append(material)
    for p, index in zip(data.polygons, face_materials):
        p.material_index = index
    old = body.data
    body.data = data
    if old.users == 0:
        bpy.data.meshes.remove(old)
    remesh = body.modifiers.new("Sewn continuous garment surface / 3mm", "REMESH")
    remesh.mode = "VOXEL"
    remesh.voxel_size = 0.0030
    remesh.use_smooth_shade = True
    bpy.context.view_layer.update()
    dep = bpy.context.evaluated_depsgraph_get()
    result = bpy.data.meshes.new_from_object(body.evaluated_get(dep), depsgraph=dep)
    body.modifiers.remove(remesh)
    body.data = result
    # Preserve the sewn shell after resampling. Individually clipping vertices to
    # a new packed-clothing crease can collapse upper and lower faces together.
    # A small common clearance preserves topology and all sewn attachments.
    clearance = max(0.0, max(support(v.co.x, v.co.y) + 0.0015 - v.co.z for v in result.vertices))
    for v in result.vertices:
        v.co.z += clearance
    for attachment in list(bpy.data.objects):
        if (
            attachment is not body
            and attachment not in parts
            and attachment.name.startswith("Puffer V3")
        ):
            attachment.location.z += clearance
    body["post_union_common_clearance_m"] = clearance
    result.update()
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(result)
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=0.00001)
    bmesh.ops.dissolve_degenerate(bm, edges=list(bm.edges), dist=0.0000001)
    remaining = set(bm.verts)
    crumbs = []
    while remaining:
        seed = remaining.pop()
        island, stack = [seed], [seed]
        while stack:
            v = stack.pop()
            for edge in v.link_edges:
                other = edge.other_vert(v)
                if other in remaining:
                    remaining.remove(other)
                    island.append(other)
                    stack.append(other)
        if len(island) < 32:
            crumbs.extend(island)
    if crumbs:
        bmesh.ops.delete(bm, geom=crumbs, context="VERTS")
    # Remove tiny pinched fins left where several voxel fronts meet, then close
    # only the short local loops. This preserves a closed single garment shell.
    for edge in list(bm.edges):
        if edge.is_valid and len(edge.link_faces) > 2:
            excess = sorted(edge.link_faces, key=lambda f: f.calc_area())[
                : len(edge.link_faces) - 2
            ]
            bmesh.ops.delete(bm, geom=excess, context="FACES_ONLY")
    boundary = [edge for edge in bm.edges if len(edge.link_faces) == 1]
    if boundary:
        bmesh.ops.holes_fill(bm, edges=boundary, sides=12)
    isolated = [v for v in bm.verts if not v.link_faces]
    if isolated:
        bmesh.ops.delete(bm, geom=isolated, context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    bm.to_mesh(result)
    bm.free()
    if data.users == 0:
        bpy.data.meshes.remove(data)
    for part in parts:
        bpy.data.objects.remove(part, do_unlink=True)
    for polygon in body.data.polygons:
        polygon.use_smooth = True
    body["construction"] = "single padded garment shell; 3mm signed-distance sewn union"
    body["surface_union_resolution_m"] = 0.0030


def puffer(h):
    """Thick collapsed jacket, asymmetric elbow folds and an open turned collar.

    Geometry is deterministic; no time-stepped solve is run during a room build.
    The torso underside follows the existing packed clothes. Sleeves are filled
    swept shells whose lower surfaces are lifted above the torso where overlapping.
    """
    navy, seam = _puffer_nylon(h), h["navy_seam"]
    support = _puffer_support(h)
    cuts = [0, 0.105, 0.223, 0.352, 0.493, 0.622, 0.757, 0.882, 1]
    amplitudes = [0.021, 0.028, 0.025, 0.021, 0.035, 0.025, 0.030, 0.018]

    def seam_v(u, i):
        v = cuts[i]
        if i in (0, len(cuts) - 1):
            return v
        return v + 0.030 * math.sin(u * 3.7 + i * 0.83) * math.sin(math.pi * u)

    def torso(u, v, underside=False):
        # Anatomical shoulder/waist outline, gathered near the turned collar.
        width = 0.48 + 0.068 * math.sin(v * math.pi) - 0.080 * max(0, (v - 0.79) / 0.21)
        x = -0.265 + (u - 0.5) * width + 0.052 * math.sin(v * 4.5 - 0.3)
        y = 2.216 + 0.655 * v + 0.021 * math.sin(u * 5 + 0.6) * math.sin(v * math.pi)
        turn = math.exp(-(((u - 0.18) / 0.21) ** 2) - (v / 0.115) ** 2)
        y += 0.051 * turn
        # A left edge folded inward and one lifted shoulder establish the heap.
        x += 0.035 * math.exp(-((u / 0.13) ** 2) - ((v - 0.48) / 0.28) ** 2)
        interior = max(0, math.sin(math.pi * u) * math.sin(math.pi * v)) ** 0.42
        broad = 0.051 * math.exp(-(((u - 0.29) / 0.34) ** 2) - ((v - 0.43) / 0.38) ** 2)
        broad += 0.079 * math.exp(-(((u - 0.66) / 0.27) ** 2) - ((v - 0.70) / 0.29) ** 2)
        broad += 0.052 * math.exp(-(((u - 0.49) / 0.24) ** 2) - ((v - 0.33) / 0.22) ** 2)
        # Rest on the packed layer, but do not inherit hard edges as top ridges.
        base = 0.264 + 0.012 * math.sin(v * 3.3 + u) + 0.006 * _puffer_noise(u * 3, v * 3)
        base += 0.062 * turn
        below = max(support(x, y), base - 0.020 * interior)
        if underside:
            return (x, y, below)
        interval = next((i for i in range(len(cuts) - 1) if v <= seam_v(u, i + 1)), len(cuts) - 2)
        a, b = seam_v(u, interval), seam_v(u, interval + 1)
        f = min(1, max(0, (v - a) / (b - a)))
        quilt = amplitudes[interval] * max(0, math.sin(math.pi * f)) ** 0.72
        quilt *= 0.72 + 0.28 * math.sin(u * 4.7 + interval * 0.68) ** 2
        crease = 0.0048 * _puffer_noise(u * 19, v * 25, 0.3)
        crease += 0.0020 * _puffer_noise(u * 46, v * 53, 1.5)
        # Short converging folds from the left gathering and compressed right hip.
        for cu, cv, slope, depth, length in [
            (0.12, 0.27, 0.56, 0.010, 0.21),
            (0.23, 0.48, -0.39, 0.009, 0.17),
            (0.77, 0.61, 0.25, 0.008, 0.19),
            (0.72, 0.85, -0.7, 0.012, 0.14),
        ]:
            d = v - cv - slope * (u - cu)
            crease -= depth * math.exp(-((d / 0.014) ** 2) - ((u - cu) / length) ** 2)
        loft = (0.031 + broad + quilt + crease) * interior
        return (x, y, below + 0.003 + loft)

    body = _puffer_closed_panel(h, "Puffer V3 compressed filled torso", torso, navy)
    # Spatial support for overlapping sleeves, computed from the actual closed torso.
    from mathutils.bvhtree import BVHTree

    body_bvh = BVHTree.FromPolygons(
        [tuple(v.co) for v in body.data.vertices], [tuple(p.vertices) for p in body.data.polygons]
    )

    def jacket_top(x, y):
        hit = body_bvh.ray_cast(Vector((x, y, 0.80)), Vector((0, 0, -1)), 0.70)
        return hit[0].z if hit[0] is not None else support(x, y)

    for i in range(1, len(cuts) - 1):
        path = [
            tuple(Vector(torso(u / 112, seam_v(u / 112, i))) + Vector((0, 0, 0.0002)))
            for u in range(113)
        ]
        h["tube"]("Puffer V3 recessed torso stitch %02d" % i, path, 0.00036, seam)
    for u in (0.016, 0.984):
        h["tube"](
            "Puffer V3 garment side binding", [torso(u, j / 112) for j in range(113)], 0.0010, seam
        )
    hem = [torso(i / 112, 0.026) for i in range(113)]
    h["tube"]("Puffer V3 gathered hem", hem, 0.0016, seam)
    # A dark fabric zipper strip is partly lost under the folded right sleeve.
    zipper = []
    for j in range(75):
        v = 0.035 + j / 74 * 0.90
        p = Vector(torso(0.53 + 0.075 * math.sin(v * 5.1), v))
        p.z += 0.0013
        zipper.append(tuple(p))
    h["tube"]("Puffer V3 exposed zip tape", zipper, 0.0024, seam)
    h["tube"](
        "Puffer V3 fine dark zipper chain",
        [(x, y, z + 0.0010) for x, y, z in zipper],
        0.0006,
        h["silver"],
    )
    slider = zipper[12]
    h["B"]("Puffer V3 small zipper slider", slider, (0.007, 0.012, 0.003), h["silver"], 0.001)

    def sleeve(name, control, widths, depths, seed):
        path = _catmull(control, 22)
        sides = 56
        vertices, faces, uvs, top_ring = [], [], [], []
        sleeve_cuts = [0, 0.11, 0.236, 0.374, 0.518, 0.645, 0.774, 0.902, 1]
        for i, origin in enumerate(path):
            t = i / (len(path) - 1)
            q = t * (len(widths) - 1)
            a = min(int(q), len(widths) - 2)
            f = q - a
            rw = widths[a] * (1 - f) + widths[a + 1] * f
            rz = depths[a] * (1 - f) + depths[a + 1] * f
            if 0 < i < len(path) - 1:
                aa = path[i] - path[i - 1]
                bb = path[i + 1] - path[i]
                aa.z = bb.z = 0
                cross = abs(aa.x * bb.y - aa.y * bb.x)
                if cross > 1e-10:
                    turn_radius = aa.length * bb.length * (aa + bb).length / (2 * cross)
                    # Compress the inner elbow where the bend radius cannot fit
                    # a circular filled section. This is a geometric constraint.
                    rw = min(rw, 0.78 * turn_radius)
            tangent = path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]
            # Keep the section vertical to give predictable support at tight elbows.
            side = Vector((-tangent.y, tangent.x, 0)).normalized()
            p = origin.copy()
            # Pressure flattens the underside while retaining a filled upper sleeve.
            # Include the full sleeve width, not only its centre ray. Otherwise
            # a low centre with one side over the torso can invert the underside.
            floor = max(
                jacket_top(p.x + side.x * rw * k / 16, p.y + side.y * rw * k / 16)
                for k in range(-16, 17)
            )
            tucked_shoulder = math.exp(-((t / 0.095) ** 2))
            cloth_floor = max(
                support(p.x + side.x * rw * k / 16, p.y + side.y * rw * k / 16)
                for k in range(-16, 17)
            )
            floor = floor * (1 - tucked_shoulder) + cloth_floor * tucked_shoulder
            p.z = max(p.z - 0.065 * tucked_shoulder, floor + rz * 0.68 + 0.007)
            ring = []
            for j in range(sides):
                angle = TAU * j / sides
                phase = t + 0.012 * math.sin(angle * 2.2 + seed) * math.sin(math.pi * t)
                seg = next(
                    (k for k in range(len(sleeve_cuts) - 1) if phase <= sleeve_cuts[k + 1]),
                    len(sleeve_cuts) - 2,
                )
                fv = min(
                    1,
                    max(0, (phase - sleeve_cuts[seg]) / (sleeve_cuts[seg + 1] - sleeve_cuts[seg])),
                )
                quilt = 0.90 + 0.10 * max(0, math.sin(math.pi * fv)) ** 0.65
                wr = 0.0028 * _puffer_noise(t * 28, math.cos(angle) * 6, math.sin(angle) * 6 + seed)
                wr += 0.0012 * _puffer_noise(t * 69, angle * 12, seed)
                pressure = 0.0022 + 0.0027 * math.exp(-(((t - 0.58) / 0.21) ** 2))
                wr += pressure * _puffer_noise(
                    t * 58, math.cos(angle) * 14, math.sin(angle) * 14 + seed
                )
                wr *= max(0, math.sin(math.pi * t)) ** 0.55
                # An elliptical cross-section is compressed underneath, padded above.
                horizontal = rw * math.cos(angle) * quilt
                vertical = rz * math.sin(angle) * quilt
                if vertical < 0:
                    vertical *= 0.68
                pt = p + side * horizontal + Vector((0, 0, vertical + wr))
                ring.append(tuple(pt))
                vertices.append(tuple(pt))
                uvs.append((j / sides, t))
            top_ring.append(ring)
        for i in range(len(path) - 1):
            for j in range(sides):
                a, b = i * sides + j, i * sides + (j + 1) % sides
                faces.append((a, b, b + sides, a + sides))
        faces.append(tuple(range(sides - 1, -1, -1)))
        # Recess the cuff lining into an actual opening, rather than closing the
        # visible wrist with a flat navy disk.
        cuff_center = Vector(tuple(sum(p[k] for p in top_ring[-1]) / sides for k in range(3)))
        preceding_center = Vector(tuple(sum(p[k] for p in top_ring[-2]) / sides for k in range(3)))
        along = (cuff_center - preceding_center).normalized()
        inner_start = len(vertices)
        for point in top_ring[-1]:
            q = cuff_center + (Vector(point) - cuff_center) * 0.72 - along * 0.018
            vertices.append(tuple(q))
            uvs.append((0.5, 1))
        last_start = (len(path) - 1) * sides
        for j in range(sides):
            nxt = (j + 1) % sides
            faces.append((last_start + j, last_start + nxt, inner_start + nxt, inner_start + j))
        faces.append(tuple(inner_start + j for j in range(sides)))
        ob = _uv(h["mesh"](name, vertices, faces, navy), uvs)
        ob["construction"] = "filled nonuniform sleeve, compressed underside and a curved elbow"
        # Trace actual recessed sections, with interrupted stitches at elbow compression.
        for k, cut in enumerate(sleeve_cuts[1:-1]):
            row = round(cut * (len(path) - 1))
            points = top_ring[row]
            h["tube"](name + " recessed seam %02d" % k, points + points[:1], 0.00034, seam)
        cuff = top_ring[-1]
        h["tube"](name + " rolled cuff edge", cuff + cuff[:1], 0.0016, seam)
        # Short overstitched diagonal creases around the strongly compressed elbow.
        return ob

    left_sleeve = sleeve(
        "Puffer V3 left sleeve doubled at elbow",
        [
            (-0.432, 2.805, 0.356),
            (-0.565, 2.690, 0.337),
            (-0.570, 2.500, 0.297),
            (-0.517, 2.373, 0.316),
            (-0.390, 2.320, 0.345),
            (-0.263, 2.373, 0.378),
            (-0.208, 2.535, 0.430),
        ],
        [0.092, 0.093, 0.082, 0.073, 0.066, 0.046],
        [0.067, 0.071, 0.071, 0.063, 0.056, 0.040],
        2.1,
    )
    right_sleeve = sleeve(
        "Puffer V3 right sleeve loosely folded",
        [
            (-0.074, 2.803, 0.375),
            (0.045, 2.720, 0.355),
            (0.080, 2.562, 0.329),
            (0.012, 2.467, 0.319),
            (-0.039, 2.381, 0.306),
        ],
        [0.086, 0.085, 0.073, 0.063, 0.043],
        [0.068, 0.073, 0.060, 0.052, 0.034],
        5.6,
    )

    # Turned collar: thick U-shaped roll with a visible concave lining, not a lid.
    lining = h["material"]("puffer V3 shadowed collar lining", (0.009, 0.007, 0.027), 0.55)
    n, sides = 92, 40
    vv, ff, uv = [], [], []
    for i in range(n + 1):
        t = i / n
        a = -0.18 + t * (math.pi + 0.36)
        p = Vector(
            (
                -0.242 + 0.101 * math.cos(a),
                2.741 + 0.082 * math.sin(a),
                0.399 + 0.021 * math.sin(a) + 0.007 * math.sin(a * 3 + 1),
            )
        )
        p.z = jacket_top(p.x, p.y) + 0.008
        radial = Vector((math.cos(a), math.sin(a), 0))
        for j in range(sides):
            b = TAU * j / sides
            q = p + radial * (0.026 * math.cos(b)) + Vector((0, 0, 0.037 * math.sin(b)))
            q.z += 0.0019 * _puffer_noise(t * 23, j / sides * 9, 4)
            vv.append(tuple(q))
            uv.append((t, j / sides))
    for i in range(n):
        for j in range(sides):
            a, b = i * sides + j, i * sides + (j + 1) % sides
            ff.append((a, b, b + sides, a + sides))
    ff.extend([tuple(range(sides - 1, -1, -1)), tuple(n * sides + j for j in range(sides))])
    # The radial/up frame is opposite-handed to the sleeve frame.
    ff = [tuple(reversed(face)) for face in ff]
    collar = _uv(h["mesh"]("Puffer V3 turned padded open collar", vv, ff, navy), uv)
    collar.data.materials.append(lining)
    for p in collar.data.polygons:
        if p.index < n * sides and sides * 0.25 < p.index % sides < sides * 0.75:
            p.material_index = 1
    h["tube"](
        "Puffer V3 collar outer stitched edge",
        [vv[i * sides + sides // 4] for i in range(n + 1)],
        0.00065,
        seam,
    )
    _puffer_join_shells(body, [left_sleeve, right_sleeve, collar], support)


def backpack(h):
    """Continuous slumped shell, shallow sewn pockets and flattened webbing."""
    body, cream = h["backpack"], h["ivory_fabric"]
    sides, rings = 64, 48
    profile = [
        (0, 0.082, 0.115),
        (0.05, 0.100, 0.144),
        (0.22, 0.113, 0.163),
        (0.53, 0.107, 0.157),
        (0.75, 0.095, 0.147),
        (0.9, 0.072, 0.119),
        (0.97, 0.047, 0.072),
        (1, 0.009, 0.013),
    ]

    def shell(t, a):
        lo = next((i for i in range(len(profile) - 1) if profile[i + 1][0] >= t), len(profile) - 2)
        f = (t - profile[lo][0]) / (profile[lo + 1][0] - profile[lo][0])
        # Smoothstep avoids visible planar rings between the bag's profile sections.
        f = f * f * (3 - 2 * f)
        depth = profile[lo][1] * (1 - f) + profile[lo + 1][1] * f
        width = profile[lo][2] * (1 - f) + profile[lo + 1][2] * f
        ca, sa = math.cos(a), math.sin(a)
        wrinkle = 0.0021 * math.sin(9 * a + 15 * t) + 0.0011 * math.sin(19 * a - 29 * t)
        wrinkle *= math.sin(math.pi * t) * (0.4 + 0.6 * math.exp(-(((t - 0.20) / 0.18) ** 2)))
        return (
            -1.286 - 0.025 * t + depth * math.copysign(abs(ca) ** 0.78, ca) + wrinkle,
            2.805 + width * math.copysign(abs(sa) ** 0.88, sa) + wrinkle * 0.4,
            0.89 + 0.425 * t + 0.0024 * math.sin(a * 3) * math.sin(math.pi * t),
        )

    vertices = [shell(i / rings, TAU * j / sides) for i in range(rings + 1) for j in range(sides)]
    faces = []
    for i in range(rings):
        for j in range(sides):
            a = i * sides + j
            b = i * sides + (j + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces += [tuple(range(sides - 1, -1, -1)), tuple(rings * sides + j for j in range(sides))]
    ob = h["mesh"]("Backpack continuous shaped nylon shell", vertices, faces, body)
    ob.data.materials.append(cream)
    for i in range(rings):
        for j in range(sides):
            a = TAU * (j + 0.5) / sides
            if (i + 0.5) / rings > 0.735 + 0.11 * abs(math.sin(a)):
                ob.data.polygons[i * sides + j].material_index = 1
    _uv(ob, [(j / sides, i / rings) for i in range(rings + 1) for j in range(sides)])
    h["tube"](
        "Backpack crown panel seam",
        [shell(0.735 + 0.11 * abs(math.sin(a)), a) for a in [TAU * j / 160 for j in range(161)]],
        0.00075,
        h["backpack_piping"],
    )

    def pocket(name, center_z, width, height, front_x, depth):
        def panel(u, v):
            # Arched top panel: upright lower sides and a shallow semicircular crown.
            arch = math.sqrt(max(0, 1 - (2 * u - 1) ** 2))
            z = center_z - height * 0.5 + v * height * (0.72 + 0.28 * arch)
            edge = max(0, math.sin(math.pi * u) * math.sin(math.pi * v))
            x = front_x + depth * edge**0.6
            x += 0.0014 * math.sin(u * 22 + v * 11) * edge
            y = 2.805 + (u - 0.5) * width
            return (x, y, z)

        # Grid order y,z gives front normals +X.
        _grid(h, name + " sewn front panel", panel, body, 64, 42, 0.004)
        border = (
            [panel(i / 96, 0) for i in range(97)]
            + [panel(1, j / 48) for j in range(1, 49)]
            + [panel(i / 96, 1) for i in range(95, -1, -1)]
            + [panel(0, j / 48) for j in range(47, 0, -1)]
        )
        # Real sewn gussets connect the pocket face back into the preceding shell.
        # A floating front-only patch otherwise exposes a gap in oblique views.
        back = [(front_x - max(0.016, depth), y, z) for x, y, z in border]
        length = len(border)
        walls = [
            (i, (i + 1) % length, (i + 1) % length + length, i + length) for i in range(length)
        ]
        h["mesh"](name + " joined fabric gussets", border + back, walls, body)
        h["tube"](name + " perimeter binding", border + border[:1], 0.0013, h["backpack_piping"])
        path = [panel(i / 96, 0.89) for i in range(97)]
        h["tube"](name + " cream zip tape", path, 0.002, h["backpack_piping"])
        h["tube"](
            name + " metal zip chain",
            [(x + 0.0015, y, z) for x, y, z in path],
            0.00052,
            h["silver"],
        )
        for idx in (9, 86):
            x, y, z = path[idx]
            h["B"](
                name + " narrow zipper pull",
                (x + 0.003, y, z - 0.008),
                (0.003, 0.006, 0.019),
                h["silver"],
                0.001,
            )
        return panel

    pocket("Backpack middle compartment", 1.099, 0.294, 0.285, -1.192, 0.041)
    panel = pocket("Backpack front pocket", 1.036, 0.253, 0.221, -1.151, 0.030)
    labelpos = panel(0.5, 0.52)
    h["B"](
        "Backpack fabric identity patch",
        (labelpos[0] + 0.002, labelpos[1], labelpos[2]),
        (0.001, 0.062, 0.023),
        h["tissue"],
        0.001,
    )
    h["text"](
        "Backpack neutral woven label",
        "TRAVEL",
        (labelpos[0] + 0.0028, labelpos[1] - 0.024, labelpos[2] - 0.004),
        0.008,
        body,
        right=(0, 1, 0),
        up=(0, 0, 1),
    )

    def ribbon(name, control, width, mat):
        path = _catmull(control, 12)
        vv, ff = [], []
        for i, p in enumerate(path):
            # Webbing is broad across y, very thin across x: no tubular straps.
            for side in (-1, 1):
                q = p + Vector((0.0012 * math.sin(i * 0.42), side * width * 0.5, 0))
                vv.append(tuple(q))
        for i in range(len(path) - 1):
            a = i * 2
            ff.append((a, a + 2, a + 3, a + 1))
        ob = h["mesh"](name, vv, ff, mat)
        thick = ob.modifiers.new("Webbing thickness", "SOLIDIFY")
        thick.thickness = 0.003
        for side in (0, 1):
            h["tube"](
                name + " edge stitching",
                [vv[i * 2 + side] for i in range(len(path))],
                0.0004,
                h["backpack_piping"],
            )

    ribbon(
        "Backpack folded top carry handle",
        [
            (-1.322, 2.805, 1.300),
            (-1.346, 2.805, 1.359),
            (-1.275, 2.805, 1.367),
            (-1.238, 2.805, 1.298),
        ],
        0.024,
        body,
    )
    for yy in (2.684, 2.919):
        ribbon(
            "Backpack padded shoulder strap",
            [(-1.356, yy, 1.25), (-1.415, yy, 1.167), (-1.421, yy, 0.994), (-1.356, yy, 0.910)],
            0.042,
            body,
        )
        h["B"](
            "Backpack strap adjuster",
            (-1.419, yy, 0.997),
            (0.011, 0.042, 0.022),
            h["shellrim"],
            0.002,
        )
    # Side pockets follow a shallow cloth cup; gathered mouth breaks perfect symmetry.
    for side in (-1, 1):

        def sidepanel(u, v, sign=side):
            return (
                -1.28 + (u - 0.5) * 0.13,
                2.805 + sign * (0.150 + 0.014 * math.sin(math.pi * u) * math.sin(math.pi * v)),
                0.918 + v * 0.134 + 0.002 * math.sin(u * 27) * v,
            )

        _grid(h, "Backpack gathered side mesh pocket", sidepanel, body, 36, 28, 0.002)
        h["tube"](
            "Backpack elastic pocket mouth",
            [sidepanel(i / 60, 1) for i in range(61)],
            0.002,
            h["backpack_piping"],
        )


def sneaker(h, name, center, angle=0, scale=1):
    """Last-shaped upper with a genuine open collar, tongue, crossed laces and EVA sole."""
    before = {o.name for o in bpy.data.objects}
    origin = Vector(center)

    def world(p):
        return tuple(origin + Vector(p) * scale)

    # Start at the heel and travel clockwise when viewed from above.
    outline = _catmull(
        [
            (0.022, 0.121, 0),
            (0.039, 0.083, 0),
            (0.041, 0.016, 0),
            (0.048, -0.060, 0),
            (0.044, -0.110, 0),
            (0.021, -0.132, 0),
            (-0.019, -0.132, 0),
            (-0.043, -0.110, 0),
            (-0.046, -0.065, 0),
            (-0.040, 0.002, 0),
            (-0.045, 0.065, 0),
            (-0.029, 0.119, 0),
        ],
        8,
        closed=True,
    )[:-1]
    count = len(outline)
    rings = [(0.009, 0.94), (0.013, 1.005), (0.027, 1.017), (0.041, 0.955)]
    vv, ff = [], []
    for zz, width in rings:
        for p in outline:
            toe_lift = 0.008 * max(0, (-p.y - 0.075) / 0.06) ** 1.6
            vv.append(world((p.x * width, p.y, zz + toe_lift)))
    for i in range(len(rings) - 1):
        for j in range(count):
            a, b = i * count + j, i * count + (j + 1) % count
            ff.append((a, a + count, b + count, b))
    ff += [
        tuple(range(count)),
        tuple((len(rings) - 1) * count + j for j in range(count - 1, -1, -1)),
    ]
    h["mesh"](name + " layered EVA midsole", vv, ff, h["sole"])
    # No flat lines across the shoe: grooves follow the actual sidewall contours.
    for zz in (0.014, 0.033):
        pts = [
            world(
                (
                    p.x * (1.01 if zz < 0.02 else 0.985),
                    p.y,
                    zz + 0.007 * max(0, (-p.y - 0.075) / 0.06) ** 1.6,
                )
            )
            for p in outline
        ]
        h["tube"](
            name + " sole molded sidewall groove", pts + pts[:1], 0.00065 * scale, h["shoeupper"]
        )
    for j in range(0, count, 4):
        p = outline[j]
        h["tube"](
            name + " outsole tread notch",
            [world((p.x * 1.005, p.y, 0.012)), world((p.x * 1.017, p.y + 0.003, 0.026))],
            0.00055 * scale,
            h["shoeupper"],
        )

    vv, ff, uv = [], [], []
    rows = 24
    collar = []
    for j, p in enumerate(outline):
        # Radial correspondence between the sole and the smaller, heelward collar.
        a = math.atan2(p.y - 0.057, p.x)
        collar.append(
            Vector(
                (
                    0.0265 * math.cos(a),
                    0.068 + 0.041 * math.sin(a),
                    0.108 + 0.009 * (math.sin(a) + 1) * 0.5,
                )
            )
        )
    for row in range(rows + 1):
        t = row / rows
        for j, p in enumerate(outline):
            edge = collar[j]
            x = p.x * 0.94 * (1 - t) + edge.x * t
            y = p.y * (1 - t) + edge.y * t
            # A full toe box and instep rise into the actual empty ankle opening.
            zbase = 0.042 + 0.008 * max(0, (-p.y - 0.075) / 0.06) ** 1.6
            z = zbase + (edge.z - zbase) * math.sin(t * math.pi / 2) ** 0.72
            z += 0.0014 * math.sin(j / count * TAU * 9 + t * 13) * math.sin(math.pi * t)
            vv.append(world((x, y, z)))
            uv.append((j / count, t))
    for i in range(rows):
        for j in range(count):
            a, b = i * count + j, i * count + (j + 1) % count
            ff.append((a, a + count, b + count, b))
    _uv(h["mesh"](name + " shaped knitted upper with open collar", vv, ff, h["shoeupper"]), uv)
    # A short dark liner makes the collar a cavity, rather than a black disk on a solid blob.
    innerv, innerf = [], []
    for p in collar:
        innerv.append(world(p))
    for p in collar:
        innerv.append(world((p.x * 0.89, 0.068 + (p.y - 0.068) * 0.89, 0.061)))
    for j in range(count):
        k = (j + 1) % count
        innerf.append((j, k, count + k, count + j))
    innerf.append(tuple(count + j for j in range(count - 1, -1, -1)))
    h["mesh"](name + " recessed ankle lining", innerv, innerf, h["rubber"])
    points = [world(p) for p in collar]
    h["tube"](name + " padded collar binding", points + points[:1], 0.0023 * scale, h["cotton"])

    def tongue(u, v):
        x = (u - 0.5) * (0.048 - 0.007 * v)
        y = -0.065 + 0.128 * v
        z = 0.096 + 0.021 * v + 0.0035 * math.sin(math.pi * u)
        z += 0.001 * math.sin(u * 11 + v * 8)
        return world((x, y, z))

    _grid(h, name + " separate folded shoe tongue", tongue, h["cotton"], 22, 32, 0.003 * scale)
    h["tube"](
        name + " tongue stitched edge",
        [tongue(0.06, j / 40) for j in range(41)]
        + [tongue(0.94, j / 40) for j in range(40, -1, -1)],
        0.00055 * scale,
        h["sole"],
    )
    for row in range(6):
        yy = -0.052 + row * 0.016
        zz = 0.101 + row * 0.0029
        # Each row contains two opposing flat shoelace runs and a visible eyelet pair.
        for direction in (-1, 1):
            h["tube"](
                name + " crossed cotton shoelace",
                [
                    world((-direction * 0.027, yy, zz)),
                    world((-direction * 0.008, yy + 0.006, zz + 0.004)),
                    world((direction * 0.027, yy + 0.015, zz + 0.003)),
                ],
                0.0012 * scale,
                h["sole"],
            )
        for side in (-1, 1):
            # Small neutral fabric eyelets, no oversized polished metal buttons.
            h["E"](
                name + " eyelet",
                world((side * 0.027, yy, zz)),
                (0.0022 * scale, 0.0025 * scale, 0.00075 * scale),
                h["sole"],
            )
    for side in (-1, 1):
        h["tube"](
            name + " lace bow loop",
            [
                world((side * 0.009, 0.039, 0.121)),
                world((side * 0.045, 0.052, 0.123)),
                world((side * 0.032, 0.072, 0.117)),
                world((side * 0.005, 0.041, 0.121)),
            ],
            0.0012 * scale,
            h["sole"],
        )
        h["tube"](
            name + " loose lace end",
            [
                world((side * 0.005, 0.041, 0.12)),
                world((side * 0.041, 0.006, 0.111)),
                world((side * 0.046, -0.017, 0.078)),
            ],
            0.0011 * scale,
            h["sole"],
        )
        # Heel counter and stitched overlays follow the last's curved outside wall.
        h["tube"](
            name + " side panel stitched overlay",
            [
                world((side * 0.040, -0.091, 0.061)),
                world((side * 0.042, -0.025, 0.075)),
                world((side * 0.035, 0.044, 0.093)),
                world((side * 0.029, 0.092, 0.097)),
            ],
            0.0007 * scale,
            h["sole"],
        )
    h["B"](
        name + " heel pull tab",
        world((0, 0.114, 0.111)),
        (0.017 * scale, 0.004 * scale, 0.025 * scale),
        h["cotton"],
        0.001,
    )
    h["transform_group"](before, center, angle)


def _crumpled_sheet(h, name, center, size, mat, seed=0, lift=0.03, angle=0):
    """A deformed square sheet with folded corners and narrow crease ridges."""
    sx, sy = size
    ca, sa = math.cos(angle), math.sin(angle)

    def sheet(u, v):
        a, b = u - 0.5, v - 0.5
        fold = 0.013 * math.sin(u * 13 + v * 4 + seed)
        fold += 0.008 * math.sin(v * 17 - u * 6 + seed * 0.7)
        ridge = math.exp(-(((v - 0.18 - u * 0.56) / 0.075) ** 2))
        x = a * sx + 0.12 * sx * math.sin(v * 7 + seed) * abs(a) ** 1.4
        y = b * sy + 0.10 * sy * math.sin(u * 6 + seed) * abs(b) ** 1.4
        z = lift * (0.34 + 0.45 * math.sin(u * 8 + v * 6 + seed) ** 2 + 0.45 * ridge)
        z += fold * min(sx, sy) / 0.10
        # Corners curl back into the wad; the material retains visible thin edges.
        z += lift * 0.42 * (abs(a) * 2) ** 5 * (abs(b) * 2) ** 3
        return (center[0] + ca * x - sa * y, center[1] + sa * x + ca * y, center[2] + max(0.001, z))

    return _grid(h, name, sheet, mat, 42, 38, 0.00035)


def entry_wastebasket(h):
    """Tapered hollow office bin, folded translucent liner and photographed white waste."""
    shellmat = h["material"](
        "warm grey injection molded wastebasket", (0.29, 0.30, 0.278), 0.48, bump=0.00015, scale=280
    )
    lipmat = h["material"]("wastebasket slightly polished lip", (0.27, 0.278, 0.262), 0.34)
    liner = h["material"](
        "thin translucent folded bin liner",
        (0.70, 0.71, 0.695),
        0.31,
        transmission=0.62,
        bump=0.00008,
        scale=210,
    )
    liner.node_tree.nodes.get("Principled BSDF").inputs["Specular IOR Level"].default_value = 0.33
    x, y = -0.44, 0.49
    sides = 96
    profiles = [
        (0.014, 0.122, 0.103),
        (0.022, 0.129, 0.11),
        (0.398, 0.159, 0.134),
        (0.418, 0.163, 0.137),
        (0.426, 0.16, 0.135),
        (0.426, 0.153, 0.128),
        (0.409, 0.151, 0.126),
        (0.029, 0.120, 0.101),
        (0.022, 0.120, 0.101),
    ]

    def rounded(a, rx, ry, zz):
        ca, sa = math.cos(a), math.sin(a)
        return (
            x + rx * math.copysign(abs(ca) ** 0.40, ca),
            y + ry * math.copysign(abs(sa) ** 0.40, sa),
            zz,
        )

    verts = [rounded(TAU * j / sides, rx, ry, zz) for zz, rx, ry in profiles for j in range(sides)]
    faces = []
    for i in range(len(profiles) - 1):
        for j in range(sides):
            a, b = i * sides + j, i * sides + (j + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces += [
        tuple(range(sides - 1, -1, -1)),
        tuple((len(profiles) - 1) * sides + j for j in range(sides)),
    ]
    h["mesh"]("Entry grey wastebasket / hollow tapered shell", verts, faces, shellmat)
    h["tube"](
        "Wastebasket rounded molded upper lip",
        [rounded(TAU * i / 160, 0.16, 0.135, 0.424) for i in range(161)],
        0.003,
        lipmat,
    )
    h["tube"](
        "Wastebasket raised bottom foot",
        [rounded(TAU * i / 128, 0.123, 0.104, 0.016) for i in range(129)],
        0.002,
        shellmat,
    )

    liner_profiles = [
        (0, 0.112, 0.094, 0.25),
        (0.40, 0.149, 0.124, 0.394),
        (0.57, 0.163, 0.137, 0.429),
        (0.72, 0.168, 0.143, 0.431),
        (1, 0.165, 0.141, 0.373),
    ]

    def lining(a, t):
        i = next(
            (j for j in range(len(liner_profiles) - 1) if liner_profiles[j + 1][0] >= t),
            len(liner_profiles) - 2,
        )
        t0, rx0, ry0, z0 = liner_profiles[i]
        t1, rx1, ry1, z1 = liner_profiles[i + 1]
        f = (t - t0) / (t1 - t0)
        rx, ry, zz = (rx0 * (1 - f) + rx1 * f, ry0 * (1 - f) + ry1 * f, z0 * (1 - f) + z1 * f)
        fold = 0.0028 * math.sin(19 * a + t * 11) + 0.0018 * math.sin(31 * a - 7 * t)
        fold *= 0.4 + 0.6 * t
        zz += t * (0.008 * math.sin(11 * a + 6 * t) + 0.004 * math.cos(a * 23))
        if t > 0.72:
            zz += (t - 0.72) / 0.28 * (0.010 * math.sin(a * 5 + 0.5))
        p = rounded(a, rx + fold, ry + fold * 0.7, zz)
        return p

    # The same sheet travels up the interior, over the lip, and down the outside.
    vv = [lining(TAU * j / sides, i / 40) for i in range(41) for j in range(sides)]
    ff = []
    for i in range(40):
        for j in range(sides):
            a, b = i * sides + j, i * sides + (j + 1) % sides
            ff.append((a, b, b + sides, a + sides))
    ob = h["mesh"]("Wastebasket transparent liner folded over rim", vv, ff, liner)
    mod = ob.modifiers.new("Polyethylene film gauge", "SOLIDIFY")
    mod.thickness = 0.000055
    mod.offset = 0
    h["tube"](
        "Wastebasket liner irregular loose edge",
        [lining(TAU * j / 192, 1) for j in range(193)],
        0.0004,
        liner,
    )
    # Paper wads have real angular creases, rather than sphere stand-ins.
    for i, (dx, dy, zz, size, rot) in enumerate(
        [
            (-0.052, -0.028, 0.359, 0.100, 0.3),
            (0.050, 0.032, 0.366, 0.095, -0.6),
            (0.015, -0.071, 0.378, 0.089, 0.8),
            (-0.070, 0.042, 0.384, 0.095, -0.2),
            (0.035, 0.012, 0.398, 0.088, 0.4),
            (-0.026, -0.006, 0.405, 0.086, -0.4),
            (0.064, -0.029, 0.382, 0.074, 1.0),
        ]
    ):
        _crumpled_sheet(
            h,
            "Wastebasket crumpled paper %02d" % i,
            (x + dx, y + dy, zz),
            (size, size * 0.85),
            h["tissue"],
            seed=i + 2,
            lift=0.034,
            angle=rot,
        )
    _crumpled_sheet(
        h,
        "Wastebasket folded ochre wrapper",
        (x - 0.064, y - 0.060, 0.388),
        (0.063, 0.041),
        h["gold"],
        seed=3.2,
        lift=0.009,
        angle=-0.4,
    )
    _crumpled_sheet(
        h,
        "Wastebasket white receipt strip",
        (x - 0.038, y - 0.070, 0.413),
        (0.089, 0.028),
        h["paper"],
        seed=0.8,
        lift=0.007,
        angle=0.13,
    )


def _folded_packet(h, name, center, size, mat, height=0.035, phase=0, angle=0, support=None):
    """Sewn or heat-sealed flat packaging, with compressed edges and asymmetric creases."""
    sx, sy = size
    ca, sa = math.cos(angle), math.sin(angle)

    def surface(u, v, underside=False):
        u, v = min(1, max(0, u)), min(1, max(0, v))
        x, y = (u - 0.5) * sx, (v - 0.5) * sy
        interior = max(0, math.sin(math.pi * u) * math.sin(math.pi * v))
        # A couple of broad folds establish volume; narrow ridges read as crushed film.
        volume = height * (0.17 + 0.32 * math.sin(u * 4 + phase) ** 2) * interior**0.6
        ridge1 = height * 0.61 * math.exp(-(((v - 0.16 - u * 0.55) / 0.045) ** 2))
        ridge2 = height * 0.32 * math.exp(-(((u - 0.75 + v * 0.34) / 0.035) ** 2))
        creases = height * 0.10 * math.sin(u * 39 + v * 19 + phase) * interior
        creases += height * 0.045 * math.sin(v * 53 - u * 13)
        corner = height * (0.14 + 0.15 * math.sin(u * 8 + phase)) * (abs(v - 0.5) * 2) ** 8
        z = 0.0013 + max(0, corner)
        if not underside:
            z += max(0.001, volume + ridge1 + ridge2 + creases)
        x += 0.012 * sx * math.sin(v * 17 + phase) * (abs(u - 0.5) * 2) ** 6
        y += 0.018 * sy * math.sin(u * 14 + phase) * (abs(v - 0.5) * 2) ** 6
        wx, wy = center[0] + ca * x - sa * y, center[1] + sa * x + ca * y
        base = max(center[2], support(wx, wy)) if support is not None else center[2]
        return (wx, wy, base + z)

    # Keep small wrappers light while resolving folds on the large foreground bag.
    longest = max(size)
    nx, ny = (
        (88, 64)
        if longest > 0.4
        else (64, 48)
        if longest > 0.2
        else (44, 32)
        if longest > 0.13
        else (32, 28)
    )
    verts, uv, faces = [], [], []
    for underneath in (False, True):
        for j in range(ny + 1):
            for i in range(nx + 1):
                verts.append(surface(i / nx, j / ny, underneath))
                uv.append((i / nx, j / ny))
    count = (nx + 1) * (ny + 1)
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
            faces.append((a + count, a + count + nx + 1, a + count + nx + 2, a + count + 1))
    boundary = (
        list(range(nx + 1))
        + [j * (nx + 1) + nx for j in range(1, ny + 1)]
        + [ny * (nx + 1) + i for i in range(nx - 1, -1, -1)]
        + [j * (nx + 1) for j in range(ny - 1, 0, -1)]
    )
    for i, a in enumerate(boundary):
        b = boundary[(i + 1) % len(boundary)]
        faces.append((a, a + count, b + count, b))
    _uv(h["mesh"](name, verts, faces, mat), uv)
    return surface


def _print_on_packet(h, name, body, uv_origin, size, mat, surface):
    """Conform actual font triangles to a folded packet; no floating flat decal."""
    tmp = h["text"](
        name + " temporary font", body, (*uv_origin, 0), size, mat, right=(1, 0, 0), up=(0, 1, 0)
    )
    bpy.context.view_layer.update()
    data = bpy.data.meshes.new_from_object(tmp.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    vv = []
    for v in data.vertices:
        co = tmp.matrix_world @ v.co
        p = surface(co.x, co.y)
        vv.append((p[0], p[1], p[2] + 0.00018))
    faces = [tuple(p.vertices) for p in data.polygons]
    h["mesh"](name, vv, faces, mat, smooth=False)
    bpy.data.meshes.remove(data)
    fontdata = tmp.data
    bpy.data.objects.remove(tmp, do_unlink=True)
    bpy.data.curves.remove(fontdata)


def _ribbon_on_points(h, name, points, width, mat, axis=(1, 0, 0), floor=None):
    path = _catmull(points, 10)
    vv, ff = [], []
    for i, p in enumerate(path):
        if floor is not None:
            p.z = max(p.z, floor(p.x, p.y))
        tangent = path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]
        across = tangent.cross(Vector((0, 0, 1)))
        if across.length < 0.000001:
            across = Vector(axis)
        half = across.normalized() * width * 0.5
        vv.extend([tuple(p - half), tuple(p + half)])
    for i in range(len(path) - 1):
        a = 2 * i
        ff.append((a, a + 1, a + 3, a + 2))
    ob = h["mesh"](name, vv, ff, mat)
    mod = ob.modifiers.new("Flattened handle tape", "SOLIDIFY")
    mod.thickness = 0.0008
    return ob


def kitchen_soft_packages(h):
    """White shopping bag, burgundy handles, dark crumpled bag, cap and zipped pouch."""
    white = h["material"](
        "white satin plastic shopping bag", (0.83, 0.827, 0.79), 0.51, bump=0.0001, scale=250
    )
    maroon = h["material"](
        "burgundy woven shopping bag handles", (0.12, 0.015, 0.027), 0.68, bump=0.00015, scale=360
    )
    darkfilm = h["material"](
        "creased charcoal shopping bag", (0.027, 0.028, 0.026), 0.49, bump=0.00008, scale=310
    )
    olive = h["material"](
        "washed olive cotton cap", (0.165, 0.164, 0.13), 0.86, bump=0.00024, scale=420
    )
    # Fridge/tall cupboards are towards the entry after the kitchen reflection.
    # These coordinates keep the bag on that free worktop, clear of the hob at x1.07.
    white_surface = _folded_packet(
        h,
        "Kitchen large white crumpled shopping bag",
        (0.13, 0.347, 0.94),
        (0.56, 0.342),
        white,
        height=0.085,
        phase=0.9,
        angle=-0.09,
    )
    for v in (0.035, 0.965):
        h["tube"](
            "White shopping bag sealed edge",
            [white_surface(i / 100, v) for i in range(101)],
            0.0005,
            h["paper"],
        )
    _print_on_packet(
        h,
        "Shopping bag burgundy authored store print",
        "CAMPUS",
        (0.27, 0.34),
        0.112,
        maroon,
        white_surface,
    )
    _print_on_packet(
        h,
        "Shopping bag small authored lettering",
        "BOOKSTORE",
        (0.29, 0.26),
        0.061,
        maroon,
        white_surface,
    )

    def bag_height(x, y):
        ca, sa = math.cos(-0.09), math.sin(-0.09)
        xx, yy = x - 0.13, y - 0.347
        u = (ca * xx + sa * yy) / 0.56 + 0.5
        v = (-sa * xx + ca * yy) / 0.342 + 0.5
        return white_surface(u, v)[2] + 0.0013 if 0 <= u <= 1 and 0 <= v <= 1 else 0.944

    # Thin, flattened textile handles loop down onto the bag; they are not round cables.
    for i, dy in enumerate((0, 0.022)):
        _ribbon_on_points(
            h,
            "Shopping bag burgundy flattened handle %d" % i,
            [
                (0.06, 0.464 + dy, 0.965),
                (0.115, 0.536 + dy, 0.951),
                (0.252, 0.519 + dy, 0.949),
                (0.274, 0.451 + dy, 0.969),
                (0.173, 0.416 + dy, 0.975),
                (0.06, 0.464 + dy, 0.965),
            ],
            0.009,
            maroon,
            axis=(0, 1, 0),
            floor=bag_height,
        )
    dark_surface = _folded_packet(
        h,
        "Kitchen crushed dark plastic carrier bag",
        (0.29, 0.159, 0.94),
        (0.302, 0.199),
        darkfilm,
        height=0.125,
        phase=2.6,
        angle=0.06,
        support=bag_height,
    )
    _ribbon_on_points(
        h,
        "Dark bag folded loop handle",
        [
            dark_surface(0.14, 0.43),
            (0.18, 0.191, 1.050),
            (0.25, 0.186, 1.070),
            dark_surface(0.48, 0.59),
        ],
        0.017,
        darkfilm,
        axis=(0, 1, 0),
    )
    _crumpled_sheet(
        h,
        "Dark bag gathered upper mouth",
        (0.28, 0.138, 1.013),
        (0.136, 0.092),
        darkfilm,
        seed=1.1,
        lift=0.022,
        angle=0.26,
    )

    # Cotton cap: six stitched panels sag asymmetrically instead of a featureless ellipsoid.
    cx, cy, zbase = 0.505, 0.285, 0.944
    n, rows = 72, 30

    def crown(t, a):
        phi = (0.018 + t * 0.482) * math.pi
        radius = math.sin(phi)
        zz = zbase + 0.082 * math.cos(phi)
        zz -= 0.014 * math.exp(-(((a - 1.4) / 0.6) ** 2)) * math.sin(phi) ** 2
        zz += 0.002 * math.sin(a * 7 + t * 9) * math.sin(phi)
        return (cx + 0.073 * radius * math.cos(a), cy + 0.077 * radius * math.sin(a), zz)

    vv = [crown(i / rows, TAU * j / n) for i in range(rows + 1) for j in range(n)]
    ff = []
    for i in range(rows):
        for j in range(n):
            a, b = i * n + j, i * n + (j + 1) % n
            ff.append((a, a + n, b + n, b))
    ff.append(tuple(range(n)))
    ob = h["mesh"]("Olive cap sagged six panel crown", vv, ff, olive)
    mod = ob.modifiers.new("Cap cotton thickness", "SOLIDIFY")
    mod.thickness = 0.0012
    for j in range(6):
        h["tube"](
            "Cap crown stitched panel seam",
            [crown(i / 70, TAU * j / 6) for i in range(71)],
            0.0004,
            h["ivory_fabric"],
        )
    h["E"](
        "Cap small fabric covered top button",
        (cx, cy, zbase + 0.083),
        (0.0045, 0.0045, 0.0022),
        olive,
    )

    def brim(u, v):
        xx = (u - 0.5) * 0.159
        arch = math.sqrt(max(0, 1 - (2 * u - 1) ** 2))
        yy = 0.014 + v * (0.033 + 0.080 * arch)
        return (
            cx + xx,
            cy + yy,
            zbase + 0.003 + 0.010 * (2 * u - 1) ** 2 - 0.002 * v + 0.0007 * math.sin(v * 9 + u * 6),
        )

    _grid(h, "Cap curved flattened visor", brim, olive, 64, 38, 0.0025)
    for v in (0.78, 0.9):
        h["tube"](
            "Cap visor parallel stitching",
            [brim(i / 96, v) for i in range(97)],
            0.00032,
            h["ivory_fabric"],
        )
    pouch = _folded_packet(
        h,
        "Kitchen flattened black zip pouch",
        (0.22, 0.567, 0.941),
        (0.161, 0.077),
        h["rubber"],
        height=0.021,
        phase=0.1,
        angle=-0.19,
    )
    path = [pouch(i / 80, 0.89) for i in range(81)]
    h["tube"]("Black pouch fine zipper", path, 0.00065, h["silver"])
    h["B"](
        "Black pouch zipper pull",
        (path[11][0], path[11][1], path[11][2] + 0.001),
        (0.007, 0.016, 0.002),
        h["silver"],
        0.001,
    )


def sink_toiletries(h):
    """Two small items occupying the alcove side ledges, clear of the basin opening."""
    pale_blue = h["material"]("pale blue toiletries carton", (0.42, 0.57, 0.68), 0.74)
    darkblue = h["material"]("small toiletries ink blue", (0.028, 0.06, 0.15), 0.74)

    def world(x, y, z):
        # Sink's local-to-room transform: (-1.72,.56,0), -90 degrees about Z.
        return (-1.72 + y, 0.56 - x, z)

    h["B"](
        "Sink small blue carton",
        world(0.343, 0.158, 0.929),
        (0.101, 0.061, 0.050),
        pale_blue,
        0.0013,
    )
    h["B"](
        "Sink carton white folded top",
        world(0.343, 0.158, 0.955),
        (0.102, 0.062, 0.002),
        h["paper"],
        0.0006,
    )
    h["tube"](
        "Sink carton folded lid seam",
        [world(0.315, 0.158, 0.9563), world(0.372, 0.158, 0.9563)],
        0.00035,
        pale_blue,
    )
    h["text"](
        "Sink carton neutral lettering",
        "CARE",
        world(0.367, 0.171, 0.9568),
        0.009,
        darkblue,
        right=(0, 1, 0),
        up=(-1, 0, 0),
    )
    # The existing soap and toothpaste are provided by the architectural builder.
    # This extra soft squeeze tube is placed behind the toothpaste on the other ledge.
    center = world(-0.343, -0.166, 0.9034)
    tube_surface = _folded_packet(
        h,
        "Sink small flattened cream tube",
        center,
        (0.106, 0.036),
        h["paper"],
        height=0.020,
        phase=1.4,
        angle=-0.10,
    )
    for v in (0.17, 0.26):
        h["tube"](
            "Cream tube printed navy stripe",
            [tube_surface(i / 80, v) for i in range(16, 67)],
            0.0015,
            darkblue,
        )
    h["C"](
        "Cream tube short screw cap",
        (center[0] + 0.058, center[1], 0.914),
        0.010,
        0.015,
        h["paper"],
        (0, math.pi / 2, 0),
    )
    h["tube"](
        "Cream tube crimped tail",
        [tube_surface(0.015, i / 32) for i in range(33)],
        0.0013,
        pale_blue,
    )
    # A loosely folded wrapper tucked beside the tube, present in the reference.
    _crumpled_sheet(
        h,
        "Sink opened cream paper wrapper",
        world(-0.366, -0.050, 0.934),
        (0.058, 0.044),
        h["ivory_fabric"],
        seed=3.1,
        lift=0.005,
        angle=0.4,
    )


def desktop_wrappers(h):
    """A phone carton on the canvas tote and two small creased foil wrappers."""
    carton = (1.366, 1.164, 0.833)
    h["B"]("Desk white handset carton base", carton, (0.163, 0.083, 0.034), h["paper"], 0.0015)
    h["B"](
        "Desk handset carton fitted lid",
        (carton[0], carton[1], 0.852),
        (0.164, 0.084, 0.008),
        h["tissue"],
        0.0013,
    )
    sage = h["material"]("neutral handset carton sage graphic", (0.34, 0.40, 0.28), 0.68)
    h["B"](
        "Desk carton printed handset silhouette",
        (1.366, 1.164, 0.8566),
        (0.131, 0.065, 0.0005),
        sage,
        0.009,
    )
    for xx in (1.411, 1.390):
        h["C"]("Desk carton printed lens graphic", (xx, 1.183, 0.8571), 0.008, 0.0004, h["keymat"])
    foil = h["material"]("creased silver wrapper laminate", (0.54, 0.57, 0.55), 0.36, metallic=0.50)
    surface = _folded_packet(
        h,
        "Desk small torn foil packet on crisps",
        (1.095, 1.219, 0.867),
        (0.086, 0.056),
        foil,
        height=0.014,
        phase=3.2,
        angle=0.45,
    )
    for v in (0.035, 0.10):
        h["tube"](
            "Foil packet pressed crimp",
            [surface(i / 70, v) for i in range(71)],
            0.0005,
            h["silver"],
        )
    _crumpled_sheet(
        h,
        "Desk narrow white snack wrapper",
        (1.129, 1.525, 0.781),
        (0.095, 0.036),
        h["paper"],
        seed=2.7,
        lift=0.006,
        angle=-0.14,
    )
