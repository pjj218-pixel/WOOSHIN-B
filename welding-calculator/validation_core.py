"""실측 사이클 시간·품질 기록의 비교 분석."""

from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path


LEAK_VALUES = ("미검사", "합격", "불합격")
DEFECT_VALUES = ("미검사", "없음", "있음")
MEASUREMENT_FIELDS = ("vehicle", "productName", "cycle", "leak", "defect", "note")


def analyze_measurements(plan, calculation, raw_rows, tolerance_text=""):
    if not raw_rows:
        raise ValueError("실측값을 한 건 이상 입력해 주세요.")
    rows = []
    for index, raw in enumerate(raw_rows, 1):
        try:
            cycle = float(str(raw.get("cycle") or "").strip())
        except ValueError as exc:
            raise ValueError(f"{index}번 실측 사이클 시간을 숫자로 입력해 주세요.") from exc
        if not math.isfinite(cycle) or cycle <= 0:
            raise ValueError(f"{index}번 실측 사이클 시간은 0보다 커야 합니다.")
        leak = str(raw.get("leak") or "미검사").strip()
        defect = str(raw.get("defect") or "미검사").strip()
        if leak not in LEAK_VALUES or defect not in DEFECT_VALUES:
            raise ValueError(f"{index}번 검사 결과를 목록에서 선택해 주세요.")
        rows.append({"cycle": cycle, "leak": leak, "defect": defect, "note": str(raw.get("note") or "").strip()})
    tolerance = None
    if str(tolerance_text).strip():
        try:
            tolerance = float(str(tolerance_text).strip())
        except ValueError as exc:
            raise ValueError("허용 오차율은 숫자로 입력해 주세요.") from exc
        if not math.isfinite(tolerance) or tolerance < 0:
            raise ValueError("허용 오차율은 0 이상이어야 합니다.")
    actual_mean = statistics.mean(row["cycle"] for row in rows)
    estimated = calculation["cycle"]
    error_seconds = estimated - actual_mean
    error_pct = error_seconds / actual_mean * 100
    quality_fail = any(row["leak"] == "불합격" or row["defect"] == "있음" for row in rows)
    quality_untested = any(row["leak"] == "미검사" or row["defect"] == "미검사" for row in rows)
    quality_status = "불합격·불량 기록 있음" if quality_fail else "검사 미완료" if quality_untested else "입력된 검사 모두 합격"
    actual_uph = 3600 / actual_mean * plan["batch"] * plan["uptime"] / 100
    return {
        "rows": rows, "count": len(rows), "actual_mean": actual_mean,
        "minimum": min(row["cycle"] for row in rows), "maximum": max(row["cycle"] for row in rows),
        "estimated": estimated, "error_seconds": error_seconds, "error_pct": error_pct,
        "tolerance": tolerance, "within_tolerance": None if tolerance is None else abs(error_pct) <= tolerance,
        "quality_status": quality_status,
        "leak_fail_count": sum(row["leak"] == "불합격" for row in rows),
        "defect_count": sum(row["defect"] == "있음" for row in rows),
        "suggested_nonarc": actual_mean - calculation["weldElapsed"],
        "actual_uph": actual_uph,
    }


def load_measurements_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        if not all(name in headers for name in MEASUREMENT_FIELDS):
            raise ValueError("실측 CSV에 vehicle, productName, cycle, leak, defect, note 열이 필요합니다.")
        records = list(reader)
    if not records or any(None in record for record in records):
        raise ValueError("실측 CSV에 올바른 측정 행을 한 개 이상 입력해 주세요.")
    vehicle = (records[0].get("vehicle") or "").strip()
    product = (records[0].get("productName") or "").strip()
    if any((row.get("vehicle") or "").strip() != vehicle or (row.get("productName") or "").strip() != product for row in records):
        raise ValueError("한 CSV에는 같은 차종·제품명에 대한 실측값만 입력해 주세요.")
    rows = [{name: row.get(name) or "" for name in ("cycle", "leak", "defect", "note")} for row in records]
    return {"vehicle": vehicle, "productName": product, "rows": rows}


def save_measurements_csv(path, vehicle, product_name, rows):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MEASUREMENT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({"vehicle": vehicle, "productName": product_name,
                             **{name: row.get(name, "") for name in ("cycle", "leak", "defect", "note")}})
