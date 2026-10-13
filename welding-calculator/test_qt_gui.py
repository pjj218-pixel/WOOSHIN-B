"""PySide6 화면의 핵심 사용자 흐름 검증."""

import copy
import csv
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QPushButton

from approved_wps import FIELDS
from weld_core import SAMPLE, calculate, normalize_plan, recommend_wire
from qt_app import MainWindow


class QtGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = MainWindow()

    def tearDown(self):
        self.window.close()

    def test_sample_rows_and_bad_csv_keeps_current_input(self):
        self.window.load_sample()
        self.assertEqual(self.window.work_page.raw_plan()["vehicle"], SAMPLE["vehicle"])
        self.assertEqual(len(self.window.work_page.raw_plan()["rows"]), 2)
        next(button for button in self.window.work_page.findChildren(QPushButton)
             if button.text() == "+ 구간 추가").click()
        self.assertEqual(len(self.window.work_page.raw_plan()["rows"]), 3)
        self.window.work_page.remove_row(1)
        self.assertEqual(len(self.window.work_page.raw_plan()["rows"]), 2)
        before = copy.deepcopy(self.window.work_page.raw_plan())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.csv"
            path.write_text("length,mode\n100,speed\n", encoding="utf-8")
            self.assertFalse(self.window.load_conditions_csv(path))
        self.assertEqual(self.window.work_page.raw_plan(), before)

    def test_valid_example_csv_loads_into_new_screen(self):
        self.assertTrue(self.window.load_conditions_csv(Path(__file__).with_name("예시_용접조건.csv")))
        self.assertEqual(len(self.window.work_page.raw_plan()["rows"]), 2)
        self.assertTrue(self.window.calculate_result())
        self.assertEqual(self.window.result_page.metric_values["cycle"].text(), "210초")

    def test_editing_sample_marks_it_as_user_input(self):
        self.window.load_sample()
        self.assertTrue(self.window.work_page.raw_plan()["sample"])
        self.window.work_page.common["nonArc"].setText("35")
        self.assertFalse(self.window.work_page.raw_plan()["sample"])
        self.assertEqual(self.window.source, "사용자 입력")

    def test_sample_result_and_wire_candidates_match_core(self):
        self.window.load_sample()
        self.assertTrue(self.window.calculate_result())
        expected = calculate(normalize_plan(SAMPLE))
        for key in ("arc", "cycle", "uph"):
            self.assertAlmostEqual(self.window.result_page.last_numbers[key], expected[key])
        self.assertEqual(self.window.result_page.last_candidates[0]["wire"],
                         recommend_wire(SAMPLE["rows"][0], SAMPLE)["wire"])
        self.assertEqual(self.window.result_page.metric_values["cycle"].text(), "210초")
        self.assertIn("비아크 설비", self.window.result_page.details.toPlainText())

    def test_unknown_material_and_missing_energy_keep_time_result(self):
        raw = copy.deepcopy(SAMPLE)
        raw["rows"][0].update(materialA="SUS441L", materialB="SS400", voltage="", current="")
        self.window.work_page.load_raw_plan(raw)
        self.assertTrue(self.window.calculate_result())
        self.assertEqual(self.window.result_page.last_candidates[0]["status"], "자료 부족")
        self.assertEqual(self.window.result_page.metric_values["energy"].text(), "입력 필요")
        self.assertEqual(self.window.result_page.metric_values["cycle"].text(), "210초")

    def test_approved_wps_applies_only_exact_selected_row(self):
        self.window.load_sample()
        record = dict(zip(FIELDS, (
            "WPS-TEST", "A", "담당자", "GMAW", "409", "409Ti", 1.0, 2.0,
            "butt", "flat", "Ar98O2_2", "예시 로봇 용접기", "ER409Nb", 23.0, 175.0, 290.0,
        )))
        page = self.window.wps_page
        page.records = [record]
        page.set_context(self.window.work_page.raw_plan(), 0)
        self.assertEqual(len(page.find_matches()), 1)
        self.assertTrue(page.apply_selected())
        self.assertEqual(self.window.work_page.raw_plan()["rows"][0]["voltage"], "23.0")
        self.assertEqual(self.window.work_page.raw_plan()["rows"][1]["voltage"], "22")
        self.assertTrue(self.window.calculate_result())
        self.assertIn("승인 조건 WPS-TEST", self.window.result_page.details.toPlainText())
        self.window.work_page.rows[0].widgets["voltage"].setText("24")
        self.assertTrue(self.window.calculate_result())
        self.assertNotIn("WPS-TEST", self.window.result_page.details.toPlainText())
        page.set_context(self.window.work_page.raw_plan(), 1)
        self.assertEqual(page.find_matches(), [])
        before = copy.deepcopy(self.window.work_page.raw_plan())
        self.assertFalse(page.apply_selected())
        self.assertFalse(page.load_records(""))
        self.assertEqual(self.window.work_page.raw_plan(), before)

    def test_approved_wps_csv_loads_and_applies(self):
        self.window.load_sample()
        values = (
            "WPS-CSV", "B", "담당자", "GMAW", "409", "409Ti", "1", "2",
            "butt", "flat", "Ar98O2_2", "예시 로봇 용접기", "ER409Nb", "23", "175", "290",
        )
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "wps.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.writer(handle)
                writer.writerow(FIELDS)
                writer.writerow(values)
            self.assertTrue(self.window.wps_page.load_records(path))
        self.window.wps_page.set_context(self.window.work_page.raw_plan(), 0)
        self.assertEqual(len(self.window.wps_page.find_matches()), 1)
        self.assertTrue(self.window.wps_page.apply_selected())
        self.assertEqual(self.window.work_page.raw_plan()["rows"][0]["speed"], "290.0")

    def test_wire_inputs_follow_segment_after_removal_and_optional_fields(self):
        self.window.load_sample()
        page = self.window.wire_page
        page.set_row_value(1, "wireName", "M-409Cb")
        page.set_row_value(1, "wireDiameter", "1.2")
        page.set_row_value(1, "wireDensity", "7.8")
        page.set_row_value(1, "wireFeedSpeed", "6")
        self.window.work_page.remove_row(0)
        self.assertEqual(self.window.work_page.raw_plan()["rows"][0]["wireName"], "M-409Cb")
        self.assertEqual(page.row_fields[0]["wireDiameter"].text(), "1.2")
        plan = normalize_plan(self.window.work_page.raw_plan())
        result = page.calculate(plan, calculate(plan))
        self.assertIn("cycle_g", result)
        page.common_fields["wireStartKg"].setText("1")
        page.common_fields["wireEndKg"].setText("0.9")
        page.common_fields["wireMeasuredCycles"].setText("2")
        plan = normalize_plan(self.window.work_page.raw_plan())
        page.calculate(plan, calculate(plan))
        self.assertIn("실측 - 추정", page.report.toPlainText())

    def test_validation_csv_round_trip_and_analysis(self):
        self.window.load_sample()
        page = self.window.validation_page
        page.set_measurements([
            {"cycle": "212", "leak": "합격", "defect": "없음", "note": "첫 측정"},
            {"cycle": "208", "leak": "합격", "defect": "없음", "note": "두 번째"},
        ])
        plan = normalize_plan(self.window.work_page.raw_plan())
        result = page.analyze(plan, calculate(plan))
        self.assertEqual(result["actual_mean"], 210)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "measurements.csv"
            self.assertTrue(page.save_csv(path, plan["vehicle"], plan["productName"]))
            page.set_measurements([{"cycle": "99"}])
            self.assertTrue(page.load_csv(path, plan["vehicle"], plan["productName"]))
        self.assertEqual(len(page.measurements()), 2)

    def test_product_image_preview_appears_in_result_without_copy(self):
        self.window.load_sample()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "shape.png"
            self.assertTrue(QPixmap(32, 20).save(str(path)))
            self.window.work_page.attach_image(path)
            self.assertTrue(self.window.calculate_result())
            self.assertFalse(self.window.result_page.image_label.pixmap().isNull())
            self.assertEqual(list(Path(folder).iterdir()), [path])


if __name__ == "__main__":
    unittest.main()
