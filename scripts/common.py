"""Small deterministic, meter-based Blender modeling primitives."""

import bpy
import math
import hashlib
from mathutils import Vector

ACTIVE = None


def collection(name):
    global ACTIVE
    ACTIVE = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if ACTIVE.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(ACTIVE)
    return ACTIVE


def register(obj, name, mat=None):
    obj.name = name
    if ACTIVE:
        for c in list(obj.users_collection):
            c.objects.unlink(obj)
        ACTIVE.objects.link(obj)
    if mat:
        obj.data.materials.append(mat)
    return obj


def box(name, loc, dims, mat, bevel=0.005):
    # Construct data directly: thousands of small details should not force
    # operator context/dependency-graph updates individually.
    dx, dy, dz = (d / 2 for d in dims)
    vertices = [
        (-dx, -dy, -dz),
        (-dx, -dy, dz),
        (-dx, dy, -dz),
        (-dx, dy, dz),
        (dx, -dy, -dz),
        (dx, -dy, dz),
        (dx, dy, -dz),
        (dx, dy, dz),
    ]
    faces = [(0, 2, 6, 4), (1, 5, 7, 3), (0, 4, 5, 1), (2, 3, 7, 6), (0, 1, 3, 2), (4, 6, 7, 5)]
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    o = bpy.data.objects.new(name, data)
    (ACTIVE or bpy.context.scene.collection).objects.link(o)
    o.location = loc
    if mat:
        data.materials.append(mat)
    layer = data.uv_layers.new(name="UVMap")
    # Face-local square UVs for arbitrary image materials, including the caps.
    for p in data.polygons:
        for li, uv in zip(p.loop_indices, [(0, 0), (1, 0), (1, 1), (0, 1)]):
            layer.data[li].uv = uv
    if mat and "oak" in mat.name.lower():
        # Grain follows each manufactured part's long direction, at real scale.
        layer = o.data.uv_layers.active
        # Blender's resolved name distinguishes adjacent same-named components.
        # A stable hash avoids near-identical grain crops on consecutive doors.
        offset = int.from_bytes(hashlib.sha256(o.name.encode()).digest()[:4], "big") / 2**32
        for p in o.data.polygons:
            axes = [i for i in range(3) if abs(p.normal[i]) < 0.5]
            axes.sort(key=lambda i: dims[i], reverse=True)
            if "field" in name.lower() and 2 in axes:
                # Short raised-panel door inserts still use vertical grain;
                # their horizontal rails retain their own long-axis mapping.
                axes.remove(2)
                axes.insert(0, 2)
            for li in p.loop_indices:
                co = o.data.vertices[o.data.loops[li].vertex_index].co
                layer.data[li].uv = (co[axes[0]] / 1.15 + offset, co[axes[1]] / 0.72 + offset * 0.3)
    if bevel:
        b = o.modifiers.new("Manufactured edge radius", "BEVEL")
        b.width = bevel
        b.segments = 3
        b = o.modifiers.new("Corner normals", "WEIGHTED_NORMAL")
    return o


