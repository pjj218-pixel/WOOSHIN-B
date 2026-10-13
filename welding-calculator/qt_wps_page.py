"""사용자 제공 사내 승인 조건 CSV를 엄격하게 조회·적용한다."""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QVBoxLayout, QWidget,
)

from approved_wps import find_matching_wps, load_approved_wps


class WpsPage(QWidget):
    applied = Signal(int, dict, dict)

    def __init__(self, current_plan_provider):
        super().__init__()
        self.current_plan_provider = current_plan_provider
        self.records = []
        self.matches = []
        self.match_target = None
        self.context = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 18)
        title = QLabel("사내 승인 조건")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        intro = QLabel("제공받은 승인 조건표에서 재질·두께·방식·이음·자세·가스·설비가 모두 일치하는 기록만 찾습니다.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        card = QFrame()
        card.setObjectName("card")
        content = QVBoxLayout(card)
        top = QHBoxLayout()
        choose = QPushButton("승인 조건 CSV 첨부")
        choose.clicked.connect(self.choose_csv)
        top.addWidget(choose)
        self.file_label = QLabel("조건표 미첨부")
        top.addWidget(self.file_label, 1)
        content.addLayout(top)
        row = QHBoxLayout()
        row.addWidget(QLabel("용접 구간"))
        self.target = QComboBox()
        row.addWidget(self.target)
        find = QPushButton("일치 조건 찾기")
        find.clicked.connect(self.find_matches)
        row.addWidget(find)
        self.choice = QComboBox()
        row.addWidget(self.choice, 1)
        apply = QPushButton("선택 조건 적용")
        apply.clicked.connect(self.apply_selected)
        row.addWidget(apply)
        content.addLayout(row)
        self.status = QLabel("조건표를 첨부하고 입력값과 일치하는 조건을 찾으세요.")
        self.status.setWordWrap(True)
        content.addWidget(self.status)
        layout.addWidget(card)
        self.report = QTextEdit()
        self.report.setReadOnly(True)
        layout.addWidget(self.report, 1)

    def set_context(self, raw_plan, index=0):
        self.context = raw_plan
        count = len(raw_plan.get("rows", []))
        self.target.clear()
        self.target.addItems([str(i) for i in range(1, count + 1)])
        if 0 <= index < count:
            self.target.setCurrentIndex(index)
        self.matches = []
        self.choice.clear()

    def load_records(self, path):
        if not path:
            return False
        try:
            records = load_approved_wps(path)
        except (OSError, UnicodeError, ValueError) as exc:
            self.status.setText(f"조건표 입력 확인: {exc}")
            return False
        self.records = records
        self.matches = []
        self.choice.clear()
        self.file_label.setText(f"{Path(path).name} · {len(records)}개 조건")
        self.status.setText("조건표를 불러왔습니다. 일치 조건을 찾으세요.")
        return True

    def choose_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "사내 승인 조건 CSV", "", "CSV 파일 (*.csv)")
        if path:
            self.load_records(path)

    def find_matches(self):
        self.matches = []
        self.choice.clear()
        if not self.records:
            self.status.setText("사내 승인 조건 CSV를 먼저 첨부해 주세요.")
            return []
        index = self.target.currentIndex()
        raw = self.current_plan_provider()
        if index < 0 or index >= len(raw.get("rows", [])):
            self.status.setText("조회할 용접 구간을 선택해 주세요.")
            return []
        self.matches = find_matching_wps(self.records, raw["rows"][index], raw)
        self.match_target = index
        self.choice.addItems([f"{m['approvalId']} · 개정 {m['revision']}" for m in self.matches])
        if self.matches:
            self.status.setText(f"{index + 1}번 구간과 일치하는 승인 기록 {len(self.matches)}개")
            self.report.setPlainText("\n".join(
                f"{m['approvalId']} · 개정 {m['revision']} · 승인자 {m['approvedBy']}\n"
                f"{m['voltage']} V · {m['current']} A · {m['travelSpeed']} mm/min · {m['wire']}"
                for m in self.matches
            ) + "\n\n승인 상태와 현행 유효성을 확인한 뒤 적용하세요.")
        else:
            self.status.setText("재질·두께·방식·이음·자세·가스·설비가 모두 일치하는 조건이 없습니다.")
            self.report.setPlainText("")
        return self.matches

    def apply_selected(self):
        index = self.target.currentIndex()
        selected = self.choice.currentIndex()
        if selected < 0 or selected >= len(self.matches) or index != self.match_target:
            self.status.setText("먼저 적용할 구간의 일치 조건을 찾으세요.")
            return False
        raw = self.current_plan_provider()
        if index >= len(raw.get("rows", [])) or not find_matching_wps(
            [self.matches[selected]], raw["rows"][index], raw
        ):
            self.status.setText("조건 검색 후 입력값이 바뀌었습니다. 다시 검색해 주세요.")
            return False
        match = self.matches[selected]
        values = {"voltage": match["voltage"], "current": match["current"],
                  "mode": "speed", "speed": match["travelSpeed"], "wireName": match["wire"]}
        self.applied.emit(index, values, match)
        self.status.setText(f"{match['approvalId']} · 개정 {match['revision']} 조건을 {index + 1}번 구간에 적용했습니다.")
        return True
