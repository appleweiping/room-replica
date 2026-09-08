"""Material-only look development for the photographed room, Blender 4.5 LTS.

Call ``apply_material_upgrades(M, T)`` immediately after ``setup_materials()``.
The function preserves material identities, does not edit geometry, and never
saves a scene, renders, downloads, or writes an external texture. Derived wood,
mineral pigment and textile images are deterministic, packed in-memory images, rebuilt from the
existing licensed/authored inputs. Blender's bundled NumPy is sufficient.

The oak diffuse / roughness / normal graph uses glTF-compatible image nodes.
Fine procedural carpet, paint, laminate and metal relief is Cycles detail;
export retains calibrated image colors and constant roughness, not those noise graphs.
The measured-looking millimetre values below are authored hypotheses for look
development, not measurements recovered from the reference photographs.

Existing source provenance: assets/MATERIALS_V2_SOURCES.json (CC0 Oak Veneer 01)
and scripts/make_textures.py (authored carpet image). No photo projection is used.
Coordinate reference:
https://docs.blender.org/manual/en/4.5/render/shader_nodes/input/texture_coordinate.html
"""

from pathlib import Path

import bpy
import numpy as np


PROFILE_VERSION = "2.3.0"
# Calibrated against the r01 room, with its actual exposure and fixtures. The
# previous (0.69, 0.52, 0.33) was too bright and neutral in that setting.
OAK_STAIN = (0.52, 0.33, 0.105, 1.0)
OAK_UV_SCALE = (1.15 / 1.8, 0.72 / 1.8, 1.0)


def _linear(srgb):
    return np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)


def _srgb(linear):
    linear = np.maximum(linear, 0.0)
    return np.where(linear <= 0.0031308, linear * 12.92, 1.055 * linear ** (1 / 2.4) - 0.055)


def _load_image(path, color_space):
    image = bpy.data.images.load(str(path), check_existing=True)
    image.colorspace_settings.name = color_space
    return image


def _pixels(image):
    """Byte-backed input buffers expose encoded values, verified on Blender 4.5.

    np.mean(dtype=float64) avoids substantial float32 accumulation drift over
    four million texels. Explicit transfer functions keep contrast in linear
    light, then return an ordinary sRGB byte texture for portable export.
    """
    values = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(values)
    return values.reshape(image.size[1], image.size[0], 4)


def _packed_image(name, rgb, color_space, source):
    height, width = rgb.shape[:2]
    image = bpy.data.images.get(name)
    if image is None:
        image = bpy.data.images.new(
            name, width=width, height=height, alpha=False, float_buffer=False
        )
    elif tuple(image.size) != (width, height):
        image.scale(width, height)
    image.colorspace_settings.name = color_space
    rgba = np.ones((height, width, 4), dtype=np.float32)
    rgba[:, :, :3] = np.clip(rgb, 0.0, 1.0)
    image.pixels.foreach_set(rgba.ravel())
    image.update()
    image.pack()
    image["material_profile"] = PROFILE_VERSION
    image["source_asset"] = source
    image["derivation"] = "Deterministic material processing; no reference-photo pixels."
    return image


