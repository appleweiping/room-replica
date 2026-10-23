"""Render saved room cameras without rebuilding or modifying the native master.

Examples (from the repository root):
  blender --background scene/room.blend --python-exit-code 1 \
    --python scripts/render.py -- --view all --resolution 1600 --samples 96

Resolution is the horizontal pixel count; images use the project's 4:3 framing.
Outputs: renders/{view}.jpg and renders/render-stats.json.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback


ROOT = Path(__file__).resolve().parents[1]
CAMERAS = {
    "bedroom": "Camera_Bedroom",
    "kitchen": "Camera_Kitchen",
    "desk": "Camera_Desk",
    "overview": "Camera_Overview",
}
# Keep the cutaway consistent with build_scene.py and the authored camera rig.
CUTAWAY_PREFIXES = (
    "Shell_Ceiling",
    "Shell_Wall_Front",
    "Shell_Wall_Left",
    "Shell_Wall_Alcove",
    "Entry_Door",
    "Interior_Door",
    "Mirror_full",
    "Ceiling_Light",
    "Smoke_detector",
)


def bounded_integer(low: int, high: int):
    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be an integer") from exc
        if not low <= number <= high:
            raise argparse.ArgumentTypeError(f"must be between {low} and {high}")
        return number

    return parse


def parse_arguments(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    framing = parser.add_mutually_exclusive_group()
    framing.add_argument("--view", choices=(*CAMERAS, "all"), default="bedroom")
    framing.add_argument(
        "--reference",
        type=int,
        choices=(1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 13, 14, 16),
        help="render the calibrated camera corresponding to one supplied photograph",
    )
    parser.add_argument(
        "--resolution",
        type=bounded_integer(64, 8192),
        default=1600,
        help="image width in pixels (default: 1600)",
    )
    parser.add_argument(
        "--samples",
        type=bounded_integer(1, 8192),
        default=96,
        help="maximum Cycles samples (default: 96)",
    )
    parser.add_argument(
        "--threads",
        type=bounded_integer(1, 64),
        default=12,
        help="fixed CPU rendering threads (default: 12)",
    )
    parser.add_argument(
        "--stats-file",
        type=Path,
        default=ROOT / "renders/render-stats.json",
        help="statistics JSON path; relative paths are resolved from the repository root",
    )
    if argv is None:
        argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    return parser.parse_args(argv)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_stats(path: Path, stats: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def main(argv=None) -> int:
    args = parse_arguments(argv)
    import bpy

    if not bpy.data.filepath:
        raise RuntimeError(
            "Load scene/room.blend before running this script: "
            "blender --background scene/room.blend --python scripts/render.py -- ..."
        )
    scene = bpy.context.scene
    views = list(CAMERAS) if args.view == "all" else [args.view]
    camera_names = dict(CAMERAS)
    if args.reference is not None:
        name = f"reference-{args.reference:02d}"
        views = [name]
        camera_names[name] = f"Camera_Reference_{args.reference:02d}"
    cameras = {}
    for view in views:
        camera = scene.objects.get(camera_names[view])
        if camera is None or camera.type != "CAMERA":
            raise RuntimeError(
                f"Saved scene is missing {camera_names[view]}; rebuild scene/room.blend first."
            )
        cameras[view] = camera

    output = ROOT / "renders"
    output.mkdir(parents=True, exist_ok=True)
    stats_path = args.stats_file if args.stats_file.is_absolute() else ROOT / args.stats_file
    stats_path = stats_path.resolve()
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    width, height = args.resolution, round(args.resolution * 0.75)
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.02
    scene.render.threads_mode = "FIXED"
    scene.render.threads = args.threads
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "JPEG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.image_settings.quality = 95
    scene.render.film_transparent = False
    scene.render.use_file_extension = True

    # A previous interactive cutaway may have hidden shells. Every interior view
    # explicitly restores them, then overview applies the known cutaway only.
    shell_objects = [o for o in scene.objects if o.name.startswith("Shell_")]
    cutaway_objects = [o for o in scene.objects if o.name.startswith(CUTAWAY_PREFIXES)]
    initial_camera, initial_frame = scene.camera, scene.frame_current
    initial_exposure = scene.view_settings.exposure
    marker_bindings = [(marker, marker.camera) for marker in scene.timeline_markers]
    source_scene = Path(bpy.data.filepath).resolve()
    stats = {
        "schema_version": 1,
        "started_at": timestamp(),
        "source_scene": (
            source_scene.relative_to(ROOT).as_posix()
            if ROOT in source_scene.parents
            else source_scene.name
        ),
        "source_scene_sha256_at_start": hashlib.sha256(source_scene.read_bytes()).hexdigest(),
        "blender_version": bpy.app.version_string,
        "engine": "Cycles",
        "device": "CPU",
        "threads": args.threads,
        "resolution": [width, height],
        "samples": args.samples,
        "denoising": True,
        "adaptive_threshold": 0.02,
        "requested_views": views,
        "status": "running",
        "renders": [],
    }
    started = time.perf_counter()
    write_stats(stats_path, stats)
    try:
        # Render frame evaluation can reapply a marker even after scene.camera
        # was assigned. Temporarily unbind the rig, then restore it in finally.
        # This is essential for calibrated reference cameras without a marker.
        for marker, _ in marker_bindings:
            marker.camera = None
        for view in views:
            for obj in shell_objects + cutaway_objects:
                obj.hide_render = False
            if view == "overview":
                for obj in cutaway_objects:
                    obj.hide_render = True
            # Use the rig's matching marker frame so frame evaluation cannot
            # silently switch the requested camera back to another marker.
            marker = next((m for m, cam in marker_bindings if cam == cameras[view]), None)
            if marker is not None:
                scene.frame_set(marker.frame)
            scene.camera = cameras[view]
            scene.view_settings.exposure = float(cameras[view].get("exposure_ev", initial_exposure))
            destination = output / f"{view}.jpg"
            scene.render.filepath = str(destination)
            record = {
                "view": view,
                "camera": cameras[view].name,
                "camera_position_m": list(cameras[view].matrix_world.translation),
                "camera_lens_mm": cameras[view].data.lens,
                "exposure_ev": scene.view_settings.exposure,
                "view_transform": scene.view_settings.view_transform,
                "view_look": scene.view_settings.look,
                "frame": scene.frame_current,
                "output": f"renders/{view}.jpg",
                "resolution": [width, height],
                "samples": args.samples,
                "cutaway": view == "overview",
                "started_at": timestamp(),
                "status": "running",
            }
            stats["renders"].append(record)
            write_stats(stats_path, stats)
            print(
                f"RENDER_START {view}: {width}x{height}, {args.samples} samples, "
                f"{args.threads} CPU threads",
                flush=True,
            )
            view_started = time.perf_counter()
            try:
                result = bpy.ops.render.render(write_still=True)
                if scene.camera != cameras[view]:
                    raise RuntimeError(
                        f"Render camera changed from {cameras[view].name} to {scene.camera.name}"
                    )
                if (
                    "FINISHED" not in result
                    or not destination.is_file()
                    or destination.stat().st_size == 0
                ):
                    raise RuntimeError(
                        f"Cycles did not produce a valid output for {view}: {result}"
                    )
                image_bytes = destination.read_bytes()
                record.update(
                    status="complete",
                    bytes=len(image_bytes),
                    sha256=hashlib.sha256(image_bytes).hexdigest(),
                )
            except BaseException as exc:
                record.update(status="failed", error=f"{type(exc).__name__}: {exc}")
                raise
            finally:
                record["elapsed_seconds"] = round(time.perf_counter() - view_started, 3)
                record["finished_at"] = timestamp()
                write_stats(stats_path, stats)
            print(
                f"RENDER_COMPLETE {view}: {record['elapsed_seconds']} s, {record['bytes']} bytes",
                flush=True,
            )
        stats["status"] = "complete"
    except BaseException as exc:
        stats.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        raise
    finally:
        for obj in shell_objects + cutaway_objects:
            obj.hide_render = False
        for marker, camera in marker_bindings:
            marker.camera = camera
        scene.frame_set(initial_frame)
        scene.camera = initial_camera
        scene.view_settings.exposure = initial_exposure
        stats["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        stats["finished_at"] = timestamp()
        write_stats(stats_path, stats)
    print(f"RENDER_STATS {stats_path}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
