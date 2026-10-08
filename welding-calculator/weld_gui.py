"""자동차 머플러 용접 시간·생산량 및 와이어 후보 GUI."""

from __future__ import annotations

import copy
import math
import os
import webbrowser
from pathlib import Path

# 이 폴더에 포함된 Tcl/Tk 리소스를 우선 사용해 로컬 실행 환경 차이를 줄인다.
_tcl_root = Path(__file__).resolve().parent / "runtime-tcl"
if (_tcl_root / "tcl8.6" / "init.tcl").exists():
    os.environ["TCL_LIBRARY"] = str(_tcl_root / "tcl8.6")
    os.environ["TK_LIBRARY"] = str(_tcl_root / "tk8.6")

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from weld_core import SAMPLE, calculate, calculate_energy, load_csv, normalize_plan, recommend_wire
from wire_catalog import MAKERS
from validation_core import (DEFECT_VALUES, LEAK_VALUES, analyze_measurements,
                             load_measurements_csv, save_measurements_csv)
from wire_usage import WIRE_COMMON_FIELDS, WIRE_ROW_FIELDS, calculate_wire_usage
from approved_wps import find_matching_wps, load_approved_wps


MATERIALS = ("", "409", "409Ti", "304", "304L", "carbon", "other")
JOINTS = ("", "butt", "lap", "fillet", "other")
POSITIONS = ("", "flat", "horizontal", "vertical", "overhead", "rotating", "other")
GASES = ("", "Ar98O2_2", "Ar98CO2_2", "other")
COMMON_FIELDS = ("vehicle", "productName", "process", "equipment", "gas", "batch", "nonArc", "nonArcPower", "efficiency", "uptime", "hours", "days", "months") + WIRE_COMMON_FIELDS
ROW_FIELDS = ("length", "stage", "mode", "speed", "time", "voltage", "current", "materialA", "thicknessA", "materialB", "thicknessB", "joint", "position") + WIRE_ROW_FIELDS
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
MAX_IMAGE_BYTES = 20 * 1024 * 1024


def fmt(value):
    return f"{value:,.2f}".rstrip("0").rstrip(".") if not float(value).is_integer() else f"{value:,.0f}"


def fmt_kwh(value):
    return f"{value:,.5f}".rstrip("0").rstrip(".")


class ScrollableFrame(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        canvas = tk.Canvas(self, highlightthickness=0, background="#f4f7f5")
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        self.content = ttk.Frame(canvas, padding=18)
        self.content.bind("<Configure>", lambda _: canvas.configure(scrollregion=canvas.bbox("all")))
        window = canvas.create_window((0, 0), window=self.content, anchor="nw")
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(window, width=event.width))
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<Enter>", lambda _: canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-event.delta / 120), "units")))
        canvas.bind("<Leave>", lambda _: canvas.unbind_all("<MouseWheel>"))


class WeldApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("용접 시간·생산량 및 와이어 후보")
        self.geometry("1120x780")
        self.minsize(920, 650)
        self.configure(background="#f4f7f5")
        self._style()
        self._loading = False
        self._calculated_once = False
        self._wire_calculated = False
        self._pending = None
        self._result_mode = "calc"
        self._source = "사용자 입력"
        self._sample = False
        self.approved_wps = []
        self.wps_matches = []
        self.product_image_path = None
        self.product_image_preview = None
        self.vars = {name: tk.StringVar() for name in COMMON_FIELDS}
        self.rows = []
        self.measurement_rows = []
        self._build()
        for variable in self.vars.values():
            variable.trace_add("write", self._changed)
        self.add_row()

    def _style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#f4f7f5")
        style.configure("TLabelframe", background="#ffffff", bordercolor="#cdded5")
        style.configure("TLabelframe.Label", background="#ffffff", foreground="#18302d", font=("맑은 고딕", 11, "bold"))
        style.configure("TLabel", background="#f4f7f5", foreground="#18302d", font=("맑은 고딕", 10))
        style.configure("TButton", font=("맑은 고딕", 10, "bold"), padding=7)
        style.configure("TEntry", padding=5)
        style.configure("TCombobox", padding=5)
        style.configure("Treeview", font=("맑은 고딕", 10), rowheight=30, background="#ffffff", fieldbackground="#ffffff")
        style.configure("Treeview.Heading", font=("맑은 고딕", 10, "bold"))

    def _build(self):
        title = ttk.Frame(self, padding=(22, 18, 22, 8))
        title.pack(fill="x")
        ttk.Label(title, text="용접 시간·생산량 계산기", font=("맑은 고딕", 20, "bold")).pack(anchor="w")
        ttk.Label(title, text="여러 용접 구간의 시간과 생산량을 계산하고 재질별 와이어 시험 후보를 확인합니다.").pack(anchor="w", pady=(5, 0))

        actions = ttk.Frame(self, padding=(22, 4, 22, 9))
        actions.pack(fill="x")
        ttk.Button(actions, text="예시값 불러오기", command=self.load_sample).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="CSV 파일 첨부", command=self.import_csv).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="용접 구간 추가", command=self.add_row).pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="계산하기", command=lambda: self.run_calculation(show_result=True)).pack(side="right")
        ttk.Button(actions, text="와이어만 추천", command=lambda: self.run_wire_only(show_result=True)).pack(side="right", padx=(0, 8))

        self.status = tk.StringVar(value="값을 입력하거나 예시 CSV를 첨부해 주세요. 결과는 미검증 추정치입니다.")
        ttk.Label(self, textvariable=self.status, foreground="#176f63", padding=(22, 0, 22, 8)).pack(fill="x")

        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        input_scroll = ScrollableFrame(self.tabs)
        self.tabs.add(input_scroll, text="입력")
        input_page = input_scroll.content

        product = ttk.LabelFrame(input_page, text="제품 정보", padding=16)
        product.pack(fill="x", pady=(0, 12))
        self._field(product, "차종", self.vars["vehicle"], 0, 0)
        self._field(product, "제품명", self.vars["productName"], 0, 1)
        image_controls = ttk.Frame(product)
        image_controls.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Button(image_controls, text="제품 형상 이미지 첨부", command=self.attach_product_image).pack(side="left", padx=(0, 8))
        self.remove_image_button = ttk.Button(image_controls, text="이미지 제거", command=self.clear_product_image, state="disabled")
        self.remove_image_button.pack(side="left")
        self.image_name = tk.StringVar(value="첨부 이미지 없음")
        ttk.Label(image_controls, textvariable=self.image_name).pack(side="left", padx=12)
        self.input_image_label = ttk.Label(product, text="이미지를 첨부하면 여기에 미리보기가 표시됩니다.", background="#ffffff")
        self.input_image_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))
        ttk.Label(product, text="형상 이미지는 현재 화면에서만 미리봅니다. 작업 폴더에 복사하지 않으며 용접 조건을 자동 판독하지 않습니다.", background="#ffffff", foreground="#5e756d").grid(row=3, column=0, columnspan=2, sticky="w", pady=(7, 0))

        process = ttk.LabelFrame(input_page, text="용접 방식·설비", padding=16)
        process.pack(fill="x", pady=(0, 12))
        self._field(process, "용접 방식", self.vars["process"], 0, 0, ("", "GMAW", "GTAW", "other"))
        self._field(process, "설비명", self.vars["equipment"], 0, 1)
        self._field(process, "보호가스", self.vars["gas"], 0, 2, GASES)

        production = ttk.LabelFrame(input_page, text="사이클·생산 일정", padding=16)
        production.pack(fill="x", pady=(0, 12))
        entries = (("한 사이클 생산 수량 (개)", "batch"), ("비아크 시간 (초/사이클)", "nonArc"), ("가동률 (%)", "uptime"),
                   ("일일 근무시간 (시간)", "hours"), ("월간 가동일수 (일)", "days"), ("연간 가동 개월 수", "months"),
                   ("용접기 효율 (%)", "efficiency"), ("비아크 설비 입력전력 (kW)", "nonArcPower"))
        for index, (label, key) in enumerate(entries):
            self._field(production, label, self.vars[key], index // 3, index % 3)
        ttk.Label(production, text="전력량은 전압·전류·효율·비아크 설비 전력을 모두 입력한 경우에 계산합니다. 전력계 실측값과 비교하세요.", background="#ffffff", foreground="#5e756d").grid(row=3, column=0, columnspan=3, sticky="w")

        ttk.Label(input_page, text="용접 구간", font=("맑은 고딕", 13, "bold")).pack(anchor="w", pady=(7, 8))
        self.rows_frame = ttk.Frame(input_page)
        self.rows_frame.pack(fill="x")
        ttk.Label(input_page, text="같은 작업 단계 번호의 구간은 동시에, 다른 번호의 단계는 순서대로 용접합니다. 완제품 1개가 나오면 한 사이클 생산 수량은 1입니다.", foreground="#5e756d").pack(anchor="w", pady=12)

        result_page = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(result_page, text="결과")
        self.result_tabs = ttk.Notebook(result_page)
        self.result_tabs.pack(fill="both", expand=True)
        summary_scroll = ScrollableFrame(self.result_tabs)
        self.result_tabs.add(summary_scroll, text="한눈에 보기")
        self._build_result_summary(summary_scroll.content)
        products_scroll = ScrollableFrame(self.result_tabs)
        self.result_tabs.add(products_scroll, text="와이어 추천 제품")
        self._build_product_results(products_scroll.content)
        details_page = ttk.Frame(self.result_tabs, padding=10)
        self.result_tabs.add(details_page, text="계산 근거·안내")
        self.report = tk.Text(details_page, wrap="word", font=("맑은 고딕", 10), padx=18, pady=15, borderwidth=0, background="#ffffff", foreground="#18302d")
        report_scroll = ttk.Scrollbar(details_page, orient="vertical", command=self.report.yview)
        self.report.configure(yscrollcommand=report_scroll.set)
        self.report.pack(side="left", fill="both", expand=True)
        report_scroll.pack(side="right", fill="y")
        self.report.tag_configure("title", font=("맑은 고딕", 17, "bold"), spacing3=12)
        self.report.tag_configure("heading", font=("맑은 고딕", 12, "bold"), spacing1=15, spacing3=5)
        self.report.tag_configure("warning", foreground="#a45a12", font=("맑은 고딕", 10, "bold"))
        self.report.configure(state="disabled")
        self._build_measurement_tab()
        self._build_wire_tab()
        self._build_wps_tab()

    def _build_wps_tab(self):
        page = ttk.Frame(self.tabs, padding=14)
        self.tabs.add(page, text="사내 승인 조건")
        ttk.Button(page, text="승인 조건 CSV 첨부", command=self.import_approved_wps).pack(anchor="w")
        self.wps_file_name = tk.StringVar(value="조건표 미첨부")
        ttk.Label(page, textvariable=self.wps_file_name, wraplength=940).pack(anchor="w", pady=(8, 12))
        selection = ttk.Frame(page)
        selection.pack(fill="x")
        self.wps_target = tk.StringVar(value="1")
        self.wps_target_widget = ttk.Combobox(selection, textvariable=self.wps_target, state="readonly", width=8, values=("1",))
        self.wps_target_widget.pack(side="left", padx=(0, 8))
        ttk.Button(selection, text="입력값과 일치하는 조건 찾기", command=self.find_approved_wps).pack(side="left", padx=(0, 8))
        self.wps_match_choice = tk.StringVar()
        self.wps_match_widget = ttk.Combobox(selection, textvariable=self.wps_match_choice, state="readonly", width=38)
        self.wps_match_widget.pack(side="left", padx=(0, 8))
        ttk.Button(selection, text="선택한 승인 조건 적용", command=self.apply_matched_wps).pack(side="left")
        self.wps_status = tk.StringVar(value="입력 탭에서 재질·두께·방식·이음·자세·가스·설비를 입력한 뒤 조건을 찾으세요.")
        ttk.Label(page, textvariable=self.wps_status, wraplength=940).pack(anchor="w", pady=(12, 8))
        self.wps_report = tk.Text(page, height=12, wrap="word", font=("맑은 고딕", 10), padx=12, pady=10, background="#ffffff", borderwidth=0)
        self.wps_report.pack(fill="both", expand=True)
        self.wps_report.configure(state="disabled")

    def _refresh_wps_targets(self):
        choices = tuple(str(index) for index in range(1, len(self.rows) + 1))
        self.wps_target_widget.configure(values=choices)
        if self.wps_target.get() not in choices:
            self.wps_target.set(choices[0] if choices else "")

    def import_approved_wps(self):
        selected = filedialog.askopenfilename(title="사내 승인 조건 CSV 선택", filetypes=[("CSV 파일", "*.csv")])
        if not selected:
            return
        try:
            rows = load_approved_wps(selected)
        except (OSError, UnicodeError, ValueError) as exc:
            messagebox.showerror("승인 조건표 불러오기 실패", str(exc), parent=self)
            return
        self.approved_wps = rows
        self.wps_matches = []
        self.wps_match_choice.set("")
        self.wps_match_widget.configure(values=())
        self.wps_file_name.set(f"{Path(selected).name} · {len(rows)}개 조건 · 사용자 제공 승인 기록")
        self.wps_status.set("조건표를 불러왔습니다. 입력값과 일치하는 조건을 찾으세요.")

    def _set_wps_report(self, lines):
        self.wps_report.configure(state="normal")
        self.wps_report.delete("1.0", "end")
        self.wps_report.insert("end", "\n".join(lines))
        self.wps_report.configure(state="disabled")

    def find_approved_wps(self):
        if not self.approved_wps:
            self.wps_status.set("사내 승인 조건 CSV를 먼저 첨부해 주세요.")
            return
        try:
            target = int(self.wps_target.get()) - 1
            item = self.rows[target]
        except (ValueError, IndexError):
            self.wps_status.set("조회할 용접 구간을 선택해 주세요.")
            return
        row = {key: variable.get() for key, variable in item["vars"].items()}
        self.wps_matches = find_matching_wps(self.approved_wps, row, self._raw_plan())
        self.wps_match_target = target
        self.wps_match_row_identity = id(item)
        self.wps_match_labels = [f"{index + 1}. {match['approvalId']} · 개정 {match['revision']}" for index, match in enumerate(self.wps_matches)]
        self.wps_match_widget.configure(values=self.wps_match_labels)
        self.wps_match_choice.set(self.wps_match_labels[0] if self.wps_match_labels else "")
        if self.wps_matches:
            lines = [f"{match['approvalId']} (개정 {match['revision']}, 승인자 {match['approvedBy']}): {match['voltage']} V · {match['current']} A · {match['travelSpeed']} mm/min · {match['wire']}" for match in self.wps_matches]
            lines.append("조건표의 승인 상태와 현행 유효성을 확인한 뒤 적용하세요.")
            self.wps_status.set(f"{target + 1}번 구간과 일치하는 조건 {len(self.wps_matches)}개를 찾았습니다.")
        else:
            lines = ["재질·두께·방식·이음·자세·가스·설비가 모두 일치하는 조건이 없습니다."]
            self.wps_status.set("일치하는 조건이 없습니다. 입력값과 승인 조건표를 확인해 주세요.")
        self._set_wps_report(lines)

    def apply_matched_wps(self):
        choice = self.wps_match_choice.get()
        if choice not in getattr(self, "wps_match_labels", []):
            self.wps_status.set("먼저 입력값과 일치하는 승인 조건을 찾으세요.")
            return
        match = self.wps_matches[self.wps_match_labels.index(choice)]
        try:
            target = int(self.wps_target.get()) - 1
            item = self.rows[target]
        except (ValueError, IndexError):
            self.wps_status.set("적용할 용접 구간을 다시 선택해 주세요.")
            return
        if target != self.wps_match_target or id(item) != self.wps_match_row_identity or not find_matching_wps([match], {key: var.get() for key, var in item["vars"].items()}, self._raw_plan()):
            self.wps_status.set("조건 검색 후 입력값이 바뀌었습니다. 다시 검색해 주세요.")
            return
        values = item["vars"]
        if self._pending is not None:
            self.after_cancel(self._pending)
            self._pending = None
        self._loading = True
        try:
            values["voltage"].set(str(match["voltage"]))
            values["current"].set(str(match["current"]))
            values["mode"].set("speed")
            values["speed"].set(str(match["travelSpeed"]))
            values["wireName"].set(match["wire"])
        finally:
            self._loading = False
        item["approved_wps"] = match
        self._source = f"사용자 제공 조건표: {match['approvalId']} · 개정 {match['revision']}"
        self.run_calculation(show_result=False)
        self.wps_status.set(f"{match['approvalId']}의 전압·전류·이동 속도를 적용했습니다. 결과 탭에서 확인하세요.")

    def _build_result_summary(self, parent):
        self.summary_product = tk.StringVar(value="계산 결과가 여기에 표시됩니다.")
        ttk.Label(parent, textvariable=self.summary_product, font=("맑은 고딕", 15, "bold")).pack(anchor="w", pady=(0, 8))
        self.result_image_label = ttk.Label(parent)
        self.result_image_label.pack(anchor="w", pady=(0, 6))
        self.summary_note = tk.StringVar(value="값을 입력하고 계산하기를 눌러 주세요.")
        ttk.Label(parent, textvariable=self.summary_note, foreground="#6b746f", wraplength=940).pack(anchor="w", pady=(0, 16))
        cards = ttk.Frame(parent)
        cards.pack(fill="x", pady=(0, 16))
        self.summary_metrics = {}
        for column, (key, label) in enumerate((
            ("arc", "총 아크 시간"), ("cycle", "사이클 시간"),
            ("uph", "시간당 생산량"), ("energy", "제품당 전력량"),
        )):
            card = ttk.LabelFrame(cards, text=label, padding=14)
            card.grid(row=0, column=column, sticky="nsew", padx=(0, 8))
            cards.columnconfigure(column, weight=1)
            value = tk.StringVar(value="—")
            ttk.Label(card, textvariable=value, font=("맑은 고딕", 17, "bold"), foreground="#176f63").pack(anchor="w")
            self.summary_metrics[key] = value
        ttk.Label(parent, text="기간별 예상치", font=("맑은 고딕", 12, "bold")).pack(anchor="w", pady=(0, 6))
        self.production_table = self._result_tree(parent, (
            ("period", "기간", 110), ("units", "생산량 (개)", 170),
            ("power", "전력량 (kWh)", 180), ("wire", "와이어 (kg)", 180),
        ), height=4)
        ttk.Label(parent, text="용접 구간별 입력·시간", font=("맑은 고딕", 12, "bold")).pack(anchor="w", pady=(18, 6))
        self.segment_table = self._result_tree(parent, (
            ("section", "구간", 75), ("stage", "작업 단계", 95), ("length", "길이 (mm)", 140),
            ("time", "용접 시간 (초)", 170), ("voltage", "전압 (V)", 130),
            ("current", "전류 (A)", 130),
        ), height=5)
        self.summary_footer = tk.StringVar(value="전력·와이어 값이 없으면 해당 입력값을 확인해 주세요.")
        ttk.Label(parent, textvariable=self.summary_footer, wraplength=940, foreground="#6b746f").pack(anchor="w", pady=(10, 4))

    def _build_product_results(self, parent):
        self.product_result_heading = tk.StringVar(value="재질을 선택하면 브랜드별 와이어 후보를 확인할 수 있습니다.")
        ttk.Label(parent, textvariable=self.product_result_heading, font=("맑은 고딕", 13, "bold")).pack(anchor="w", pady=(0, 8))
        ttk.Label(parent, text="제품 행을 두 번 클릭하면 제조사 자료가 열립니다. 동일 AWS 분류를 확인하지 못한 제품은 표시하지 않습니다.", foreground="#5e756d").pack(anchor="w", pady=(0, 8))
        self.product_table = self._result_tree(parent, (
            ("section", "구간", 75), ("brand", "브랜드", 170),
            ("product", "제품명", 240), ("aws", "AWS 분류", 150),
            ("status", "상태", 210),
        ), height=12)
        self.product_table.bind("<Double-1>", self._open_product_source)
        self.wire_product_links = {}
        self.product_result_note = tk.StringVar(value="추천 결과는 시편 시험과 사내 승인 전 검토 후보입니다.")
        ttk.Label(parent, textvariable=self.product_result_note, wraplength=940, foreground="#6b746f").pack(anchor="w", pady=(10, 0))

    def _result_tree(self, parent, columns, height):
        names = tuple(item[0] for item in columns)
        container = ttk.Frame(parent)
        container.pack(fill="x")
        tree = ttk.Treeview(container, columns=names, show="headings", height=height)
        for name, label, width in columns:
            tree.heading(name, text=label)
            tree.column(name, width=width, anchor="w", stretch=True)
        tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        scrollbar.pack(side="right", fill="y")
        tree.configure(yscrollcommand=scrollbar.set)
        return tree

    def _open_product_source(self, event):
        row = self.product_table.identify_row(event.y)
        url = self.wire_product_links.get(row)
        if url:
            webbrowser.open(url)

    def _render_product_results(self, rows, plan):
        self.product_table.delete(*self.product_table.get_children())
        self.wire_product_links.clear()
        self.product_result_heading.set(f"{plan.get('vehicle') or '차종 미입력'} · {plan.get('productName') or '제품명 미입력'}")
        notes = []
        for index, row in enumerate(rows, 1):
            candidate = recommend_wire(row, plan)
            if "wire" not in candidate:
                self.product_table.insert("", "end", values=(index, "—", "—", "—", candidate["status"]))
                notes.append(f"{index}번: {candidate['message']}")
                continue
            products = {product["maker"]: product for product in candidate["products"]}
            for maker in MAKERS:
                brand = "COWEL (KOWEL)" if maker == "KOWEL" else maker
                product = products.get(maker)
                item_id = self.product_table.insert("", "end", values=(
                    index, brand, product["name"] if product else "—",
                    product["aws"] if product else "—",
                    candidate["status"] if product else "동일 분류 제품 미확인",
                ))
                if product:
                    self.wire_product_links[item_id] = product["url"]
            notes.append(f"{index}번 {candidate['wire']}: {candidate['gas_note']}")
            if candidate["missing"]:
                notes.append(f"추가 확인: {', '.join(candidate['missing'])}")
        notes.append("제조사 제품별 보호가스·직경·공급 여부와 실제 이음 적용성을 확인하세요.")
        self.product_result_note.set("\n".join(notes))

    def _render_result_summary(self, plan, numbers):
        self.summary_product.set(f"{plan['vehicle'] or '차종 미입력'} · {plan['productName'] or '제품명 미입력'}")
        self.summary_note.set(f"{self._source}  |  미검증 추정" + ("  |  화면 확인용 예시 데이터" if plan["sample"] else ""))
        self.summary_metrics["arc"].set(f"{fmt(numbers['arc'])}초")
        self.summary_metrics["cycle"].set(f"{fmt(numbers['cycle'])}초")
        self.summary_metrics["uph"].set(f"{fmt(numbers['uph'])}개")
        energy = calculate_energy(plan, numbers)
        self.summary_metrics["energy"].set(f"{fmt_kwh(energy['part_kwh'])} kWh" if "part_kwh" in energy else "입력 필요")
        try:
            wire = calculate_wire_usage(plan, numbers)
        except ValueError as exc:
            wire = {"status": "입력 오류", "missing": [str(exc)]}
        self.production_table.delete(*self.production_table.get_children())
        for label, key, energy_key, wire_key in (
            ("시간", "uph", "hour_kwh", "hour_kg"), ("일", "day", "day_kwh", "day_kg"),
            ("월", "month", "month_kwh", "month_kg"), ("년", "year", "year_kwh", "year_kg"),
        ):
            units = fmt(numbers[key]) if key == "uph" else f"{math.floor(numbers[key]):,}"
            self.production_table.insert("", "end", values=(
                label, units,
                fmt_kwh(energy[energy_key]) if energy_key in energy else "입력 필요",
                fmt_kwh(wire[wire_key]) if wire_key in wire else "입력 확인" if wire["status"] == "입력 오류" else "선택 입력",
            ))
        self.segment_table.delete(*self.segment_table.get_children())
        for index, row in enumerate(plan["rows"], 1):
            self.segment_table.insert("", "end", values=(
                index, row["stage"], fmt(row["length"]), fmt(row["time"]),
                fmt(row["voltage"]) if row["voltage"] is not None else "—",
                fmt(row["current"]) if row["current"] is not None else "—",
            ))
        footer = []
        if energy["missing"]:
            footer.append("전력량 입력 필요: " + ", ".join(energy["missing"]))
        if wire.get("missing"):
            footer.append("와이어 사용량 확인: " + ", ".join(wire["missing"]))
        footer.append("기간별 값은 입력한 가동률과 근무 일정에 따른 계획용 추정치입니다.")
        self.summary_footer.set("\n".join(footer))

    def _build_wire_tab(self):
        page = ttk.Frame(self.tabs)
        self.tabs.add(page, text="와이어 사용량 (선택)")
        toolbar = ttk.Frame(page, padding=12)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="구간별 실제 송급 설정 또는 측정값을 입력하세요. 전류·전압만으로 송급량을 역산하지 않습니다.").pack(side="left")
        ttk.Button(toolbar, text="와이어 사용량 계산", command=lambda: self.run_wire_calculation(show_tab=True)).pack(side="right")
        self.wire_status = tk.StringVar(value="입력하지 않아도 기존 시간·전력량·와이어 추천 계산에 영향이 없습니다.")
        ttk.Label(page, textvariable=self.wire_status, foreground="#176f63", padding=(14, 0, 14, 8)).pack(fill="x")
        scroll = ScrollableFrame(page)
        scroll.pack(fill="both", expand=True)
        self.wire_rows_frame = ttk.Frame(scroll.content)
        self.wire_rows_frame.pack(fill="x")
        measured = ttk.LabelFrame(scroll.content, text="실측 와이어 사용량 비교 (선택)", padding=12)
        measured.pack(fill="x", pady=(4, 12))
        for index, (label, key) in enumerate((
            ("시작 와이어 잔량 합계 (kg)", "wireStartKg"),
            ("종료 와이어 잔량 합계 (kg)", "wireEndKg"),
            ("실측 생산 사이클 수", "wireMeasuredCycles"),
        )):
            self._field(measured, label, self.vars[key], 0, index)
        ttk.Label(measured, text="같은 와이어·같은 용기 기준의 시작·종료 잔량을 사용하세요. 실측 중 교체한 와이어가 있다면 투입량까지 반영한 잔량을 입력합니다.", background="#ffffff", foreground="#5e756d").grid(row=1, column=0, columnspan=3, sticky="w")
        self.wire_report = tk.Text(scroll.content, height=18, wrap="word", font=("맑은 고딕", 10), padx=14, pady=12, background="#ffffff", borderwidth=0)
        self.wire_report.pack(fill="both", expand=True)
        self.wire_report.configure(state="disabled")

    def _refresh_wire_rows(self):
        for child in self.wire_rows_frame.winfo_children():
            child.destroy()
        fields = (
            ("사용 와이어 제품명", "wireName"),
            ("와이어 직경 (mm)", "wireDiameter"),
            ("와이어 밀도 (g/cm³)", "wireDensity"),
            ("평균 송급 속도 (m/min)", "wireFeedSpeed"),
            ("실측 송급 길이 (m/사이클, 우선 적용)", "wireFeedLength"),
            ("실측 아크 시간 (초, 선택)", "wireActualArcTime"),
            ("추가 송급 길이 (m/사이클)", "wireExtraFeedLength"),
            ("절단·폐기량 (g/사이클)", "wireScrap"),
            ("용착 효율 (%)", "wireDepositionEfficiency"),
            ("와이어 단가 (원/kg)", "wirePrice"),
        )
        for index, item in enumerate(self.rows, 1):
            frame = ttk.LabelFrame(self.wire_rows_frame, text=f"용접 구간 {index} · 와이어 입력", padding=12)
            frame.pack(fill="x", pady=(0, 10))
            for position, (label, key) in enumerate(fields):
                self._field(frame, label, item["vars"][key], position // 3, position % 3)
            ttk.Label(frame, text="실측 송급 길이가 있으면 송급 속도×아크 시간 대신 사용합니다. 추가 송급·폐기량 미입력분은 추정에서 제외합니다.", background="#ffffff", foreground="#5e756d").grid(row=4, column=0, columnspan=3, sticky="w")

    def _image_preview(self, path, max_size=(360, 220)):
        try:
            from PIL import Image, ImageOps, ImageTk
        except ImportError:
            if path.suffix.lower() not in {".png", ".gif"}:
                raise ValueError("JPG·BMP·WebP 이미지를 첨부하려면 Pillow가 필요합니다. PNG 또는 GIF 파일을 사용해 주세요.")
            image = tk.PhotoImage(file=str(path))
            scale = max(1, math.ceil(image.width() / max_size[0]), math.ceil(image.height() / max_size[1]))
            return image.subsample(scale)
        try:
            with Image.open(path) as source:
                source.verify()
            with Image.open(path) as source:
                preview = ImageOps.exif_transpose(source)
                preview.thumbnail(max_size)
                return ImageTk.PhotoImage(preview.copy(), master=self)
        except (OSError, ValueError, Image.DecompressionBombError) as exc:
            raise ValueError("이미지 파일을 읽을 수 없습니다. 정상적인 PNG·JPG·GIF·BMP·WebP 파일인지 확인해 주세요.") from exc

    def attach_product_image(self):
        selected = filedialog.askopenfilename(
            title="제품 형상 이미지 선택",
            filetypes=[("이미지 파일", "*.png *.jpg *.jpeg *.gif *.bmp *.webp")],
        )
        if not selected:
            return
        source = Path(selected)
        try:
            if source.suffix.lower() not in IMAGE_EXTENSIONS:
                raise ValueError("PNG·JPG·GIF·BMP·WebP 이미지만 첨부할 수 있습니다.")
            if source.stat().st_size > MAX_IMAGE_BYTES:
                raise ValueError("이미지 크기는 20MB 이하여야 합니다.")
            preview = self._image_preview(source)
            result_preview = self._image_preview(source, (180, 110))
        except (OSError, ValueError, tk.TclError) as exc:
            messagebox.showerror("이미지 첨부 실패", str(exc), parent=self)
            return
        self.product_image_path = source
        self.product_image_preview = preview
        self.product_result_preview = result_preview
        self.image_name.set(source.name)
        self.input_image_label.configure(image=preview, text="")
        self.result_image_label.configure(image=result_preview, text=f"제품 형상: {source.name}", compound="left")
        self.remove_image_button.configure(state="normal")
        self._changed()

    def clear_product_image(self):
        self.product_image_path = None
        self.product_image_preview = None
        self.product_result_preview = None
        self.image_name.set("첨부 이미지 없음")
        self.input_image_label.configure(image="", text="이미지를 첨부하면 여기에 미리보기가 표시됩니다.")
        self.result_image_label.configure(image="", text="")
        self.remove_image_button.configure(state="disabled")
        self._changed()

    def _build_measurement_tab(self):
        page = ttk.Frame(self.tabs)
        self.tabs.add(page, text="실측 검증")
        toolbar = ttk.Frame(page, padding=12)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="측정 행 추가", command=self.add_measurement).pack(side="left", padx=(0, 7))
        ttk.Button(toolbar, text="실측 CSV 불러오기", command=self.import_measurements).pack(side="left", padx=(0, 7))
        ttk.Button(toolbar, text="실측 CSV 저장", command=self.export_measurements).pack(side="left", padx=(0, 7))
        ttk.Button(toolbar, text="실측값 비교", command=self.run_validation).pack(side="right")
        self.tolerance = tk.StringVar()
        ttk.Entry(toolbar, textvariable=self.tolerance, width=8).pack(side="right", padx=(6, 14))
        ttk.Label(toolbar, text="허용 오차율 (%)").pack(side="right")
        self.validation_status = tk.StringVar(value="실측 사이클 시간과 기밀·불량 결과를 입력해 계산값과 비교합니다.")
        ttk.Label(page, textvariable=self.validation_status, foreground="#176f63", padding=(14, 0, 14, 8)).pack(fill="x")
        scroll = ScrollableFrame(page)
        scroll.pack(fill="both", expand=True)
        self.measurements_frame = ttk.Frame(scroll.content)
        self.measurements_frame.pack(fill="x")
        ttk.Label(scroll.content, text="측정값은 제품과 설비 조건이 같은 경우에만 묶어 비교하세요. 검사 결과와 오차 기준은 담당자가 판단합니다.", foreground="#5e756d").pack(anchor="w", pady=10)
        self.validation_report = tk.Text(scroll.content, height=16, wrap="word", font=("맑은 고딕", 10), padx=14, pady=10, background="#ffffff", borderwidth=0)
        self.validation_report.pack(fill="both", expand=True)
        self.validation_report.configure(state="disabled")
        self.add_measurement()

    def add_measurement(self, data=None):
        data = data or {}
        frame = ttk.LabelFrame(self.measurements_frame, padding=10)
        frame.pack(fill="x", pady=(0, 9))
        variables = {name: tk.StringVar(value=str(data.get(name, "") or "")) for name in ("cycle", "leak", "defect", "note")}
        if not variables["leak"].get():
            variables["leak"].set("미검사")
        if not variables["defect"].get():
            variables["defect"].set("미검사")
        self._field(frame, "실측 사이클 시간 (초)", variables["cycle"], 0, 0)
        self._field(frame, "기밀 검사", variables["leak"], 0, 1, LEAK_VALUES)
        self._field(frame, "불량 여부", variables["defect"], 0, 2, DEFECT_VALUES)
        self._field(frame, "메모", variables["note"], 0, 3)
        button = ttk.Button(frame, text="이 측정 삭제", command=lambda: self.remove_measurement(frame))
        button.grid(row=1, column=3, sticky="e")
        self.measurement_rows.append({"frame": frame, "vars": variables, "button": button})
        self._refresh_measurements()

    def _refresh_measurements(self):
        for index, item in enumerate(self.measurement_rows, 1):
            item["frame"].configure(text=f"실측 {index}")
            item["button"].configure(state="disabled" if len(self.measurement_rows) == 1 else "normal")

    def remove_measurement(self, frame):
        if len(self.measurement_rows) == 1:
            return
        self.measurement_rows = [item for item in self.measurement_rows if item["frame"] is not frame]
        frame.destroy()
        self._refresh_measurements()

    def _measurement_raw(self):
        return [{name: variable.get() for name, variable in item["vars"].items()} for item in self.measurement_rows]

    def run_validation(self):
        try:
            plan = normalize_plan(self._raw_plan())
            numbers = calculate(plan)
            analysis = analyze_measurements(plan, numbers, self._measurement_raw(), self.tolerance.get())
        except ValueError as exc:
            self.validation_status.set(f"입력 확인: {exc}")
            return
        self.validation_status.set(f"실측 {analysis['count']}건 비교 완료 · 품질: {analysis['quality_status']} · 양산 승인 아님")
        lines = [
            f"차종: {plan['vehicle'] or '미입력'}  |  제품명: {plan['productName'] or '미입력'}",
            f"실측 {analysis['count']}건 · 최소 {fmt(analysis['minimum'])}초 · 최대 {fmt(analysis['maximum'])}초",
            f"계산 사이클 시간: {fmt(analysis['estimated'])}초",
            f"실측 평균 사이클 시간: {fmt(analysis['actual_mean'])}초",
            f"오차(계산 - 실측 평균): {analysis['error_seconds']:+.2f}초 ({analysis['error_pct']:+.2f}%)",
            f"실측 평균 기준 UPH 추정: {fmt(analysis['actual_uph'])}개/시간",
            f"기밀 불합격 {analysis['leak_fail_count']}건 · 불량 있음 {analysis['defect_count']}건",
            f"품질 상태: {analysis['quality_status']}",
        ]
        if analysis["tolerance"] is not None:
            lines.append(f"설정한 허용 오차 ±{fmt(analysis['tolerance'])}%: {'범위 안' if analysis['within_tolerance'] else '범위 밖'}")
        lines.append(f"실측 평균 기준 비아크 시간 참고값: {fmt(analysis['suggested_nonarc'])}초 (실측 평균 - 경과 용접 시간)")
        lines.append("참고값을 바로 승인 조건으로 사용하지 말고 누락된 공정 시간을 확인하세요.")
        if analysis["count"] < 3:
            lines.append("실측 표본이 3건 미만입니다. 반복 측정 후 다시 비교하세요.")
        lines.append("이 화면은 계산 오차와 검사 기록을 보여줍니다. 용접 조건 또는 생산능력을 자동 승인하지 않습니다.")
        self.validation_report.configure(state="normal")
        self.validation_report.delete("1.0", "end")
        self.validation_report.insert("end", "\n".join(lines))
        self.validation_report.configure(state="disabled")

    def import_measurements(self):
        path = filedialog.askopenfilename(title="실측 CSV 선택", filetypes=[("CSV 파일", "*.csv")])
        if not path:
            return
        try:
            data = load_measurements_csv(path)
        except (OSError, UnicodeError, ValueError) as exc:
            messagebox.showerror("실측 CSV 불러오기 실패", str(exc), parent=self)
            return
        current_vehicle = self.vars["vehicle"].get().strip()
        current_product = self.vars["productName"].get().strip()
        if (current_vehicle and current_vehicle != data["vehicle"]) or (current_product and current_product != data["productName"]):
            messagebox.showerror("제품 정보 불일치", "실측 CSV의 차종·제품명이 현재 입력과 다릅니다.", parent=self)
            return
        if not current_vehicle:
            self.vars["vehicle"].set(data["vehicle"])
        if not current_product:
            self.vars["productName"].set(data["productName"])
        for item in self.measurement_rows:
            item["frame"].destroy()
        self.measurement_rows.clear()
        for row in data["rows"]:
            self.add_measurement(row)
        self.validation_status.set(f"실측 CSV {Path(path).name}: {len(data['rows'])}건 불러옴. 실측값 비교를 눌러 주세요.")

    def export_measurements(self):
        rows = self._measurement_raw()
        try:
            plan = normalize_plan(self._raw_plan())
            analyze_measurements(plan, calculate(plan), rows)
        except ValueError as exc:
            self.validation_status.set(f"저장 전 입력 확인: {exc}")
            return
        path = filedialog.asksaveasfilename(title="실측 CSV 저장", defaultextension=".csv", filetypes=[("CSV 파일", "*.csv")])
        if not path:
            return
        try:
            save_measurements_csv(path, plan["vehicle"], plan["productName"], rows)
        except OSError as exc:
            messagebox.showerror("실측 CSV 저장 실패", str(exc), parent=self)
            return
        self.validation_status.set(f"실측 {len(rows)}건 저장: {Path(path).name}")

    def _field(self, parent, label, variable, row, column, choices=None):
        box = ttk.Frame(parent, padding=(0, 0, 12, 9))
        box.grid(row=row, column=column, sticky="ew")
        parent.columnconfigure(column, weight=1)
        ttk.Label(box, text=label, background="#ffffff").pack(anchor="w", pady=(0, 4))
        if choices is None:
            widget = ttk.Entry(box, textvariable=variable)
        else:
            widget = ttk.Combobox(box, textvariable=variable, values=choices, state="normal" if choices == MATERIALS else "readonly")
        widget.pack(fill="x")
        return widget

    def add_row(self, data=None):
        data = data or {}
        frame = ttk.LabelFrame(self.rows_frame, padding=14)
        frame.pack(fill="x", pady=(0, 12))
        variables = {name: tk.StringVar(value=str(data.get(name, "") if data.get(name) is not None else "")) for name in ROW_FIELDS}
        if not variables["stage"].get():
            existing = []
            for item in self.rows:
                try:
                    existing.append(int(float(item["vars"]["stage"].get())))
                except (ValueError, OverflowError):
                    continue
            variables["stage"].set(str(max(existing, default=0) + 1))
        if not variables["mode"].get():
            variables["mode"].set("speed")
        for variable in variables.values():
            variable.trace_add("write", self._changed)
        fields = (
            ("용접 길이 (mm)", "length", None), ("작업 단계 (같은 번호는 동시)", "stage", None),
            ("시간 입력 방식", "mode", ("speed", "time")), ("이동 속도 (mm/min)", "speed", None),
            ("직접 입력 시간 (초)", "time", None),
            ("용접 전압 (V)", "voltage", None), ("용접 전류 (A)", "current", None),
            ("부품 A 재질", "materialA", MATERIALS), ("부품 A 두께 (mm)", "thicknessA", None),
            ("부품 B 재질", "materialB", MATERIALS), ("부품 B 두께 (mm)", "thicknessB", None),
            ("이음 형상", "joint", JOINTS), ("용접 자세", "position", POSITIONS),
        )
        widgets = {}
        for index, (label, name, choices) in enumerate(fields):
            widgets[name] = self._field(frame, label, variables[name], index // 4, index % 4, choices)
        button = ttk.Button(frame, text="이 구간 삭제", command=lambda: self.remove_row(frame))
        button.grid(row=4, column=3, sticky="e", pady=(5, 0))
        self.rows.append({"frame": frame, "vars": variables, "button": button, "widgets": widgets})
        variables["mode"].trace_add("write", lambda *_: self._update_mode(frame))
        self._update_mode(frame)
        self._refresh_rows()
        self._refresh_wire_rows()
        self._refresh_wps_targets()
        self._changed()

    def _update_mode(self, frame):
        item = next((item for item in self.rows if item["frame"] is frame), None)
        if not item:
            return
        direct = item["vars"]["mode"].get() == "time"
        item["widgets"]["speed"].configure(state="disabled" if direct else "normal")
        item["widgets"]["time"].configure(state="normal" if direct else "disabled")

    def _refresh_rows(self):
        for index, item in enumerate(self.rows, 1):
            item["frame"].configure(text=f"용접 구간 {index}")
            item["button"].configure(state="disabled" if len(self.rows) == 1 else "normal")

    def remove_row(self, frame):
        if len(self.rows) == 1:
            return
        self.rows = [item for item in self.rows if item["frame"] is not frame]
        frame.destroy()
        self._refresh_rows()
        self._refresh_wire_rows()
        self._refresh_wps_targets()
        self._changed()

    def _changed(self, *_):
        if self._loading:
            return
        self._source = "사용자 입력"
        self._sample = False
        if self._calculated_once:
            if self._pending is not None:
                self.after_cancel(self._pending)
            action = self.run_wire_only if self._result_mode == "wire" else self.run_calculation
            def refresh():
                action(show_result=False)
                if self._wire_calculated:
                    self.run_wire_calculation()
            self._pending = self.after(350, refresh)

    def _fill(self, raw, source):
        previous_product = (self.vars["vehicle"].get().strip(), self.vars["productName"].get().strip())
        next_product = (str(raw.get("vehicle") or "").strip(), str(raw.get("productName") or "").strip())
        self._loading = True
        try:
            self.clear_product_image()
            for item in self.rows:
                item["frame"].destroy()
            self.rows.clear()
            for name in COMMON_FIELDS:
                value = raw.get(name)
                self.vars[name].set("" if value is None else str(value))
            for row in raw["rows"]:
                self.add_row(row)
            self._source = source
            self._sample = bool(raw.get("sample"))
        finally:
            self._loading = False
        if previous_product != next_product and any(previous_product):
            for item in self.measurement_rows:
                item["frame"].destroy()
            self.measurement_rows.clear()
            self.add_measurement()
            self.validation_report.configure(state="normal")
            self.validation_report.delete("1.0", "end")
            self.validation_report.configure(state="disabled")
            self.validation_status.set("제품이 바뀌어 이전 실측값을 비웠습니다. 새 제품의 실측값을 입력해 주세요.")
        self.run_calculation(show_result=True)

    def load_sample(self):
        self._fill(copy.deepcopy(SAMPLE), "화면 확인용 예시 데이터")

    def import_csv(self):
        path = filedialog.askopenfilename(title="용접 조건 CSV 선택", filetypes=[("CSV 파일", "*.csv")])
        if not path:
            return
        try:
            plan = load_csv(path)
        except (OSError, UnicodeError, ValueError) as exc:
            messagebox.showerror("CSV 불러오기 실패", str(exc), parent=self)
            return
        self._fill(plan, f"CSV 파일: {Path(path).name}")

    def _raw_plan(self):
        return {
            **{name: variable.get() for name, variable in self.vars.items()},
            "rows": [{name: variable.get() for name, variable in item["vars"].items()} for item in self.rows],
            "sample": self._sample,
        }

    def run_calculation(self, show_result=False):
        self._pending = None
        try:
            plan = normalize_plan(self._raw_plan())
            numbers = calculate(plan)
        except ValueError as exc:
            self.status.set(f"입력 확인: {exc}")
            if show_result:
                self.tabs.select(0)
            return
        self._calculated_once = True
        self._result_mode = "calc"
        self.status.set(f"계산 완료 · {self._source} · 미검증 추정")
        self._write_report(plan, numbers)
        self._render_result_summary(plan, numbers)
        self._render_product_results(plan["rows"], plan)
        if show_result:
            self.result_tabs.select(0)
            self.tabs.select(1)

    def run_wire_only(self, show_result=False):
        self._pending = None
        raw = self._raw_plan()
        self.report.configure(state="normal")
        self.report.delete("1.0", "end")
        self.report.insert("end", "재질 기반 와이어 예비 후보\n\n", "title")
        self.report.insert("end", f"차종: {raw['vehicle'] or '미입력'}  |  제품명: {raw['productName'] or '미입력'}\n")
        self.report.insert("end", f"제품 형상 이미지: {self.product_image_path or '미첨부'}\n")
        self.report.insert("end", "재질만으로 후보를 확인할 수 있습니다. 전압·전류·와이어 송급 속도는 제시하지 않습니다.\n")
        for index, row in enumerate(raw["rows"], 1):
            candidate = recommend_wire(row, raw)
            self.report.insert("end", f"\n{index}번 구간 · {candidate['status']}\n", "heading")
            if "wire" in candidate:
                self.report.insert("end", f"와이어: {candidate['wire']}\n근거: {candidate['reason']}\n")
                self.report.insert("end", f"보호가스: {candidate['gas_note']}\n")
                self._insert_wire_products(candidate)
                if candidate["missing"]:
                    self.report.insert("end", f"추가 확인: {', '.join(candidate['missing'])}\n")
                self.report.insert("end", f"출처: {candidate['source']}\n{candidate['url']}\n")
            else:
                self.report.insert("end", candidate["message"] + "\n")
        self.report.insert("end", "\n표시된 와이어는 제조사 자료 기반 검토 후보입니다. 시편 시험과 품질 확인 전에는 양산 조건으로 사용하지 마세요.\n", "warning")
        self.report.configure(state="disabled")
        self._calculated_once = True
        self._result_mode = "wire"
        self.status.set(f"와이어 예비 후보 표시 · {self._source} · 양산 승인 아님")
        self.summary_product.set(f"{raw['vehicle'] or '차종 미입력'} · {raw['productName'] or '제품명 미입력'}")
        self.summary_note.set("와이어 후보만 갱신했습니다. 시간·생산량은 계산하기를 눌러 확인하세요.")
        for value in self.summary_metrics.values():
            value.set("—")
        self.production_table.delete(*self.production_table.get_children())
        self.segment_table.delete(*self.segment_table.get_children())
        self.summary_footer.set("재질 기반 와이어 후보는 '와이어 추천 제품'에서 확인하세요.")
        self._render_product_results(raw["rows"], raw)
        if show_result:
            self.result_tabs.select(1)
            self.tabs.select(1)

    def run_wire_calculation(self, show_tab=False):
        try:
            plan = normalize_plan(self._raw_plan())
            production = calculate(plan)
            usage = calculate_wire_usage(plan, production)
        except ValueError as exc:
            self.wire_status.set(f"와이어 입력 확인: {exc}")
            return
        self._wire_calculated = True
        self.wire_status.set("와이어 사용량 계산 완료 · 송급량 추정과 실측값을 구분해 확인하세요.")
        lines = [f"차종: {plan['vehicle'] or '미입력'}  |  제품명: {plan['productName'] or '미입력'}"]
        if usage["status"] == "미입력":
            lines.append("와이어 정보를 입력하면 사용량을 계산합니다.")
        else:
            for index, item in enumerate(usage["rows"], 1):
                if "used_g" in item:
                    lines.append(f"{index}번 구간 · {item['name']} · {item['source']}")
                    lines.append(f"  기본 송급 {fmt_kwh(item['base_length'])} m + 추가 송급 {fmt_kwh(item['extra_length'])} m")
                    lines.append(f"  송급 와이어 {fmt_kwh(item['fed_g'])} g + 절단·폐기 {fmt_kwh(item['scrap_g'])} g = {fmt_kwh(item['used_g'])} g/사이클")
                    if item["deposited_g"] is not None:
                        lines.append(f"  예상 용착량: {fmt_kwh(item['deposited_g'])} g/사이클")
                else:
                    lines.append(f"{index}번 구간 · 입력 자료 부족")
            if usage["missing"]:
                lines.append("총 사용량 계산에 필요한 값: " + ", ".join(usage["missing"]))
            else:
                lines.extend((
                    f"예상 사용량: {fmt_kwh(usage['cycle_g'])} g/사이클 · {fmt_kwh(usage['part_g'])} g/개",
                    f"시간당 {fmt_kwh(usage['hour_kg'])} kg · 일 {fmt_kwh(usage['day_kg'])} kg",
                    f"월 {fmt_kwh(usage['month_kg'])} kg · 년 {fmt_kwh(usage['year_kg'])} kg",
                ))
                if "deposited_g" in usage:
                    lines.append(f"용착 효율 적용 예상 용착량: {fmt_kwh(usage['deposited_g'])} g/사이클")
                if "cost_cycle" in usage:
                    lines.append(f"예상 와이어 비용: {usage['cost_cycle']:,.2f} 원/사이클 · {usage['cost_part']:,.2f} 원/개")
            if "measured_g_cycle" in usage:
                lines.append(f"잔량 실측 사용량: {fmt_kwh(usage['measured_g_cycle'])} g/사이클 · {fmt_kwh(usage['measured_g_part'])} g/개")
                if "difference_g" in usage:
                    lines.append(f"실측 - 추정: {usage['difference_g']:+.5f} g/사이클" + (f" ({usage['difference_pct']:+.2f}%)" if usage["difference_pct"] is not None else ""))
            if usage["omitted_extras"] or usage["omitted_scrap"]:
                lines.append("추가 송급 또는 절단·폐기량이 비어 있는 구간은 해당 손실이 추정에 포함되지 않았습니다.")
        lines.append("송급량 = π × (직경/2)² × 송급 길이 × 밀도. 전류·전압만으로 와이어 사용량을 역산하지 않습니다.")
        lines.append("실측값에는 시동·종료·교체 손실이 포함될 수 있습니다. 같은 제품·설비 조건으로 비교하세요.")
        self.wire_report.configure(state="normal")
        self.wire_report.delete("1.0", "end")
        self.wire_report.insert("end", "\n".join(lines))
        self.wire_report.configure(state="disabled")
        if show_tab:
            self.tabs.select(3)

    def _insert_wire_products(self, candidate):
        self.report.insert("end", "브랜드별 추천 와이어 (공식 제품 자료 기준):\n")
        products_by_maker = {product["maker"]: product for product in candidate["products"]}
        for maker in MAKERS:
            brand = "COWEL(공식명 KOWEL)" if maker == "KOWEL" else maker
            product = products_by_maker.get(maker)
            if product:
                self.report.insert("end", f"  • 브랜드: {brand} | 제품명: {product['name']} | AWS: {product['aws']}\n")
                self.report.insert("end", f"    제조사 자료: {product['url']}\n")
            else:
                self.report.insert("end", f"  • 브랜드: {brand} | 동일 AWS 분류 제품 미확인\n")
        self.report.insert("end", "  제품별 보호가스·직경·국내 공급 및 실제 적용성은 별도 확인하세요.\n")

    def _write_report(self, plan, numbers):
        report = self.report
        report.configure(state="normal")
        report.delete("1.0", "end")

        def line(text="", tag=None):
            report.insert("end", text + "\n", tag)

        line("용접 시간·생산량 결과", "title")
        line(f"차종: {plan['vehicle'] or '미입력'}  |  제품명: {plan['productName'] or '미입력'}")
        line(f"제품 형상 이미지: {self.product_image_path or '미첨부'}")
        line(f"출처: {self._source}  |  검증 상태: 미검증 추정")
        if plan["sample"]:
            line("화면 확인용 예시입니다. 양산 조건·확정 생산능력으로 사용 불가", "warning")
        line("\n시간과 생산량", "heading")
        line(f"총 아크 시간(구간별 합계): {fmt(numbers['arc'])} 초/사이클")
        line(f"경과 용접 시간(동시 단계 반영): {fmt(numbers['weldElapsed'])} 초/사이클")
        line(f"사이클 시간: {fmt(numbers['cycle'])} 초/사이클")
        line(f"UPH: {fmt(numbers['uph'])} 개/시간")
        line(f"일 예상 생산량: {math.floor(numbers['day']):,} 개")
        line(f"월 예상 생산량: {math.floor(numbers['month']):,} 개")
        line(f"년 예상 생산량: {math.floor(numbers['year']):,} 개")
        line("\n구간별 계산 근거", "heading")
        for index, row in enumerate(plan["rows"], 1):
            if row["mode"] == "speed":
                line(f"{index}번 · {row['stage']}단계: {fmt(row['length'])} mm ÷ {fmt(row['speed'])} mm/min × 60 = {fmt(row['time'])} 초")
            else:
                line(f"{index}번 · {row['stage']}단계: 길이 {fmt(row['length'])} mm, 직접 입력한 시간 {fmt(row['time'])} 초")
        line(f"사이클 = 단계별 최장 시간 합계 {fmt(numbers['weldElapsed'])} + 비아크 시간 {fmt(plan['nonArc'])} = {fmt(numbers['cycle'])} 초")
        line(f"UPH = 3,600 ÷ {fmt(numbers['cycle'])} × {plan['batch']}개/사이클 × {fmt(plan['uptime'])}%")
        line("생산량은 반올림 전 계산값을 이어서 사용하고 최종 표시값만 내림 처리합니다.")
        energy = calculate_energy(plan, numbers)
        line("\n예상 소비 전력량", "heading")
        if energy["arc_kwh"] is not None:
            line(f"용접 중 설비 입력 전력량: {fmt_kwh(energy['arc_kwh'])} kWh/사이클")
        if energy["nonarc_kwh"] is not None:
            line(f"비아크 설비 입력 전력량: {fmt_kwh(energy['nonarc_kwh'])} kWh/사이클")
        if "cycle_kwh" in energy:
            line(f"합계: {fmt_kwh(energy['cycle_kwh'])} kWh/사이클")
            line(f"제품 1개당: {fmt_kwh(energy['part_kwh'])} kWh/개")
            line(f"시간당: {fmt_kwh(energy['hour_kwh'])} kWh")
            line(f"일: {fmt_kwh(energy['day_kwh'])} kWh  |  월: {fmt_kwh(energy['month_kwh'])} kWh  |  년: {fmt_kwh(energy['year_kwh'])} kWh")
            line("용접 중 = Σ(구간 전압 × 전류 × 아크 시간) ÷ (3,600,000 × 효율). 비아크 = 입력전력(kW) × 비아크 시간(초) ÷ 3,600.")
            line("시간·일·월·년 값은 제품당 전력량 × 예상 생산량으로 계산합니다. 가동하지 않는 시간의 대기전력과 주변 설비는 제외합니다.")
        else:
            line(f"합계 계산에 필요한 값: {', '.join(energy['missing'])}")
            line("값이 없는 전력 항목은 0으로 가정하지 않습니다.")
        line("모든 전력량은 입력값에 따른 추정치입니다. 실제 사용량은 설비 입력 전력계로 검증하세요.")
        try:
            wire_usage = calculate_wire_usage(plan, numbers)
        except ValueError as exc:
            line(f"\n와이어 사용량: 입력 확인 필요 · {exc}", "heading")
        else:
            line("\n와이어 사용량", "heading")
            if "cycle_g" in wire_usage:
                line(f"예상 와이어 사용량: {fmt_kwh(wire_usage['cycle_g'])} g/사이클 · {fmt_kwh(wire_usage['part_g'])} g/개")
                line(f"일 {fmt_kwh(wire_usage['day_kg'])} kg · 월 {fmt_kwh(wire_usage['month_kg'])} kg · 년 {fmt_kwh(wire_usage['year_kg'])} kg")
            elif wire_usage["status"] == "미입력":
                line("선택 사항입니다. '와이어 사용량 (선택)' 탭에서 송급 정보를 입력해 계산하세요.")
            else:
                line("계산에 필요한 값: " + ", ".join(wire_usage["missing"]))
            if "measured_g_cycle" in wire_usage:
                line(f"실측 잔량 기준: {fmt_kwh(wire_usage['measured_g_cycle'])} g/사이클")
            line("와이어 사용량은 송급량 추정치입니다. 상세 근거는 '와이어 사용량 (선택)' 탭에서 확인하세요.")
        line("\n와이어 후보", "heading")
        for index, row in enumerate(plan["rows"], 1):
            candidate = recommend_wire(row, plan)
            line(f"{index}번 구간 · {candidate['status']}")
            if "wire" in candidate:
                line(f"  와이어: {candidate['wire']}")
                line(f"  근거: {candidate['reason']}")
                line(f"  가스 확인: {candidate['gas_note']}")
                self._insert_wire_products(candidate)
                if candidate["missing"]:
                    line(f"  추가 확인: {', '.join(candidate['missing'])}")
                line(f"  출처: {candidate['source']}")
                line(f"  {candidate['url']}")
            else:
                line(f"  {candidate['message']}")
            applied = self.rows[index - 1].get("approved_wps")
            if applied and row["mode"] == "speed" and row["voltage"] == applied["voltage"] and row["current"] == applied["current"] and row["speed"] == applied["travelSpeed"] and find_matching_wps([applied], row, plan):
                line(f"  전압·전류·이동 속도: 승인 조건 {applied['approvalId']} · 개정 {applied['revision']}에서 적용. 현행 유효성 확인 필요.")
            else:
                line("  전압·전류·이동 속도: 사내 승인 조건 적용 기록 없음. 입력값의 승인 여부 확인 필요.")
            line()
        line("같은 작업 단계의 구간은 동시에 용접하고, 단계 간에는 순서대로 작업한다고 가정합니다. 불량·재작업·병목·설비 수는 반영하지 않습니다.")
        report.configure(state="disabled")


if __name__ == "__main__":
    WeldApp().mainloop()