def _derived_images(texture_dir):
    diffuse_path = texture_dir / "oak_veneer_01_diff_2k.jpg"
    rough_path = texture_dir / "oak_veneer_01_rough_2k.jpg"
    normal_path = texture_dir / "oak_veneer_01_nor_gl_2k.jpg"
    carpet_path = texture_dir / "carpet_weave.png"
    # This photographed veneer has long, naturally continuous cathedral grain.
    # Its native grain is V-oriented. Rotate *all* maps into the common.box U
    # convention, rather than stretching red oak's short pore flecks into lines.
    raw = np.rot90(_pixels(_load_image(diffuse_path, "sRGB"))[:, :, :3], 1)
    linear = _linear(raw)
    mean = np.mean(linear, axis=(0, 1), dtype=np.float64)
    # A mild photographic contrast treatment suffices for this scan. Preserve
    # growth-ring shapes and use a fixed linear-light mean so the room exposure
    # calibration survives changing from the earlier pale Red Oak source.
    contrasted = np.power(np.maximum(linear / mean, 1e-4), 1.20)
    contrasted *= np.array((0.5444, 0.4090, 0.2851)) / np.mean(
        contrasted, axis=(0, 1), dtype=np.float64
    )
    oak = _packed_image(
        "MATV2 golden oak veneer albedo.png", _srgb(contrasted), "sRGB", diffuse_path.name
    )
    oak["license"] = "CC0-1.0 derivative of Poly Haven Oak Veneer 01"

    source_rough = np.rot90(_pixels(_load_image(rough_path, "Non-Color"))[:, :, :3], 1)
    # The scan's spatial variations survive under a restrained varnished finish.
    rough_values = np.clip(0.28 + source_rough * 0.28, 0.30, 0.53)
    roughness = _packed_image(
        "MATV2 golden oak finish roughness.png", rough_values, "Non-Color", rough_path.name
    )
    roughness["license"] = "CC0-1.0 derivative of Poly Haven Oak Veneer 01"
    source_normal = np.rot90(_pixels(_load_image(normal_path, "Non-Color"))[:, :, :3], 1)
    # For source (u,v)=(1-v_new,u_new), tangent XY transforms to (Y,-X).
    # Merely rotating the RGB image would leave grain relief lit from the wrong
    # direction. Z is unchanged; all three images stay registered.
    rotated_normal = np.stack(
        (source_normal[:, :, 1], 1 - source_normal[:, :, 0], source_normal[:, :, 2]), axis=2
    )
    normal = _packed_image(
        "MATV2 golden oak rotated normal.png", rotated_normal, "Non-Color", normal_path.name
    )
    normal["license"] = "CC0-1.0 derivative of Poly Haven Oak Veneer 01"

    source_carpet = _linear(_pixels(_load_image(carpet_path, "sRGB"))[:, :, :3])
    luminance = source_carpet @ np.array((0.2126, 0.7152, 0.0722), dtype=np.float32)
    mean_luma = np.mean(luminance, dtype=np.float64)
    relative = np.power(np.maximum(luminance / mean_luma, 0.1), 1.35)
    relative /= np.mean(relative, dtype=np.float64)
    carpet = _packed_image(
        "MATV2 neutral charcoal carpet albedo.png",
        _srgb(relative[:, :, None] * np.array((0.065, 0.068, 0.073))),
        "sRGB",
        carpet_path.name,
    )
    carpet["license"] = "Project-authored carpet texture derivative"
    # One portable fine particulate image serves the laminate and resilient tile
    # pigments. Relief remains a separate, much shallower native micro-normal.
    rng = np.random.default_rng(2519)
    grains = np.clip(rng.normal(0.82, 0.055, (2048, 2048)), 0.58, 0.98)
    dark_flecks = rng.random(grains.shape) < 0.014
    grains[dark_flecks] *= rng.uniform(0.23, 0.55, np.count_nonzero(dark_flecks))
    mineral = _packed_image(
        "MATV2 fine mineral particulate albedo.png",
        _srgb(np.repeat(grains[:, :, None], 3, axis=2)),
        "sRGB",
        "Original seeded procedural pigment / materials_v2.py",
    )
    mineral["license"] = "Project-authored procedural material image"
    return oak, roughness, normal, carpet, mineral


def _new(material, color, roughness, metallic=0.0):
    material.use_nodes = True
    material.diffuse_color = (*color, 1.0)
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    bs = nodes.new("ShaderNodeBsdfPrincipled")
    bs.name = "Principled BSDF"
    bs.location = (560, 120)
    bs.inputs["Base Color"].default_value = (*color, 1.0)
    bs.inputs["Roughness"].default_value = roughness
    bs.inputs["Metallic"].default_value = metallic
    out = nodes.new("ShaderNodeOutputMaterial")
    out.location = (860, 120)
    links.new(bs.outputs["BSDF"], out.inputs["Surface"])
    material["material_profile"] = PROFILE_VERSION
    return nodes, links, bs


