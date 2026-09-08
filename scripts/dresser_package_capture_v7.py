"""Photo-informed wet-wipe and snack volumes in the calibrated dresser frame.

Run after layout_v3 in final room coordinates. Only the two old package groups
are replaced. Their photograph texture retains some illumination; it is not a
measured albedo. The room, backpack, cable, camera and lights are untouched.
"""

from pathlib import Path
import hashlib
import json
import math

import bpy
from mathutils import Vector

VERSION = "7.0.0"
PREFIX = "DresserPackagesV7_"
OLD_PREFIXES = ("Turquoise wipes", "Wipes ", "Small yellow snack", "Yellow packet")
SUPPORT_Z = 0.7412
PARAMETERS = {
    "wipes": {
        "center": (-1.11204923, 2.79110666),
        "yaw": 1.482736024,
        "length": 0.167497625,
        "width": 0.109821994,
        "top": 0.777,
    },
    "snack": {
        "center": (-1.000055946, 2.995346368),
        "yaw": 1.508682854,
        "length": 0.190547842,
        "width": 0.107662709,
        "top": 0.750,
    },
}


def _mat(name, directory):
    mat = bpy.data.materials.new(PREFIX + name + " estimated film")
    mat.use_nodes = True
    mat.diffuse_color = (0.28, 0.51, 0.58, 1) if name == "wipes" else (0.48, 0.48, 0.025, 1)
    bs = mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Roughness"].default_value = 0.60 if name == "wipes" else 0.57
    bs.inputs["Metallic"].default_value = 0.0
    bs.inputs["Specular IOR Level"].default_value = 0.14
    mat["appearance_mode"] = (
        "Estimated fixed-lighting photo-derived color; residual captured shading, not measured reflectance."
    )
    for filename, color in (
        (f"{name}-estimated-basecolor.png", True),
        (f"{name}-pressure-normal.png", False),
    ):
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(path)
        image = bpy.data.images.load(str(path), check_existing=True)
        image.colorspace_settings.name = "sRGB" if color else "Non-Color"
        image.pack()
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        node.extension = "EXTEND"
        if color:
            mat.node_tree.links.new(node.outputs["Color"], bs.inputs["Base Color"])
        else:
            normal = mat.node_tree.nodes.new("ShaderNodeNormalMap")
            normal.inputs["Strength"].default_value = 0.40
            mat.node_tree.links.new(node.outputs["Color"], normal.inputs["Color"])
            mat.node_tree.links.new(normal.outputs["Normal"], bs.inputs["Normal"])
    return mat


def _point(name, u, v, bottom=False):
    p = PARAMETERS[name]
    a = Vector((math.cos(p["yaw"]), math.sin(p["yaw"]), 0))
    b = Vector((a.y, -a.x, 0))
    # Gentle cut corners and unequal tuck-in near the pressed ends.
    s, t = 2 * u - 1, 2 * v - 1
    contraction = 1 - 0.040 * abs(s) ** 12 * abs(t) ** 10
    width_scale = 1 - 0.065 * abs(s) ** 10
    loc = (
        Vector((*p["center"], 0))
        + a * (s * p["length"] * 0.5 * contraction)
        - b * (t * p["width"] * 0.5 * width_scale)
    )

    def g(cu, cv, su, sv):
        return math.exp(-(((u - cu) / su) ** 2) - ((v - cv) / sv) ** 2)

    if bottom:
        z = SUPPORT_Z + 0.00006 + 0.0005 * max(abs(s), abs(t)) ** 8
    elif name == "wipes":
        z = p["top"] - 0.0031 * abs(s) ** 8 - 0.0058 * abs(t) ** 10
        z -= 0.0021 * g(0.78, 0.69, 0.15, 0.22) + 0.0014 * g(0.28, 0.31, 0.14, 0.17)
        z += 0.0010 * g(0.41, 0.83, 0.2, 0.12)
        # A few shallow oblique end folds; not a periodic blanket wave.
        for cu, cv, slope, depth in (
            (0.08, 0.28, 1.5, -0.0013),
            (0.91, 0.70, -1.1, -0.0011),
            (0.09, 0.78, -0.8, 0.0009),
            (0.84, 0.1, 0.4, -0.0008),
        ):
            z += (
                depth
                * math.exp(-(((v - cv - slope * (u - cu)) / 0.045) ** 2))
                * math.exp(-(((u - cu) / 0.13) ** 4))
            )
    else:
        envelope = max(0, 1 - abs(s) ** 5) * max(0, 1 - abs(t) ** 6)
        z = SUPPORT_Z + 0.0014 + 0.0080 * envelope
        z -= 0.0038 * g(0.31, 0.42, 0.14, 0.20) + 0.0024 * g(0.72, 0.74, 0.19, 0.14)
        z += 0.0018 * g(0.86, 0.14, 0.12, 0.15) + 0.0016 * g(0.11, 0.85, 0.09, 0.16)
        for cu, cv, slope, depth in (
            (0.23, 0.17, 0.95, -0.0012),
            (0.71, 0.40, -1.3, -0.0013),
            (0.49, 0.86, 0.4, -0.0011),
        ):
            z += (
                depth
                * math.exp(-(((v - cv - slope * (u - cu)) / 0.024) ** 2))
                * math.exp(-(((u - cu) / 0.20) ** 4))
                * envelope
            )
        z = max(SUPPORT_Z + 0.00075, z)
    loc.z = z
    return loc


