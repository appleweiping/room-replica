"""Unit tests for scripts/check_assets.py and the render CLI; no Blender needed."""

from pathlib import Path
import json
import struct
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import check_assets as checks
import render as renderer


def jpeg(width, height):
    """Smallest byte string with a frame header; enough for the size parser."""
    return b"\xff\xd8\xff\xe0\x00\x06TEST\xff\xc2" + struct.pack(">HBHHB", 8, 8, height, width, 0) + b"\xff\xd9"


def render_stats():
    return {
        "status": "complete",
        "engine": "Cycles",
        "resolution": [1600, 1200],
        "samples": 64,
        "renders": [
            {
                "view": view,
                "camera": camera,
                "status": "complete",
                "resolution": [1600, 1200],
                "elapsed_seconds": 120,
            }
            for view, camera in checks.CAMERAS.items()
        ],
    }


def glb(doc, binary=b""):
    body = json.dumps(doc).encode()
    body += b" " * (-len(body) % 4)
    binary += b"\0" * (-len(binary) % 4)
    chunks = struct.pack("<II", len(body), 0x4E4F534A) + body + struct.pack("<II", len(binary), 0x004E4942) + binary
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


class JpegTests(unittest.TestCase):
    def test_reads_frame_size(self):
        self.assertEqual(checks.jpeg_dimensions(jpeg(1600, 1200)), [1600, 1200])

    def test_truncated_segment_rejected(self):
        with self.assertRaisesRegex(AssertionError, "overrun"):
            checks.jpeg_dimensions(b"\xff\xd8\xff\xe0\xff\xff\xff\xd9")


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        for folder in ("renders", "demo/public/renders"):
            (self.root / folder).mkdir(parents=True)
            for view in checks.CAMERAS:
                (self.root / folder / f"{view}.jpg").write_bytes(jpeg(1600, 1200))

    def tearDown(self):
        self.tmp.cleanup()

    def test_complete_batch_passes(self):
        minutes = checks.check_renders(render_stats(), self.root)
        self.assertEqual(minutes["bedroom"], 2.0)

    def test_running_batch_rejected(self):
        stats = render_stats()
        stats["status"] = "running"
        with self.assertRaisesRegex(AssertionError, "not complete"):
            checks.check_renders(stats, self.root)

    def test_missing_view_rejected(self):
        stats = render_stats()
        stats["renders"].pop()
        with self.assertRaisesRegex(AssertionError, "exactly four"):
            checks.check_renders(stats, self.root)

    def test_preview_resolution_rejected(self):
        stats = render_stats()
        stats["resolution"] = [800, 600]
        with self.assertRaisesRegex(AssertionError, "1600x1200"):
            checks.check_renders(stats, self.root)

    def test_stale_demo_copy_rejected(self):
        (self.root / "demo/public/renders/desk.jpg").write_bytes(jpeg(1600, 1200) + b"x")
        with self.assertRaisesRegex(AssertionError, "out of date"):
            checks.check_renders(render_stats(), self.root)


class GlbTests(unittest.TestCase):
    def doc(self):
        return {
            "asset": {"version": "2.0"},
            "meshes": [{} for _ in range(301)],
            "nodes": [{"name": n} for n in checks.ESSENTIAL_NODES],
            "cameras": [{}, {}, {}],
            "buffers": [{"byteLength": 4}],
            "bufferViews": [{"buffer": 0, "byteLength": 4}],
            "accessors": [{"min": [0, 0, 0], "max": [1, 1, 1]}],
        }

    def write(self, data):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "m.glb"
        path.write_bytes(data)
        return path

    def test_valid_container_passes(self):
        summary = checks.check_glb(self.write(glb(self.doc(), b"\0\0\0\0")))
        self.assertEqual(summary["meshes"], 301)

    def test_external_texture_rejected(self):
        doc = self.doc()
        doc["images"] = [{"uri": "wood.jpg"}]
        with self.assertRaisesRegex(AssertionError, "not embedded"):
            checks.check_glb(self.write(glb(doc, b"\0\0\0\0")))

    def test_missing_furniture_rejected(self):
        doc = self.doc()
        doc["nodes"] = doc["nodes"][1:]
        with self.assertRaisesRegex(AssertionError, "Mattress"):
            checks.check_glb(self.write(glb(doc, b"\0\0\0\0")))


class RenderCliTests(unittest.TestCase):
    def test_preview_arguments_parse(self):
        args = renderer.parse_arguments(
            ["--view", "overview", "--resolution", "800", "--samples", "8", "--stats-file", "renders/probe.json"]
        )
        self.assertEqual((args.view, args.resolution, args.samples), ("overview", 800, 8))
        self.assertEqual(args.stats_file, Path("renders/probe.json"))


if __name__ == "__main__":
    unittest.main()