def _coord(nodes, world=True):
    if world:
        node = nodes.new("ShaderNodeNewGeometry")
        node.label = "World position / metres"
        node.location = (-950, 120)
        return node.outputs["Position"]
    node = nodes.new("ShaderNodeTexCoord")
    node.label = "Local metre coordinates / apply object scale for correct yarn size"
    node.location = (-950, 120)
    return node.outputs["Object"]


def _noise(nodes, links, coord, scale, label, detail=2.0):
    node = nodes.new("ShaderNodeTexNoise")
    node.name = label
    node.label = label
    node.location = (-670, 140)
    node.inputs["Scale"].default_value = scale
    node.inputs["Detail"].default_value = detail
    node.inputs["Roughness"].default_value = 0.68
    links.new(coord, node.inputs["Vector"])
    return node


def _bump(nodes, links, height, strength, distance, label, normal=None):
    node = nodes.new("ShaderNodeBump")
    node.name = label
    node.label = label
    node.location = (220, -120)
    node.inputs["Strength"].default_value = strength
    node.inputs["Distance"].default_value = distance
    links.new(height, node.inputs["Height"])
    if normal is not None:
        links.new(normal, node.inputs["Normal"])
    return node.outputs["Normal"]


def _texture(nodes, links, image, uv, label):
    node = nodes.new("ShaderNodeTexImage")
    node.image = image
    node.name = label
    node.label = label
    node.interpolation = "Linear"
    node.extension = "REPEAT"
    links.new(uv, node.inputs["Vector"])
    return node


def _oak(material, albedo, roughness, normal_image):
    nodes, links, bs = _new(material, (0.34, 0.20, 0.095), 0.39)
    uv = nodes.new("ShaderNodeTexCoord")
    uv.location = (-950, 140)
    mapping = nodes.new("ShaderNodeMapping")
    mapping.name = "Oak / preserve 1.8 metre scan scale"
    mapping.inputs["Scale"].default_value = OAK_UV_SCALE
    links.new(uv.outputs["UV"], mapping.inputs["Vector"])
    mapped = mapping.outputs["Vector"]
    # The same socket drives all maps: grain, pore relief and finish vary together.
    color = _texture(nodes, links, albedo, mapped, "Oak / captured cathedral grain")
    color.location = (-690, 370)
    stain = nodes.new("ShaderNodeMix")
    stain.name = "Oak amber stain"
    stain.label = "Golden amber finish / room-exposure calibrated constant tint"
    stain.data_type = "RGBA"
    stain.blend_type = "MULTIPLY"
    stain.inputs[0].default_value = 1.0
    stain.inputs[7].default_value = OAK_STAIN
    stain.location = (100, 350)
    links.new(color.outputs["Color"], stain.inputs[6])
    links.new(stain.outputs[2], bs.inputs["Base Color"])
    rough = _texture(nodes, links, roughness, mapped, "Oak / varying finish roughness")
    rough.location = (-690, 30)
    separate = nodes.new("ShaderNodeSeparateColor")
    separate.mode = "RGB"
    links.new(rough.outputs["Color"], separate.inputs["Color"])
    links.new(separate.outputs["Green"], bs.inputs["Roughness"])
    normal = _texture(nodes, links, normal_image, mapped, "Oak / registered pore normal")
    normal.location = (-690, -330)
    normal_map = nodes.new("ShaderNodeNormalMap")
    normal_map.inputs["Strength"].default_value = 0.10
    normal_map.uv_map = "UVMap"
    links.new(normal.outputs["Color"], normal_map.inputs["Color"])
    links.new(normal_map.outputs["Normal"], bs.inputs["Normal"])
    bs.inputs["IOR"].default_value = 1.47
    bs.inputs["Coat Weight"].default_value = 0.045
    bs.inputs["Coat Roughness"].default_value = 0.40