def _mesh(name, vertices, faces, uvs, mat, collection):
    mesh = bpy.data.meshes.new(PREFIX + name)
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    ob = bpy.data.objects.new(mesh.name, mesh)
    collection.objects.link(ob)
    mesh.materials.append(mat)
    layer = mesh.uv_layers.new(name="UVMap")
    for polygon, values in zip(mesh.polygons, uvs):
        polygon.use_smooth = True
        for loop, uv in zip(polygon.loop_indices, values):
            layer.data[loop].uv = uv
    return ob


def _body(name, mat, collection):
    nu, nv = 81, 49
    vertices = [
        tuple(_point(name, i / (nu - 1), j / (nv - 1), bottom))
        for bottom in (False, True)
        for j in range(nv)
        for i in range(nu)
    ]
    faces, uvs = [], []
    offset = nu * nv
    for bottom in (False, True):
        for j in range(nv - 1):
            for i in range(nu - 1):
                k = j * nu + i + int(bottom) * offset
                ids = [k, k + 1, k + nu + 1, k + nu]
                coords = [
                    (i / (nu - 1), j / (nv - 1)),
                    ((i + 1) / (nu - 1), j / (nv - 1)),
                    ((i + 1) / (nu - 1), (j + 1) / (nv - 1)),
                    (i / (nu - 1), (j + 1) / (nv - 1)),
                ]
                if name == "wipes":
                    coords = [(u, 0.44921875 + 0.55078125 * v) for u, v in coords]
                if bottom:
                    ids.reverse()
                    coords = [(0.1, 0.025)] * 4
                faces.append(ids)
                uvs.append(coords)
    boundary = [
        *range(nu),
        *[j * nu + nu - 1 for j in range(1, nv)],
        *[((nv - 1) * nu + i) for i in range(nu - 2, -1, -1)],
        *[j * nu for j in range(nv - 2, 0, -1)],
    ]
    for i, a in enumerate(boundary):
        b = boundary[(i + 1) % len(boundary)]
        faces.append([a, a + offset, b + offset, b])
        if name == "wipes" and a < nu and b < nu:
            uvs.append(
                [
                    (a / (nu - 1), 0.41796875),
                    (a / (nu - 1), 0.099609375),
                    (b / (nu - 1), 0.099609375),
                    (b / (nu - 1), 0.41796875),
                ]
            )
        else:
            # Unobserved edges/underside intentionally have no invented wording.
            uvs.append([(0.08, 0.025)] * 4)
    return _mesh(name + " closed pillow body", vertices, faces, uvs, mat, collection)


def _seal(name, end, mat, collection):
    p = PARAMETERS[name]
    a = Vector((math.cos(p["yaw"]), math.sin(p["yaw"]), 0))
    vertices, faces, uvs = [], [], []
    nu, nv = 9, 65
    for j in range(nv):
        v = j / (nv - 1)
        for i in range(nu):
            t = i / (nu - 1)
            base = _point(name, 0 if end < 0 else 1, v)
            extension = (0.0060 if name == "wipes" else 0.0075) * t
            # Regular microscopic crimp ridges belong only to the heat seal.
            crimp = math.cos(2 * math.pi * v * 31) * (0.00016 if name == "wipes" else 0.00011)
            base += a * end * extension
            near = base.z
            far = (
                SUPPORT_Z
                + (0.010 if name == "wipes" else 0.0020)
                + 0.0012 * math.exp(-(((v - 0.21) / 0.15) ** 2))
            )
            base.z = near * (1 - t) + far * t + crimp * math.sin(math.pi * t)
            base.z += 0.00065 * t * max(0, math.sin(v * math.pi))
            vertices.append(tuple(base))
    for j in range(nv - 1):
        for i in range(nu - 1):
            k = j * nu + i
            ids = [k, k + 1, k + nu + 1, k + nu]
            if end < 0:
                ids.reverse()
            faces.append(ids)
            uvs.append(
                [(0.012 if end < 0 else 0.986, 0.44921875 + 0.55078125 * j / (nv - 1))] * 4
                if name == "wipes"
                else [(0.012 if end < 0 else 0.986, j / (nv - 1))] * 4
            )
    ob = _mesh(f"{name} {end:+d} pressed heat seal", vertices, faces, uvs, mat, collection)
    solid = ob.modifiers.new("laminate thickness", "SOLIDIFY")
    solid.thickness = 0.00022
    solid.offset = 0
    return ob


