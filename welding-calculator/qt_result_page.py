"""계산 수치와 제조사 와이어 후보를 구분해 보여주는 화면."""

import math

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QScrollArea,
    QLayout, QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

from wire_catalog import MAKERS
from wire_usage import calculate_wire_usage


def number(value, places=2):
    return f"{value:,.{places}f}".rstrip("0").rstrip(".")


def _table(headers):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.verticalHeader().hide()
    return table


def _add_row(table, values):
    index = table.rowCount()
    table.insertRow(index)
    for column, value in enumerate(values):
        table.setItem(index, column, QTableWidgetItem(str(value)))
    return index


class ResultPage(QWidget):
    def __init__(self):
        super().__init__()
        self.last_numbers = None
        self.last_candidates = []
        self.source_links = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)
        summary_scroll = QScrollArea()
        summary_scroll.setWidgetResizable(True)
        summary_scroll.setFrameShape(QFrame.NoFrame)
        self.tabs.addTab(summary_scroll, "한눈에 보기")
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setSizeConstraint(QLayout.SetMinimumSize)
        layout.setContentsMargins(16, 18, 16, 22)
        layout.setSpacing(15)
        summary_scroll.setWidget(body)
        self.product = QLabel("계산 결과가 여기에 표시됩니다.")
        self.product.setObjectName("pageTitle")
        layout.addWidget(self.product)
        self.note = QLabel("입력값을 확인한 뒤 계산하기를 누르세요.")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.image_label.setVisible(False)
        layout.addWidget(self.image_label)
        cards = QGridLayout()
        self.metric_values = {}
        for index, (key, label) in enumerate((
            ("arc", "총 아크 시간"), ("cycle", "사이클 시간"),
            ("uph", "예상 UPH"), ("energy", "제품당 전력량"),
        )):
            card = QFrame()
            card.setObjectName("card")
            content = QVBoxLayout(card)
            content.addWidget(QLabel(label))
            value = QLabel("—")
            value.setStyleSheet("font-size: 24px; font-weight: 800; color: #087d76; background: transparent;")
            content.addWidget(value)
            self.metric_values[key] = value
            cards.addWidget(card, 0, index)
        layout.addLayout(cards)
        heading = QLabel("기간별 예상치")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        self.production_table = _table(("기간", "예상 생산량", "전력량 (kWh)", "와이어 (kg)"))
        self.production_table.setMinimumHeight(170)
        layout.addWidget(self.production_table)
        heading = QLabel("용접 구간별 입력·시간")
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        self.segment_table = _table(("구간", "단계", "길이 (mm)", "시간 (초)", "전압 (V)", "전류 (A)"))
        self.segment_table.setMinimumHeight(170)
        layout.addWidget(self.segment_table)
        self.footer = QLabel("")
        self.footer.setWordWrap(True)
        layout.addWidget(self.footer)
        layout.addStretch()

        products = QWidget()
        product_layout = QVBoxLayout(products)
        self.wire_heading = QLabel("재질을 입력하면 브랜드별 시험 후보를 확인할 수 있습니다.")
        self.wire_heading.setObjectName("sectionTitle")
        product_layout.addWidget(self.wire_heading)
        product_layout.addWidget(QLabel("제품 행을 두 번 클릭하면 제조사 자료가 열립니다."))
        self.product_table = _table(("구간", "브랜드", "제품명", "AWS", "상태"))
        self.product_table.cellDoubleClicked.connect(self._open_source)
        product_layout.addWidget(self.product_table)
        self.product_note = QLabel("표시된 제품은 시편 시험 및 사내 승인 전 검토 후보입니다.")
        self.product_note.setWordWrap(True)
        product_layout.addWidget(self.product_note)
        self.tabs.addTab(products, "와이어 추천 제품")

        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.tabs.addTab(self.details, "계산 근거·안내")

    def show_calculation(self, plan, production, energy, candidates, source="사용자 입력", approved_records=None):
        self.last_numbers = production
        self.last_candidates = candidates
        self.product.setText(f"{plan['vehicle'] or '차종 미입력'} · {plan['productName'] or '제품명 미입력'}")
        self.note.setText(f"{source}  |  미검증 추정" + ("  |  화면 확인용 예시 데이터" if plan["sample"] else ""))
        self.metric_values["arc"].setText(f"{number(production['arc'])}초")
        self.metric_values["cycle"].setText(f"{number(production['cycle'])}초")
        self.metric_values["uph"].setText(f"{number(production['uph'])}개/시간")
        self.metric_values["energy"].setText(
            f"{number(energy['part_kwh'], 5)} kWh" if "part_kwh" in energy else "입력 필요"
        )
        try:
            usage = calculate_wire_usage(plan, production)
        except ValueError as exc:
            usage = {"status": "입력 오류", "missing": [str(exc)]}
        self.production_table.setRowCount(0)
        for label, key, energy_key, wire_key in (
            ("시간", "uph", "hour_kwh", "hour_kg"),
            ("일", "day", "day_kwh", "day_kg"),
            ("월", "month", "month_kwh", "month_kg"),
            ("년", "year", "year_kwh", "year_kg"),
        ):
            units = number(production[key]) if key == "uph" else f"{math.floor(production[key]):,}"
            wire_text = number(usage[wire_key], 5) if wire_key in usage else "입력 확인" if usage["status"] == "입력 오류" else "선택 입력"
            _add_row(self.production_table, (label, units,
                    number(energy[energy_key], 5) if energy_key in energy else "입력 필요", wire_text))
        self.segment_table.setRowCount(0)
        for index, row in enumerate(plan["rows"], 1):
            _add_row(self.segment_table, (index, row["stage"], number(row["length"]),
                     number(row["time"]), number(row["voltage"]) if row["voltage"] is not None else "—",
                     number(row["current"]) if row["current"] is not None else "—"))
        notes = []
        if energy["missing"]:
            notes.append("전력량 입력 필요: " + ", ".join(energy["missing"]))
        if usage.get("missing"):
            notes.append("와이어 사용량 확인: " + ", ".join(usage["missing"]))
        notes.append("기간별 수치는 입력한 가동률과 일정에 따른 계획용 추정치입니다.")
        self.footer.setText("\n".join(notes))
        self._render_products(candidates, plan)
        lines = [
            "용접 시간·생산량 계산 근거",
            f"제품: {self.product.text()}", f"출처: {source} / 검증 상태: 미검증 추정",
            f"총 아크 시간: {number(production['arc'])}초",
            f"경과 용접 시간: {number(production['weldElapsed'])}초",
            f"사이클 = 경과 용접 시간 {number(production['weldElapsed'])} + 비아크 시간 {number(plan['nonArc'])} = {number(production['cycle'])}초",
            f"UPH = 3,600 ÷ {number(production['cycle'])} × {plan['batch']} × {number(plan['uptime'])}% = {number(production['uph'])}",
        ]
        if plan["sample"]:
            lines.append("화면 확인용 예시입니다. 양산 조건·확정 생산능력으로 사용하지 마세요.")
        for index, row in enumerate(plan["rows"], 1):
            formula = (f"{number(row['length'])} mm ÷ {number(row['speed'])} mm/min × 60"
                       if row["mode"] == "speed" else "직접 입력")
            lines.append(f"{index}번 구간 · 단계 {row['stage']}: {formula} = {number(row['time'])}초")
            lines.append(approved_records[index - 1] if approved_records else
                         "  사내 승인 조건 적용 기록 없음. 입력값의 승인 여부를 확인하세요.")
        if "cycle_kwh" in energy:
            lines.append(f"용접 중 설비 입력 전력량: {number(energy['arc_kwh'], 5)} kWh/사이클")
            lines.append(f"비아크 설비 입력 전력량: {number(energy['nonarc_kwh'], 5)} kWh/사이클")
            lines.append(f"예상 전력량: {number(energy['cycle_kwh'], 5)} kWh/사이클 · {number(energy['part_kwh'], 5)} kWh/개")
            lines.append("용접 중 = Σ(전압 × 전류 × 아크 시간) ÷ (3,600,000 × 효율). 비아크 = 설비 입력전력 × 비아크 시간 ÷ 3,600.")
        else:
            lines.append("전력량 계산에 필요한 값: " + ", ".join(energy["missing"]))
        lines.extend(notes)
        lines.append("와이어 후보와 전력량은 실측·시편 시험 및 사내 승인 전 검토 자료입니다.")
        self.details.setPlainText("\n".join(lines))
        self.tabs.setCurrentIndex(0)

    def show_wire_only(self, candidates, raw=None):
        raw = raw or {}
        self.last_numbers = None
        self.last_candidates = candidates
        self.product.setText(f"{raw.get('vehicle') or '차종 미입력'} · {raw.get('productName') or '제품명 미입력'}")
        self.note.setText("재질 기반 예비 후보 · 시간과 생산량은 계산하기로 확인하세요.")
        for value in self.metric_values.values():
            value.setText("—")
        self.production_table.setRowCount(0)
        self.segment_table.setRowCount(0)
        self.footer.setText("재질만으로 와이어 후보를 볼 수 있습니다. 양산 승인 조건은 아닙니다.")
        self._render_products(candidates, raw)
        self.details.setPlainText("재질 기반 와이어 예비 후보\n\n전압·전류·송급 속도는 제시하지 않습니다.\n시편 시험과 사내 승인을 거쳐 사용하세요.")
        self.tabs.setCurrentIndex(1)

    def set_image(self, path):
        if not path:
            self.image_label.clear()
            self.image_label.setVisible(False)
            return
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self.image_label.clear()
            self.image_label.setVisible(False)
            return
        self.image_label.setPixmap(pixmap.scaled(320, 190, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.image_label.setVisible(True)

    def _render_products(self, candidates, plan):
        self.product_table.setRowCount(0)
        self.source_links.clear()
        self.wire_heading.setText(f"{plan.get('vehicle') or '차종 미입력'} · {plan.get('productName') or '제품명 미입력'}")
        notes = []
        for segment, candidate in enumerate(candidates, 1):
            if "wire" not in candidate:
                _add_row(self.product_table, (segment, "—", "—", "—", candidate["status"]))
                notes.append(f"{segment}번: {candidate['message']}")
                continue
            products = {product["maker"]: product for product in candidate["products"]}
            for maker in MAKERS:
                product = products.get(maker)
                brand = "COWEL (KOWEL)" if maker == "KOWEL" else maker
                index = _add_row(self.product_table, (
                    segment, brand, product["name"] if product else "—",
                    product["aws"] if product else "—",
                    candidate["status"] if product else "동일 분류 제품 미확인",
                ))
                if product:
                    self.source_links[index] = product["url"]
            notes.append(f"{segment}번 {candidate['wire']}: {candidate['reason']}")
            notes.append(candidate["gas_note"])
            if candidate["missing"]:
                notes.append("추가 확인: " + ", ".join(candidate["missing"]))
        notes.append("제품별 보호가스·직경·공급 여부와 실제 이음 적용성은 별도 확인하세요.")
        self.product_note.setText("\n".join(notes))

    def _open_source(self, row, _column):
        if row in self.source_links:
            QDesktopServices.openUrl(QUrl(self.source_links[row]))