def _carpet(material, albedo):
    nodes, links, bs = _new(material, (0.065, 0.068, 0.073), 0.96)
    uv = nodes.new("ShaderNodeTexCoord")
    image = _texture(nodes, links, albedo, uv.outputs["UV"], "Carpet / neutral fibre albedo")
    links.new(image.outputs["Color"], bs.inputs["Base Color"])
    local = _coord(nodes, world=False)
    stretch = nodes.new("ShaderNodeVectorMath")
    stretch.operation = "MULTIPLY"
    stretch.name = "Carpet yarn spacing / 5mm by 0.8mm stochastic bands"
    stretch.inputs[1].default_value = (200, 1250, 800)
    links.new(local, stretch.inputs[0])
    yarn = _noise(nodes, links, stretch.outputs["Vector"], 1, "Carpet / woven yarn ridges", 2.5)
    primary = _bump(nodes, links, yarn.outputs["Fac"], 0.65, 0.00065, "Carpet / 0.65mm yarn relief")
    micro = _noise(nodes, links, local, 2800, "Carpet / submillimetre fibre irregularity", 2.0)
    detail = _bump(
        nodes, links, micro.outputs["Fac"], 0.23, 0.00012, "Carpet / fine fibre normal", primary
    )
    links.new(detail, bs.inputs["Normal"])
    bs.inputs["Sheen Weight"].default_value = 0.12
    bs.inputs["Sheen Tint"].default_value = (0.16, 0.17, 0.19, 1.0)
    bs.inputs["Diffuse Roughness"].default_value = 0.55
    bs.inputs["Sheen Roughness"].default_value = 0.84
    bs.inputs["Specular IOR Level"].default_value = 0.16


def _mineral_color(nodes, links, bs, image, base):
    # A supported image multiplied by a constant gives glTF actual pigment.
    # Unsupported procedural Base Color links otherwise export as pure white.
    coord = nodes.new("ShaderNodeTexCoord")
    texture = _texture(nodes, links, image, coord.outputs["UV"], "Portable fine mineral pigment")
    tint = nodes.new("ShaderNodeMix")
    tint.data_type = "RGBA"
    tint.blend_type = "MULTIPLY"
    tint.inputs[0].default_value = 1.0
    tint.inputs[7].default_value = (*[min(c / 0.81, 1.0) for c in base], 1.0)
    links.new(texture.outputs["Color"], tint.inputs[6])
    links.new(tint.outputs[2], bs.inputs["Base Color"])


def _mineral_laminate(material, mineral, counter=False):
    base = (0.58, 0.57, 0.53) if counter else (0.45, 0.445, 0.42)
    nodes, links, bs = _new(material, base, 0.455 if counter else 0.515)
    _mineral_color(nodes, links, bs, mineral, base)
    coord = _coord(nodes)
    fine = _noise(nodes, links, coord, 1550, "Laminate / 0.6mm fine particulate", 2.4)
    relief = _bump(
        nodes, links, fine.outputs["Fac"], 0.21, 0.00008, "Laminate / 80 micron surface texture"
    )
    links.new(relief, bs.inputs["Normal"])
    bs.inputs["Coat Weight"].default_value = 0.035
    bs.inputs["Coat Roughness"].default_value = 0.42


def _paint(material, ceiling=False):
    nodes, links, bs = _new(
        material, (0.73, 0.72, 0.66) if ceiling else (0.70, 0.68, 0.595), 0.92 if ceiling else 0.84
    )
    coord = _coord(nodes)
    texture = _noise(
        nodes,
        links,
        coord,
        230 if ceiling else 380,
        "Ceiling / 4.3mm aggregate" if ceiling else "Wall / 2.6mm roller stipple",
        2.4,
    )
    # Noise Fac naturally occupies a narrow part of 0..1, so small bumps washed
    # out at room-camera distance. A smooth contrast ramp provides rounded
    # aggregate mounds with a restrained height range, not hard Voronoi cells.
    shape = nodes.new("ShaderNodeValToRGB")
    shape.name = "Paint / rounded aggregate profile"
    shape.color_ramp.interpolation = "EASE"
    shape.color_ramp.elements[0].position = 0.26 if ceiling else 0.28
    shape.color_ramp.elements[1].position = 0.72 if ceiling else 0.70
    links.new(texture.outputs["Fac"], shape.inputs["Fac"])
    bump = _bump(
        nodes,
        links,
        shape.outputs["Color"],
        0.68 if ceiling else 0.38,
        0.0030 if ceiling else 0.00055,
        "Paint / authored aggregate relief hypothesis",
    )
    micro = _noise(
        nodes, links, coord, 1350 if ceiling else 2100, "Paint / fine coating grain", 1.7
    )
    finish = _bump(
        nodes,
        links,
        micro.outputs["Fac"],
        0.22,
        0.00032 if ceiling else 0.00011,
        "Paint / secondary microscopic coating",
        bump,
    )
    links.new(finish, bs.inputs["Normal"])
    bs.inputs["Specular IOR Level"].default_value = 0.28