def _sticker(mat, collection):
    # Separate thin peel film follows the printed top and its shallow dents.
    nu, nv = 51, 31
    vertices, faces, uvs = [], [], []
    for j in range(nv):
        for i in range(nu):
            u = 0.155 + 0.68 * i / (nu - 1)
            v = 0.24 + 0.55 * j / (nv - 1)
            p = _point("wipes", u, v)
            p.z += 0.00027
            vertices.append(tuple(p))
    for j in range(nv - 1):
        for i in range(nu - 1):
            k = j * nu + i
            faces.append([k, k + 1, k + nu + 1, k + nu])
            coords = [
                (0.155 + 0.68 * a / (nu - 1), 0.24 + 0.55 * b / (nv - 1))
                for a, b in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1))
            ]
            uvs.append([(u, 0.44921875 + 0.55078125 * v) for u, v in coords])
    ob = _mesh("wipes thin reseal film", vertices, faces, uvs, mat, collection)
    solid = ob.modifiers.new("Peel sticker thickness", "SOLIDIFY")
    solid.thickness = 0.00016
    solid.offset = -1
    return ob


def refine_dresser_packages(M=None, texture_dir=None):
    scene = bpy.context.scene
    if scene.get("dresser_package_capture_v7") == VERSION:
        return json.loads(scene["dresser_package_capture_v7_audit"])
    for required in ("Turquoise wipes pack", "Small yellow snack packet"):
        if required not in bpy.data.objects:
            raise ValueError(f"Expected calibrated source object {required}")
    directory = (
        Path(texture_dir)
        if texture_dir
        else Path(__file__).resolve().parents[1] / "assets/textures/dresser_package_capture_v7"
    )
    mats = {name: _mat(name, directory) for name in PARAMETERS}
    removed = []
    for ob in list(scene.objects):
        if ob.name.startswith(OLD_PREFIXES):
            removed.append(ob.name)
            bpy.data.objects.remove(ob, do_unlink=True)
    collection = bpy.data.collections.new("Props / Dresser photographed packages v7")
    scene.collection.children.link(collection)
    objects = []
    for name in PARAMETERS:
        objects.append(_body(name, mats[name], collection))
        objects.extend(_seal(name, end, mats[name], collection) for end in (-1, 1))
    objects.append(_sticker(mats["wipes"], collection))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    bounds = {}
    for ob in objects:
        eval_ob = ob.evaluated_get(dg)
        mesh = eval_ob.to_mesh()
        points = [eval_ob.matrix_world @ v.co for v in mesh.vertices]
        bounds[ob.name] = {
            "min": [min(v[k] for v in points) for k in range(3)],
            "max": [max(v[k] for v in points) for k in range(3)],
        }
        eval_ob.to_mesh_clear()
    assert min(value["min"][2] for value in bounds.values()) >= SUPPORT_Z - 0.00005
    audit = {
        "version": VERSION,
        "removed_objects": removed,
        "new_objects": [o.name for o in objects],
        "parameters": PARAMETERS,
        "support_z": SUPPORT_Z,
        "evaluated_bounds": bounds,
        "source_reference": "11 for masked surface pixels and fitted top rectangles; registered10/14 cross-view checks",
        "placement_limit": "Soft corners marked by hand; top-plane assumptions and 1.5–11px rectangle residual, not measured metric accuracy.",
        "captured_vs_estimated": "Captured source layer retained separately. Actual shader reads estimated basecolor with residual photographed illumination.",
        "texture_hashes": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.glob("*estimated-basecolor.png"))
        },
    }
    scene["dresser_package_capture_v7"] = VERSION
    scene["dresser_package_capture_v7_audit"] = json.dumps(audit)
    return json.loads(scene["dresser_package_capture_v7_audit"])