def uvball(name, loc, scale, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=20, location=loc)
    o = register(bpy.context.object, name, mat)
    o.scale = scale
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def cyl(name, loc, radius, depth, mat, rotation=None):
    count = 32
    vertices = []
    for z in (-depth / 2, depth / 2):
        for i in range(count):
            angle = 2 * math.pi * i / count
            vertices.append((radius * math.cos(angle), radius * math.sin(angle), z))
    faces = [(i, (i + 1) % count, (i + 1) % count + count, i + count) for i in range(count)]
    faces += [tuple(range(count - 1, -1, -1)), tuple(range(count, 2 * count))]
    data = bpy.data.meshes.new(name)
    data.from_pydata(vertices, [], faces)
    data.update()
    o = bpy.data.objects.new(name, data)
    (ACTIVE or bpy.context.scene.collection).objects.link(o)
    o.location = loc
    if mat:
        data.materials.append(mat)
    layer = data.uv_layers.new(name="UVMap")
    for p in data.polygons:
        if p.index < count:
            u = p.index / count
            for li, uv in zip(
                p.loop_indices, [(u, 0), (u + 1 / count, 0), (u + 1 / count, 1), (u, 1)]
            ):
                layer.data[li].uv = uv
        else:
            for li in p.loop_indices:
                co = data.vertices[data.loops[li].vertex_index].co
                layer.data[li].uv = (0.5 + 0.5 * co.x / radius, 0.5 + 0.5 * co.y / radius)
    if rotation:
        o.rotation_euler = rotation
    b = o.modifiers.new("Edge roll", "BEVEL")
    b.width = min(0.002, radius * 0.12)
    b.segments = 2
    o.modifiers.new("Corner normals", "WEIGHTED_NORMAL")
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def curve(name, points, radius, mat):
    dense = len(points) >= 32
    data = bpy.data.curves.new(name, "CURVE")
    data.dimensions = "3D"
    data.resolution_u = 1 if dense else 16
    data.bevel_depth = radius
    data.bevel_resolution = 2 if dense else 3
    if dense:
        s = data.splines.new("POLY")
        s.points.add(len(points) - 1)
        for p, co in zip(s.points, points):
            p.co = (*co, 1)
    else:
        s = data.splines.new("BEZIER")
        s.bezier_points.add(len(points) - 1)
        for p, co in zip(s.bezier_points, points):
            p.co = co
            p.handle_left_type = "AUTO"
            p.handle_right_type = "AUTO"
    o = bpy.data.objects.new(name, data)
    (ACTIVE or bpy.context.scene.collection).objects.link(o)
    if mat:
        data.materials.append(mat)
    return o


def mesh(name, verts, faces, mat, uvs=None, smooth=False):
    d = bpy.data.meshes.new(name)
    d.from_pydata(verts, [], faces)
    d.update()
    o = bpy.data.objects.new(name, d)
    (ACTIVE or bpy.context.scene.collection).objects.link(o)
    if mat:
        d.materials.append(mat)
    if uvs:
        layer = d.uv_layers.new(name="UVMap")
        for p in d.polygons:
            for li in p.loop_indices:
                layer.data[li].uv = uvs[d.loops[li].vertex_index]
    if smooth:
        for p in d.polygons:
            p.use_smooth = True
    return o


def material(name, color, rough=0.5, metal=0):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    m.use_nodes = True
    bs = m.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = (*color, 1)
    bs.inputs["Roughness"].default_value = rough
    bs.inputs["Metallic"].default_value = metal
    return m


def noise_bump(m, scale, strength, distance):
    n = m.node_tree.nodes
    links = m.node_tree.links
    bs = n.get("Principled BSDF")
    tex = n.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = 3
    bump = n.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = strength
    bump.inputs["Distance"].default_value = distance
    links.new(tex.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bs.inputs["Normal"])


def image_material(name, path, rough=0.75, scale=(1, 1, 1)):
    m = material(name, (0.65, 0.65, 0.65), rough)
    n = m.node_tree.nodes
    links = m.node_tree.links
    tex = n.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(path), check_existing=True)
    tex.interpolation = "Linear"
    tex.extension = "REPEAT"
    uv = n.new("ShaderNodeTexCoord")
    mapping = n.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = scale
    links.new(uv.outputs["UV"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
    links.new(tex.outputs["Color"], n.get("Principled BSDF").inputs["Base Color"])
    return m


def point_camera(name, loc, target, lens=24):
    d = bpy.data.cameras.new(name)
    o = bpy.data.objects.new(name, d)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - o.location).to_track_quat("-Z", "Y").to_euler()
    d.lens = lens
    d.clip_start = 0.025
    d.clip_end = 100
    return o


def area(name, loc, target, power, color, size, size_y=None):
    d = bpy.data.lights.new(name, "AREA")
    d.energy = power
    d.color = color
    if size_y:
        d.shape = "RECTANGLE"
        d.size = size
        d.size_y = size_y
    else:
        d.shape = "DISK"
        d.size = size
    o = bpy.data.objects.new(name, d)
    bpy.context.scene.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - o.location).to_track_quat("-Z", "Y").to_euler()
    return o
