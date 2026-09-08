"""Authored VCT mineral chips at physical scale; deterministic portable maps.

The photographs show small dark and light chips, not perfectly uniform
cream surfaces. Size/coverage/reflectance are look-development estimates. No
reference image pixels are used. Blender's bundled NumPy is sufficient.
"""

import numpy as np
from materials_v2 import _packed_image, _srgb

PERIOD_M = 0.306627060635


def _fields(size=2048):
    rng = np.random.default_rng(521044)
    field = rng.normal(0, 1, (size, size))
    freq = np.fft.fftfreq(size)
    radial = freq[:, None] ** 2 + freq[None, :] ** 2
    field = np.fft.ifft2(np.fft.fft2(field) * np.exp(-2 * np.pi**2 * 8.0**2 * radial)).real
    field /= field.std()
    pigment = np.clip(1 + field * 0.15, 0.52, 1.48).astype(np.float32)
    # 0.9--2.5mm irregular aggregate survives the observed close-up scale.
    for k in range(12000):
        cx, cy = rng.integers(0, size, 2)
        radius = rng.uniform(3.0, 8.5) if k % 17 else rng.uniform(8.0, 11.0)
        aspect = rng.uniform(0.52, 1.0)
        angle = rng.uniform(0, 2 * np.pi)
        r = int(np.ceil(radius)) + 1
        yy, xx = np.mgrid[-r : r + 1, -r : r + 1]
        c, s = np.cos(angle), np.sin(angle)
        u = (c * xx + s * yy) / radius
        v = (-s * xx + c * yy) / (radius * aspect)
        theta = np.arctan2(v, u)
        shape = np.sqrt(u * u + v * v) / (
            1 + 0.13 * np.sin(5 * theta + k) + 0.09 * np.sin(3 * theta + 2 * k)
        )
        mask = np.clip((1 - shape) * 3.0, 0, 1)
        value = rng.uniform(0.12, 0.48) if k % 4 else rng.uniform(1.25, 1.65)
        iy = (cy + yy) % size
        ix = (cx + xx) % size
        pigment[iy, ix] = pigment[iy, ix] * (1 - mask) + value * mask
    pigment /= pigment.mean(dtype=np.float64)
    rough = np.clip(0.60 + (1 - pigment) * 0.07 + rng.normal(0, 0.006, pigment.shape), 0.53, 0.70)
    height = (pigment - 1) * 0.000025
    pixel = PERIOD_M / size
    dx = (np.roll(height, -1, axis=1) - np.roll(height, 1, axis=1)) / (2 * pixel)
    dy = (np.roll(height, -1, axis=0) - np.roll(height, 1, axis=0)) / (2 * pixel)
    normal = np.stack((-dx, -dy, np.ones_like(height)), axis=2)
    normal /= np.linalg.norm(normal, axis=2, keepdims=True)
    return pigment, rough, normal * 0.5 + 0.5


def refine_vinyl_material(materials):
    pigment, rough, normal = _fields()
    common_rough = _packed_image(
        "VCT V4 mineral chip roughness.png",
        np.repeat(rough[:, :, None], 3, axis=2),
        "Non-Color",
        "Authored seeded mineral chips / vinyl_material_v4.py",
    )
    common_normal = _packed_image(
        "VCT V4 smooth resilient tile normal.png",
        normal,
        "Non-Color",
        "Authored microscopic relief / vinyl_material_v4.py",
    )
    updated = []
    for key, base in (("tilecream", (0.49, 0.48, 0.435)), ("tilegray", (0.32, 0.303, 0.287))):
        mat = materials[key]
        mat.use_nodes = True
        mat.diffuse_color = (*base, 1)
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        bs = nodes.new("ShaderNodeBsdfPrincipled")
        bs.name = "Principled BSDF"
        bs.inputs["Base Color"].default_value = (*base, 1)
        bs.inputs["Roughness"].default_value = 0.60
        bs.inputs["Specular IOR Level"].default_value = 0.26
        out = nodes.new("ShaderNodeOutputMaterial")
        links.new(bs.outputs["BSDF"], out.inputs["Surface"])
        color = _packed_image(
            f"VCT V4 {key} mineral pigment.png",
            _srgb(pigment[:, :, None] * np.array(base)),
            "sRGB",
            "Original authored mineral pigment / vinyl_material_v4.py",
        )
        uv = nodes.new("ShaderNodeTexCoord")
        for label, im in (
            ("Colour", color),
            ("Roughness", common_rough),
            ("Normal", common_normal),
        ):
            tex = nodes.new("ShaderNodeTexImage")
            tex.name = "VCT / " + label
            tex.image = im
            links.new(uv.outputs["UV"], tex.inputs["Vector"])
            if label == "Colour":
                links.new(tex.outputs["Color"], bs.inputs["Base Color"])
            elif label == "Roughness":
                channel = nodes.new("ShaderNodeSeparateColor")
                links.new(tex.outputs["Color"], channel.inputs["Color"])
                links.new(channel.outputs["Green"], bs.inputs["Roughness"])
            else:
                nm = nodes.new("ShaderNodeNormalMap")
                nm.inputs["Strength"].default_value = 0.30
                links.new(tex.outputs["Color"], nm.inputs["Color"])
                links.new(nm.outputs["Normal"], bs.inputs["Normal"])
        mat["vinyl_material_v4"] = "authored mineral chip pigment and smooth resilient finish"
        mat["texture_period_m"] = PERIOD_M
        updated.append(mat.name)
    return {
        "materials": updated,
        "texture_period_m": PERIOD_M,
        "resolution": 2048,
        "provenance": "Seeded project-authored texture, no photograph pixels",
        "limits": "Chip sizes and surface reflectance remain visual estimates",
    }
