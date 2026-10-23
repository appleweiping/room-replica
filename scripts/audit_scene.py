"""Read-only native-scene audit; never saves or renders the Blender file.

Run from the repository root:
    blender --background scene/room.blend --python-exit-code 1 --python scripts/audit_scene.py

Prints a JSON summary. Failed checks raise an exception, which
--python-exit-code 1 converts into a nonzero Blender process exit code.
"""

from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
from mathutils import Vector
import bpy, hashlib, json, math, time

root = Path(__file__).resolve().parents[1]
source = Path(bpy.data.filepath)
if not source.is_file():
    raise RuntimeError("Open scene/room.blend before running this audit.")
source_hash_at_start = hashlib.sha256(source.read_bytes()).hexdigest()
started = time.perf_counter()
scene = bpy.context.scene
objects = list(scene.objects)
meshes = [o for o in objects if o.type == "MESH"]
geometry = [o for o in objects if o.type in {"MESH", "CURVE", "SURFACE", "FONT"}]
used_materials = {m for o in objects for slot in o.material_slots if (m := slot.material)}
used_images = {}


def collect_images(node_tree, owner, visited=None):
    if node_tree is None:
        return
    visited = set() if visited is None else visited
    if node_tree in visited:
        return
    visited.add(node_tree)
    for node in node_tree.nodes:
        if node.type == "TEX_IMAGE" and node.image:
            used_images.setdefault(node.image, set()).add(owner)
        if node.type == "GROUP" and node.node_tree:
            collect_images(node.node_tree, owner, visited)


for material in used_materials:
    collect_images(material.node_tree, material.name)
if scene.world:
    collect_images(scene.world.node_tree, "WORLD / " + scene.world.name)
images = []
for image, owners in sorted(used_images.items(), key=lambda pair: pair[0].name):
    packed = bool(image.packed_file) or bool(len(image.packed_files))
    images.append(
        {
            "name": image.name,
            "source": image.source,
            "packed": packed,
            "dimensions_px": list(image.size),
            "colorspace": image.colorspace_settings.name,
            "materials": sorted(owners),
        }
    )
nonfinite = []
for obj in objects:
    if not all(math.isfinite(value) for row in obj.matrix_world for value in row):
        nonfinite.append(obj.name + ": world transform")
    if obj.type == "MESH" and not all(
        math.isfinite(value) for v in obj.data.vertices for value in v.co
    ):
        nonfinite.append(obj.name + ": mesh vertex")
base = {
    "mesh_objects": len(meshes),
    "vertices": sum(len(o.data.vertices) for o in meshes),
    "polygons": sum(len(o.data.polygons) for o in meshes),
}
base["triangles"] = 0
for obj in meshes:
    obj.data.calc_loop_triangles()
    base["triangles"] += len(obj.data.loop_triangles)

print("AUDIT_EVALUATING_GEOMETRY", len(geometry), flush=True)
depsgraph = bpy.context.evaluated_depsgraph_get()
evaluated = {
    "dependency_graph_mode": depsgraph.mode,
    "converted_geometry_objects": 0,
    "vertices": 0,
    "polygons": 0,
    "triangles": 0,
    "notes": "Current view-layer dependency graph evaluation. Includes meshes and converted bevelled curves with enabled viewport modifiers. Render-only subdivision can exceed these counts.",
}
by_type = {}
for index, obj in enumerate(geometry):
    evaluated_obj = obj.evaluated_get(depsgraph)
    temp_mesh = None
    try:
        temp_mesh = evaluated_obj.to_mesh(preserve_all_data_layers=False, depsgraph=depsgraph)
        if temp_mesh:
            temp_mesh.calc_loop_triangles()
            counts = {
                "objects": 1,
                "vertices": len(temp_mesh.vertices),
                "polygons": len(temp_mesh.polygons),
                "triangles": len(temp_mesh.loop_triangles),
            }
            evaluated["converted_geometry_objects"] += 1
            current_type = by_type.setdefault(obj.type, {key: 0 for key in counts})
            for key, value in counts.items():
                current_type[key] += value
                if key != "objects":
                    evaluated[key] += value
    finally:
        if temp_mesh is not None:
            evaluated_obj.to_mesh_clear()
    if (index + 1) % 250 == 0:
        print("AUDIT_GEOMETRY_PROGRESS", index + 1, flush=True)
evaluated["by_source_type"] = by_type
subdivision_differences = []
for obj in geometry:
    for mod in obj.modifiers:
        if mod.type == "SUBSURF" and mod.show_render and mod.render_levels != mod.levels:
            subdivision_differences.append(
                {
                    "object": obj.name,
                    "viewport_levels": mod.levels,
                    "render_levels": mod.render_levels,
                }
            )