def _vinyl(material, base, mineral):
    nodes, links, bs = _new(material, base, 0.57)
    _mineral_color(nodes, links, bs, mineral, base)
    coord = _coord(nodes)
    fleck = _noise(nodes, links, coord, 1900, "Vinyl / fine mineral flecks", 2.7)
    normal = _bump(nodes, links, fleck.outputs["Fac"], 0.12, 0.00007, "Vinyl / 70 micron finish")
    links.new(normal, bs.inputs["Normal"])


def _manufactured(material, color, rough_range, metallic=0.0):
    nodes, links, bs = _new(material, color, sum(rough_range) / 2, metallic)
    coord = _coord(nodes)
    fine = _noise(nodes, links, coord, 3100, "Manufactured surface / fine roughness breakup", 1.5)
    # Keep the calibrated mean roughness directly on Principled. An arbitrary
    # Noise/MapRange connection is not portable and exports as roughness=1.
    # Fine native normal breakup still varies the highlight locally.
    normal = _bump(
        nodes,
        links,
        fine.outputs["Fac"],
        0.12,
        0.000022 if metallic else 0.00004,
        "Manufactured surface / microscopic relief",
    )
    links.new(normal, bs.inputs["Normal"])
    if metallic:
        bs.inputs["Anisotropic"].default_value = 0.18
    else:
        bs.inputs["IOR"].default_value = 1.46


def _textile_image(texture_dir, rose=False):
    reference = texture_dir / (
        "rose_cotton_reference_v3.png" if rose else "blue_floral_reference_v3.png"
    )
    if reference.exists():
        image = _load_image(reference, "sRGB")
        image.pack()
        image["provenance"] = (
            "AI-assisted flat print reconstruction from user-provided textile reference; see assets/TEXTILE_V3_SOURCES.json"
        )
        return image
    filename = "rose_cotton.png" if rose else "blue_floral_art.png"
    source = _pixels(_load_image(texture_dir / filename, "sRGB"))[:, :, :3]
    linear = _linear(source)
    if rose:
        # Darker red-pink ink; preserve the original cream cotton ground.
        red = np.clip((source[:, :, 0] - source[:, :, 1] - 0.06) / 0.16, 0, 1)
        red *= np.clip((source[:, :, 0] - source[:, :, 2] + 0.01) / 0.10, 0, 1)
        ink = linear * np.array((0.93, 0.76, 0.82))
        result = linear * (1 - red[:, :, None]) + ink * red[:, :, None]
        name = "MATV2 rose cotton richer ink.png"
    else:
        # Isolate the blue ground so pink petals and sage leaves retain their hue.
        blue = np.minimum(
            np.clip((source[:, :, 2] - source[:, :, 0] - 0.04) / 0.12, 0, 1),
            np.clip((source[:, :, 2] - source[:, :, 1] - 0.015) / 0.08, 0, 1),
        )
        samples = linear[blue > 0.80]
        if len(samples) < 100:
            raise ValueError("Blue textile ground could not be identified for calibration")
        ground = np.median(samples, axis=0)
        target = _linear(np.array((135, 170, 205), dtype=np.float32) / 255)
        blue_result = linear * target / np.maximum(ground, 1e-4)
        result = linear * (1 - blue[:, :, None]) + blue_result * blue[:, :, None]
        # Recover the printed motifs' muted detail without whitening highlights.
        luma = result @ np.array((0.2126, 0.7152, 0.0722), dtype=np.float32)
        saturated = luma[:, :, None] + (result - luma[:, :, None]) * 1.12
        result = result * blue[:, :, None] + saturated * (1 - blue[:, :, None])
        name = "MATV2 blue floral calibrated ground.png"
    image = _packed_image(name, _srgb(result), "sRGB", filename)
    image["license"] = (
        "Derivative of project-authored / AI-assisted input; see docs/fabric-generation.md"
    )
    return image


