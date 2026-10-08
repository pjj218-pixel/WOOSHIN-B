"""사용자가 제공한 사내 승인 조건 CSV의 엄격한 일치 검색."""

import csv
import math
from pathlib import Path


FIELDS = (
    "approvalId", "revision", "approvedBy", "process", "materialA", "materialB",
    "minThickness", "maxThickness", "joint", "position", "gas", "equipment",
    "wire", "voltage", "current", "travelSpeed",
)


def _positive(value, label):
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}은(는) 양수로 입력해 주세요.") from exc
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label}은(는) 양수로 입력해 주세요.")
    return number


def load_approved_wps(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in FIELDS if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("승인 조건 CSV에 필요한 열이 없습니다: " + ", ".join(missing))
        records = []
        for line_number, row in enumerate(reader, 2):
            if None in row:
                raise ValueError(f"{line_number}행에 열보다 많은 값이 있습니다.")
            clean = {field: (row.get(field) or "").strip() for field in FIELDS}
            if any(not value for value in clean.values()):
                raise ValueError(f"{line_number}행에 빈 필수 값이 있습니다.")
            clean["minThickness"] = _positive(clean["minThickness"], f"{line_number}행 최소 두께")
            clean["maxThickness"] = _positive(clean["maxThickness"], f"{line_number}행 최대 두께")
            if clean["maxThickness"] < clean["minThickness"]:
                raise ValueError(f"{line_number}행 최대 두께가 최소 두께보다 작습니다.")
            for field in ("voltage", "current", "travelSpeed"):
                clean[field] = _positive(clean[field], f"{line_number}행 {field}")
            records.append(clean)
    if not records:
        raise ValueError("승인 조건 CSV에 데이터 행이 없습니다.")
    return records


def find_matching_wps(rows, row, plan):
    """재질·두께·공정·이음·자세·가스·설비가 전부 일치하는 행만 반환."""
    required_row = ("materialA", "materialB", "thicknessA", "thicknessB", "joint", "position")
    required_plan = ("process", "gas", "equipment")
    if any(not row.get(key) for key in required_row) or any(not plan.get(key) for key in required_plan):
        return []
    pair = {str(row["materialA"]), str(row["materialB"])}
    try:
        thicknesses = (float(row["thicknessA"]), float(row["thicknessB"]))
    except (TypeError, ValueError):
        return []
    if not all(math.isfinite(value) and value > 0 for value in thicknesses):
        return []
    return [item for item in rows if (
        {item["materialA"], item["materialB"]} == pair
        and all(item["minThickness"] <= value <= item["maxThickness"] for value in thicknesses)
        and all(item[key] == plan[key] for key in required_plan)
        and all(item[key] == row[key] for key in ("joint", "position"))
    )]
