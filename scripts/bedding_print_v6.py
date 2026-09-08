"""Uniform physical print scale on the calibrated, folded blue quilt.

The compact chart cache comes from the five original cloth surfaces, measured
after the accepted layout and pose. It supplies a separate albedo UV channel;
the original cloth-relief UVs and every geometric coordinate remain untouched.
"""

from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json
import numpy as np


@dataclass(frozen=True)
class BeddingPrintConfig:
    period_u_m: float = 2.5
    period_v_m: float = 1.825
    albedo_gain: float = 1.0
    albedo_tint_rgb: tuple = (1.0, 1.0, 1.0)


# One authored full duvet panel, no repeated all-over pattern. Offset the fold
# charts so the central lap stays blue and the outer returns carry flower bands.
CHART_CENTRES = np.array(
    [
        (0.50, 0.50),  # base casing
        (0.71, 0.52),  # central overturned lap
        (0.83, 0.54),  # right return
        (0.47, 0.55),  # front rolled edge
        (0.09, 0.70),  # left crushed return
    ],
    dtype=np.float64,
)


def _uv_from_metres(metres, charts, config):
    uv = np.asarray(metres, dtype=np.float64) / [config.period_u_m, config.period_v_m]
    uv += CHART_CENTRES[np.asarray(charts, dtype=np.int32)]
    # Only peripheral base-chart tips pass beyond the full panel. Reflection
    # makes their continuation continuous, instead of a hard clamp or a tiled
    # grid. Every chart retains the same physical pixels-per-metre scale.
    return (1 - np.abs(np.mod(uv, 2) - 1)).astype(np.float32)


