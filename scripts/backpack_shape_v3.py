"""Shape-only backpack refinement in the final calibrated world coordinates.

Call ``refine_backpack_shape(M)`` AFTER dresser layout AND the 0.894 uniform
Backpack* correction from pivot (-1.27, 2.8, .738) to (-1.271, 2.8618, .741).
No save, render, external asset, or change to another prop occurs here.

The smooth spatial warp is shared by shell, compartments, seam curves, zipper
chains, pulls, and webbing. Each compartment and its trims also share a height
compression; its rear hems are then attached to the actual parent fabric.
The small woven identity patch is explicitly fitted to four-view observations.
"""

from __future__ import annotations

import math
from functools import partial

VERSION = "3.0.0"
MARKER = "backpack_shape_version"
FLOOR = 0.741
HEIGHT = 0.380
OLD_LABEL = (-1.106709, 2.8618, 0.8754755)
LABEL_CENTER = (-1.187230, 2.856749, 0.907756)
LABEL_NORMAL = (0.939581166, -0.102769828, 0.326535750)
LABEL_RIGHT = (0.029460519, 0.974575963, 0.221970261)
LABEL_WIDTH = 0.0595
LABEL_HEIGHT = 0.027
LABEL_SURFACE_LIFT = 0.00065
BODY_NAME = "Backpack continuous shaped nylon shell"
PATCH_NAME = "Backpack fabric identity patch"
TEXT_NAME = "Backpack neutral woven label"


def _smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def _middle_weight(z):
    # The centre is slightly above the label, giving the shallow front panel
    # an upward-facing normal instead of making a vertical flat plastic slab.
    centre = OLD_LABEL[2] + 0.025
    gaussian = math.exp(-(((z - centre) / 0.105) ** 2))
    gaussian /= math.exp(-(((OLD_LABEL[2] - centre) / 0.105) ** 2))
    bottom = _smooth((z - FLOOR) / 0.095)
    return gaussian * bottom


def _world_warp(point):
    """Continuous low-frequency cloth-volume deformation; metres, Z up."""
    x, y, z = point
    w = _middle_weight(z)
    crown = _smooth((z - 1.015) / 0.105)
    dy = y - OLD_LABEL[1]
    # Compress the depth of the overinflated compartments without collapsing
    # their thickness. X derivative stays positive throughout the bag.
    depth_scale = 1.0 - 0.40 * w
    nx = OLD_LABEL[0] + (x - OLD_LABEL[0]) * depth_scale
    nx += (LABEL_CENTER[0] - OLD_LABEL[0]) * w + 0.043 * crown
    nx += 0.030 * dy * w
    ny = y + (LABEL_CENTER[1] - OLD_LABEL[1]) * w + 0.042 * crown
    # Keep the base planted while lifting the sagged compartment/label height.
    nz = z + (LABEL_CENTER[2] - OLD_LABEL[2]) * w
    nz += 0.230 * dy * w
    # Broad tension wrinkles remain millimetric and vanish at the fitted label.
    edge = min(1.0, (dy / 0.15) ** 2)
    nx += 0.0022 * math.sin(dy * 85 + (z - FLOOR) * 38) * math.sin((z - FLOOR) * 29) * w * edge
    nz += 0.0010 * math.sin(dy * 92 + z * 41) * w * edge
    return (nx, ny, nz)


def _handle_warp(point):
    """Fold the standing carry loop down/back along the actual crown."""
    p = list(_world_warp(point))
    amount = _smooth((point[2] - 1.095) / 0.078)
    p[0] -= 0.026 * amount
    p[2] -= 0.035 * amount
    return tuple(p)


def _pocket_warp(point, height_scale, center_height=0.0):
    """Shorten the sewn compartment along its cloth plane, not global Z.

    The old front pocket reached the pack's bottom cuff. In the references it
    ends above that separate cuff. Using the local up axis preserves the fitted
    front normal and makes zipper/binding paths follow the same new silhouette.
    """
    p = _world_warp(point)
    n, r = LABEL_NORMAL, LABEL_RIGHT
    up = (n[1] * r[2] - n[2] * r[1], n[2] * r[0] - n[0] * r[2], n[0] * r[1] - n[1] * r[0])
    length = math.sqrt(sum(v * v for v in up))
    up = tuple(v / length for v in up)
    amount = sum((p[i] - LABEL_CENTER[i]) * up[i] for i in range(3)) - center_height
    p = tuple(p[i] + up[i] * amount * (height_scale - 1) for i in range(3))
    # A sewn pocket has a round lower bowl, not a rectangular plate extending
    # to the bottom cuff. Preserve its fitted label while drawing up the hem.
    u = sum((p[i] - LABEL_CENTER[i]) * r[i] for i in range(3))
    v = sum((p[i] - LABEL_CENTER[i]) * up[i] for i in range(3))
    depth = sum((p[i] - LABEL_CENTER[i]) * n[i] for i in range(3))
    front = height_scale < 0.8
    lower = _smooth((-v - 0.010) / 0.060)
    nv = v * (1.0 - (0.35 if front else 0.12) * lower)
    rounding = _smooth((-v - 0.025) / 0.065)
    nu = u * (1.0 - (0.17 if front else 0.08) * rounding)
    nv += (0.010 if front else 0.005) * min(1.0, abs(u / 0.135) ** 6) * rounding
    nd = depth * (0.55 if front else 0.72)
    textile_edge = min(1.0, abs(u / 0.14) ** 2)
    nd += 0.0018 * math.sin(u * 78 + v * 62) * textile_edge
    return tuple(p[i] + r[i] * (nu - u) + up[i] * (nv - v) + n[i] * (nd - depth) for i in range(3))


