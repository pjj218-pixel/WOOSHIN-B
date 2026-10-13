"""실측 사이클과 검사 기록을 계산 결과와 비교한다."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLayout, QLineEdit, QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

from qt_result_page import number
from validation_core import (
    DEFECT_VALUES, LEAK_VALUES, analyze_measurements,
    load_measurements_csv, save_measurements_csv,
)


class MeasurementCard(QFrame):
    remove_requested = Signal(object)

    def __init__(self, index, values=None):
        super().__init__()
        self.setObjectName("card")
        values = values or {}
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.title = QLabel(f"실측 {index}")
        self.title.setObjectName("sectionTitle")
        header.addWidget(self.title)
        header.addStretch()
        self.remove_button = QPushButton("측정 삭제")
        self.remove_button.setObjectName("ghostButton")
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self))
        header.addWidget(self.remove_button)
        layout.addLayout(header)
        grid = QGridLayout()
        self.widgets = {}
        for col, (key, label) in enumerate((
            ("cycle", "실측 사이클 시간 (초)"), ("leak", "기밀 검사"),
            ("defect", "불량 여부"), ("note", "메모"),
        )):
            box = QWidget()
            box.setObjectName("fieldBox")
            field = QVBoxLayout(box)
            field.setContentsMargins(0, 0, 0, 0)
            caption = QLabel(label)
            caption.setObjectName("fieldLabel")
            field.addWidget(caption)
            if key in ("leak", "defect"):
                widget = QComboBox()
                widget.addItems(LEAK_VALUES if key == "leak" else DEFECT_VALUES)
                widget.setCurrentText(str(values.get(key) or "미검사"))
            else:
                widget = QLineEdit(str(values.get(key) or ""))
            field.addWidget(widget)
            self.widgets[key] = widget
            grid.addWidget(box, 0, col)
        layout.addLayout(grid)

    def values(self):
        return {key: widget.currentText() if isinstance(widget, QComboBox) else widget.text()
                for key, widget in self.widgets.items()}


class ValidationPage(QWidget):
    analyze_requested = Signal()

    def __init__(self, work_page):
        super().__init__()
        self.work_page = work_page
        self.cards = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setSizeConstraint(QLayout.SetMinimumSize)
        layout.setContentsMargins(16, 18, 16, 22)
        layout.setSpacing(13)
        scroll.setWidget(body)
        top = QHBoxLayout()
        title = QLabel("실측 검증")
        title.setObjectName("pageTitle")
        top.addWidget(title)
        top.addStretch()
        add = QPushButton("+ 측정 추가")
        add.setObjectName("ghostButton")
        add.clicked.connect(lambda: self.add_measurement())
        top.addWidget(add)
        load = QPushButton("실측 CSV 불러오기")
        load.setObjectName("ghostButton")
        load.clicked.connect(self.choose_load_csv)
        top.addWidget(load)
        save = QPushButton("실측 CSV 저장")
        save.setObjectName("ghostButton")
        save.clicked.connect(self.choose_save_csv)
        top.addWidget(save)
        compare = QPushButton("실측값 비교")
        compare.clicked.connect(self.analyze_requested)
        top.addWidget(compare)
        layout.addLayout(top)
        tolerance_row = QHBoxLayout()
        tolerance_row.addWidget(QLabel("허용 오차율 (%)"))
        self.tolerance = QLineEdit()
        self.tolerance.setFixedWidth(90)
        tolerance_row.addWidget(self.tolerance)
        tolerance_row.addStretch()
        layout.addLayout(tolerance_row)
        self.status = QLabel("같은 제품·설비 조건의 실측 사이클과 기밀·불량 기록을 입력하세요.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(11)
        layout.addLayout(self.rows_layout)
        self.report = QTextEdit()
        self.report.setReadOnly(True)
        self.report.setMinimumHeight(270)
        layout.addWidget(self.report)
        layout.addStretch()
        self.add_measurement()

    def add_measurement(self, data=None):
        card = MeasurementCard(len(self.cards) + 1, data)
        card.remove_requested.connect(lambda current: self.remove_measurement(self.cards.index(current)))
        self.cards.append(card)
        self.rows_layout.addWidget(card)
        self._refresh()
        return card

    def remove_measurement(self, index):
        if len(self.cards) <= 1:
            return
        card = self.cards.pop(index)
        self.rows_layout.removeWidget(card)
        card.hide()
        card.deleteLater()
        self._refresh()

    def _refresh(self):
        for index, card in enumerate(self.cards, 1):
            card.title.setText(f"실측 {index}")
            card.remove_button.setEnabled(len(self.cards) > 1)

    def measurements(self):
        return [card.values() for card in self.cards]

    def set_measurements(self, rows):
        for card in self.cards:
            self.rows_layout.removeWidget(card)
            card.deleteLater()
        self.cards.clear()
        for row in rows:
            self.add_measurement(row)
        if not self.cards:
            self.add_measurement()
        self.report.clear()

    def analyze(self, plan, production):
        result = analyze_measurements(plan, production, self.measurements(), self.tolerance.text())
        self.status.setText(f"실측 {result['count']}건 비교 · {result['quality_status']} · 양산 승인 아님")
        lines = [
            f"제품: {plan['vehicle'] or '미입력'} · {plan['productName'] or '미입력'}",
            f"계산 사이클: {number(result['estimated'])}초",
            f"실측 평균: {number(result['actual_mean'])}초 (최소 {number(result['minimum'])}, 최대 {number(result['maximum'])})",
            f"오차(계산 - 실측): {result['error_seconds']:+.2f}초 ({result['error_pct']:+.2f}%)",
            f"실측 평균 기준 UPH 추정: {number(result['actual_uph'])}개/시간",
            f"기밀 불합격 {result['leak_fail_count']}건 · 불량 있음 {result['defect_count']}건",
            f"품질 상태: {result['quality_status']}",
        ]
        if result["tolerance"] is not None:
            lines.append(f"허용 오차 ±{number(result['tolerance'])}%: "
                         f"{'범위 안' if result['within_tolerance'] else '범위 밖'}")
        lines.append(f"비아크 시간 참고값: {number(result['suggested_nonarc'])}초")
        if result["count"] < 3:
            lines.append("실측 표본이 3건 미만입니다. 반복 측정 후 다시 비교하세요.")
        lines.append("이 결과는 용접 조건이나 생산능력을 자동 승인하지 않습니다.")
        self.report.setPlainText("\n".join(lines))
        return result

    def load_csv(self, path, vehicle="", product_name=""):
        if not path:
            return False
        try:
            data = load_measurements_csv(path)
        except (OSError, UnicodeError, ValueError) as exc:
            self.status.setText(f"실측 CSV 입력 확인: {exc}")
            return False
        if (vehicle and vehicle != data["vehicle"]) or (product_name and product_name != data["productName"]):
            self.status.setText("실측 CSV의 차종·제품명이 현재 입력과 다릅니다.")
            return False
        if not vehicle:
            self.work_page.common["vehicle"].setText(data["vehicle"])
        if not product_name:
            self.work_page.common["productName"].setText(data["productName"])
        self.set_measurements(data["rows"])
        self.status.setText(f"{Path(path).name} · 실측 {len(data['rows'])}건 불러옴")
        return True

    def save_csv(self, path, vehicle, product_name):
        if not path:
            return False
        try:
            save_measurements_csv(path, vehicle, product_name, self.measurements())
        except OSError as exc:
            self.status.setText(f"실측 CSV 저장 실패: {exc}")
            return False
        self.status.setText(f"실측 {len(self.cards)}건 저장: {Path(path).name}")
        return True

    def choose_load_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "실측 CSV 선택", "", "CSV 파일 (*.csv)")
        if path:
            raw = self.work_page.raw_plan()
            self.load_csv(path, raw["vehicle"], raw["productName"])

    def choose_save_csv(self):
        raw = self.work_page.raw_plan()
        try:
            from weld_core import calculate, normalize_plan
            plan = normalize_plan(raw)
            analyze_measurements(plan, calculate(plan), self.measurements(), self.tolerance.text())
        except ValueError as exc:
            self.status.setText(f"저장 전 입력 확인: {exc}")
            return
        path, _ = QFileDialog.getSaveFileName(self, "실측 CSV 저장", "", "CSV 파일 (*.csv)")
        if path:
            self.save_csv(path, plan["vehicle"], plan["productName"])
