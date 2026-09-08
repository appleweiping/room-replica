"""Photo-estimated resilient tile grid; keeps physical floor elevation fixed."""

import math
import bpy

DEFAULT = {
    "origin_xy_m": [-1.560157215594, 0.035363709932],
    "yaw_deg": -0.19114753258,
    "pitch_m": 0.306627060635,
    "joint_m": 0.0004,
    "top_m": 0.014,
}


def _clip(poly, axis, boundary, keep_above):
    output = []
    for a, b in zip(poly[-1:] + poly[:-1], poly):
        ina = (a[axis] >= boundary) if keep_above else (a[axis] <= boundary)
        inb = (b[axis] >= boundary) if keep_above else (b[axis] <= boundary)
        if ina != inb:
            t = (boundary - a[axis]) / (b[axis] - a[axis])
            output.append(tuple(a[k] + t * (b[k] - a[k]) for k in (0, 1)))
        if inb:
            output.append(b)
    return output


def refine_vinyl_layout(materials, room, parameters=None, gray_cells=None):
    cfg = {**DEFAULT, **(parameters or {})}
    existing = [o for o in bpy.data.objects if o.name.startswith("Floor_Vinyl_")]
    if not existing:
        raise ValueError("Expected the original vinyl floor grid")
    group = existing[0].users_collection[0]
    for ob in existing:
        bpy.data.objects.remove(ob, do_unlink=True)
    c, s = math.cos(math.radians(cfg["yaw_deg"])), math.sin(math.radians(cfg["yaw_deg"]))
    pitch = cfg["pitch_m"]
    joint = cfg["joint_m"]
    ox, oy = cfg["origin_xy_m"]
    low, high, front, back = room["left"], room["right"], 0, room["floor_transition_y"]
    # Find the cells in the rotated grid's own frame. A range based only on
    # room width misses cells when a calibrated origin lies outside the room.
    corners = [(x, y) for x in (low, high) for y in (front, back)]
    local = [(c * (x - ox) + s * (y - oy), -s * (x - ox) + c * (y - oy)) for x, y in corners]
    indices = [
        range(
            math.floor(min(p[k] for p in local) / pitch),
            math.ceil(max(p[k] for p in local) / pitch),
        )
        for k in (0, 1)
    ]
    count = 0
    areas = []
    for i in indices[0]:
        for j in indices[1]:
            xa, xb = i * pitch + joint / 2, (i + 1) * pitch - joint / 2
            ya, yb = j * pitch + joint / 2, (j + 1) * pitch - joint / 2
            polygon = [
                (ox + c * x - s * y, oy + s * x + c * y)
                for x, y in ((xa, ya), (xb, ya), (xb, yb), (xa, yb))
            ]
            for axis, boundary, above in (
                (0, low, True),
                (0, high, False),
                (1, front, True),
                (1, back, False),
            ):
                if polygon:
                    polygon = _clip(polygon, axis, boundary, above)
            if len(polygon) < 3:
                continue
            area = (
                abs(
                    sum(
                        a[0] * b[1] - b[0] * a[1]
                        for a, b in zip(polygon, polygon[1:] + polygon[:1])
                    )
                )
                / 2
            )
            if area < 1e-9:
                continue
            n = len(polygon)
            vertices = [(x, y, z) for z in (0, cfg["top_m"]) for x, y in polygon]
            faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
            faces += [(k, (k + 1) % n, (k + 1) % n + n, k + n) for k in range(n)]
            name = f"Floor_Vinyl_{i}_{j}"
            data = bpy.data.meshes.new(name)
            data.from_pydata(vertices, [], faces)
            data.update()
            ob = bpy.data.objects.new(name, data)
            group.objects.link(ob)
            gray = ((i + 3 * j) % 7 in (1, 4)) if gray_cells is None else [i, j] in gray_cells
            data.materials.append(materials["tilegray" if gray else "tilecream"])
            uv = data.uv_layers.new(name="UVMap")
            for face in data.polygons:
                for loop in face.loop_indices:
                    x, y, z = vertices[data.loops[loop].vertex_index]
                    uv.data[loop].uv = (
                        (c * (x - ox) + s * (y - oy)) / pitch,
                        (-s * (x - ox) + c * (y - oy)) / pitch,
                    )
            mod = ob.modifiers.new("Hairline tile edge", "BEVEL")
            mod.width = 0.00025
            mod.segments = 2
            # Clipping creates n-gons whose tangent frame the glTF exporter
            # cannot reliably compute before evaluated triangulation.
            ob.modifiers.new("Portable clipped-tile triangles", "TRIANGULATE")
            ob.modifiers.new("Flat surface normals", "WEIGHTED_NORMAL")
            ob["vinyl_layout_v4"] = True
            areas.append(area)
            count += 1
    return {
        "tiles": count,
        "surface_area_m2": sum(areas),
        "parameters": cfg,
        "status": "Photo-estimated grid, not surveyed; material choices require reference review",
    }
