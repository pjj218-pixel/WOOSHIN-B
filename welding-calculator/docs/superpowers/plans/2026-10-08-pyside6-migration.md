# PySide6 Welding Calculator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the existing welding calculator in GitHub and replace its Windows Tkinter UI with a complete PySide6 UI while keeping calculation results and CSV formats.

**Architecture:** Keep the five existing Python core modules unchanged. A PySide6 main window coordinates focused pages for work conditions, results, approved WPS, wire usage, and measured validation. Publish this local project under `welding-calculator/` in the existing, unrelated GitHub repository without replacing its root files.

**Tech Stack:** Python 3.14, PySide6 >=6.10.1,<7, Qt Widgets, Python `unittest`, Git.

**Spec:** `docs/superpowers/specs/2026-10-08-pyside6-migration-design.md`

## Global Constraints

- The existing Python core and CSV formats are the source of truth for calculations.
- Keep the Tkinter and web prototypes as archived sources; the new launch path uses PySide6.
- Product images stay local for preview; no image analysis or upload.
- Wire products remain test candidates, distinct from approved WPS and measured validation.
- Preserve all existing content in `pjj218-pixel/WOOSHIN-B`; publish in `welding-calculator/`, never force push.
- Exclude caches, virtual environments, user product images and generated executables from Git.

## Review Focus

- A malformed CSV must leave the current work conditions unchanged (Task 2).
- Removing a welding segment must keep the remaining stage numbers and wire inputs aligned (Tasks 2 and 5).
- Unsupported or directly entered material names must not produce an invented wire product (Task 3).
- A WPS mismatch or cancelled file selection must not change voltage, current or speed (Task 4).
- Missing optional energy or wire fields must still allow time and UPH results (Tasks 3 and 5).

---

### Task 1: Archive the current project in the existing GitHub repository

**Files:** Modify `.gitignore`; create a remote branch based on GitHub `master` with local source copied into `welding-calculator/`.

**Interfaces:** Produces a remote source snapshot and a documented remote branch/commit; no product runtime interface.

- [ ] Inspect local files for accidental credentials or private drawings; retain the existing synthetic examples and bundled Tk runtime.
- [ ] Update `.gitignore` for `.venv/`, build output and `product_images/`; check `git status --ignored`.
- [ ] Preserve a local baseline commit of the existing project and passing `python -m unittest test_weld.py -q` output.
- [ ] Fetch the remote `master`, create an isolated publish checkout from it, copy the baseline under `welding-calculator/`, and verify the remote root `index.html` is unchanged.
- [ ] Commit and push the publish branch without force; record the branch URL for the user.

### Task 2: New shell and work-condition input

**Files:** Create `qt_app.py`, `qt_work_page.py`, `test_qt_gui.py`; modify `용접계산기_실행.cmd`.

**Interfaces:** `WorkPage.raw_plan() -> dict`, `WorkPage.load_raw_plan(raw: dict) -> None`, `WorkPage.apply_row_values(index: int, values: dict) -> None`; `MainWindow.work_page` is the shared input source.

- [ ] Write an offscreen Qt test that opens the app, loads `SAMPLE`, adds/removes a welding row and verifies `raw_plan()`; add a malformed CSV test that preserves prior values.
- [ ] Run `python -m unittest test_qt_gui.py -q` and confirm the test fails because the PySide6 app is absent.
- [ ] Implement the main window, navigation, stylesheet, product/image preview, common fields, editable segment rows and validated CSV import using `load_csv` before `load_raw_plan`.
- [ ] Run the focused Qt tests with `QT_QPA_PLATFORM=offscreen`; commit this working shell.

### Task 3: Results and wire candidate presentation

**Files:** Create `qt_result_page.py`; modify `qt_app.py`, `test_qt_gui.py`.

**Interfaces:** `ResultPage.show_calculation(plan: dict, production: dict, energy: dict | None, candidates: list) -> None`; `ResultPage.show_wire_only(candidates: list) -> None`.

- [ ] Write Qt tests using `SAMPLE` that compare arc time, cycle time, UPH and candidate names against direct core calls; verify unsupported materials show no invented products and missing energy fields leave time metrics visible.
- [ ] Run the focused tests and confirm the new result behavior fails.
- [ ] Connect Calculate and Wire Only actions to `normalize_plan`, `calculate`, `calculate_energy`, `recommend_wire`; render summary cards, period tables, segment breakdowns, source links and validation-state labels.
- [ ] Run focused tests and the existing `test_weld.py`; commit results parity.

### Task 4: Approved WPS workflow

**Files:** Create `qt_wps_page.py`; modify `qt_app.py`, `test_qt_gui.py`.

**Interfaces:** `WpsPage.set_context(raw_plan: dict, index: int) -> None`; successful selection emits `(index, {voltage, current, speed})` to `WorkPage.apply_row_values`.

- [ ] Write an offscreen test with `사내승인조건_입력양식.csv` shaped records that confirms exact matches apply only to the selected row; mismatch and cancelled selection leave values intact.
- [ ] Run the test and confirm failure; implement file loading, exact matching, approval metadata and explicit Apply using existing `approved_wps.py`.
- [ ] Run focused tests and commit WPS parity.

### Task 5: Wire usage and measured validation

**Files:** Create `qt_wire_page.py`, `qt_validation_page.py`; modify `qt_app.py`, `test_qt_gui.py`.

**Interfaces:** `WirePage.calculate(plan: dict, production: dict) -> dict`; `ValidationPage.analyze(plan: dict, production: dict) -> dict`.

- [ ] Write offscreen tests for optional wire fields, wire input alignment after row removal, measured cycle comparison, and measurement CSV save/reload using temporary files.
- [ ] Run tests and confirm failure; implement the two pages against `wire_usage.py` and `validation_core.py`, including all existing optional inputs and status text.
- [ ] Run the focused tests plus `test_weld.py`; commit both workflows.

### Task 6: Launch, parity check and GitHub update

**Files:** Modify `README.md`, `용접계산기_실행.cmd`, `.gitignore`; update published `welding-calculator/` contents.

**Interfaces:** Double-click launch opens PySide6; `python qt_app.py` is the documented direct launch.

- [ ] Add installation/launch instructions for PySide6 and describe the legacy Tkinter entry point.
- [ ] Run all Python tests; run a visible instance with one sample input and compare key results and wire candidates to the core, then check CSV import, WPS, validation, wire usage and image preview.
- [ ] Inspect the final Git diff and exclusion list; commit locally.
- [ ] Update `welding-calculator/` on the publish branch from the final local commit, check the unrelated remote root remains unchanged, and push without force.
