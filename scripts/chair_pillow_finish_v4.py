"""Independent surface finish for the already calibrated chair_pillow_v4.

AI-assisted flat print is connected directly to Principled Base Color.  Authored
normal and metallic/roughness PNGs keep the material usable in glTF; no color
ramp is required by the runtime.  No room image is generated or altered here.
"""

import math
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

import chair_pillow_v4 as shape


ROOT = Path(__file__).resolve().parents[1]
TEXTURES = ROOT / "assets" / "textures"
ALBEDO = TEXTURES / "pillowcase_damask_art_v4.png"
NORMAL = TEXTURES / "pillowcase_satin_normal_v4.png"
MR = TEXTURES / "pillowcase_satin_mr_v4.png"
REVISION = "chair_pillow_finish_v4_1"


def _save_data_image(name, path, rgb):
    height, width = rgb.shape[:2]
    rgba = np.ones((height, width, 4), dtype=np.float32)
    rgba[:, :, :3] = rgb
    image = bpy.data.images.new(name, width=width, height=height, alpha=False)
    image.colorspace_settings.name = "Non-Color"
    image.pixels.foreach_set(rgba.ravel())
    image.filepath_raw = str(path)
    image.file_format = "PNG"
    image.save()
    bpy.data.images.remove(image)


def _ensure_surface_maps():
    """Deterministic numerical textile micro-surface, not a modified photograph."""
    if NORMAL.is_file() and MR.is_file():
        return
    h, w = 1536, 1024
    rng = np.random.default_rng(521941)
    spectrum = np.fft.rfft2(rng.normal(size=(h, w)))
    fy, fx = np.fft.fftfreq(h)[:, None], np.fft.rfftfreq(w)[None, :]

    def field(sx, sy, angle):
        c, s = math.cos(angle), math.sin(angle)
        x, y = fx * c + fy * s, -fx * s + fy * c
        kernel = np.exp(-2 * math.pi**2 * (sx * sx * x * x + sy * sy * y * y))
        out = np.fft.irfft2(spectrum * kernel, s=(h, w)).real
        return (out - out.mean()) / max(1e-10, out.std())

    fine = field(0.8, 3.7, 0.03)
    soft = field(7.0, 29.0, 0.21)
    broad = field(22.0, 63.0, -0.16)
    height = 0.000009 * fine + 0.00011 * soft + 0.000042 * broad
    # UV physical dimensions approximate the draped sheet's unfolded metrics.
    dv, du = np.gradient(height, 0.67 / h, 0.464 / w)
    normals = np.stack((-du, -dv, np.ones_like(du)), axis=-1)
    normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
    roughness = np.clip(0.395 + 0.040 * broad + 0.018 * soft + 0.012 * fine, 0.29, 0.53)
    mr = np.stack((np.ones_like(roughness), roughness, np.zeros_like(roughness)), axis=-1)
    TEXTURES.mkdir(parents=True, exist_ok=True)
    _save_data_image("Pillowcase v4 / authored tangent normal", NORMAL, normals * 0.5 + 0.5)
    _save_data_image("Pillowcase v4 / authored metallic roughness", MR, mr)


def _load_image(path, color_space):
    image = bpy.data.images.load(str(path), check_existing=True)
    image.colorspace_settings.name = color_space
    image.pack()
    return image


def _material():
    if not ALBEDO.is_file():
        raise FileNotFoundError(f"Missing AI-assisted pillowcase print: {ALBEDO}")
    _ensure_surface_maps()
    mat = bpy.data.materials.new("Pillowcase v4 / grey rose printed satin / direct PBR")
    mat.use_nodes = True
    n, links = mat.node_tree.nodes, mat.node_tree.links
    n.clear()
    out = n.new("ShaderNodeOutputMaterial")
    shader = n.new("ShaderNodeBsdfPrincipled")
    shader.inputs["IOR"].default_value = 1.46
    shader.inputs["Roughness"].default_value = 0.395
    shader.inputs["Metallic"].default_value = 0.0
    shader.inputs["Anisotropic"].default_value = 0.18
    shader.inputs["Anisotropic Rotation"].default_value = 0.0
    # Blender 4.5's exporter gates sheen by Weight but exports Tint directly,
    # without multiplying the weight.  Encode its modest strength in Tint so
    # the native and glTF material do not diverge into a white velvet layer.
    shader.inputs["Sheen Weight"].default_value = 1.0
    shader.inputs["Sheen Tint"].default_value = (0.17, 0.15, 0.145, 1.0)
    shader.inputs["Sheen Roughness"].default_value = 0.38
    links.new(shader.outputs["BSDF"], out.inputs["Surface"])
    uv = n.new("ShaderNodeTexCoord")
    for tag, path, space in [
        ("albedo", ALBEDO, "sRGB"),
        ("normal", NORMAL, "Non-Color"),
        ("metallic roughness", MR, "Non-Color"),
    ]:
        tex = n.new("ShaderNodeTexImage")
        tex.label = tag
        tex.name = f"Pillowcase {tag} / direct export image"
        tex.image = _load_image(path, space)
        tex.interpolation = "Linear"
        tex.extension = "EXTEND"
        links.new(uv.outputs["UV"], tex.inputs["Vector"])
        if tag == "albedo":
            links.new(tex.outputs["Color"], shader.inputs["Base Color"])
        elif tag == "normal":
            node = n.new("ShaderNodeNormalMap")
            node.inputs["Strength"].default_value = 0.72
            links.new(tex.outputs["Color"], node.inputs["Color"])
            links.new(node.outputs["Normal"], shader.inputs["Normal"])
        else:
            node = n.new("ShaderNodeSeparateColor")
            node.mode = "RGB"
            links.new(tex.outputs["Color"], node.inputs["Color"])
            links.new(node.outputs["Green"], shader.inputs["Roughness"])
            links.new(node.outputs["Blue"], shader.inputs["Metallic"])
    mat["provenance"] = (
        "Albedo is AI-generated from a reference photo, not a scan; the normal and roughness maps are generated by this script. See docs/AI_TEXTURES.md"
    )
    return mat


