"""Reference-informed raised centre panels for the existing oak cabinet frames.

These are authored joinery profiles, not a manufacturer's measured section.
Run after layout and before final wood UVs. Cabinet placement is preserved.
"""

import bpy
from mathutils import Vector


PREFIXES = ("Upper_Left_door", "Upper_Right_door", "Kitchen_Base door", "Sink_Base_door")


def refine_cabinet_profiles():
    fields = [
        o
        for o in bpy.data.objects
        if o.name.startswith(PREFIXES) and "field" in o.name and o.type == "MESH"
    ]
    for part in bpy.data.objects:
        if (
            not part.name.startswith(PREFIXES)
            or part.type != "MESH"
            or part.get("cabinet_frame_v4")
        ):
            continue
        stile, rail = " stile" in part.name, " rail" in part.name
        if not (stile or rail):
            continue
        owner = min(
            fields,
            key=lambda f: (f.matrix_world.translation - part.matrix_world.translation).length,
        )
        relative = owner.matrix_world.inverted() @ part.matrix_world.translation
        axis = 0 if stile else 2
        old_width, new_width = (0.056, 0.040) if stile else (0.062, 0.045)
        for vertex in part.data.vertices:
            vertex.co[axis] *= new_width / old_width
        movement = [0.0, 0.0, 0.0]
        movement[axis] = (1 if relative[axis] > 0 else -1) * (old_width - new_width) / 2
        part.matrix_world.translation = part.matrix_world @ Vector(movement)
        part["cabinet_frame_v4"] = True
    count = 0
    for obj in list(bpy.data.objects):
        if not obj.name.startswith(PREFIXES):
            continue
        if "inner molding" in obj.name:
            bpy.data.objects.remove(obj, do_unlink=True)
            continue
        if "field" not in obj.name or obj.type != "MESH" or obj.get("cabinet_profile_v4"):
            continue
        old = obj.data
        xs = [v.co.x for v in old.vertices]
        zs = [v.co.z for v in old.vertices]
        w, h = max(xs) - min(xs) + 0.030, max(zs) - min(zs) + 0.030
        # y is local front depth relative to the old field's centre. The outer
        # tongue nests beneath stiles; a wide sloping panel rises toward centre.
        profile = [(0, 0.006), (0.010, 0.009), (0.013, 0.012), (0.030, 0.030), (0.032, 0.035)]
        vertices, faces = [], []
        for inset, depth in profile:
            a, b = w / 2 - inset, h / 2 - inset
            if min(a, b) <= 0:
                raise ValueError(f"Cabinet field too small for profile: {obj.name}")
            vertices.extend([(-a, depth, -b), (a, depth, -b), (a, depth, b), (-a, depth, b)])
        for ring in range(len(profile) - 1):
            a, b = 4 * ring, 4 * (ring + 1)
            for i in range(4):
                j = (i + 1) % 4
                faces.append((a + i, b + i, b + j, a + j))
        faces.append(tuple(4 * (len(profile) - 1) + i for i in (3, 2, 1, 0)))
        back = len(vertices)
        vertices.extend(
            [
                (-w / 2, -0.016, -h / 2),
                (w / 2, -0.016, -h / 2),
                (w / 2, -0.016, h / 2),
                (-w / 2, -0.016, h / 2),
            ]
        )
        faces.append(tuple(back + i for i in range(4)))
        for i in range(4):
            j = (i + 1) % 4
            faces.append((i, j, back + j, back + i))
        data = bpy.data.meshes.new(obj.name + " / raised profile")
        data.from_pydata(vertices, [], faces)
        data.update()
        for mat in old.materials:
            data.materials.append(mat)
        layer = data.uv_layers.new(name="UVMap")
        for face in data.polygons:
            # The visible sloped panel is one continuous vertically grained
            # board. Only its thin back edges receive separate end-grain charts.
            if abs(face.normal.y) > 0.01:
                axes = (2, 0)
            elif abs(face.normal.x) > 0.5:
                axes = (2, 1)
            else:
                axes = (1, 0)
            for index in face.loop_indices:
                point = data.vertices[data.loops[index].vertex_index].co
                layer.data[index].uv = (point[axes[0]] / 1.15, point[axes[1]] / 0.72)
        obj.data = data
        if old.users == 0:
            bpy.data.meshes.remove(old)
        for modifier in list(obj.modifiers):
            obj.modifiers.remove(modifier)
        bevel = obj.modifiers.new("Worn lacquer edge / submillimetre radius", "BEVEL")
        bevel.width = 0.0008
        bevel.segments = 3
        obj.modifiers.new("Manufactured panel face normals", "WEIGHTED_NORMAL")
        if "wood_uv_v3_face_axes" in obj:
            del obj["wood_uv_v3_face_axes"]
        obj["cabinet_profile_v4"] = True
        obj["profile_status"] = (
            "Photo-informed broad raised-panel slope; depth is authored estimate"
        )
        count += 1
    return {
        "raised_fields": count,
        "slope_width_m": 0.017,
        "centre_lift_m": 0.026,
        "stile_width_m": 0.040,
        "rail_width_m": 0.045,
    }
