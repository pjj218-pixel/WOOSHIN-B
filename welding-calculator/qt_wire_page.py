"""와이어 송급량·단가 및 실측 잔량 입력 화면."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QLayout, QLineEdit, QPushButton,
    QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

from wire_usage import WIRE_COMMON_FIELDS, WIRE_ROW_FIELDS, calculate_wire_usage
from qt_result_page import number


WIRE_LABELS = {
    "wireName": "사용 와이어 제품명", "wireDiameter": "와이어 직경 (mm)",
    "wireDensity": "와이어 밀도 (g/cm³)", "wireFeedSpeed": "평균 송급 속도 (m/min)",
    "wireFeedLength": "실측 송급 길이 (m/사이클)", "wireActualArcTime": "실측 아크 시간 (초)",
    "wireExtraFeedLength": "추가 송급 길이 (m)", "wireScrap": "절단·폐기량 (g)",
    "wireDepositionEfficiency": "용착 효율 (%)", "wirePrice": "와이어 단가 (원/kg)",
    "wireStartKg": "시작 잔량 합계 (kg)", "wireEndKg": "종료 잔량 합계 (kg)",
    "wireMeasuredCycles": "실측 생산 사이클 수",
}


class WirePage(QWidget):
    calculate_requested = Signal()

    def __init__(self, work_page):
        super().__init__()
        self.work_page = work_page
        self.row_fields = []
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
        layout.setSpacing(14)
        scroll.setWidget(body)
        top = QHBoxLayout()
        heading = QLabel("와이어 사용량")
        heading.setObjectName("pageTitle")
        top.addWidget(heading)
        top.addStretch()
        calculate_button = QPushButton("와이어 사용량 계산")
        calculate_button.clicked.connect(self.calculate_requested)
        top.addWidget(calculate_button)
        layout.addLayout(top)
        layout.addWidget(QLabel("실제 송급 설정 또는 측정값을 입력하세요. 전류·전압만으로 송급량을 역산하지 않습니다."))
        self.status = QLabel("선택 입력입니다. 비워 두어도 시간과 생산량 계산에는 영향이 없습니다.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.rows_container = QVBoxLayout()
        self.rows_container.setSpacing(12)
        layout.addLayout(self.rows_container)
        card = QFrame()
        card.setObjectName("card")
        content = QVBoxLayout(card)
        title = QLabel("실측 와이어 잔량 비교")
        title.setObjectName("sectionTitle")
        content.addWidget(title)
        grid = QGridLayout()
        self.common_fields = {}
        for col, key in enumerate(WIRE_COMMON_FIELDS):
            edit = self._field(grid, 0, col, key)
            edit.textChanged.connect(lambda value, field=key: self._set_common(field, value))
            self.common_fields[key] = edit
        content.addLayout(grid)
        content.addWidget(QLabel("같은 와이어·같은 용기 기준으로 계량하고 교체 시 투입량을 반영하세요."))
        layout.addWidget(card)
        self.report = QTextEdit()
        self.report.setReadOnly(True)
        self.report.setMinimumHeight(250)
        layout.addWidget(self.report)
        layout.addStretch()
        self.sync_rows()

    def _field(self, grid, row, col, key):
        box = QWidget()
        box.setObjectName("fieldBox")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel(WIRE_LABELS[key])
        title.setObjectName("fieldLabel")
        box_layout.addWidget(title)
        edit = QLineEdit()
        edit.setObjectName(key)
        box_layout.addWidget(edit)
        grid.addWidget(box, row, col)
        return edit

    def sync_rows(self):
        for edit in self.common_fields.values():
            edit.blockSignals(True)
        for key, edit in self.common_fields.items():
            edit.setText(self.work_page.wire_common.get(key, ""))
            edit.blockSignals(False)
        while self.rows_container.count():
            item = self.rows_container.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.row_fields = []
        for index, card in enumerate(self.work_page.rows, 1):
            frame = QFrame()
            frame.setObjectName("card")
            box = QVBoxLayout(frame)
            label = QLabel(f"용접 구간 {index} · 와이어 입력")
            label.setObjectName("sectionTitle")
            box.addWidget(label)
            grid = QGridLayout()
            fields = {}
            for pos, key in enumerate(WIRE_ROW_FIELDS):
                edit = self._field(grid, pos // 3, pos % 3, key)
                edit.setText(card.wire_values.get(key, ""))
                edit.textChanged.connect(lambda value, row_card=card, field=key:
                                         self._set_row(row_card, field, value))
                fields[key] = edit
            box.addLayout(grid)
            box.addWidget(QLabel("실측 송급 길이를 입력하면 송급 속도 × 아크 시간 대신 사용합니다."))
            self.rows_container.addWidget(frame)
            self.row_fields.append(fields)

    def set_row_value(self, index, key, value):
        self.row_fields[index][key].setText(str(value))

    def _set_common(self, key, value):
        self.work_page.wire_common[key] = value
        self.work_page.mark_changed()

    def _set_row(self, card, key, value):
        card.wire_values[key] = value
        self.work_page.mark_changed()

    def calculate(self, plan, production):
        result = calculate_wire_usage(plan, production)
        self.status.setText(f"와이어 사용량: {result['status']} · 송급량 추정과 잔량 실측을 구분하세요.")
        lines = [f"제품: {plan['vehicle'] or '미입력'} · {plan['productName'] or '미입력'}"]
        if result["status"] == "미입력":
            lines.append("구간별 와이어 정보가 입력되지 않았습니다.")
        else:
            for index, item in enumerate(result["rows"], 1):
                if "used_g" in item:
                    lines.append(f"{index}번 · {item['name']} · {item['source']}: "
                                 f"송급 {number(item['fed_g'], 5)} g + 폐기 {number(item['scrap_g'], 5)} g "
                                 f"= {number(item['used_g'], 5)} g/사이클")
                    if item["deposited_g"] is not None:
                        lines.append(f"  예상 용착량 {number(item['deposited_g'], 5)} g")
                else:
                    lines.append(f"{index}번 · 입력 자료 부족")
            if result["missing"]:
                lines.append("필요한 값: " + ", ".join(result["missing"]))
            else:
                lines.append(f"사이클당 {number(result['cycle_g'], 5)} g · 제품당 {number(result['part_g'], 5)} g")
                lines.append(f"시간 {number(result['hour_kg'], 5)} kg · 일 {number(result['day_kg'], 5)} kg · "
                             f"월 {number(result['month_kg'], 5)} kg · 년 {number(result['year_kg'], 5)} kg")
                if "cost_cycle" in result:
                    lines.append(f"예상 비용: {number(result['cost_cycle'])} 원/사이클 · {number(result['cost_part'])} 원/개")
                if "deposited_g" in result:
                    lines.append(f"용착 효율 적용 예상 용착량: {number(result['deposited_g'], 5)} g/사이클")
            if "measured_g_cycle" in result:
                lines.append(f"잔량 실측: {number(result['measured_g_cycle'], 5)} g/사이클")
                if "difference_g" in result:
                    difference = f"실측 - 추정: {result['difference_g']:+.5f} g/사이클"
                    if result["difference_pct"] is not None:
                        difference += f" ({result['difference_pct']:+.2f}%)"
                    lines.append(difference)
            if result["omitted_extras"] or result["omitted_scrap"]:
                lines.append("빈 추가 송급·절단·폐기 항목은 사용량 추정에 포함되지 않았습니다.")
        lines.append("전류·전압만으로 와이어 사용량을 역산하지 않습니다. 실측으로 비교하세요.")
        self.report.setPlainText("\n".join(lines))
        return result
