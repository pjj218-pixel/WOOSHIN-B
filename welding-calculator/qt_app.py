"""PySide6 용접 계산기 실행 진입점과 화면 전환."""

import copy
from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from qt_work_page import WorkPage
from qt_result_page import ResultPage
from qt_wps_page import WpsPage
from qt_wire_page import WirePage
from qt_validation_page import ValidationPage
from approved_wps import find_matching_wps
from weld_core import SAMPLE, calculate, calculate_energy, load_csv, normalize_plan, recommend_wire


STYLE = """
QMainWindow, QWidget { background: #f4f6f8; color: #172a32; font-family: 'Malgun Gothic'; font-size: 13px; }
QFrame#sidebar { background: #102b35; border: none; }
QFrame#sidebar QLabel { background: transparent; color: #d9e8e8; }
QLabel#brand { color: white; font-size: 20px; font-weight: 800; }
QLabel#pageTitle { font-size: 21px; font-weight: 800; }
QLabel#sectionTitle { font-size: 16px; font-weight: 700; }
QLabel#fieldLabel { background: transparent; color: #53666b; font-size: 12px; font-weight: 600; }
QWidget#fieldBox { background: transparent; }
QLabel#eyebrow { color: #11877f; font-weight: 700; }
QLabel#imagePreview { background: #eaf0f1; border: 1px dashed #b5cbcb; border-radius: 12px; color: #6a7e82; }
QFrame#card { background: white; border: 1px solid #dfe7e9; border-radius: 14px; }
QFrame#card QLabel { background: transparent; }
QTabWidget::pane { border: 0; }
QTabBar::tab { background: #e9eff0; color: #4d666d; border: 0; border-radius: 8px; padding: 9px 17px; margin-right: 6px; }
QTabBar::tab:selected { background: white; color: #0e736d; font-weight: 700; }
QLineEdit, QComboBox { background: white; border: 1px solid #cbd8da; border-radius: 8px; min-height: 31px; padding: 4px 9px; }
QLineEdit:focus, QComboBox:focus { border: 2px solid #168c80; }
QPushButton { background: #117d76; color: white; border: 0; border-radius: 9px; padding: 10px 15px; font-weight: 700; }
QPushButton:hover { background: #0d6b65; }
QPushButton:disabled { background: #aebcbe; }
QPushButton#ghostButton { background: #edf4f4; color: #21575a; }
QPushButton#ghostButton:hover { background: #dbeaea; }
QPushButton#navButton { background: transparent; color: #b7d0d1; text-align: left; border-radius: 8px; }
QPushButton#navButton:hover, QPushButton#navButton[active='true'] { background: #244650; color: white; }
QTableWidget { background: white; alternate-background-color: #f7fafa; border: 1px solid #dfe7e9; border-radius: 8px; gridline-color: #ecf1f1; }
QHeaderView::section { background: #ecf3f4; color: #34535a; padding: 8px; border: 0; font-weight: 700; }
QTextEdit { background: white; border: 1px solid #dfe7e9; border-radius: 10px; padding: 12px; }
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        font_id = QFontDatabase.addApplicationFont("C:/Windows/Fonts/malgun.ttf")
        if font_id >= 0:
            QApplication.instance().setFont(QFont(QFontDatabase.applicationFontFamilies(font_id)[0], 10))
        self.setWindowTitle("용접 생산기술 계산기")
        self.resize(1420, 900)
        self.setMinimumSize(1030, 680)
        self.setStyleSheet(STYLE)
        self.source = "사용자 입력"
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(230)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(18, 26, 18, 22)
        side.setSpacing(7)
        brand = QLabel("WELD · PLAN")
        brand.setObjectName("brand")
        side.addWidget(brand)
        side.addWidget(QLabel("생산기술 업무 도구"))
        side.addSpacing(27)
        self.nav_buttons = {}
        self.stack = QStackedWidget()
        self.pages = {}
        for name in ("작업 조건", "결과", "사내 승인 조건", "와이어 사용량", "실측 검증"):
            button = QPushButton(name)
            button.setObjectName("navButton")
            button.setCursor(Qt.PointingHandCursor)
            button.clicked.connect(lambda checked=False, page=name: self.show_page(page))
            side.addWidget(button)
            self.nav_buttons[name] = button
            if name == "작업 조건":
                page = WorkPage()
                self.work_page = page
            elif name == "결과":
                page = ResultPage()
                self.result_page = page
            elif name == "사내 승인 조건":
                page = WpsPage(self.work_page.raw_plan)
                self.wps_page = page
            elif name == "와이어 사용량":
                page = WirePage(self.work_page)
                self.wire_page = page
            elif name == "실측 검증":
                page = ValidationPage(self.work_page)
                self.validation_page = page
            else:
                page = QWidget()
            self.pages[name] = page
            self.stack.addWidget(page)
        side.addStretch()
        side.addWidget(QLabel("계산값은 미검증 추정치입니다."))
        layout.addWidget(sidebar)
        main = QVBoxLayout()
        main.setContentsMargins(26, 19, 26, 16)
        main.setSpacing(14)
        head = QHBoxLayout()
        head_text = QVBoxLayout()
        eyebrow = QLabel("PRODUCTION ENGINEERING")
        eyebrow.setObjectName("eyebrow")
        head_text.addWidget(eyebrow)
        title = QLabel("용접 시간 · 생산량 · 와이어")
        title.setObjectName("pageTitle")
        head_text.addWidget(title)
        head.addLayout(head_text)
        head.addStretch()
        sample = QPushButton("예시값 불러오기")
        sample.setObjectName("ghostButton")
        sample.clicked.connect(self.load_sample)
        head.addWidget(sample)
        csv_button = QPushButton("CSV 가져오기")
        csv_button.setObjectName("ghostButton")
        csv_button.clicked.connect(self.choose_conditions_csv)
        head.addWidget(csv_button)
        wire = QPushButton("와이어만 추천")
        wire.setObjectName("ghostButton")
        wire.clicked.connect(self.recommend_only)
        head.addWidget(wire)
        calculate = QPushButton("계산하기 →")
        calculate.clicked.connect(self.calculate_result)
        head.addWidget(calculate)
        main.addLayout(head)
        main.addWidget(self.stack, 1)
        self.status = QLabel("값을 입력하거나 예시 CSV를 가져오세요. 결과는 미검증 추정치입니다.")
        self.status.setWordWrap(True)
        main.addWidget(self.status)
        layout.addLayout(main, 1)
        self.wps_page.applied.connect(self._apply_wps)
        self.work_page.rows_changed.connect(lambda: self.wps_page.set_context(self.work_page.raw_plan()))
        self.work_page.rows_changed.connect(self.wire_page.sync_rows)
        self.work_page.changed.connect(self._on_work_changed)
        self.work_page.product_changed.connect(lambda: self.validation_page.set_measurements([{}]))
        self.wire_page.calculate_requested.connect(self.run_wire_usage)
        self.validation_page.analyze_requested.connect(self.run_validation)
        self.wps_page.set_context(self.work_page.raw_plan())
        self.show_page("작업 조건")

    def show_page(self, name):
        self.stack.setCurrentWidget(self.pages[name])
        for label, button in self.nav_buttons.items():
            button.setProperty("active", label == name)
            button.style().unpolish(button)
            button.style().polish(button)

    def replace_page(self, name, widget):
        old = self.pages[name]
        index = self.stack.indexOf(old)
        self.stack.removeWidget(old)
        old.deleteLater()
        self.stack.insertWidget(index, widget)
        self.pages[name] = widget

    def load_sample(self):
        self.work_page.load_raw_plan(copy.deepcopy(SAMPLE))
        self.source = "화면 확인용 예시 데이터"
        self.status.setText("화면 확인용 예시값을 불러왔습니다. 실제 생산 조건이 아닙니다.")
        self.show_page("작업 조건")

    def load_conditions_csv(self, path):
        try:
            raw = load_csv(path)
        except (OSError, UnicodeError, ValueError) as exc:
            self.status.setText(f"CSV 입력 확인: {exc}")
            return False
        self.work_page.load_raw_plan(raw)
        self.source = f"CSV 파일: {Path(path).name}"
        self.status.setText(f"{Path(path).name} 파일을 불러왔습니다.")
        self.show_page("작업 조건")
        return True

    def choose_conditions_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "용접 조건 CSV", "", "CSV 파일 (*.csv)")
        if path:
            self.load_conditions_csv(path)

    def calculate_result(self):
        try:
            plan = normalize_plan(self.work_page.raw_plan())
            numbers = calculate(plan)
        except ValueError as exc:
            self.status.setText(f"입력 확인: {exc}")
            self.show_page("작업 조건")
            return False
        energy = calculate_energy(plan, numbers)
        candidates = [recommend_wire(row, plan) for row in plan["rows"]]
        approved_records = []
        for card, row in zip(self.work_page.rows, plan["rows"]):
            match = card.approved_wps
            if (match and row["mode"] == "speed" and row["voltage"] == match["voltage"]
                    and row["current"] == match["current"] and row["speed"] == match["travelSpeed"]
                    and find_matching_wps([match], row, plan)):
                approved_records.append(
                    f"  승인 조건 {match['approvalId']} · 개정 {match['revision']}에서 전압·전류·속도를 적용. 현행 유효성 확인 필요."
                )
            else:
                approved_records.append("  사내 승인 조건 적용 기록 없음. 입력값의 승인 여부를 확인하세요.")
        self.result_page.show_calculation(plan, numbers, energy, candidates, self.source, approved_records)
        self.result_page.set_image(self.work_page.image_path)
        self.status.setText(f"계산 완료 · {self.source} · 미검증 추정")
        self.show_page("결과")
        return True

    def recommend_only(self):
        raw = self.work_page.raw_plan()
        candidates = [recommend_wire(row, raw) for row in raw["rows"]]
        self.result_page.show_wire_only(candidates, raw)
        self.result_page.set_image(self.work_page.image_path)
        self.status.setText("재질 기반 와이어 예비 후보 · 양산 승인 아님")
        self.show_page("결과")
        return candidates

    def _apply_wps(self, index, values, match):
        self.work_page.apply_row_values(index, values)
        self.work_page.rows[index].approved_wps = match
        self.source = f"사용자 제공 조건표: {match['approvalId']} · 개정 {match['revision']}"
        self.status.setText(f"{index + 1}번 구간에 사내 승인 기록을 적용했습니다. 승인 상태를 확인하세요.")
        self.wire_page.sync_rows()

    def _on_work_changed(self):
        self.source = "사용자 입력"
        self.status.setText("입력이 변경됐습니다. 계산하기를 눌러 결과를 갱신하세요.")
        if self.result_page.last_numbers is not None:
            self.result_page.note.setText("입력이 변경됐습니다. 표시된 결과는 이전 입력값입니다. 계산하기를 눌러 갱신하세요.")

    def run_wire_usage(self):
        try:
            plan = normalize_plan(self.work_page.raw_plan())
            numbers = calculate(plan)
            result = self.wire_page.calculate(plan, numbers)
        except ValueError as exc:
            self.wire_page.status.setText(f"와이어 입력 확인: {exc}")
            return None
        self.show_page("와이어 사용량")
        return result

    def run_validation(self):
        try:
            plan = normalize_plan(self.work_page.raw_plan())
            numbers = calculate(plan)
            result = self.validation_page.analyze(plan, numbers)
        except ValueError as exc:
            self.validation_page.status.setText(f"입력 확인: {exc}")
            return None
        self.show_page("실측 검증")
        return result


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
