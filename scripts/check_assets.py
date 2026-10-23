"""Sanity checks for the committed renders, web model and scene manifest.

    python scripts/check_assets.py

Runs in CI without Blender. It only reads files; nothing is rebuilt.
"""

from pathlib import Path
import json
import math
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
CAMERAS = {
    "bedroom": "Camera_Bedroom",
    "kitchen": "Camera_Kitchen",
    "desk": "Camera_Desk",
    "overview": "Camera_Overview",
}
MIN_RESOLUTION = (1600, 1200)
MIN_SAMPLES = 64
WEB_MODEL = "demo/public/models/room-web.glb"
ESSENTIAL_NODES = ["Mattress", "Microwave", "Blind_Slat", "Sink_stainless", "Wardrobe", "Desk_top", "Dresser"]


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def jpeg_dimensions(data):
    """Read [width, height] from the JPEG frame header (no Pillow needed)."""
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


def check_renders(stats, root):
    """The four gallery renders exist, match render-stats.json and the demo copies."""
    check(stats.get("status") == "complete", "Render batch is not complete: " + str(stats.get("status")))
    check(stats.get("engine") == "Cycles", "Renders must come from Cycles")
    records = stats.get("renders", [])
    check(isinstance(records, list) and len(records) == 4, "Expected exactly four render records")
    check({r.get("view") for r in records} == set(CAMERAS), "Render records must cover the four views")
    check(len({r.get("camera") for r in records}) == 4, "Render records repeat a camera")
    resolution = stats.get("resolution")
    check(
        isinstance(resolution, list) and all(v >= m for v, m in zip(resolution, MIN_RESOLUTION)),
        "Gallery renders must be at least 1600x1200",
    )
    check(isinstance(stats.get("samples"), int) and stats["samples"] >= MIN_SAMPLES, "Gallery renders need at least 64 samples")
    summary = {}
    for record in records:
        view = record["view"]
        check(record.get("status") == "complete", "Render is not complete: " + view)
        check(record.get("camera") == CAMERAS[view], "Wrong camera for view: " + view)
        check(record.get("resolution") == resolution, "Per-view resolution disagrees with batch: " + view)
        data = (root / "renders" / f"{view}.jpg").read_bytes()
        check(jpeg_dimensions(data) == resolution, "JPEG size disagrees with render-stats.json: " + view)
        check(
            (root / "demo/public/renders" / f"{view}.jpg").read_bytes() == data,
            "demo/public/renders is out of date: " + view,
        )
        summary[view] = round(record.get("elapsed_seconds", 0) / 60, 1)
    return summary


def read_glb(data):
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
    check(chunks and chunks[0][0] == 0x4E4F534A, "GLB JSON must be the first chunk")
    bins = [c[1] for c in chunks if c[0] == 0x004E4942]
    check(len(bins) == 1, "Expected one embedded binary buffer")
    return json.loads(chunks[0][1]), bins[0]


def check_glb(path):
    """Self-contained, complete enough for the viewer, and finite."""
    data = path.read_bytes()
    doc, binary = read_glb(data)
    check(doc["asset"]["version"] == "2.0", "Wrong glTF asset version")
    check(len(doc.get("meshes", [])) > 300, "Incomplete browser scene")
    names = [n.get("name", "") for n in doc.get("nodes", [])]
    for token in ESSENTIAL_NODES:
        check(any(token in n for n in names), "Missing essential geometry: " + token)
    check(len(doc.get("cameras", [])) >= 3, "The viewer needs the authored cameras")
    for buffer in doc.get("buffers", []):
        check("uri" not in buffer, "GLB references an external file")
    for image in doc.get("images", []):
        check("bufferView" in image, "Texture is not embedded")
    for view in doc.get("bufferViews", []):
        if view.get("buffer", 0) == 0:
            check(view.get("byteOffset", 0) + view["byteLength"] <= len(binary), "Buffer view overrun")
    for accessor in doc.get("accessors", []):
        for bound in ("min", "max"):
            check(all(math.isfinite(v) for v in accessor.get(bound, [])), "Non-finite accessor bound")
    return {
        "megabytes": round(len(data) / 1e6, 1),
        "meshes": len(doc["meshes"]),
        "textures": len(doc.get("images", [])),
        "extensions": sorted(doc.get("extensionsUsed", [])),
    }


def check_manifest(manifest):
    dims = manifest["dimensions"]
    check(dims["status"] == "photo-estimated", "Room size is an estimate and must stay labelled as one")
    check(dims["mattress"][:2] == [2.032, 0.9144], "Twin XL mattress (36 x 80 in) is the scale reference")


def main():
    stats = json.loads((ROOT / "renders/render-stats.json").read_text(encoding="utf-8"))
    report = {
        "render_minutes": check_renders(stats, ROOT),
        "web_model": check_glb(ROOT / WEB_MODEL),
    }
    check_manifest(json.loads((ROOT / "scene/scene-manifest.json").read_text(encoding="utf-8")))
    builder = (ROOT / "scripts/build_scene.py").read_text(encoding="utf-8")
    check("xwechat" not in builder and "RWTemp" not in builder, "Private photo path in the builder")
    print(json.dumps(report, indent=2))
    print("ok")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, OSError, ValueError, KeyError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)