def _cotton(material, image, rose=False):
    base = (0.63, 0.57, 0.45) if rose else (0.24, 0.40, 0.61)
    nodes, links, bs = _new(material, base, 0.93 if rose else 0.91)
    coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (6.0, 2.875, 1) if rose else (1, 1, 1)
    mapping.name = (
        "Cotton print density / small roses" if rose else "Floral single swatch / no wrap seam"
    )
    links.new(coord.outputs["UV"], mapping.inputs["Vector"])
    texture = _texture(
        nodes, links, image, mapping.outputs["Vector"], "Cotton / portable printed albedo"
    )
    links.new(texture.outputs["Color"], bs.inputs["Base Color"])
    # UV-space fibre height follows the cloth's deformed parameterization.
    # Nominal bedding dimensions keep the weave submillimetre; small pillow
    # pieces sharing this shader will show a finer weave, which is a known limit.
    metre_uv = nodes.new("ShaderNodeVectorMath")
    metre_uv.operation = "MULTIPLY"
    metre_uv.inputs[1].default_value = (2.0, 1.1, 1.0)
    links.new(coord.outputs["UV"], metre_uv.inputs[0])
    wrinkles = _noise(
        nodes,
        links,
        metre_uv.outputs["Vector"],
        65,
        "Cotton / fine relaxed compression wrinkles",
        3.0,
    )
    profile = nodes.new("ShaderNodeValToRGB")
    profile.name = "Cotton / soft crease cross section"
    profile.color_ramp.interpolation = "EASE"
    profile.color_ramp.elements[0].position = 0.34
    profile.color_ramp.elements[1].position = 0.68
    links.new(wrinkles.outputs["Fac"], profile.inputs["Fac"])
    crease_normal = _bump(
        nodes,
        links,
        profile.outputs["Color"],
        0.37,
        0.0013 if rose else 0.0032,
        "Cotton / millimetre-scale compression creases",
    )
    fibre = _noise(
        nodes,
        links,
        metre_uv.outputs["Vector"],
        3600,
        "Cotton / approximately 0.28mm fine weave",
        2.0,
    )
    normal = _bump(
        nodes,
        links,
        fibre.outputs["Fac"],
        0.27,
        0.00013,
        "Cotton / 130 micron thread relief",
        crease_normal,
    )
    links.new(normal, bs.inputs["Normal"])
    bs.inputs["Diffuse Roughness"].default_value = 0.45
    bs.inputs["Specular IOR Level"].default_value = 0.20
    bs.inputs["Sheen Weight"].default_value = 0.08
    bs.inputs["Sheen Tint"].default_value = (*[c * 0.55 for c in base], 1.0)
    bs.inputs["Sheen Roughness"].default_value = 0.80


