"""Independent integrity checks for the shipped native and browser deliverables."""

from pathlib import Path
import hashlib, json, struct, sys, math
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CAMERAS = {
    "bedroom": "Camera_Bedroom",
    "kitchen": "Camera_Kitchen",
    "desk": "Camera_Desk",
    "overview": "Camera_Overview",
}
MIN_RESOLUTION = (1600, 1200)
MIN_SAMPLES = 64


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def jpeg_dimensions(data):
    """Read dimensions from JPEG SOF markers without requiring Pillow in CI."""
    check(data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9", "Invalid JPEG markers")
    offset = 2
    start_of_frame = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
    while offset < len(data):
        check(data[offset] == 0xFF, "Invalid JPEG segment marker")
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        check(offset < len(data), "Truncated JPEG marker")
        marker = data[offset]
        offset += 1
        if marker in {0xDA, 0xD9}:
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD8:
            continue
        check(offset + 2 <= len(data), "Truncated JPEG segment length")
        size = struct.unpack_from(">H", data, offset)[0]
        check(size >= 2 and offset + size <= len(data), "JPEG segment overrun")
        if marker in start_of_frame:
            check(size >= 8, "Truncated JPEG frame header")
            height, width = struct.unpack_from(">HH", data, offset + 3)
            check(width > 0 and height > 0, "Empty JPEG dimensions")
            return [width, height]
        offset += size
    raise AssertionError("JPEG has no supported frame dimensions")


def validate_render_batch(stats, root):
    """Require one finished release batch; preview renders remain valid work files."""
    check(isinstance(stats, dict), "Malformed render statistics")
    check(
        stats.get("status") == "complete",
        "Render batch is not complete: " + str(stats.get("status")),
    )
    expected = set(CAMERAS)
    requested = stats.get("requested_views", [])
    check(len(requested) == 4 and set(requested) == expected, "Batch must request all four views")
    records = stats.get("renders", [])
    check(
        isinstance(records, list) and len(records) == 4,
        "Batch must contain exactly four render records",
    )
    check(all(isinstance(record, dict) for record in records), "Malformed render record")
    views = [record.get("view") for record in records]
    check(
        len(set(views)) == 4 and set(views) == expected,
        "Render records must cover four distinct views",
    )
    check(len({record.get("camera") for record in records}) == 4, "Render records repeat a camera")
    resolution = stats.get("resolution", [])
    check(
        isinstance(resolution, list)
        and len(resolution) == 2
        and all(type(v) is int for v in resolution),
        "Invalid batch resolution",
    )
    check(
        all(v >= minimum for v, minimum in zip(resolution, MIN_RESOLUTION)),
        "Final batch resolution must be at least 1600x1200",
    )
    samples = stats.get("samples")
    check(
        type(samples) is int and samples >= MIN_SAMPLES,
        "Final batch must use a sample budget of at least 64",
    )
    check(stats.get("engine") == "Cycles", "Final batch must use Cycles")
    images = {}
    for record in records:
        name = record["view"]
        check(record.get("status") == "complete", "Render is not complete: " + name)
        check(record.get("camera") == CAMERAS[name], "Wrong camera for view: " + name)
        check(
            record.get("resolution") == resolution,
            "Per-view resolution disagrees with batch: " + name,
        )
        check(record.get("samples") == samples, "Per-view samples disagree with batch: " + name)
        check(
            record.get("output") == f"renders/{name}.jpg", "Unexpected render output path: " + name
        )
        data = (root / "renders" / f"{name}.jpg").read_bytes()
        dimensions = jpeg_dimensions(data)
        check(dimensions == resolution, "JPEG dimensions disagree with render record: " + name)
        check(
            all(v >= minimum for v, minimum in zip(dimensions, MIN_RESOLUTION)),
            "Render is below final resolution: " + name,
        )
        check(len(data) > 30_000, "Suspiciously small render: " + name)
        check(
            record.get("bytes") == len(data), "JPEG byte size disagrees with render record: " + name
        )
        digest = hashlib.sha256(data).hexdigest()
        if record.get("sha256") is not None:
            check(record["sha256"] == digest, "JPEG hash disagrees with render record: " + name)
        check(
            (root / "demo/public/renders" / f"{name}.jpg").read_bytes() == data,
            "Demo render out of sync: " + name,
        )
        images[name] = {
            "camera": record["camera"],
            "status": "complete",
            "bytes": len(data),
            "resolution": dimensions,
            "samples": samples,
            "sha256": digest,
        }
    check(
        len({image["sha256"] for image in images.values()}) == 4,
        "Camera batch produced duplicate images",
    )
    return images


def validate_source_hash(blend, stats, root):
    current_hash = hashlib.sha256(blend.read_bytes()).hexdigest()
    check(
        str(stats.get("source_scene", "")).replace("\\", "/").rsplit("/", 1)[-1] == "room.blend",
        "Render statistics name the wrong native scene",
    )
    audit_path = root / "docs/native-validation.json"
    audit = json.loads(audit_path.read_text(encoding="utf-8")) if audit_path.exists() else {}
    audit_passed = (
        audit.get("status") == "passed"
        and bool(audit.get("checks"))
        and all(value is True for value in audit["checks"].values())
    )
    audit_matches = audit_passed and audit.get("source_sha256") == current_hash
    recorded = stats.get("source_scene_sha256_at_start")
    if recorded is not None:
        check(recorded == current_hash, "Scene changed since the render batch started")
    else:
        # Compatibility for the first delivery run, which started before
        # render-start hashes were implemented. This fallback is explicitly
        # labeled as delivery-time evidence, never as a pre-render hash.
        check(
            audit_passed,
            "This legacy run needs a passed native audit for source fingerprint evidence",
        )
        check(audit_matches, "Native audit is stale: current .blend hash changed")
    return {
        "file": "scene/room.blend",
        "bytes": blend.stat().st_size,
        "sha256": current_hash,
        "matches_native_audit": bool(audit_matches),
        "hash_recorded_at_render_start": recorded is not None,
        "hash_evidence": "render-start record matches current scene"
        if recorded
        else "current file checked against native audit at delivery validation; this run did not record a pre-render hash",
    }


def validate_record_provenance(stats, root):
    """An assembled delivery must retain and faithfully select completed source records."""
    kind = stats.get("kind", "single_batch")
    check(kind in {"single_batch", "assembled_delivery"}, "Unknown render statistics kind")
    if kind == "single_batch":
        return {"kind": kind}
    check(bool(stats.get("assembled_at")), "Assembled delivery needs an assembly timestamp")
    sources = stats.get("record_sources", {})
    check(
        isinstance(sources, dict) and set(sources) == set(CAMERAS),
        "Assembled delivery must identify a source statistics file for each view",
    )
    source_batches = {}
    records = {record["view"]: record for record in stats["renders"]}
    # Timing and optional image hashes are part of the selected evidence too;
    # they must not be invented when replacing one superseded view.
    record_fields = (
        "view",
        "camera",
        "status",
        "resolution",
        "samples",
        "output",
        "bytes",
        "sha256",
        "started_at",
        "finished_at",
        "elapsed_seconds",
        "camera_position_m",
        "camera_lens_mm",
        "frame",
        "cutaway",
    )
    for view, source_name in sources.items():
        check(isinstance(source_name, str), "Invalid statistics source path")
        path = (root / source_name).resolve()
        check(
            root.resolve() in path.parents and path.suffix == ".json",
            "Statistics source must be a repository JSON file",
        )
        if source_name not in source_batches:
            raw = path.read_bytes()
            original = json.loads(raw)
            check(
                original.get("status") == "complete",
                "Source render batch is not complete: " + source_name,
            )
            check(
                original.get("kind", "single_batch") == "single_batch",
                "Source records must come from original render runs: " + source_name,
            )
            check(original.get("engine") == "Cycles", "Source batch did not use Cycles")
            original_records = original.get("renders", [])
            check(
                isinstance(original_records, list)
                and all(
                    isinstance(record, dict) and record.get("status") == "complete"
                    for record in original_records
                ),
                "Source batch contains unfinished records: " + source_name,
            )
            native = validate_source_hash(root / "scene/room.blend", original, root)
            source_batches[source_name] = {
                "data": original,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "native_scene": native,
            }
        source = source_batches[source_name]["data"]
        matching = [record for record in source["renders"] if record.get("view") == view]
        check(len(matching) == 1, "Source batch must contain exactly one record for: " + view)
        check(view in source.get("requested_views", []), "Source run did not request view: " + view)
        check(
            matching[0].get("resolution") == source.get("resolution")
            and matching[0].get("samples") == source.get("samples"),
            "Selected source record disagrees with its run settings: " + view,
        )
        for field in record_fields:
            check(
                records[view].get(field) == matching[0].get(field),
                f"Assembled {view} record changed source evidence field: {field}",
            )
    return {
        "kind": kind,
        "assembled_at": stats["assembled_at"],
        "record_sources": sources,
        "source_batches": {
            name: {
                "sha256": entry["sha256"],
                "status": "complete",
                "native_scene": entry["native_scene"],
            }
            for name, entry in source_batches.items()
        },
    }


def write_report(report):
    destination = ROOT / "docs/validation.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)


def validate_glb(path):
    data = path.read_bytes()
    check(len(data) > 20, "GLB is empty")
    magic, version, length = struct.unpack_from("<4sII", data)
    check(magic == b"glTF" and version == 2, "Expected binary glTF 2.0")
    check(length == len(data), "GLB header length mismatch")
    offset = 12
    chunks = []
    while offset < len(data):
        size, kind = struct.unpack_from("<II", data, offset)
        offset += 8
        check(offset + size <= len(data), "GLB chunk overflows file")
        chunks.append((kind, data[offset : offset + size]))
        offset += size
    check(chunks[0][0] == 0x4E4F534A, "GLB JSON must be first chunk")
    d = json.loads(chunks[0][1])
    check(d["asset"]["version"] == "2.0", "Wrong glTF asset version")
    bins = [x[1] for x in chunks if x[0] == 0x004E4942]
    check(len(bins) == 1, "Expected one embedded binary buffer")
    binary = bins[0]
    check(len(d.get("meshes", [])) > 300, "Incomplete browser scene")
    names = [x.get("name", "") for x in d["nodes"]]
    for token in [
        "Mattress",
        "Microwave",
        "Blind_Slat",
        "Sink_stainless",
        "Wardrobe",
        "Desk_top",
        "Dresser",
    ]:
        check(any(token in x for x in names), "Missing essential geometry: " + token)
    for b in d.get("buffers", []):
        check("uri" not in b, "GLB references external binary data")
        check(b["byteLength"] <= len(binary), "Binary buffer shorter than declared")
    for im in d.get("images", []):
        check("bufferView" in im, "Texture is not embedded")
    for view in d.get("bufferViews", []):
        check(view.get("byteOffset", 0) + view["byteLength"] <= len(binary), "Buffer view overrun")
    for acc in d.get("accessors", []):
        for bound in ["min", "max"]:
            check(all(math.isfinite(v) for v in acc.get(bound, [])), "Non-finite accessor bound")
    return {
        "bytes": len(data),
        "nodes": len(names),
        "meshes": len(d["meshes"]),
        "embedded_images": len(d.get("images", [])),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def validate_delivery():
    stats = json.loads((ROOT / "renders/render-stats.json").read_text(encoding="utf-8"))
    images = validate_render_batch(stats, ROOT)
    blend = ROOT / "scene/room.blend"
    check(blend.stat().st_size > 100_000, "Native Blender file missing or empty")
    native = validate_source_hash(blend, stats, ROOT)
    provenance = validate_record_provenance(stats, ROOT)
    glb = validate_glb(ROOT / "demo/public/models/room.glb")
    manifest = json.loads((ROOT / "scene/scene-manifest.json").read_text(encoding="utf-8"))
    check(
        manifest["dimensions"]["status"] == "photo-estimated",
        "Unmeasured room must retain uncertainty status",
    )
    check(
        manifest["dimensions"]["mattress"][:2] == [2.032, 0.9144],
        "Official mattress dimensions changed",
    )
    sources = json.loads((ROOT / "assets/ASSET_SOURCES.json").read_text(encoding="utf-8"))
    # Rebuilding should never depend on a private reference photo.
    src = (ROOT / "scripts/build_scene.py").read_text(encoding="utf-8")
    check(
        "xwechat" not in src and "RWTemp" not in src,
        "Private reference path leaked into build script",
    )
    report = {
        "result": "passed",
        "checks": [
            "completed four-camera render batch",
            "four distinct expected cameras completed",
            "actual JPEG dimensions match records and are at least 1600x1200",
            "sample budget at least 64 and consistent across records",
            "JPEG byte counts match completion records",
            "GLB container integrity",
            "embedded resources",
            "essential scene components",
            "finite geometry bounds",
            "native scene present",
            "current native scene SHA-256 checked against recorded evidence",
            "scale uncertainty metadata",
            "four valid renders",
            "gallery synchronized",
            "no private path in builder",
        ],
        "glb": glb,
        "native_scene": native,
        "render_batch": {
            "status": stats["status"],
            "resolution": stats["resolution"],
            "samples": stats["samples"],
            "source": "renders/render-stats.json",
            "provenance": provenance,
        },
        "renders": images,
    }
    return report


def main():
    try:
        report = validate_delivery()
        exit_code = 0
    except (AssertionError, OSError, ValueError, KeyError, TypeError, struct.error) as exc:
        # Replace old successful evidence immediately when final artifacts are
        # incomplete, stale or still rendering; do not leave a misleading pass.
        report = {"result": "failed", "error": f"{type(exc).__name__}: {exc}"}
        exit_code = 1
    report["validated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_report(report)
    print(json.dumps(report, indent=2))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