def _cached_loop_uv(data, world_vertices, loops, sizes, fingerprint, config):
    """Accept only the calibrated surface, with a checked remesh-ID fallback.

    Voxel cleanup may remove a few coincident vertices during a fresh build.
    The fallback proves sub-millimetre surface correspondence, chooses a chart
    per physical face, and looks up (source vertex, chart) seam coordinates.
    It never accepts an arbitrary new topology solely by vertex count.
    """
    source = np.asarray(data["source_world_vertices"], dtype=np.float64)
    exact = str(data["topology_sha256"]) == fingerprint and len(source) == len(world_vertices)
    if exact and np.max(np.abs(source - world_vertices)) < 1e-6:
        uv = _uv_from_metres(data["vertex_metres"], data["vertex_charts"], config)[loops]
        uv[data["override_loops"]] = _uv_from_metres(
            data["override_metres"], data["override_charts"], config
        )
        return uv, {"method": "exact topology and calibrated coordinates", "spatial_remap": False}

    from mathutils import Vector
    from mathutils.kdtree import KDTree

    if abs(len(source) - len(world_vertices)) / len(source) > 0.001:
        raise RuntimeError(
            "Cloth topology changed beyond the calibrated cleanup tolerance; rebuild UV donors"
        )
    bbox_error = float(
        np.max(
            np.abs(
                np.array([source.min(0), source.max(0)])
                - np.array([world_vertices.min(0), world_vertices.max(0)])
            )
        )
    )
    if bbox_error > 0.0005:
        raise RuntimeError(f"Cloth bounds differ by {bbox_error:.6f} m; rebuild UV donors")

    def nearest(points, queries):
        tree = KDTree(len(points))
        for i, p in enumerate(points):
            tree.insert(Vector(p), i)
        tree.balance()
        ids = np.empty(len(queries), np.int32)
        distance = np.empty(len(queries), np.float64)
        for i, p in enumerate(queries):
            _, ids[i], distance[i] = tree.find(Vector(p))
        return ids, distance

    mapped, vertex_distance = nearest(source, world_vertices)
    percentiles = np.percentile(vertex_distance, [50, 90, 99, 100])
    if (
        percentiles[-1] > 0.0012
        or percentiles[2] > 0.00005
        or len(np.unique(mapped)) / len(mapped) < 0.999
    ):
        raise RuntimeError(
            f"Cloth vertex correspondence failed strict geometry gate: {percentiles.tolist()}"
        )
    sample = np.linspace(0, len(source) - 1, min(20000, len(source)), dtype=np.int32)
    _, reverse_distance = nearest(world_vertices, source[sample])
    reverse = np.percentile(reverse_distance, [50, 90, 99, 100])
    if reverse[-1] > 0.0012 or reverse[2] > 0.00005:
        raise RuntimeError(f"Cloth reverse correspondence failed geometry gate: {reverse.tolist()}")
    starts = np.r_[0, np.cumsum(sizes)[:-1]]
    centres = np.add.reduceat(world_vertices[loops], starts, axis=0) / sizes[:, None]
    old_faces, face_distance = nearest(data["source_face_centres"], centres)
    face_percentiles = np.percentile(face_distance, [50, 90, 99, 100])
    if face_percentiles[-1] > 0.0025 or face_percentiles[2] > 0.00005:
        raise RuntimeError(
            f"Cloth face-chart correspondence failed geometry gate: {face_percentiles.tolist()}"
        )
    face_charts = data["source_face_charts"][old_faces]
    loop_charts = np.repeat(face_charts, sizes)
    keys = np.r_[
        np.arange(len(source), dtype=np.int64) * 5 + data["vertex_charts"],
        data["override_vertices"].astype(np.int64) * 5 + data["override_charts"],
    ]
    values = np.concatenate([data["vertex_metres"], data["override_metres"]])
    order = np.argsort(keys, kind="stable")
    keys = keys[order]
    values = values[order]
    wanted = mapped[loops].astype(np.int64) * 5 + loop_charts
    positions = np.searchsorted(keys, wanted)
    valid = positions < len(keys)
    valid[valid] &= keys[positions[valid]] == wanted[valid]
    if not valid.all():
        raise RuntimeError(
            f"Cloth seam-chart identity is unsupported for {int((~valid).sum())} loops; rebuild UV donors"
        )
    uv = _uv_from_metres(values[positions], loop_charts, config)
    return uv, {
        "method": "geometry-gated source vertex and per-face chart transfer",
        "spatial_remap": True,
        "source_vertices": len(source),
        "target_vertices": len(world_vertices),
        "bounds_max_difference_m": bbox_error,
        "vertex_distance_m_p50_p90_p99_max": percentiles.tolist(),
        "reverse_sample_distance_m_p50_p90_p99_max": reverse.tolist(),
        "face_centre_distance_m_p50_p90_p99_max": face_percentiles.tolist(),
        "missing_seam_keys": 0,
        "limits_m": {
            "vertex_max": 0.0012,
            "vertex_p99": 0.00005,
            "face_centre_max": 0.0025,
            "face_centre_p99": 0.00005,
            "bounds": 0.0005,
        },
    }