expected_cameras = {"Camera_Bedroom", "Camera_Kitchen", "Camera_Desk", "Camera_Overview"}
cameras = [o for o in objects if o.type == "CAMERA"]
camera_names = {o.name for o in cameras}
mattress = scene.objects.get("Mattress")
mattress_size = list(mattress.dimensions) if mattress else None
expected_size = [2.032, 0.9144, 0.208]


# Semantic scale guards catch transformed unit spheres that remain finite but
# become implausibly large. Long cable curves are intentionally out of scope.
def dimensions_record(obj):
    return {
        "object": obj.name,
        "dimensions_m": list(obj.dimensions),
        "max_dimension_m": max(obj.dimensions),
    }


lens_objects = [o for o in meshes if "lens" in o.name.lower()]
eyelet_objects = [o for o in meshes if "eyelet" in o.name.lower()]
prop_meshes = [o for o in meshes if any(c.name.startswith("Props /") for c in o.users_collection)]
prop_spheres = [o for o in prop_meshes if len(o.data.vertices) == 610]
semantic = {
    "scope": "Named lenses and eyelets, all mesh objects in Props / collections, and default UV-sphere topology among those props. Bounds are sanity checks, not a proof of all geometry correctness.",
    "lens_eyelet_limit_m": 0.02,
    "prop_mesh_limit_m": 1.2,
    "prop_uv_sphere_limit_m": 1.0,
    "lens_count": len(lens_objects),
    "eyelet_count": len(eyelet_objects),
    "prop_mesh_count": len(prop_meshes),
    "prop_uv_sphere_count": len(prop_spheres),
    "lenses": [dimensions_record(o) for o in lens_objects],
    "eyelets_max_dimension_m": max((max(o.dimensions) for o in eyelet_objects), default=None),
    "largest_prop_meshes": [
        dimensions_record(o)
        for o in sorted(prop_meshes, key=lambda o: max(o.dimensions), reverse=True)[:10]
    ],
    "oversized_lens_eyelets": [
        dimensions_record(o) for o in lens_objects + eyelet_objects if max(o.dimensions) >= 0.02
    ],
    "oversized_prop_meshes": [
        dimensions_record(o) for o in prop_meshes if max(o.dimensions) >= 1.2
    ],
    "oversized_prop_uv_spheres": [
        dimensions_record(o) for o in prop_spheres if max(o.dimensions) >= 1.0
    ],
}
# Ray-cast from inside the sink opening: a solid cabinet must not fill the bowl.
# These points are in the basin mesh's local coordinates, transformed into world space.
basin = scene.objects.get("Sink_stainless_basin")
sink_rays = []
for label, local_origin in [
    ("right", (0.1, 0.07, 0.88)),
    ("left", (-0.1, 0.07, 0.88)),
    ("center", (0, 0, 0.88)),
]:
    record = {
        "sample": label,
        "origin_local_m": list(local_origin),
        "direction_world": [0, 0, -1],
        "maximum_distance_m": 0.4,
        "hit": False,
        "passed": False,
    }
    if basin:
        origin = basin.matrix_world @ Vector(local_origin)
        record["origin_world_m"] = list(origin)
        hit, location, normal, face_index, hit_object, hit_matrix = scene.ray_cast(
            depsgraph, origin, Vector((0, 0, -1)), distance=0.4
        )
        record["hit"] = bool(hit)
        if hit:
            record.update(
                {
                    "object": hit_object.name,
                    "location_world_m": list(location),
                    "face_index": face_index,
                    "material_slots": [
                        slot.material.name for slot in hit_object.material_slots if slot.material
                    ],
                }
            )
            allowed = hit_object.name == basin.name
            if label == "center":
                allowed = allowed or hit_object.name.startswith(
                    ("Sink_drain", "Sink_strainer_hole")
                )
            record["passed"] = allowed and 0.68 < location.z < 0.76
    sink_rays.append(record)
