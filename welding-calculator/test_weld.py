import copy
import math
import unittest
from pathlib import Path

from weld_core import SAMPLE, calculate, calculate_energy, load_csv, normalize_plan, recommend_wire
from validation_core import analyze_measurements, load_measurements_csv, save_measurements_csv
from wire_usage import calculate_wire_usage
from approved_wps import FIELDS, find_matching_wps, load_approved_wps
import csv
import tempfile
from unittest.mock import patch


class WeldCoreTests(unittest.TestCase):
    def test_gui_has_wps_tab_without_drawing_tab(self):
        from weld_gui import WeldApp

        app = WeldApp()
        try:
            labels = [app.tabs.tab(tab, "text") for tab in app.tabs.tabs()]
            self.assertNotIn("도면 읽기", labels)
            self.assertIn("사내 승인 조건", labels)
            app.load_sample()
            record = dict(zip(FIELDS, ("WPS-TEST", "A", "담당자", "GMAW", "409", "409Ti", 1.0, 2.0, "butt", "flat", "Ar98O2_2", "예시 로봇 용접기", "ER409Nb", 23.0, 175.0, 290.0)))
            app.approved_wps = [record]
            app.find_approved_wps()
            self.assertEqual(len(app.wps_matches), 1)
            app.apply_matched_wps()
            self.assertEqual(app.rows[0]["vars"]["voltage"].get(), "23.0")
            self.assertNotIn("사내 승인 조건 자료 없음", app.report.get("1.0", "end"))
            self.assertIn("화면 확인용 예시", app.report.get("1.0", "end"))
            self.assertEqual(str(app.rows[0]["widgets"]["materialA"].cget("state")), "normal")
            app.rows[0]["vars"]["materialA"].set("SCM435")
            self.assertEqual(app.rows[0]["vars"]["materialA"].get(), "SCM435")
            app.run_calculation()
            self.assertIn("사내 승인 조건 적용 기록 없음", app.report.get("1.0", "end"))
        finally:
            app.destroy()

    def test_sample_calculation(self):
        plan = normalize_plan(SAMPLE)
        result = calculate(plan)
        self.assertEqual(result["arc"], 180)
        self.assertEqual(result["cycle"], 210)
        self.assertEqual(math.floor(result["day"]), 219)
        self.assertEqual(math.floor(result["month"]), 4827)
        self.assertEqual(math.floor(result["year"]), 57929)

    def test_parallel_stage_uses_longest_row_for_cycle(self):
        raw = copy.deepcopy(SAMPLE)
        raw["rows"][0]["stage"] = "1"
        raw["rows"][1]["stage"] = "1"
        result = calculate(normalize_plan(raw))
        self.assertEqual(result["arc"], 180)
        self.assertEqual(result["weldElapsed"], 120)
        self.assertEqual(result["cycle"], 150)

    def test_product_image_uses_original_file_without_copy(self):
        from PIL import Image
        from weld_gui import WeldApp

        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "shape.png"
            Image.new("RGB", (20, 20), "white").save(source)
            app = WeldApp()
            try:
                with patch("weld_gui.filedialog.askopenfilename", return_value=str(source)):
                    app.attach_product_image()
                self.assertEqual(app.product_image_path, source)
            finally:
                app.clear_product_image()
                app.destroy()

    def test_new_row_gets_unused_stage_after_row_removal(self):
        from weld_gui import WeldApp

        app = WeldApp()
        try:
            app.load_sample()
            app.remove_row(app.rows[0]["frame"])
            app.add_row()
            self.assertEqual(app.rows[-1]["vars"]["stage"].get(), "3")
        finally:
            app.destroy()

    def test_energy_calculation_and_missing_inputs(self):
        plan = normalize_plan(SAMPLE)
        energy = calculate_energy(plan, calculate(plan))
        expected_arc = (24 * 180 * 120 + 22 * 150 * 60) / (3_600_000 * .85)
        self.assertAlmostEqual(energy["arc_kwh"], expected_arc)
        self.assertAlmostEqual(energy["nonarc_kwh"], 30 / 3600)
        self.assertAlmostEqual(energy["part_kwh"], (expected_arc + 30 / 3600) / 2)
        self.assertAlmostEqual(energy["day_kwh"], energy["part_kwh"] * calculate(plan)["day"])
        raw = copy.deepcopy(SAMPLE)
        raw["rows"][1]["current"] = ""
        missing = calculate_energy(normalize_plan(raw), calculate(normalize_plan(raw)))
        self.assertNotIn("cycle_kwh", missing)
        self.assertIn("2번 구간 전류 (A)", missing["missing"])
        raw = copy.deepcopy(SAMPLE)
        raw["efficiency"] = "101"
        with self.assertRaises(ValueError):
            normalize_plan(raw)

    def test_optional_wire_usage_and_measured_length_priority(self):
        self.assertEqual(calculate_wire_usage(normalize_plan(SAMPLE), calculate(normalize_plan(SAMPLE)))["status"], "미입력")
        raw = copy.deepcopy(SAMPLE)
        for row in raw["rows"]:
            row.update(wireName="시험 와이어", wireDiameter="1", wireDensity="7.9", wireFeedSpeed="6", wireExtraFeedLength="0", wireScrap="0")
        raw["rows"][0]["wireFeedLength"] = "10"
        raw["rows"][0]["wireActualArcTime"] = "140"
        raw.update(wireStartKg="15", wireEndKg="14.8", wireMeasuredCycles="2")
        plan = normalize_plan(raw)
        usage = calculate_wire_usage(plan, calculate(plan))
        expected = math.pi / 4 * (10 + 6) * 7.9
        self.assertAlmostEqual(usage["cycle_g"], expected)
        self.assertEqual(usage["rows"][0]["source"], "실측 송급 길이")
        self.assertAlmostEqual(usage["measured_g_cycle"], 100)
        self.assertAlmostEqual(usage["part_g"], expected / 2)

    def test_approved_wps_matches_all_conditions(self):
        record = dict(zip(FIELDS, ("WPS-TEST", "A", "담당자", "GMAW", "409", "409Ti", "1", "2", "butt", "flat", "Ar98O2_2", "예시 로봇 용접기", "ER409Nb", "24", "180", "300")))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "wps.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerow(record)
            catalog = load_approved_wps(path)
        plan = normalize_plan(SAMPLE)
        self.assertEqual(len(find_matching_wps(catalog, plan["rows"][0], plan)), 1)
        changed = dict(plan, gas="other")
        self.assertEqual(find_matching_wps(catalog, plan["rows"][0], changed), [])

    def test_sample_csv(self):
        plan = load_csv(Path(__file__).with_name("예시_용접조건.csv"))
        self.assertEqual(plan["vehicle"], "시험 차종 A")
        self.assertEqual(plan["productName"], "리어 머플러")
        self.assertEqual(len(plan["rows"]), 2)
        self.assertTrue(plan["sample"])
        self.assertEqual(calculate(plan)["arc"], 180)

    def test_wire_candidates(self):
        plan = normalize_plan(SAMPLE)
        self.assertEqual(recommend_wire(plan["rows"][0], plan)["wire"], "ER409Nb")
        plan["rows"][0]["materialA"] = plan["rows"][0]["materialB"] = "304L"
        self.assertIn("ER308L", recommend_wire(plan["rows"][0], plan)["wire"])
        plan["rows"][0]["materialA"] = "carbon"
        plan["gas"] = "Ar98CO2_2"
        self.assertEqual(recommend_wire(plan["rows"][0], plan)["wire"], "ER309LSi")

    def test_invalid_values(self):
        raw = copy.deepcopy(SAMPLE)
        raw["rows"][0]["speed"] = "0"
        with self.assertRaises(ValueError):
            normalize_plan(raw)
        raw = copy.deepcopy(SAMPLE)
        raw["batch"] = "1.5"
        with self.assertRaises(ValueError):
            normalize_plan(raw)
        raw = copy.deepcopy(SAMPLE)
        raw["uptime"] = "0"
        self.assertEqual(calculate(normalize_plan(raw))["uph"], 0)

    def test_material_only_candidate(self):
        row = {"materialA": "409", "materialB": "409Ti"}
        candidate = recommend_wire(row, {})
        self.assertEqual(candidate["wire"], "ER409Nb")
        self.assertEqual(candidate["status"], "재질 기반 예비 후보")
        self.assertIn("보호가스", candidate["missing"])

    def test_manufacturer_products_match_classification(self):
        cases = [
            ("409", "409Ti", "ER409Nb", {"KISWEL", "ESAB"}),
            ("304L", "304L", "ER308LSi", {"KISWEL", "KOWEL", "ESAB", "HYUNDAI"}),
            ("304", "304", "ER308", {"KISWEL", "KOWEL", "HYUNDAI"}),
            ("carbon", "304", "ER309LSi", {"KISWEL", "KOWEL", "ESAB", "HYUNDAI"}),
        ]
        for material_a, material_b, aws, makers in cases:
            with self.subTest(materials=(material_a, material_b)):
                candidate = recommend_wire({"materialA": material_a, "materialB": material_b}, {})
                self.assertEqual({p["maker"] for p in candidate["products"]}, makers)
                self.assertTrue(all(p["aws"] == aws and p["url"].startswith("https://") for p in candidate["products"]))
        candidate = recommend_wire({"materialA": "409", "materialB": "409"}, {})
        self.assertEqual(candidate["unverified_makers"], ["KOWEL", "HYUNDAI"])

    def test_measured_cycle_and_quality(self):
        plan = normalize_plan(SAMPLE)
        result = analyze_measurements(plan, calculate(plan), [
            {"cycle": "214", "leak": "합격", "defect": "없음"},
            {"cycle": "209", "leak": "합격", "defect": "없음"},
            {"cycle": "211", "leak": "불합격", "defect": "있음"},
        ], "2")
        self.assertEqual(result["count"], 3)
        self.assertAlmostEqual(result["actual_mean"], 211.33333333333334)
        self.assertTrue(result["within_tolerance"])
        self.assertEqual(result["quality_status"], "불합격·불량 기록 있음")
        self.assertEqual(result["leak_fail_count"], 1)

    def test_measurement_csv_round_trip(self):
        rows = [{"cycle": "214", "leak": "합격", "defect": "없음", "note": "1차"}]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "측정.csv"
            save_measurements_csv(path, "시험 차종 A", "리어 머플러", rows)
            loaded = load_measurements_csv(path)
        self.assertEqual(loaded["vehicle"], "시험 차종 A")
        self.assertEqual(loaded["rows"], rows)


if __name__ == "__main__":
    unittest.main()