def refine_bedding_print(config=None):
    """Apply after bed_support and bedding_surface_v5; geometry is never edited.

    ``albedo_gain`` and ``albedo_tint_rgb`` are linear pigment multipliers. They
    affect the whole printed albedo, including flowers, not only blue pixels.
    The optional multiply exports as the standard glTF baseColorFactor while
    retaining the actual baseColorTexture and its dedicated UV channel.
    """
    import bpy

    c = config if isinstance(config, BeddingPrintConfig) else BeddingPrintConfig(**(config or {}))
    if c.period_u_m <= 0 or c.period_v_m <= 0:
        raise ValueError("Print periods must be positive metre values")
    tint = np.asarray(c.albedo_tint_rgb, dtype=float)
    factor = tint * c.albedo_gain
    if (
        tint.shape != (3,)
        or not np.isfinite(factor).all()
        or (factor < 0).any()
        or (factor > 1).any()
    ):
        raise ValueError("Portable glTF albedo factors must contain three values in [0,1]")
    scene = bpy.context.scene
    if not scene.get("bed_support_v4_config") or not scene.get("bedding_surface_v5_config"):
        raise RuntimeError("Apply the resolved bed support and surface refinement first")
    stamp = json.dumps(asdict(c), sort_keys=True)
    previous = scene.get("bedding_print_v6_config")
    if previous:
        if previous != stamp:
            raise RuntimeError("Rebuild before changing the applied print configuration")
        return {"changed_objects": [], "config": asdict(c), "already_applied": True}
    root = Path(__file__).resolve().parents[1]
    cache_path = root / "assets/uv/blue_quilt_print_v6.npz"
    image_path = root / "assets/textures/blue_floral_panel_v6.png"
    quilt = bpy.data.objects.get("BedV2_Blue_Quilt_Folded")
    if quilt is None or quilt.type != "MESH":
        raise RuntimeError("Expected the calibrated blue quilt mesh")
    mesh = quilt.data
    loops = np.empty(len(mesh.loops), np.int32)
    sizes = np.empty(len(mesh.polygons), np.int32)
    mesh.loops.foreach_get("vertex_index", loops)
    mesh.polygons.foreach_get("loop_total", sizes)
    fingerprint = hashlib.sha256(loops.tobytes() + sizes.tobytes()).hexdigest()
    coordinates = np.empty(len(mesh.vertices) * 3, np.float32)
    mesh.vertices.foreach_get("co", coordinates)
    matrix = np.array(quilt.matrix_world)
    world_vertices = coordinates.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
    with np.load(cache_path, allow_pickle=False) as data:
        uv, correspondence = _cached_loop_uv(data, world_vertices, loops, sizes, fingerprint, c)
    if not np.isfinite(uv).all():
        raise RuntimeError("Nonfinite print UVs")
    layer = mesh.uv_layers.get("BeddingPrintUV") or mesh.uv_layers.new(name="BeddingPrintUV")
    layer.data.foreach_set("uv", uv.ravel())
    # The old render UV stays active so all existing weave/crease nodes keep
    # their original coordinates. Only the pigment image explicitly uses v6.
    for candidate in mesh.uv_layers:
        candidate.active_render = candidate != layer
    original = mesh.materials[0]
    material = original.copy()
    material.name = "Blue duvet / metre-scale printed pigment v6"
    mesh.materials[0] = material
    nodes, links = material.node_tree.nodes, material.node_tree.links
    image_node = nodes.get("Cotton / portable printed albedo")
    if image_node is None or image_node.type != "TEX_IMAGE":
        raise RuntimeError("Expected the portable cotton image texture")
    image_node.image = bpy.data.images.load(str(image_path), check_existing=True)
    image_node.image.colorspace_settings.name = "sRGB"
    image_node.extension = "EXTEND"
    image_node.interpolation = "Linear"
    uv_node = nodes.new("ShaderNodeUVMap")
    uv_node.name = "Bedding print / physical cloth charts"
    uv_node.uv_map = layer.name
    links.new(uv_node.outputs["UV"], image_node.inputs["Vector"])
    bsdf = next(n for n in nodes if n.type == "BSDF_PRINCIPLED")
    if np.array_equal(factor, np.ones(3)):
        links.new(image_node.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        multiply = nodes.new("ShaderNodeMix")
        multiply.name = "Bedding print / portable albedo factor"
        multiply.data_type = "RGBA"
        multiply.blend_type = "MULTIPLY"
        multiply.inputs[0].default_value = 1.0
        multiply.inputs[7].default_value = (*factor, 1.0)
        links.new(image_node.outputs["Color"], multiply.inputs[6])
        links.new(multiply.outputs[2], bsdf.inputs["Base Color"])
    material["bedding_print_v6_config"] = stamp
    material["bedding_print_v6_source"] = (
        "Generated flat textile pigment; reference-informed, not a photographed room texture"
    )
    quilt["bedding_print_v6_config"] = stamp
    scene["bedding_print_v6_config"] = stamp
    return {
        "changed_objects": [quilt.name],
        "config": asdict(c),
        "topology_sha256": fingerprint,
        "geometry_unchanged": True,
        "cache_correspondence": correspondence,
        "uv_layer": layer.name,
        "image": str(image_path),
        "chart_centres": CHART_CENTRES.tolist(),
        "albedo_factor_linear": factor.tolist(),
        "uv_bounds": [uv.min(0).tolist(), uv.max(0).tolist()],
        "texture_asset_sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
    }
