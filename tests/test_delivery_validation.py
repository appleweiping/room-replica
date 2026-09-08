"""Release-gate regression checks; no Blender process or render is started."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import struct
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import validate_delivery as validation
import render as renderer


def complete_metadata():
    return {
        "status": "complete",
        "engine": "Cycles",
        "resolution": [1600, 1200],
        "samples": 64,
        "requested_views": list(validation.CAMERAS),
        "source_scene": "scene/room.blend",
        "renders": [
            {
                "view": view,
                "camera": camera,
                "status": "complete",
                "resolution": [1600, 1200],
                "samples": 64,
                "output": f"renders/{view}.jpg",
                "bytes": 100_000,
                "elapsed_seconds": 12.5,
                "started_at": "2026-09-08T00:00:00+00:00",
                "finished_at": "2026-09-08T00:00:13+00:00",
            }
            for view, camera in validation.CAMERAS.items()
        ],
    }


class DeliveryValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "scene").mkdir()
        (self.root / "renders").mkdir()
        (self.root / "docs").mkdir()
        self.blend = self.root / "scene/room.blend"
        self.blend.write_bytes(b"test source fingerprint only")
        self.digest = hashlib.sha256(self.blend.read_bytes()).hexdigest()
        self.write_json(
            "docs/native-validation.json",
            {
                "status": "passed",
                "checks": {"example": True},
                "source_sha256": self.digest,
            },
        )

    def tearDown(self):
        self.temporary.cleanup()

    def write_json(self, path, data):
        (self.root / path).write_text(json.dumps(data), encoding="utf-8")

    def assert_batch_rejected(self, stats, message):
        with self.assertRaisesRegex(AssertionError, message):
            validation.validate_render_batch(stats, self.root)

    def test_jpeg_frame_dimensions_are_read_from_bytes(self):
        # Isolated marker-parser fixture, not a claimed decodable delivery image.
        frame = (
            b"\xff\xd8\xff\xe0\x00\x06TEST\xff\xc2"
            + struct.pack(">HBHHB", 8, 8, 1200, 1600, 0)
            + b"\xff\xd9"
        )
        self.assertEqual(validation.jpeg_dimensions(frame), [1600, 1200])

    def test_truncated_jpeg_segment_rejected(self):
        with self.assertRaisesRegex(AssertionError, "overrun"):
            validation.jpeg_dimensions(b"\xff\xd8\xff\xe0\xff\xff\xff\xd9")

    def test_running_batch_rejected(self):
        self.assert_batch_rejected({"status": "running"}, "not complete")

    def test_partial_batch_rejected_even_if_marked_complete(self):
        stats = complete_metadata()
        stats["renders"].pop()
        self.assert_batch_rejected(stats, "exactly four")

    def test_repeated_camera_rejected(self):
        stats = complete_metadata()
        stats["renders"][1]["camera"] = "Camera_Bedroom"
        self.assert_batch_rejected(stats, "repeat a camera")

    def test_preview_resolution_rejected(self):
        stats = complete_metadata()
        stats["resolution"] = [800, 600]
        self.assert_batch_rejected(stats, "at least 1600x1200")

    def test_preview_samples_rejected(self):
        stats = complete_metadata()
        stats["samples"] = 24
        self.assert_batch_rejected(stats, "at least 64")

    def test_per_view_resolution_mismatch_rejected(self):
        stats = complete_metadata()
        stats["renders"][0]["resolution"] = [800, 600]
        self.assert_batch_rejected(stats, "resolution disagrees")

    def test_unfinished_view_rejected(self):
        stats = complete_metadata()
        stats["renders"][0]["status"] = "running"
        self.assert_batch_rejected(stats, "Render is not complete")

    def test_legacy_hash_evidence_is_explicitly_delivery_time(self):
        result = validation.validate_source_hash(self.blend, complete_metadata(), self.root)
        self.assertFalse(result["hash_recorded_at_render_start"])
        self.assertTrue(result["matches_native_audit"])
        self.assertIn("did not record a pre-render hash", result["hash_evidence"])

    def test_changed_source_rejected_for_legacy_run(self):
        self.blend.write_bytes(b"changed after native audit")
        with self.assertRaisesRegex(AssertionError, "stale"):
            validation.validate_source_hash(self.blend, complete_metadata(), self.root)

    def test_new_build_uses_its_own_pre_render_hash(self):
        self.blend.write_bytes(b"deliberately rebuilt source")
        stats = complete_metadata()
        stats["source_scene_sha256_at_start"] = hashlib.sha256(self.blend.read_bytes()).hexdigest()
        result = validation.validate_source_hash(self.blend, stats, self.root)
        self.assertTrue(result["hash_recorded_at_render_start"])
        self.assertFalse(result["matches_native_audit"])

    def test_mismatched_pre_render_hash_rejected(self):
        stats = complete_metadata()
        stats["source_scene_sha256_at_start"] = "0" * 64
        with self.assertRaisesRegex(AssertionError, "changed since"):
            validation.validate_source_hash(self.blend, stats, self.root)

    def assembled_fixture(self):
        original = complete_metadata()
        rerender = complete_metadata()
        rerender["requested_views"] = ["overview"]
        rerender["renders"] = [deepcopy(original["renders"][-1])]
        rerender["renders"][0]["elapsed_seconds"] = 18.0
        rerender["source_scene_sha256_at_start"] = self.digest
        self.write_json("renders/original-batch-stats.json", original)
        self.write_json("renders/overview-rerender-stats.json", rerender)
        assembled = deepcopy(original)
        assembled["renders"][-1] = deepcopy(rerender["renders"][0])
        assembled.update(
            kind="assembled_delivery",
            assembled_at="2026-09-08T00:10:00+00:00",
            record_sources={
                view: "renders/original-batch-stats.json" for view in validation.CAMERAS
            },
        )
        assembled["record_sources"]["overview"] = "renders/overview-rerender-stats.json"
        return assembled

    def test_honest_multi_run_record_selection_accepted(self):
        result = validation.validate_record_provenance(self.assembled_fixture(), self.root)
        self.assertEqual(result["kind"], "assembled_delivery")
        self.assertEqual(len(result["source_batches"]), 2)

    def test_assembled_record_cannot_rewrite_original_timing(self):
        stats = self.assembled_fixture()
        stats["renders"][-1]["elapsed_seconds"] = 1.0
        with self.assertRaisesRegex(
            AssertionError, "changed source evidence field: elapsed_seconds"
        ):
            validation.validate_record_provenance(stats, self.root)

    def test_single_view_preview_and_custom_stats_path_still_parse(self):
        args = renderer.parse_arguments(
            [
                "--view",
                "overview",
                "--resolution",
                "800",
                "--samples",
                "8",
                "--stats-file",
                "renders/probe.json",
            ]
        )
        self.assertEqual((args.view, args.resolution, args.samples), ("overview", 800, 8))
        self.assertEqual(args.stats_file, Path("renders/probe.json"))


if __name__ == "__main__":
    unittest.main()
