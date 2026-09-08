"""Physical-scale carpet look development from an attributed CC0 fibre scan.

The source is a different carpet; neutralising its brown dye does not make it
a scan of this room. Reference-16 look development retained authored stripes
and fine scan relief after rejecting the unscaled, coarse full-scan appearance.
"""

import hashlib
from pathlib import Path

import bpy
import numpy as np

from materials_v2 import _linear, _load_image, _new, _packed_image, _pixels, _srgb, _texture


SOURCE_PERIOD_M = 0.60
PERIOD_M = 0.18
TILE_PERIOD_M = 0.50
PIGMENT_MEAN = np.array((0.065, 0.068, 0.073))


def _lowpass(values, sigma):
    """Periodic Gaussian in the frequency domain; only NumPy is required."""
    h, w = values.shape
    fy = np.fft.fftfreq(h)[:, None]
    fx = np.fft.rfftfreq(w)[None, :]
    kernel = np.exp(-2 * np.pi**2 * sigma**2 * (fx**2 + fy**2))
    return np.fft.irfft2(np.fft.rfft2(values) * kernel, s=values.shape)


def _sample_repeat(values, size, repeats=1.0):
    """Resample in the texture's periodic coordinate system, not display space."""
    h, w = values.shape[:2]
    xx = (np.arange(size) + 0.5) * w * repeats / size - 0.5
    yy = (np.arange(size) + 0.5) * h * repeats / size - 0.5
    x0, y0 = np.floor(xx).astype(int), np.floor(yy).astype(int)
    fx, fy = (xx - x0)[None, :], (yy - y0)[:, None]
    if values.ndim == 3:
        fx, fy = fx[:, :, None], fy[:, :, None]
    a = values[y0[:, None] % h, x0[None, :] % w]
    b = values[y0[:, None] % h, (x0[None, :] + 1) % w]
    c = values[(y0[:, None] + 1) % h, x0[None, :] % w]
    d = values[(y0[:, None] + 1) % h, (x0[None, :] + 1) % w]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def refine_carpet_material(material, texture_dir):
    """Replace a single carpet shader and map every tile in physical metres.

    World scale along each tile's own axes preserves alternating installation
    direction, including clipped perimeter tiles. No object positions change.
    """
    source = Path(texture_dir)
    diffuse = source / "dirty_carpet_diff_2k.jpg"
    rough = source / "dirty_carpet_rough_2k.jpg"
    normal = source / "dirty_carpet_nor_gl_2k.jpg"
    for path in (diffuse, rough, normal):
        if not path.is_file():
            raise FileNotFoundError(path)
    previous = material.node_tree.nodes.get("Carpet / neutral fibre albedo")
    if previous is None:
        raise ValueError("Run carpet v3 on the base directional carpet material")
    directional_albedo = previous.image
    rgb = _linear(_pixels(_load_image(diffuse, "sRGB"))[:, :, :3])
    luma = rgb @ np.array((0.2126, 0.7152, 0.0722))
    # Remove the source's broad brown bands and retained capture illumination.
    # Keep the registered millimetre-scale fibre contrast at restrained strength.
    base = _lowpass(luma, len(luma) * 0.025 / SOURCE_PERIOD_M)
    relative = np.maximum(luma / np.maximum(base, 1e-4), 0.05) ** 0.18
    relative /= np.mean(relative, dtype=np.float64)
    size = 2048
    tile_repeats = TILE_PERIOD_M / PERIOD_M
    fibre_pigment = _sample_repeat(relative, size, tile_repeats)
    stripe_rgb = _linear(_pixels(directional_albedo)[:, :, :3])
    stripe_luma = stripe_rgb @ np.array((0.2126, 0.7152, 0.0722))
    stripes = (stripe_luma / stripe_luma.mean()) ** 1.80
    composite = _sample_repeat(stripes, size) * fibre_pigment
    composite /= composite.mean()
    albedo = _packed_image(
        "CARPETV3 directional charcoal with captured fibres.png",
        _srgb(composite[:, :, None] * PIGMENT_MEAN),
        "sRGB",
        diffuse.name,
    )
    raw_rough = _pixels(_load_image(rough, "Non-Color"))[:, :, :3]
    roughness = _packed_image(
        "CARPETV3 registered matte fibre roughness.png",
        np.clip(0.72 + 0.27 * _sample_repeat(raw_rough, size, tile_repeats), 0.72, 0.99),
        "Non-Color",
        rough.name,
    )
    raw_normal = _pixels(_load_image(normal, "Non-Color"))[:, :, :3]
    tangent_normal = _sample_repeat(raw_normal, size, tile_repeats) * 2 - 1
    tangent_normal /= np.maximum(np.linalg.norm(tangent_normal, axis=2, keepdims=True), 1e-6)
    normal_image = _packed_image(
        "CARPETV3 registered tile tangent normal.png",
        tangent_normal * 0.5 + 0.5,
        "Non-Color",
        normal.name,
    )
    for image in (albedo, roughness, normal_image):
        image["license"] = "CC0-1.0 / Poly Haven / Dirty Carpet / Rohit Seervi"
        image["source_url"] = "https://polyhaven.com/a/dirty_carpet"
        image["source_scan_width_m"] = SOURCE_PERIOD_M
        image["authored_room_repeat_m"] = PERIOD_M
    nodes, links, bs = _new(material, tuple(PIGMENT_MEAN), 0.96)
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    color = _texture(nodes, links, albedo, uv.outputs["UV"], "Carpet / registered loop pigment")
    rough_tex = _texture(nodes, links, roughness, uv.outputs["UV"], "Carpet / fibre roughness")
    nor = _texture(nodes, links, normal_image, uv.outputs["UV"], "Carpet / captured loop normal")
    separate = nodes.new("ShaderNodeSeparateColor")
    links.new(rough_tex.outputs["Color"], separate.inputs["Color"])
    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.inputs["Strength"].default_value = 0.30
    normal_map.uv_map = "UVMap"
    links.new(nor.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], bs.inputs["Normal"])
    links.new(color.outputs["Color"], bs.inputs["Base Color"])
    links.new(separate.outputs["Green"], bs.inputs["Roughness"])
    bs.inputs["Sheen Weight"].default_value = 0.16
    # The node-tree rebuild otherwise restores default-white fibre sheen,
    # washing out charcoal tiles at the photographed grazing angles.
    bs.inputs["Sheen Tint"].default_value = (0.16, 0.17, 0.19, 1.0)
    bs.inputs["Sheen Roughness"].default_value = 0.85
    bs.inputs["Diffuse Roughness"].default_value = 0.55
    bs.inputs["Specular IOR Level"].default_value = 0.16
    count = 0
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or not obj.name.startswith("Floor_Carpet_"):
            continue
        layer = obj.data.uv_layers.get("UVMap") or obj.data.uv_layers.new(name="UVMap")
        extent = np.array([obj.matrix_world.col[i].to_3d().length for i in range(3)])
        digest = hashlib.sha256(obj.name.encode()).digest()
        phase = np.frombuffer(digest[:8], dtype="<u4") / 2**32
        for face in obj.data.polygons:
            axes = [i for i in range(3) if abs(face.normal[i]) < 0.5]
            for index in face.loop_indices:
                point = obj.data.vertices[obj.data.loops[index].vertex_index].co
                layer.data[index].uv = tuple(
                    point[axis] * extent[axis] / TILE_PERIOD_M + phase[j]
                    for j, axis in enumerate(axes)
                )
        count += 1
    material["carpet_profile"] = "3.0.1"
    return {
        "tiles": count,
        "period_m": PERIOD_M,
        "normal_strength": 0.30,
        "pigment_mean_linear": PIGMENT_MEAN.tolist(),
        "source": albedo["source_url"],
    }
