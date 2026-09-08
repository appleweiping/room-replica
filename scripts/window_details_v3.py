"""Curved, thin painted aluminium blind strips in the calibrated window.

The source assembly supplies each strip's pose and width. This replaces only
its local mesh, retaining the ladder spacing and the reference camera fit.
Dimensions are authored estimates of ordinary 25 mm Venetian blind stock.
"""

import math
import bpy
from mathutils import Matrix
from calibration import CALIBRATION


def refine_blinds():
    for obj in list(bpy.data.objects):
        if not obj.name.startswith("Blind_Slat_") or obj.type != "MESH":
            continue
        old = obj.data
        width, depth = 1.231, 0.025
        bpy.context.view_layer.update()
        world_width = width * obj.matrix_world.to_3x3().col[0].length
        centre = obj.matrix_world.translation.copy()
        nx, ny = 12, 16
        count = (nx + 1) * (ny + 1)
        vertices, faces = [], []
        for lower in (False, True):
            for j in range(ny + 1):
                v = j / ny
                for i in range(nx + 1):
                    u = i / nx
                    crown = 0.0025 * (1 - (2 * v - 1) ** 2)
                    sag = -0.00065 * math.sin(math.pi * u)
                    vertices.append(
                        (
                            (u - 0.5) * width,
                            (v - 0.5) * depth,
                            crown + sag - (0.00024 if lower else 0),
                        )
                    )
        for j in range(ny):
            for i in range(nx):
                a = j * (nx + 1) + i
                q = (a, a + 1, a + nx + 2, a + nx + 1)
                faces.append(q)
                faces.append(tuple(k + count for k in reversed(q)))
        perimeter = list(range(nx + 1))
        perimeter += [j * (nx + 1) + nx for j in range(1, ny + 1)]
        perimeter += [ny * (nx + 1) + i for i in range(nx - 1, -1, -1)]
        perimeter += [j * (nx + 1) for j in range(ny - 1, 0, -1)]
        for a, b in zip(perimeter, perimeter[1:] + perimeter[:1]):
            faces.append((a, a + count, b + count, b))
        data = bpy.data.meshes.new(obj.name + " / formed aluminium")
        data.from_pydata(vertices, [], faces)
        data.update()
        for material in old.materials:
            data.materials.append(material)
        for polygon in data.polygons:
            polygon.use_smooth = polygon.index < nx * ny * 2
        obj.data = data
        obj.modifiers.clear()
        # Room-side edges point upward: the photographed blind blocks sky in
        # its upper half while the lower leaves admit a narrow blue daylight gap.
        tilt = CALIBRATION["window"].get("blind_tilt_degrees", 64.0)
        obj.matrix_world = (
            Matrix.Translation(centre)
            @ Matrix.Rotation(math.radians(-tilt), 4, "X")
            @ Matrix.Diagonal((world_width / width, 1.0, 1.0, 1.0))
        )
        obj["physical_strip_width_m"] = world_width
        obj["physical_strip_depth_m"] = depth
        obj["physical_strip_tilt_degrees"] = tilt
        obj["construction"] = "25 mm curved aluminium strip, 0.24 mm stock; estimated"
        if old.users == 0:
            bpy.data.meshes.remove(old)
