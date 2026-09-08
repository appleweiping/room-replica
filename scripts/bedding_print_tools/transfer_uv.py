from pathlib import Path
import numpy as np, json, hashlib, time
from scipy.spatial import cKDTree
import argparse

parser = argparse.ArgumentParser(
    description="Build a checked UV chart cache from exported cloth donors; requires NumPy and SciPy"
)
parser.add_argument("--work-dir", required=True)
parser.add_argument(
    "--output-dir", help="Optional cache destination for isolated reproducibility checks"
)
args = parser.parse_args()
HERE = Path(args.work_dir).resolve()
ROOT = Path(__file__).resolve().parents[2]
t0 = time.time()
target = np.load(HERE / "target.npz")
xyz = target["xyz"]
loops = target["loops"]
sizes = target["polygon_size"]
donors = []
for i in range(5):
    d = np.load(HERE / f"donor-{i}.npz")
    v = d["xyz"][d["triangles"]]
    donors.append((v, d["triangle_uv"], np.full(len(v), i, np.uint8)))
tri = np.concatenate([d[0] for d in donors])
uv = np.concatenate([d[1] for d in donors])
labels = np.concatenate([d[2] for d in donors])


def nearest(points, tri, uv, labels):
    tree = cKDTree(tri.mean(1))
    out = np.empty((len(points), 2), np.float32)
    chart = np.empty(len(points), np.uint8)
    dist = np.empty(len(points), np.float32)
    for start in range(0, len(points), 20000):
        q = points[start : start + 20000]
        _, ids = tree.query(q, k=12, workers=1)
        faces = tri[ids]
        a = faces[:, :, 0]
        e1 = faces[:, :, 1] - a
        e2 = faces[:, :, 2] - a
        p = q[:, None, :] - a
        d11 = np.sum(e1 * e1, 2)
        d22 = np.sum(e2 * e2, 2)
        d12 = np.sum(e1 * e2, 2)
        d1 = np.sum(p * e1, 2)
        d2 = np.sum(p * e2, 2)
        det = np.maximum(d11 * d22 - d12 * d12, 1e-20)
        v = (d22 * d1 - d12 * d2) / det
        w = (d11 * d2 - d12 * d1) / det
        bary = np.stack((1 - v - w, v, w), 2)
        projected = np.sum(faces * bary[:, :, :, None], 2)
        distance = np.sum((q[:, None, :] - projected) ** 2, 2)
        distance[(bary < 0).any(2)] = np.inf
        for i, j in ((0, 1), (1, 2), (2, 0)):
            edge = faces[:, :, j] - faces[:, :, i]
            t = np.clip(
                np.sum((q[:, None, :] - faces[:, :, i]) * edge, 2)
                / np.maximum(np.sum(edge * edge, 2), 1e-20),
                0,
                1,
            )
            near = faces[:, :, i] + edge * t[:, :, None]
            d = np.sum((q[:, None, :] - near) ** 2, 2)
            choose = d < distance
            candidate = np.zeros_like(bary)
            candidate[:, :, i] = 1 - t
            candidate[:, :, j] = t
            distance[choose] = d[choose]
            bary[choose] = candidate[choose]
        best = distance.argmin(1)
        row = np.arange(len(q))
        selected = ids[row, best]
        out[start : start + len(q)] = np.sum(uv[selected] * bary[row, best, :, None], 1)
        chart[start : start + len(q)] = labels[selected]
        dist[start : start + len(q)] = np.sqrt(distance[row, best])
    return out, chart, dist


metres, charts, dist = nearest(xyz, tri, uv, labels)
starts = np.r_[0, np.cumsum(sizes)[:-1]]
counts = np.stack(
    [np.add.reduceat((charts[loops] == i).astype(np.int32), starts) for i in range(5)], axis=1
)
face_chart = counts.argmax(1).astype(np.uint8)
loop_chart = np.repeat(face_chart, sizes)
overrides = np.flatnonzero(charts[loops] != loop_chart).astype(np.int32)
override_uv = np.empty((len(overrides), 2), np.float32)
for i in range(5):
    mask = loop_chart[overrides] == i
    vertexids, inverse = np.unique(loops[overrides[mask]], return_inverse=True)
    if not len(vertexids):
        continue
    coordinates, _, _ = nearest(xyz[vertexids], *donors[i])
    override_uv[mask] = coordinates[inverse]
topology_hash = hashlib.sha256(loops.tobytes() + sizes.tobytes()).hexdigest()
outdir = Path(args.output_dir).resolve() if args.output_dir else ROOT / "assets/uv"
outdir.mkdir(exist_ok=True, parents=True)
np.savez_compressed(
    outdir / "blue_quilt_print_v6.npz",
    vertex_metres=metres,
    vertex_charts=charts,
    override_loops=overrides,
    override_metres=override_uv,
    override_charts=loop_chart[overrides],
    topology_sha256=np.array(topology_hash),
    source_world_vertices=xyz.astype(np.float32),
    source_face_centres=(
        np.add.reduceat(xyz[loops], np.r_[0, np.cumsum(sizes)[:-1]], axis=0) / sizes[:, None]
    ).astype(np.float32),
    source_face_charts=face_chart,
    override_vertices=loops[overrides],
)
report = {
    "target_vertices": len(xyz),
    "target_loops": len(loops),
    "topology_sha256": topology_hash,
    "chart_vertex_counts": np.bincount(charts).tolist(),
    "chart_seam_override_loops": len(overrides),
    "donor_nearest_distance_percentiles_m": np.percentile(dist, [0, 50, 90, 95, 99, 100]).tolist(),
    "cache_bytes": (outdir / "blue_quilt_print_v6.npz").stat().st_size,
    "seconds": time.time() - t0,
}
(HERE / "uv-transfer-report.json").write_text(json.dumps(report, indent=2), encoding="utf8")
print(json.dumps(report, indent=2))