semantic["sink_cavity"] = {
    "scope": "Three downward first-hit rays from inside the basin opening; sides must hit the metal basin and center may hit its drain. All hit heights must be 0.68 < world z < 0.76 m.",
    "basin_object_present": basin is not None,
    "rays": sink_rays,
}
manifest = json.loads((root / "scene/scene-manifest.json").read_text(encoding="utf-8"))
checks = {
    "loaded_native_master": source.resolve() == (root / "scene/room.blend").resolve(),
    "used_image_textures_packed": all(i["packed"] for i in images),
    "used_image_textures_nonempty": all(all(v > 0 for v in i["dimensions_px"]) for i in images),
    "active_camera_exists": scene.camera is not None
    and scene.camera.type == "CAMERA"
    and scene.camera.name in camera_names,
    "expected_four_cameras": camera_names == expected_cameras,
    "finite_world_transforms_and_base_mesh_vertices": not nonfinite,
    "metric_units": scene.unit_settings.system == "METRIC"
    and scene.unit_settings.scale_length == 1,
    "mattress_dimensions_match_metre_anchor": mattress_size is not None
    and all(abs(a - b) < 1e-5 for a, b in zip(mattress_size, expected_size)),
    "cycles_render_engine": scene.render.engine == "CYCLES",
    "named_lenses_and_eyelets_present": bool(lens_objects) and bool(eyelet_objects),
    "lens_eyelet_dimensions_under_20mm": not semantic["oversized_lens_eyelets"],
    "prop_mesh_dimensions_under_1_2m": not semantic["oversized_prop_meshes"],
    "prop_uv_sphere_dimensions_under_1m": not semantic["oversized_prop_uv_spheres"],
    "sink_cavity_clear_to_metal_basin": basin is not None
    and all(ray["passed"] for ray in sink_rays),
}
result = {
    "schema_version": 1,
    "audited_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "status": "passed" if all(checks.values()) else "failed",
    "scope": "Read-only load and dependency-graph inspection; no render or scene save performed.",
    "source_scene": "scene/room.blend",
    "source_bytes": source.stat().st_size,
    "source_sha256": source_hash_at_start,
    "blender": {
        "version": bpy.app.version_string,
        "build_hash": bpy.app.build_hash.decode(),
        "build_date": bpy.app.build_date.decode(),
        "build_time": bpy.app.build_time.decode(),
        "build_platform": bpy.app.build_platform.decode(),
    },
    "checks": checks,
    "object_counts": dict(Counter(o.type for o in objects)),
    "total_objects": len(objects),
    "used_materials": len(used_materials),
    "total_materials": len(bpy.data.materials),
    "collections": [
        {"name": c.name, "direct_objects": len(c.objects), "all_objects": len(c.all_objects)}
        for c in sorted(bpy.data.collections, key=lambda c: c.name)
    ],
    "active_camera": scene.camera.name if scene.camera else None,
    "cameras": [
        {"name": o.name, "position_m": list(o.matrix_world.translation), "lens_mm": o.data.lens}
        for o in sorted(cameras, key=lambda o: o.name)
    ],
    "mattress": {
        "native_dimensions_m": mattress_size,
        "expected_dimensions_m": expected_size,
        "tolerance_m": 1e-5,
    },
    "loaded_materials": len(bpy.data.materials),
    "manifest_comparison": {
        "pre_save_materials": manifest.get("materials"),
        "loaded_materials": len(bpy.data.materials),
        "note": "The pre-save manifest may include unused materials that Blender omits from the saved file. Loaded counts above inspect the native master.",
    },
    "semantic_geometry_checks": semantic,
    "used_images": images,
    "base_mesh_counts": base,
    "evaluated_geometry_counts": evaluated,
    "render_subdivision_differences": subdivision_differences,
    "cycles": {
        "device": scene.cycles.device,
        "samples": scene.cycles.samples,
        "denoising": scene.cycles.use_denoising,
        "adaptive_sampling": scene.cycles.use_adaptive_sampling,
        "adaptive_threshold": scene.cycles.adaptive_threshold,
        "max_bounces": scene.cycles.max_bounces,
        "diffuse_bounces": scene.cycles.diffuse_bounces,
        "glossy_bounces": scene.cycles.glossy_bounces,
        "transmission_bounces": scene.cycles.transmission_bounces,
        "threads_mode": scene.render.threads_mode,
        "threads": scene.render.threads,
    },
    "color_management": {
        "view_transform": scene.view_settings.view_transform,
        "look": scene.view_settings.look,
        "exposure": scene.view_settings.exposure,
    },
    "saved_resolution_px": [scene.render.resolution_x, scene.render.resolution_y],
    "nonfinite_objects": nonfinite,
    "elapsed_seconds": round(time.perf_counter() - started, 3),
}
# Re-read before reporting; a concurrent rebuild invalidates this audit.
source_hash_before_report = hashlib.sha256(source.read_bytes()).hexdigest()
checks["native_file_unchanged_during_audit"] = source_hash_at_start == source_hash_before_report
result["status"] = "passed" if all(checks.values()) else "failed"
print(
    "NATIVE_VALIDATION",
    json.dumps(
        {
            "status": result["status"],
            "checks": checks,
            "objects": len(objects),
            "base": base,
            "evaluated": evaluated,
            "images": len(images),
            "render_subdivision_differences": len(subdivision_differences),
        }
    ),
    flush=True,
)
if not all(checks.values()):
    raise RuntimeError(
        "Native audit failed: " + ", ".join(name for name, passed in checks.items() if not passed)
    )