def _smooth_crown_material_boundary(body):
    """Align an actual vertex ring with the cream/blue sewn panel boundary."""
    sides, rings, boundary_row = 64, 48, 38
    if len(body.data.vertices) != sides * (rings + 1):
        raise RuntimeError("Backpack crown refinement expects the original 64 × 48 shell grid")
    if body.data.users > 1:
        body.data = body.data.copy()
    old = [v.co.copy() for v in body.data.vertices]
    mapped_t = []
    for i in range(rings + 1):
        for j in range(sides):
            border = 0.735 + 0.11 * abs(math.sin(math.tau * j / sides))
            t = (
                i / boundary_row * border
                if i <= boundary_row
                else border + (i - boundary_row) / (rings - boundary_row) * (1 - border)
            )
            f = t * rings
            lo = min(rings - 1, int(f))
            factor = f - lo
            body.data.vertices[i * sides + j].co = old[lo * sides + j].lerp(
                old[(lo + 1) * sides + j], factor
            )
            mapped_t.append(t)
    for p in body.data.polygons:
        p.material_index = (
            int(p.index // sides >= boundary_row)
            if p.index < rings * sides
            else int(p.index == rings * sides + 1)
        )
    if body.data.uv_layers.active:
        uv = body.data.uv_layers.active.data
        for loop in body.data.loops:
            uv[loop.index].uv.y = mapped_t[loop.vertex_index]
    body.data.update()


def _deform(obj, fn):
    from mathutils import Vector

    if obj.data.users > 1:
        obj.data = obj.data.copy()
    world = obj.matrix_world.copy()
    inverse = world.inverted()

    def moved(co):
        return inverse @ Vector(fn(world @ Vector(co)))

    if obj.type == "MESH":
        for vertex in obj.data.vertices:
            vertex.co = moved(vertex.co)
        obj.data.update()
    elif obj.type == "CURVE":
        for spline in obj.data.splines:
            if spline.type == "BEZIER":
                for p in spline.bezier_points:
                    co, left, right = p.co.copy(), p.handle_left.copy(), p.handle_right.copy()
                    p.co = moved(co)
                    p.handle_left = moved(left)
                    p.handle_right = moved(right)
            else:
                for p in spline.points:
                    p.co = (*moved(p.co[:3]), p.co[3])
    else:
        raise RuntimeError(f"Unexpected backpack geometry type: {obj.name} / {obj.type}")


def _fit_identity_patch(patch, text):
    import bpy
    from mathutils import Matrix, Vector
    from mathutils.bvhtree import BVHTree

    normal = Vector(LABEL_NORMAL).normalized()
    right = Vector(LABEL_RIGHT)
    right = (right - normal * right.dot(normal)).normalized()
    up = normal.cross(right).normalized()
    # The source pocket is softly curved. A submillimetre mounting clearance
    # keeps every front corner visible without flattening the cloth beneath it.
    center = Vector(LABEL_CENTER) + normal * LABEL_SURFACE_LIFT
    # The patch itself is textile. Conform its outermost corners to the curved
    # compartment instead of forcing a rigid rectangle through the nylon.
    bpy.context.view_layer.update()
    panel = bpy.data.objects["Backpack front pocket sewn front panel"]
    evaluated = panel.evaluated_get(bpy.context.evaluated_depsgraph_get())
    panel_mesh = evaluated.to_mesh()
    tree = BVHTree.FromPolygons(
        [evaluated.matrix_world @ v.co for v in panel_mesh.vertices],
        [list(p.vertices) for p in panel_mesh.polygons],
        all_triangles=False,
    )
    evaluated.to_mesh_clear()
    nx, ny = 12, 6
    corners, faces = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            p = (
                center
                + right * ((i / nx - 0.5) * LABEL_WIDTH)
                + up * ((j / ny - 0.5) * LABEL_HEIGHT)
            )
            hit, _, _, _ = tree.ray_cast(p + normal * 0.008, -normal, 0.018)
            if hit is not None:
                p += normal * max(0.0, (hit - p).dot(normal) + 0.00045)
            corners.append(tuple(p))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
    material = patch.data.materials[0]
    previous = patch.data
    mesh = bpy.data.meshes.new(PATCH_NAME + " v3 fitted cloth mesh")
    mesh.from_pydata(corners, [], faces)
    mesh.materials.append(material)
    uv = mesh.uv_layers.new(name="UVMap")
    for polygon in mesh.polygons:
        for loop_index in polygon.loop_indices:
            j, i = divmod(mesh.loops[loop_index].vertex_index, nx + 1)
            uv.data[loop_index].uv = (i / nx, j / ny)
    mesh.update()
    patch.data = mesh
    patch.matrix_world = Matrix.Identity(4)
    patch.modifiers.clear()
    solidify = patch.modifiers.new("Woven label thickness", "SOLIDIFY")
    solidify.thickness = 0.00040
    solidify.offset = -1
    if previous.users == 0:
        bpy.data.meshes.remove(previous)
    patch["reference_label_center_xyz"] = list(LABEL_CENTER)
    patch["surface_clearance_m"] = LABEL_SURFACE_LIFT
    patch["reference_label_size_m"] = [LABEL_WIDTH, LABEL_HEIGHT]
    if text:
        if text.data.users > 1:
            text.data = text.data.copy()
        text.data.body = "TRAVEL"
        text.data.align_x = "CENTER"
        text.data.align_y = "CENTER"
        text.data.size = 0.0105
        text.matrix_world = Matrix(((*right, 0), (*up, 0), (*normal, 0), (0, 0, 0, 1))).transposed()
        text.matrix_world.translation = center + normal * 0.00072


def _attach_gusset_rear_edges():
    """Bury compartment rear hems in the parent fabric, eliminating old gaps."""
    import bpy
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree

    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    trees = {}
    for name in (BODY_NAME, "Backpack middle compartment sewn front panel"):
        ob = bpy.data.objects[name].evaluated_get(dg)
        mesh = ob.to_mesh()
        trees[name] = BVHTree.FromPolygons(
            [ob.matrix_world @ v.co for v in mesh.vertices],
            [list(p.vertices) for p in mesh.polygons],
            all_triangles=False,
        )
        ob.to_mesh_clear()
    for name, parent in (
        ("Backpack middle compartment joined fabric gussets", BODY_NAME),
        (
            "Backpack front pocket joined fabric gussets",
            "Backpack middle compartment sewn front panel",
        ),
    ):
        ob = bpy.data.objects[name]
        inverse = ob.matrix_world.inverted()
        count = len(ob.data.vertices) // 2
        fallbacks = 0
        for i in range(count):
            front = ob.matrix_world @ ob.data.vertices[i].co
            p = ob.matrix_world @ ob.data.vertices[i + count].co
            tree = trees[parent]
            point, normal, _, _ = tree.ray_cast(p + Vector((0.12, 0, 0)), Vector((-1, 0, 0)), 0.40)
            if point is None and parent != BODY_NAME:
                fallbacks += 1
                tree = trees[BODY_NAME]
                point, normal, _, _ = tree.ray_cast(
                    p + Vector((0.12, 0, 0)), Vector((-1, 0, 0)), 0.40
                )
            if point is None:
                point, normal, _, _ = tree.find_nearest(p)
            if point is None:
                raise RuntimeError("Cannot attach backpack gusset rear edge to parent cloth")
            buried = point - normal * 0.0012
            # If a hem already overlaps the parent, do not invert its side wall
            # by pulling its back edge ahead of the corresponding front edge.
            buried.x = min(buried.x, front.x - 0.001)
            ob.data.vertices[i + count].co = inverse @ buried
        ob.data.update()
        ob["rear_hem_attachment"] = "Parent fabric surface, 1.2 mm embedded"
        ob["rear_hem_body_fallbacks"] = fallbacks


def _refine_zipper_trims():
    """Flat narrow fabric tapes with fine dark teeth, rather than white tubes."""
    import bpy
    from mathutils import Vector

    def material(name, color, roughness, metallic=0.0):
        mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes.get("Principled BSDF")
        bsdf.inputs["Base Color"].default_value = (*color, 1)
        bsdf.inputs["Roughness"].default_value = roughness
        bsdf.inputs["Metallic"].default_value = metallic
        return mat

    tape_mat = material("Backpack V3 / narrow cream woven zipper tape", (0.51, 0.49, 0.39), 0.87)
    teeth_mat = material(
        "Backpack V3 / dark nickel zipper teeth", (0.045, 0.051, 0.058), 0.48, 0.65
    )
    binding_mat = material("Backpack V3 / blue-grey sewn binding", (0.135, 0.162, 0.219), 0.86)
    normal = Vector(LABEL_NORMAL).normalized()
    for ob in list(bpy.data.objects):
        if not ob.name.startswith("Backpack"):
            continue
        if "cream zip tape" in ob.name:
            spline = ob.data.splines[0]
            source = spline.bezier_points if spline.type == "BEZIER" else spline.points
            points = [ob.matrix_world @ Vector(p.co[:3]) for p in source]
            vertices, faces = [], []
            for i, p in enumerate(points):
                tangent = points[min(i + 1, len(points) - 1)] - points[max(i - 1, 0)]
                side = normal.cross(tangent).normalized()
                for sign in (-1, 1):
                    vertices.append(tuple(p + side * (sign * 0.00155) + normal * 0.00015))
            for i in range(len(points) - 1):
                a = i * 2
                faces.append((a, a + 2, a + 3, a + 1))
            name, groups = ob.name, list(ob.users_collection)
            mesh = bpy.data.meshes.new(name + " flat woven ribbon")
            mesh.from_pydata(vertices, [], faces)
            mesh.materials.append(tape_mat)
            mesh.update()
            uv = mesh.uv_layers.new(name="UVMap")
            for loop in mesh.loops:
                i, side = divmod(loop.vertex_index, 2)
                uv.data[loop.index].uv = (i / max(1, len(points) - 1), side)
            replacement = bpy.data.objects.new(name + " temporary", mesh)
            for group in groups:
                group.objects.link(replacement)
            for key in ob.keys():
                replacement[key] = ob[key]
            bpy.data.objects.remove(ob, do_unlink=True)
            replacement.name = name
            thick = replacement.modifiers.new("Thin woven zipper tape", "SOLIDIFY")
            thick.thickness = 0.00035
            thick.offset = -1
        elif "metal zip chain" in ob.name or "narrow zipper pull" in ob.name:
            ob.data.materials.clear()
            ob.data.materials.append(teeth_mat)
            if ob.type == "CURVE":
                scale = ob.matrix_world.to_scale().length / math.sqrt(3)
                ob.data.bevel_depth = 0.00030 / scale
        elif "perimeter binding" in ob.name:
            ob.data.materials.clear()
            ob.data.materials.append(binding_mat)
            if ob.type == "CURVE":
                scale = ob.matrix_world.to_scale().length / math.sqrt(3)
                ob.data.bevel_depth = 0.00065 / scale


def refine_backpack_shape(M=None):
    """Refine only Backpack* geometry after its final layout/scale transform.

    Returns a small manifest. Idempotent for this module version. A precondition
    prevents accidental use in old construction coordinates or before scaling.
    """
    import bpy
    from mathutils import Vector

    objects = [o for o in bpy.data.objects if o.name.startswith("Backpack")]
    body = bpy.data.objects.get(BODY_NAME)
    patch = bpy.data.objects.get(PATCH_NAME)
    if body is None or patch is None:
        raise RuntimeError(
            "Backpack shape refinement requires the original shell and identity patch"
        )
    if body.get(MARKER) == VERSION:
        return {"version": VERSION, "changed": [], "already_applied": True}
    before_patch = sum((patch.matrix_world @ v.co for v in patch.data.vertices), Vector()) / len(
        patch.data.vertices
    )
    if (before_patch - Vector(OLD_LABEL)).length > 0.004:
        raise RuntimeError(
            "Backpack shape refinement must follow the calibrated .894 scale/pivot correction"
        )
    _smooth_crown_material_boundary(body)
    changed = []
    for obj in objects:
        if obj.name in (PATCH_NAME, TEXT_NAME):
            continue
        if obj.name.startswith("Backpack front pocket"):
            fn = partial(_pocket_warp, height_scale=0.72)
        elif obj.name.startswith("Backpack middle compartment"):
            fn = partial(_pocket_warp, height_scale=0.90, center_height=0.035)
        else:
            fn = _handle_warp if "carry handle" in obj.name else _world_warp
        _deform(obj, fn)
        changed.append(obj.name)
    _attach_gusset_rear_edges()
    _refine_zipper_trims()
    _fit_identity_patch(patch, bpy.data.objects.get(TEXT_NAME))
    for name in (PATCH_NAME, TEXT_NAME):
        ob = bpy.data.objects.get(name)
        if ob:
            changed.append(name)
    for name in changed:
        bpy.data.objects[name][MARKER] = VERSION
    body["shape_note"] = "Shared smooth shell/pocket warp fitted to four calibrated reference views"
    bpy.context.view_layer.update()
    return {
        "version": VERSION,
        "changed": changed,
        "already_applied": False,
        "reference_label_center": LABEL_CENTER,
        "label_surface_lift_m": LABEL_SURFACE_LIFT,
        "label_size": (LABEL_WIDTH, LABEL_HEIGHT),
        "label_normal": LABEL_NORMAL,
    }
