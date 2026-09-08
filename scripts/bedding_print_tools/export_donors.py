from pathlib import Path
import sys, json, hashlib
import bpy
import numpy as np
import argparse

parser = argparse.ArgumentParser(
    description="Export the current blue quilt and temporary original cloth UV donors without saving the scene"
)
parser.add_argument("--work-dir", required=True)
args = parser.parse_args(sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else [])
ROOT = Path(__file__).resolve().parents[2]
HERE = Path(args.work_dir).resolve()
HERE.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / "scripts"))
import textiles_v2 as textiles
from bedding_surface_v5 import refine_bedding_surface, warp_surface_points
from quilt_pose_v4 import warp_points
from bed_support_v4 import release_quilt_lower_shell

scene = bpy.context.scene
source = Path(bpy.data.filepath)
if not source.is_file():
    raise RuntimeError("Load a calibrated native scene using Blender -b first")
source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
surface_config = json.loads(scene.get("bedding_surface_v5_config", "{}"))
refine_bedding_surface(surface_config)
target = bpy.data.objects["BedV2_Blue_Quilt_Folded"]


def vertices(obj):
    v = np.empty(len(obj.data.vertices) * 3)
    obj.data.vertices.foreach_get("co", v)
    m = np.array(obj.matrix_world)
    return v.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]


target_xyz = vertices(target)
indices = np.empty(len(target.data.loops), np.int32)
target.data.loops.foreach_get("vertex_index", indices)
poly_size = np.empty(len(target.data.polygons), np.int32)
target.data.polygons.foreach_get("loop_total", poly_size)
old_uv = np.empty(len(indices) * 2, np.float32)
target.data.uv_layers.active.data.foreach_get("uv", old_uv)
np.savez_compressed(
    HERE / "target.npz",
    xyz=target_xyz,
    loops=indices,
    polygon_size=poly_size,
    old_uv=old_uv.reshape(-1, 2),
)


class Captured(Exception):
    pass


parts = []
original = textiles._quilt_return_patch


def capture(*args, **kwargs):
    obj = original(*args, **kwargs)
    parts.append(obj)
    if len(parts) == 4:
        raise Captured()
    return obj


existing = set(bpy.data.objects)
textiles._quilt_return_patch = capture
try:
    textiles._quilt(textiles.BeddingConfig(seams=False), {"floral": target.data.materials[0]})
except Captured:
    pass
finally:
    textiles._quilt_return_patch = original
created = set(bpy.data.objects) - existing
base = next(o for o in created if o not in parts and o.type == "MESH")
parts = [base] + parts
bedmat = np.array(target.matrix_world)
pose_config = json.loads(target["quilt_pose_v4_config"])
support_config = json.loads(scene["bed_support_v4_config"])["support"]


def world_warp(v):
    v = v.copy()
    v[:, 2] -= 0.0055
    v = v @ bedmat[:3, :3].T + bedmat[:3, 3]
    return warp_surface_points(
        release_quilt_lower_shell(warp_points(v, pose_config), support_config), surface_config
    )


reports = []
for i, obj in enumerate(parts):
    v = vertices(obj)
    n = len(v) // 2
    indices = np.empty(len(obj.data.loops), np.int32)
    obj.data.loops.foreach_get("vertex_index", indices)
    uv = np.empty(len(indices) * 2, np.float64)
    obj.data.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    vertex_uv = np.zeros((len(v), 2))
    vertex_uv[indices] = uv
    # All original pieces have rectangular parametric grids on each casing.
    cols = len(np.unique(np.round(vertex_uv[:n, 0], 5)))
    rows = n // cols
    assert rows * cols == n, (obj.name, n, rows, cols)
    w = world_warp(v)
    grid = w.reshape(2, rows, cols, 3)
    uarc = np.concatenate(
        (np.zeros((2, rows, 1)), np.cumsum(np.linalg.norm(np.diff(grid, axis=2), axis=3), axis=2)),
        axis=2,
    )
    varc = np.concatenate(
        (np.zeros((2, 1, cols)), np.cumsum(np.linalg.norm(np.diff(grid, axis=1), axis=3), axis=1)),
        axis=1,
    )
    # A shared medial chart avoids print discontinuity at the upper/lower seam.
    uarc = uarc.mean(0)
    varc = varc.mean(0)
    uarc -= uarc[:, -1, None] / 2
    varc -= varc[-1, :][None, :] / 2
    metre_uv = np.stack((uarc, varc), axis=2).reshape(n, 2)
    metre_uv = np.concatenate((metre_uv, metre_uv), axis=0)
    obj.data.uv_layers.active.data.foreach_set("uv", metre_uv[indices].astype(np.float32).ravel())
    # Subdivision is performed before the nonlinear pose, matching the original
    # donor's geometric order. UV stores the final physical chart measurements.
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    sub = obj.modifiers.new("Donor smooth", "SUBSURF")
    sub.levels = 2 if i == 0 else 1
    bpy.ops.object.modifier_apply(modifier=sub.name)
    obj.select_set(False)
    v = world_warp(vertices(obj))
    obj.data.calc_loop_triangles()
    tri = np.empty(len(obj.data.loop_triangles) * 3, np.int32)
    obj.data.loop_triangles.foreach_get("vertices", tri)
    tri = tri.reshape(-1, 3)
    tl = np.empty(len(obj.data.loop_triangles) * 3, np.int32)
    obj.data.loop_triangles.foreach_get("loops", tl)
    tl = tl.reshape(-1, 3)
    uv = np.empty(len(obj.data.loops) * 2, np.float32)
    obj.data.uv_layers.active.data.foreach_get("uv", uv)
    uv = uv.reshape(-1, 2)
    np.savez_compressed(HERE / f"donor-{i}.npz", xyz=v, triangles=tri, triangle_uv=uv[tl])
    report = {
        "index": i,
        "name": obj.name,
        "grid": [rows, cols],
        "median_u_length_m": float(np.median(uarc[:, -1] - uarc[:, 0])),
        "median_v_length_m": float(np.median(varc[-1, :] - varc[0, :])),
        "old_uv_span": (vertex_uv.max(0) - vertex_uv.min(0)).tolist(),
        "vertices_after_subdivision": len(v),
    }
    reports.append(report)
    print(report, flush=True)
for obj in created:
    data = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if data.users == 0:
        bpy.data.meshes.remove(data)
report = {
    "source_native_sha256": source_sha,
    "source_unchanged": hashlib.sha256(source.read_bytes()).hexdigest() == source_sha,
    "target_vertices": len(target_xyz),
    "target_loops": len(old_uv) // 2,
    "donors": reports,
}
(HERE / "donor-report.json").write_text(json.dumps(report, indent=2), encoding="utf8")
print("DONOR_EXPORT_COMPLETE", flush=True)
