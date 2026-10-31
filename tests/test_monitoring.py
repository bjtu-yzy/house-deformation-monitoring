"""Regression tests for measurements, missing data and the public API contract."""
from datetime import date
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

import cv2
from fastapi.testclient import TestClient
import numpy as np

from backend.analysis import analyze_pair, quadrants, temporal_trends
from backend.app import create_app
from backend.config import ROOT, Settings
from backend.matching import SiftMatcher


def raster(name="reference.png"):
    return cv2.imread(str(ROOT / "examples" / name), cv2.IMREAD_GRAYSCALE)


def upload(name="reference.png"):
    return (name, (ROOT / "examples" / name).read_bytes(), "image/png")


class MeasurementTests(unittest.TestCase):
    def test_known_translation_is_measured_in_original_pixels(self):
        result, points = analyze_pair(raster(), raster("target-1.png"), SiftMatcher())
        self.assertEqual(result["valid_regions"], 4)
        self.assertGreater(result["matches_count"], 30)
        self.assertAlmostEqual(result["average_displacement"], 5, delta=.15)
        self.assertAlmostEqual(result["median_dx"], 4, delta=.15)
        self.assertAlmostEqual(result["median_dy"], 3, delta=.15)
        self.assertEqual(len(points), result["matches_count"])

    def test_no_texture_returns_missing_measurement_not_zero(self):
        blank = np.zeros((256, 256), np.uint8)
        result, _ = analyze_pair(blank, blank, SiftMatcher())
        self.assertEqual(result["status"], "unmeasurable")
        self.assertIsNone(result["average_displacement"])
        self.assertTrue(all(row["average_displacement"] is None for row in result["region_results"]))

    def test_mismatched_shapes_are_rejected(self):
        with self.assertRaises(ValueError):
            analyze_pair(np.zeros((256, 256), np.uint8), np.zeros((256, 255), np.uint8), SiftMatcher())

    def test_odd_sized_quadrants_cover_every_pixel(self):
        image = np.arange(65 * 67).reshape(65, 67)
        regions = quadrants(image)
        self.assertEqual(sum(region.size for region, _ in regions), image.size)
        self.assertEqual(len(set(np.concatenate([region.ravel() for region, _ in regions]))), image.size)

    def test_trend_uses_actual_days_and_excludes_missing_values(self):
        samples = []
        for day, value in [("2026-01-01", 1), ("2026-01-03", 3), ("2026-01-10", 10), ("2026-01-11", None)]:
            samples.append({"date": day, "region_results": [
                {"region": f"region{i}", "average_displacement": value if i == 1 else None} for i in range(1, 5)]})
        result = temporal_trends(samples)
        self.assertAlmostEqual(result["regions"][0]["slope_px_per_day"], 1)
        self.assertEqual(result["regions"][0]["missing_samples"], 1)
        self.assertEqual(result["regions"][1]["trend"], "insufficient_data")
        self.assertIsNone(result["regions"][1]["slope_px_per_day"])


class ApiTests(unittest.TestCase):
    def setUp(self):
        directory = (ROOT / "var" / "test-work").resolve()
        assert directory.is_relative_to(ROOT)
        directory.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=directory)
        self.client = TestClient(create_app(Settings(Path(self.temp.name))))

    def tearDown(self):
        self.client.close()
        assert Path(self.temp.name).resolve().is_relative_to(ROOT / "var" / "test-work")
        self.temp.cleanup()

    def test_ui_health_and_empty_real_history(self):
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.get("/api/history").json(), {"items": []})
        health = self.client.get("/api/health").json()
        self.assertTrue(health["engines"]["sift"]["available"])
        self.assertFalse(health["engines"]["superglue"]["available"])

    def test_pair_report_artifact_csv_and_persisted_history(self):
        response = self.client.post("/api/analyze/upload", data={"engine": "sift"},
                                    files={"image1": upload(), "image2": upload("target-1.png")})
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertAlmostEqual(result["average_displacement"], 5, delta=.15)
        self.assertEqual(self.client.get(result["match_image_path"]).headers["content-type"], "image/png")
        self.assertEqual(self.client.get(result["report_url"]).json(), result)
        csv = self.client.get(result["report_url"].replace(".json", ".csv"))
        self.assertEqual(len(csv.text.strip().splitlines()), 5)
        self.assertEqual(self.client.get("/api/history").json()["items"][0]["task_id"], result["task_id"])
        self.assertEqual(self.client.get("/api/tasks/not-a-task/report.json").status_code, 404)
        self.assertEqual(self.client.get(f"/api/tasks/{result['task_id']}/config.py").status_code, 422)

    def test_missing_research_model_fails_explicitly(self):
        response = self.client.post("/api/analyze/upload", data={"engine": "superglue"},
                                    files={"image1": upload(), "image2": upload("target-1.png")})
        self.assertEqual(response.status_code, 503)
        self.assertIn("HM_SUPERGLUE_DIR", response.json()["detail"])

    def test_invalid_and_oversize_images_fail_without_results(self):
        response = self.client.post("/api/analyze/upload", data={"engine": "sift"},
                                    files={"image1": ("fake.png", b"not an image", "image/png"), "image2": upload()})
        self.assertEqual(response.status_code, 400)
        response = self.client.post("/api/analyze/upload", data={"engine": "sift"},
                                    files={"image1": ("large.png", b"x" * (12 * 1024 * 1024 + 1), "image/png"), "image2": upload()})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.client.get("/api/history").json()["items"], [])

    def sequence(self, dates):
        return self.client.post("/api/analyze/multi-region",
                                data={"engine": "sift", "base_date": "2025-12-31", "dates": json.dumps(dates)},
                                files=[("base_image", upload()),
                                       ("comparison_images", upload("target-3.png")),
                                       ("comparison_images", upload("target-1.png")),
                                       ("comparison_images", upload("target-2.png"))])

    def test_sequence_sorts_images_with_dates_and_measures_every_point(self):
        response = self.sequence(["2026-01-10", "2026-01-01", "2026-01-03"])
        self.assertEqual(response.status_code, 200, response.text)
        result = response.json()
        self.assertEqual([row["date"] for row in result["comparison_results"]], ["2026-01-01", "2026-01-03", "2026-01-10"])
        for row, expected in zip(result["comparison_results"], [5, 10, 15]):
            self.assertAlmostEqual(row["average_displacement"], expected, delta=.2)
        self.assertTrue(result["trend_analysis"]["has_increasing_trend"])

    def test_invalid_duplicate_or_early_dates_are_rejected(self):
        for dates in [["2026-01-01"] * 3, ["2020-01-01", "2026-01-01", "2026-01-03"],
                      ["bad", "2026-01-01", "2026-01-03"]]:
            self.assertEqual(self.sequence(dates).status_code, 400)


if __name__ == "__main__":
    unittest.main()