def apply_material_upgrades(M, texture_dir):
    """Upgrade common scene materials in place; return an integration report.

    ``M`` must be the mapping returned/populated by the existing base material
    setup. Prop-specific materials created later in props.py are deliberately
    outside this function's scope. The original texture files remain intact.
    Repeated calls replace the same node graphs and packed derived images.
    """
    texture_dir = Path(texture_dir).resolve()
    needed = (
        "oak_veneer_01_diff_2k.jpg",
        "oak_veneer_01_rough_2k.jpg",
        "oak_veneer_01_nor_gl_2k.jpg",
        "carpet_weave.png",
    )
    missing = [name for name in needed if not (texture_dir / name).is_file()]
    if missing:
        raise FileNotFoundError("Material v2 source textures missing: " + ", ".join(missing))
    required_keys = {
        "oak",
        "carpet",
        "laminate",
        "counter",
        "wall",
        "ceiling",
        "white",
        "black",
        "metal",
        "darkmetal",
        "tilecream",
        "tilegray",
        "taupe",
        "trim",
        "blinds",
    }
    missing_keys = required_keys - set(M)
    if missing_keys:
        raise KeyError(
            "Run setup_materials before materials_v2: " + ", ".join(sorted(missing_keys))
        )
    oak, roughness, normal, carpet, mineral = _derived_images(texture_dir)
    _oak(M["oak"], oak, roughness, normal)
    _carpet(M["carpet"], carpet)
    _mineral_laminate(M["laminate"], mineral)
    _mineral_laminate(M["counter"], mineral, counter=True)
    _paint(M["wall"])
    _paint(M["ceiling"], ceiling=True)
    for key, base in (
        ("tilecream", (0.49, 0.48, 0.435)),
        ("tilegray", (0.32, 0.315, 0.29)),
        ("taupe", (0.27, 0.265, 0.235)),
    ):
        _vinyl(M[key], base, mineral)
    for key, color, rough_range, metal in (
        ("white", (0.79, 0.80, 0.77), (0.34, 0.44), 0),
        ("black", (0.017, 0.019, 0.020), (0.38, 0.51), 0),
        ("trim", (0.020, 0.022, 0.021), (0.44, 0.55), 0),
        ("metal", (0.55, 0.57, 0.58), (0.23, 0.34), 1),
        ("darkmetal", (0.10, 0.105, 0.11), (0.31, 0.42), 1),
        ("blinds", (0.63, 0.64, 0.60), (0.48, 0.58), 0),
    ):
        _manufactured(M[key], color, rough_range, metal)
    derived = [oak.name, roughness.name, normal.name, carpet.name, mineral.name]
    upgraded = set(required_keys)
    for key, rose in (("rose", True), ("floral", False)):
        if key in M:
            printed = _textile_image(texture_dir, rose=rose)
            _cotton(M[key], printed, rose=rose)
            derived.append(printed.name)
            upgraded.add(key)
    return {
        "profile": PROFILE_VERSION,
        "materials_upgraded": sorted(upgraded),
        "packed_derived_images": derived,
        "new_downloads": ["oak_veneer_01 / CC0-1.0 / assets/MATERIALS_V2_SOURCES.json"],
        "floral_ground_target_srgb": [135, 170, 205],
        "rose_print_uv_scale": [6.0, 2.875],
        "cotton_thread_relief_m": 0.00013,
        "cotton_compression_crease_relief_m": {"rose": 0.0013, "blue": 0.0032},
        "oak_stain_linear": list(OAK_STAIN),
        "oak_roughness_bounds": [0.30, 0.53],
        "oak_normal_strength": 0.10,
        "oak_coat_weight": 0.045,
        "oak_albedo_contrast_power": 1.20,
        "oak_scan_period_m": 1.8,
        "oak_shader_uv_scale": list(OAK_UV_SCALE),
        "oak_image_rotation": "All maps 90 degrees; tangent normal XY becomes Y,-X",
        "carpet_yarn_relief_m": 0.00065,
        "carpet_micro_relief_m": 0.00012,
        "counter_relief_m": 0.00008,
        "wall_relief_m": 0.00055,
        "ceiling_relief_m": 0.0030,
        "wall_nominal_stipple_spacing_m": 1 / 380,
        "ceiling_nominal_aggregate_spacing_m": 1 / 230,
        "coordinate_policy": "Explicit world metres for isotropic surfaces; local metres for directionally laid carpet; shared authored UVs for all oak maps.",
        "geometry_recommendations": [
            "Carpet needs 5-7mm total thickness, 0.2-0.4mm joins and no substantial hard bevel; this module does not alter tiles.",
            "Common box UVs use U along length / 1.15m and V across / 0.72m; the oak shader converts these to the new scan's 1.8m physical repeat. Keep these coordinate conventions in sync.",
            "Apply object scale to carpet meshes when changing dimensions outside edit mode so local-metre yarn sizes remain valid.",
        ],
        "limits": [
            "Material parameters are authored visual estimates and need reference-camera look-development approval.",
            "Fine procedural paint, carpet, laminate and metal relief is Cycles detail; glTF retains image colors and calibrated roughness without those micro-normal graphs.",
            "Prop-specific materials created later are outside this setup hook; improve those separately.",
        ],
    }
