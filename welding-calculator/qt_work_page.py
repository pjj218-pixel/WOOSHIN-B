"""제품·공정 조건 입력 화면. 계산은 기존 코어에 위임한다."""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLayout, QLineEdit, QPushButton, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from wire_usage import WIRE_COMMON_FIELDS, WIRE_ROW_FIELDS


COMMON_FIELDS = (
    "vehicle", "productName", "process", "equipment", "gas", "batch",
    "nonArc", "uptime", "hours", "days", "months", "efficiency", "nonArcPower",
)
ROW_FIELDS = (
    "length", "stage", "mode", "speed", "time", "voltage", "current",
    "materialA", "thicknessA", "materialB", "thicknessB", "joint", "position",
)
COMMON_LABELS = {
    "vehicle": "차종", "productName": "제품명", "process": "용접 방식",
    "equipment": "설비명", "gas": "보호가스", "batch": "한 사이클 생산 수량 (개)",
    "nonArc": "비아크 시간 (초)", "uptime": "가동률 (%)",
    "hours": "일일 근무시간", "days": "월간 가동일수", "months": "연간 가동 개월 수",
    "efficiency": "용접기 효율 (%)", "nonArcPower": "비아크 설비 입력전력 (kW)",
}
ROW_LABELS = {
    "length": "용접 길이 (mm)", "stage": "작업 단계", "mode": "시간 입력 방식",
    "speed": "이동 속도 (mm/min)", "time": "직접 입력 시간 (초)",
    "voltage": "전압 (V)", "current": "전류 (A)",
    "materialA": "부품 A 재질", "thicknessA": "A 두께 (mm)",
    "materialB": "부품 B 재질", "thicknessB": "B 두께 (mm)",
    "joint": "이음 형상", "position": "용접 자세",
}
MATERIALS = ("", "409", "409Ti", "304", "304L", "carbon", "other")
CHOICES = {
    "process": ("", "GMAW", "GTAW", "other"),
    "gas": ("", "Ar98O2_2", "Ar98CO2_2", "other"),
    "mode": ("speed", "time"),
    "materialA": MATERIALS, "materialB": MATERIALS,
    "joint": ("", "butt", "lap", "fillet", "other"),
    "position": ("", "flat", "horizontal", "vertical", "overhead", "rotating", "other"),
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024


def _field(grid, row, col, name, label):
    box = QWidget()
    box.setObjectName("fieldBox")
    layout = QVBoxLayout(box)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    title = QLabel(label)
    title.setObjectName("fieldLabel")
    layout.addWidget(title)
    if name in CHOICES:
        widget = QComboBox()
        widget.addItems(CHOICES[name])
        if name in ("materialA", "materialB"):
            widget.setEditable(True)
    else:
        widget = QLineEdit()
    widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    widget.setObjectName(name)
    layout.addWidget(widget)
    grid.addWidget(box, row, col)
    return widget


def _get(widget):
    return widget.currentText() if isinstance(widget, QComboBox) else widget.text()


def _set(widget, value):
    text = "" if value is None else str(value)
    if isinstance(widget, QComboBox):
        widget.setCurrentText(text)
    else:
        widget.setText(text)


class SegmentCard(QFrame):
    remove_requested = Signal(object)
    changed = Signal()

    def __init__(self, number, values=None):
        super().__init__()
        self.setObjectName("card")
        self.widgets = {}
        self.wire_values = {key: "" for key in WIRE_ROW_FIELDS}
        self.approved_wps = None
        layout = QVBoxLayout(self)
        header = QHBoxLayout()
        self.title = QLabel(f"용접 구간 {number}")
        self.title.setObjectName("sectionTitle")
        header.addWidget(self.title)
        header.addStretch()
        self.remove_button = QPushButton("구간 삭제")
        self.remove_button.setObjectName("ghostButton")
        self.remove_button.clicked.connect(lambda: self.remove_requested.emit(self))
        header.addWidget(self.remove_button)
        layout.addLayout(header)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(14)
        for i, key in enumerate(ROW_FIELDS):
            self.widgets[key] = _field(grid, i // 4, i % 4, key, ROW_LABELS[key])
            widget = self.widgets[key]
            if isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self.changed)
            else:
                widget.textChanged.connect(self.changed)
        for col in range(4):
            grid.setColumnStretch(col, 1)
        layout.addLayout(grid)
        self.widgets["mode"].currentTextChanged.connect(self._update_mode)
        self.set_values(values or {})

    def set_values(self, values):
        for key in ROW_FIELDS:
            _set(self.widgets[key], values.get(key, ""))
        for key in WIRE_ROW_FIELDS:
            self.wire_values[key] = str(values.get(key) or "")
        self._update_mode()

    def values(self):
        return {key: _get(widget) for key, widget in self.widgets.items()} | self.wire_values.copy()

    def _update_mode(self):
        direct = _get(self.widgets["mode"]) == "time"
        self.widgets["speed"].setEnabled(not direct)
        self.widgets["time"].setEnabled(direct)


class WorkPage(QWidget):
    rows_changed = Signal()
    product_changed = Signal()
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.common = {}
        self.rows = []
        self.wire_common = {key: "" for key in WIRE_COMMON_FIELDS}
        self.sample = False
        self._loading = True
        self.image_path = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        outer.addWidget(scroll)
        content = QWidget()
        self.body = QVBoxLayout(content)
        self.body.setSizeConstraint(QLayout.SetMinimumSize)
        self.body.setContentsMargins(16, 12, 16, 24)
        self.body.setSpacing(16)
        scroll.setWidget(content)

        self.body.addWidget(self._section("제품 정보", ("vehicle", "productName")))
        image_card = QFrame()
        image_card.setObjectName("card")
        image_layout = QHBoxLayout(image_card)
        self.image_preview = QLabel("제품 형상 이미지 미첨부")
        self.image_preview.setObjectName("imagePreview")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setFixedSize(260, 150)
        image_layout.addWidget(self.image_preview)
        image_actions = QVBoxLayout()
        attach = QPushButton("이미지 첨부")
        attach.clicked.connect(self.choose_image)
        remove = QPushButton("이미지 제거")
        remove.setObjectName("ghostButton")
        remove.clicked.connect(self.clear_image)
        image_actions.addWidget(attach)
        image_actions.addWidget(remove)
        image_actions.addWidget(QLabel("이미지는 이 PC에서 미리보기만 합니다.\n용접 부위나 조건은 자동 판독하지 않습니다."))
        image_actions.addStretch()
        image_layout.addLayout(image_actions)
        image_layout.addStretch()
        self.body.addWidget(image_card)
        self.body.addWidget(self._section("용접 방식·설비", ("process", "equipment", "gas")))
        self.body.addWidget(self._section("사이클·생산 일정", (
            "batch", "nonArc", "uptime", "hours", "days", "months", "efficiency", "nonArcPower"
        )))
        header = QHBoxLayout()
        label = QLabel("용접 구간")
        label.setObjectName("pageTitle")
        header.addWidget(label)
        header.addStretch()
        add = QPushButton("+ 구간 추가")
        add.clicked.connect(lambda: self.add_row())
        header.addWidget(add)
        self.body.addLayout(header)
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(12)
        self.body.addLayout(self.rows_layout)
        self.body.addWidget(QLabel("같은 작업 단계 번호는 동시 용접, 다른 번호는 순차 용접으로 계산합니다."))
        self.body.addStretch()
        self.add_row()
        self._loading = False

    def _section(self, title, keys):
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(14)
        for index, key in enumerate(keys):
            self.common[key] = _field(grid, index // 3, index % 3, key, COMMON_LABELS[key])
            widget = self.common[key]
            if isinstance(widget, QComboBox):
                widget.currentTextChanged.connect(self.mark_changed)
            else:
                widget.textChanged.connect(self.mark_changed)
        for col in range(min(len(keys), 3)):
            grid.setColumnStretch(col, 1)
        layout.addLayout(grid)
        return card

    def raw_plan(self):
        return {**{key: _get(widget) for key, widget in self.common.items()},
                **self.wire_common, "rows": [card.values() for card in self.rows],
                "sample": self.sample}

    def load_raw_plan(self, raw):
        old_product = (_get(self.common["vehicle"]), _get(self.common["productName"]))
        self._loading = True
        for key in COMMON_FIELDS:
            _set(self.common[key], raw.get(key, ""))
        self.wire_common = {key: str(raw.get(key) or "") for key in WIRE_COMMON_FIELDS}
        for card in self.rows:
            self.rows_layout.removeWidget(card)
            card.deleteLater()
        self.rows.clear()
        for row in raw.get("rows", []):
            self.add_row(row)
        if not self.rows:
            self.add_row()
        self.sample = bool(raw.get("sample"))
        self.clear_image()
        self._loading = False
        if old_product != (_get(self.common["vehicle"]), _get(self.common["productName"])):
            self.product_changed.emit()

    def add_row(self, values=None):
        values = dict(values or {})
        if not values.get("stage"):
            stages = []
            for card in self.rows:
                try:
                    stages.append(int(float(card.values()["stage"])))
                except ValueError:
                    pass
            values["stage"] = str(max(stages, default=0) + 1)
        values.setdefault("mode", "speed")
        card = SegmentCard(len(self.rows) + 1, values)
        card.changed.connect(self.mark_changed)
        card.remove_requested.connect(lambda current: self.remove_row(self.rows.index(current)))
        self.rows.append(card)
        self.rows_layout.addWidget(card)
        self._refresh_rows()
        self.rows_changed.emit()
        self.mark_changed()
        return card

    def remove_row(self, index):
        if len(self.rows) <= 1:
            return
        card = self.rows.pop(index)
        self.rows_layout.removeWidget(card)
        card.hide()
        card.deleteLater()
        self._refresh_rows()
        self.rows_changed.emit()
        self.mark_changed()

    def _refresh_rows(self):
        for index, card in enumerate(self.rows, 1):
            card.title.setText(f"용접 구간 {index}")
            card.remove_button.setEnabled(len(self.rows) > 1)

    def apply_row_values(self, index, values):
        card = self.rows[index]
        for key, value in values.items():
            if key in card.widgets:
                _set(card.widgets[key], value)
            elif key in card.wire_values:
                card.wire_values[key] = str(value)

    def mark_changed(self):
        if self._loading:
            return
        self.sample = False
        self.changed.emit()

    def attach_image(self, path):
        source = Path(path)
        if source.suffix.lower() not in IMAGE_EXTENSIONS or source.stat().st_size > MAX_IMAGE_BYTES:
            raise ValueError("20 MB 이하의 PNG·JPG·GIF·BMP·WebP 이미지를 선택해 주세요.")
        pixmap = QPixmap(str(source))
        if pixmap.isNull():
            raise ValueError("이미지 파일을 읽을 수 없습니다.")
        self.image_preview.setPixmap(pixmap.scaled(250, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.image_path = str(source)
        self.mark_changed()

    def choose_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "제품 형상 이미지 선택", "", "이미지 (*.png *.jpg *.jpeg *.gif *.bmp *.webp)")
        if path:
            try:
                self.attach_image(path)
            except (OSError, ValueError) as exc:
                self.image_preview.setText(str(exc))

    def clear_image(self):
        self.image_path = None
        self.image_preview.clear()
        self.image_preview.setText("제품 형상 이미지 미첨부")
        self.mark_changed()