def _edge_weight(u, v):
    x = min(1.0, max(0.0, min(u, 1 - u, v, 1 - v) / 0.065))
    return x * x * (3 - 2 * x)


def _crease_field(u, v):
    # Sparse nonrepeating curved tension folds.  Each has its own extent, width
    # and asymmetry; no regular sine/wave texture drives the new fine finish.
    curves = [
        (0.14, 0.27, 0.030, 0.0040, 0.19, 0.42, -0.36),
        (0.32, 0.48, 0.022, -0.0032, 0.24, -0.20, 0.42),
        (0.47, 0.35, 0.017, 0.0037, 0.18, 0.31, -0.12),
        (0.64, 0.58, 0.026, -0.0039, 0.21, -0.32, -0.27),
        (0.82, 0.31, 0.021, 0.0032, 0.25, 0.12, 0.30),
        (0.26, 0.82, 0.031, 0.0026, 0.14, -0.19, 0.09),
        (0.69, 0.86, 0.020, -0.0021, 0.13, 0.22, -0.17),
    ]
    value = 0.0
    for center, middle, width, amp, length, slope, bow in curves:
        dv = v - middle
        path = center + slope * dv + bow * dv * dv
        q = (u - path) / width
        envelope = math.exp(-((dv / length) ** 4))
        value += (
            amp
            * (math.exp(-0.5 * (q - 0.55) ** 2) - 0.67 * math.exp(-0.5 * (q + 0.95) ** 2))
            * envelope
        )
    return max(-0.0045, min(0.0045, value))


def refine_chair_pillow_finish(M=None):
    """Finish v4 only, keeping its perimeter, thickness modifier and support pose."""
    body = bpy.data.objects.get(shape.BODY)
    if not body or body.get("shape_revision") != shape.VERSION:
        raise RuntimeError(
            "chair_pillow_finish_v4 requires the stable chair_pillow_v4 geometry first"
        )
    if body.get("finish_revision") == REVISION:
        return {"revision": REVISION, "already_applied": True}
    material = _material()
    body.data.materials.clear()
    body.data.materials.append(material)
    uv = body.data.uv_layers.active
    values = {}
    for loop in body.data.loops:
        values.setdefault(loop.vertex_index, tuple(uv.data[loop.index].uv))
    max_displacement = 0.0
    for vertex in body.data.vertices:
        u, v = values[vertex.index]
        weight = _edge_weight(u, v)
        # Suppress the strongest regular long ridges inherited from the v4
        # candidate, while leaving all boundary vertices and hem paths fixed.
        regular = math.exp(-(((v - 0.39) / 0.28) ** 4)) * (
            0.0045 * math.sin(29 * u + 5 * v)
            + 0.0022 * math.sin(53 * u - 8 * v)
            + 0.0065 * math.sin(13 * u - 8 * v + 0.7) * math.sin(math.pi * u)
        )
        delta = weight * (_crease_field(u, v) - 0.66 * regular)
        delta = max(-0.0048, min(0.0048, delta))
        # The displacement direction is tangential to the room floor.  It does
        # not change the calibrated cloth height or thickness weights.
        vertex.co += shape.ROT @ Vector((delta, 0, 0))
        max_displacement = max(max_displacement, abs(delta))
    body.data.update()

    black = bpy.data.materials.new("Chair v4 / black powder-coated back support")
    black.use_nodes = True
    shader = black.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (0.010, 0.012, 0.014, 1)
    shader.inputs["Metallic"].default_value = 0.10
    shader.inputs["Roughness"].default_value = 0.39
    supports = []
    for ob in bpy.data.objects:
        if ob.name.startswith("Chair back supporting tube"):
            ob.data.materials.clear()
            ob.data.materials.append(black)
            supports.append(ob.name)
    body["finish_revision"] = REVISION
    body["albedo_is_scan"] = False
    bpy.context.view_layer.update()
    return {
        "revision": REVISION,
        "max_base_displacement_m": max_displacement,
        "boundary_fixed": True,
        "thickness_modifier_unchanged": True,
        "black_back_supports": supports,
        "new_objects": 0,
        "albedo_image": str(ALBEDO.relative_to(ROOT)),
        "normal_image": str(NORMAL.relative_to(ROOT)),
        "metallic_roughness_image": str(MR.relative_to(ROOT)),
    }
