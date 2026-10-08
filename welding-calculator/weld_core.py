"""용접 시간 계산과 근거가 표시된 와이어 후보 규칙."""

from __future__ import annotations

import csv
from pathlib import Path
from wire_catalog import MAKERS, PRODUCTS
from wire_usage import WIRE_COMMON_FIELDS, WIRE_ROW_FIELDS


SAMPLE = {
    "vehicle": "시험 차종 A",
    "productName": "리어 머플러",
    "process": "GMAW",
    "equipment": "예시 로봇 용접기",
    "gas": "Ar98O2_2",
    "batch": "2",
    "nonArc": "30",
    "nonArcPower": "1",
    "efficiency": "85",
    "uptime": "80",
    "hours": "8",
    "days": "22",
    "months": "12",
    "rows": [
        {"length": "600", "mode": "speed", "speed": "300", "time": "", "voltage": "24", "current": "180", "materialA": "409", "thicknessA": "1.5", "materialB": "409Ti", "thicknessB": "1.5", "joint": "butt", "position": "flat"},
        {"length": "300", "mode": "time", "speed": "", "time": "60", "voltage": "22", "current": "150", "materialA": "409", "thicknessA": "1.5", "materialB": "409", "thicknessB": "1.5", "joint": "lap", "position": "rotating"},
    ],
    "sample": True,
}

COMMON = ("batch", "nonArc", "nonArcPower", "efficiency", "uptime", "hours", "days", "months", "vehicle", "productName", "process", "equipment", "gas") + WIRE_COMMON_FIELDS
ROW_FIELDS = ("length", "stage", "mode", "speed", "time", "voltage", "current", "materialA", "thicknessA", "materialB", "thicknessB", "joint", "position") + WIRE_ROW_FIELDS
REQUIRED_CSV = ("length", "mode", "speed", "time", "batch", "nonArc", "uptime", "hours", "days", "months")

SOURCES = {
    "409": ("Lincoln Electric ER409Nb 제품 자료", "https://ch-delivery.lincolnelectric.com/api/public/content/f5e38ae6ebf441829d73d7b1a404818b?v=84bee2da"),
    "stainless": ("Lincoln Electric 스테인리스 용가재 표", "https://ch-delivery.lincolnelectric.com/api/public/content/468b884c48d34770b842ed4d20610306?v=edd177d4"),
    "dissimilar": ("ESAB 이종재 GMAW 사례", "https://esab.com/ae/mea_en/esab-university/blogs/welding-dissimilar-metals-using-309-stainless-steel/"),
}


def _number(value, label, *, allow_zero=False, optional=False):
    text = str(value if value is not None else "").strip()
    if optional and not text:
        return None
    if not text:
        raise ValueError(f"{label}을(를) 입력해 주세요.")
    try:
        number = float(text)
    except ValueError as exc:
        raise ValueError(f"{label}은(는) 숫자로 입력해 주세요.") from exc
    if not (number < float("inf")) or number < 0 or (number == 0 and not allow_zero):
        raise ValueError(f"{label}은(는) {'0 이상' if allow_zero else '0보다 큰 값'}이어야 합니다.")
    return number


def _integer(value, label, maximum=None):
    number = _number(value, label)
    if not number.is_integer() or (maximum is not None and number > maximum):
        limit = f"1~{maximum}" if maximum is not None else "1 이상"
        raise ValueError(f"{label}은(는) {limit}의 정수로 입력해 주세요.")
    return int(number)


def normalize_plan(raw):
    raw_rows = raw.get("rows") or []
    if not raw_rows:
        raise ValueError("용접 구간을 한 개 이상 추가해 주세요.")
    rows = []
    for index, source in enumerate(raw_rows, 1):
        prefix = f"{index}번 구간"
        length = _number(source.get("length"), f"{prefix} 용접 길이")
        mode = str(source.get("mode", "")).strip()
        if mode == "speed":
            speed = _number(source.get("speed"), f"{prefix} 이동 속도")
            time = length / speed * 60
        elif mode == "time":
            speed = None
            time = _number(source.get("time"), f"{prefix} 용접 시간")
        else:
            raise ValueError(f"{prefix}의 시간 입력 방식은 speed 또는 time이어야 합니다.")
        rows.append({
            "length": length, "stage": _integer(source.get("stage") or index, f"{prefix} 작업 단계"),
            "mode": mode, "speed": speed, "time": time,
            "voltage": _number(source.get("voltage"), f"{prefix} 전압", optional=True),
            "current": _number(source.get("current"), f"{prefix} 전류", optional=True),
            "materialA": str(source.get("materialA") or "").strip(),
            "thicknessA": _number(source.get("thicknessA"), f"{prefix} 부품 A 두께", optional=True),
            "materialB": str(source.get("materialB") or "").strip(),
            "thicknessB": _number(source.get("thicknessB"), f"{prefix} 부품 B 두께", optional=True),
            "joint": str(source.get("joint") or "").strip(),
            "position": str(source.get("position") or "").strip(),
            **{key: str(source.get(key) or "").strip() for key in WIRE_ROW_FIELDS},
        })
    uptime = _number(raw.get("uptime"), "가동률", allow_zero=True)
    if uptime > 100:
        raise ValueError("가동률은 0~100%로 입력해 주세요.")
    efficiency = _number(raw.get("efficiency"), "용접기 효율", optional=True)
    if efficiency is not None and efficiency > 100:
        raise ValueError("용접기 효율은 0보다 크고 100% 이하여야 합니다.")
    return {
        "rows": rows,
        "batch": _integer(raw.get("batch"), "한 사이클 생산 수량"),
        "nonArc": _number(raw.get("nonArc"), "비아크 시간", allow_zero=True),
        "nonArcPower": _number(raw.get("nonArcPower"), "비아크 설비 입력전력", allow_zero=True, optional=True),
        "efficiency": efficiency,
        "uptime": uptime,
        "hours": _number(raw.get("hours"), "일일 근무시간"),
        "days": _integer(raw.get("days"), "월간 가동일수", 31),
        "months": _integer(raw.get("months"), "연간 가동 개월 수", 12),
        **{key: str(raw.get(key) or "").strip() for key in ("vehicle", "productName", "process", "equipment", "gas")},
        **{key: str(raw.get(key) or "").strip() for key in WIRE_COMMON_FIELDS},
        "sample": bool(raw.get("sample", False)),
    }


def calculate(plan):
    arc = sum(row["time"] for row in plan["rows"])
    stages = {}
    for row in plan["rows"]:
        stage = row["stage"]
        stages[stage] = max(stages.get(stage, 0), row["time"])
    weld_elapsed = sum(stages.values())
    cycle = weld_elapsed + plan["nonArc"]
    uph = 3600 / cycle * plan["batch"] * plan["uptime"] / 100
    day = uph * plan["hours"]
    month = day * plan["days"]
    year = month * plan["months"]
    return {"arc": arc, "weldElapsed": weld_elapsed, "cycle": cycle, "uph": uph, "day": day, "month": month, "year": year}


def calculate_energy(plan, production):
    """용접 출력(V×A)을 효율로 보정한 설비 입력 전력량 추정치."""
    missing = []
    if plan["efficiency"] is None:
        missing.append("용접기 효율 (%)")
    for index, row in enumerate(plan["rows"], 1):
        if row["voltage"] is None:
            missing.append(f"{index}번 구간 전압 (V)")
        if row["current"] is None:
            missing.append(f"{index}번 구간 전류 (A)")
    arc_kwh = None
    if not missing:
        arc_kwh = sum(
            row["voltage"] * row["current"] * row["time"]
            for row in plan["rows"]
        ) / (3_600_000 * plan["efficiency"] / 100)
    nonarc_kwh = None
    if plan["nonArc"] == 0:
        nonarc_kwh = 0.0
    elif plan["nonArcPower"] is None:
        missing.append("비아크 설비 입력전력 (kW)")
    else:
        nonarc_kwh = plan["nonArcPower"] * plan["nonArc"] / 3600
    result = {"missing": missing, "arc_kwh": arc_kwh, "nonarc_kwh": nonarc_kwh}
    if arc_kwh is not None and nonarc_kwh is not None:
        cycle_kwh = arc_kwh + nonarc_kwh
        part_kwh = cycle_kwh / plan["batch"]
        result.update({
            "cycle_kwh": cycle_kwh,
            "part_kwh": part_kwh,
            "hour_kwh": part_kwh * production["uph"],
            "day_kwh": part_kwh * production["day"],
            "month_kwh": part_kwh * production["month"],
            "year_kwh": part_kwh * production["year"],
        })
    return result


def recommend_wire(row, plan):
    material_a = str(row.get("materialA") or "").strip()
    material_b = str(row.get("materialB") or "").strip()
    if not material_a or not material_b:
        return {"status": "자료 부족", "message": "두 부품의 재질을 선택하면 와이어 예비 후보를 볼 수 있습니다."}
    process = str(plan.get("process") or "").strip()
    if process and process != "GMAW":
        return {"status": "자료 부족", "message": "현재 와이어 후보 규칙은 MIG/MAG(GMAW)만 지원합니다."}
    materials = {material_a, material_b}
    if materials <= {"409", "409Ti"}:
        wire, reason, key, product_key, expected_gas = "ER409Nb", "409·409Ti 모재와 자동차 배기계에 적용하도록 제시된 페라이트계 와이어입니다.", "409", "409", "Ar98O2_2"
    elif materials == {"304L"}:
        wire, reason, key, product_key, expected_gas = "ER308L 또는 ER308LSi", "304L 모재용 GMAW 용가재 표에 제시된 분류입니다.", "stainless", "304L", None
    elif materials == {"304"}:
        wire, reason, key, product_key, expected_gas = "ER308 또는 ER308Si", "304 모재용 GMAW 용가재 표에 제시된 분류입니다.", "stainless", "304", None
    elif "carbon" in materials and ("304" in materials or "304L" in materials):
        wire, reason, key, product_key, expected_gas = "ER309LSi", "탄소강·스테인리스 이종재 GMAW 제조사 사례의 와이어입니다. 이 부품의 적합성은 시험해야 합니다.", "dissimilar", "dissimilar", "Ar98CO2_2"
    else:
        return {"status": "자료 부족", "message": "이 재질 조합의 검증된 후보 규칙이 없습니다. 제조사 자료와 사내 WPS를 확인해 주세요."}
    gas = str(plan.get("gas") or "").strip()
    if not gas:
        gas_note = "보호가스가 입력되지 않았습니다. 실제 사용할 가스와 와이어 제품의 적합성을 확인하세요."
    elif expected_gas is None:
        gas_note = "선택한 제품과 보호가스의 조합은 해당 제품 자료와 장비 조건으로 별도 확인해야 합니다."
    elif gas == expected_gas:
        gas_note = "입력한 보호가스가 기존 분류 참고 자료와 일치합니다. 아래 제조사 제품별 적합성은 별도 확인하세요."
    else:
        gas_note = "입력한 보호가스가 인용 자료와 다릅니다. 해당 가스 조합의 적합성을 먼저 확인하세요."
    label, url = SOURCES[key]
    products = [dict(product) for product in PRODUCTS[product_key]]
    unverified_makers = [maker for maker in MAKERS if maker not in {product["maker"] for product in products}]
    missing = []
    if not process:
        missing.append("용접 방식(GMAW 적용 여부)")
    if not row.get("thicknessA") or not row.get("thicknessB"):
        missing.append("부품 두께")
    if not row.get("joint"):
        missing.append("이음 형상")
    if not row.get("position"):
        missing.append("용접 자세")
    if not str(plan.get("equipment") or "").strip():
        missing.append("설비")
    if not gas:
        missing.append("보호가스")
    return {
        "status": "재질 기반 예비 후보" if missing else "제조사 자료 기반 시험 후보",
        "wire": wire, "reason": reason, "gas_note": gas_note, "source": label, "url": url,
        "products": products, "unverified_makers": unverified_makers,
        "missing": missing,
    }


def load_csv(path):
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        missing = [name for name in REQUIRED_CSV if name not in headers]
        if missing:
            raise ValueError(f"CSV 제목에 필요한 항목이 없습니다: {', '.join(missing)}")
        if len(headers) != len(set(headers)):
            raise ValueError("CSV 제목에 중복된 항목이 있습니다.")
        records = list(reader)
    if not records:
        raise ValueError("CSV에 용접 구간을 한 개 이상 입력해 주세요.")
    if any(None in record for record in records):
        raise ValueError("CSV 행에 제목보다 많은 값이 있습니다.")
    for index, record in enumerate(records[1:], 3):
        if any((record.get(name) or "").strip() for name in COMMON):
            raise ValueError(f"{index}행의 공통 조건을 비워 주세요. 공통 조건은 첫 행에만 입력합니다.")
    first = records[0]
    raw = {
        "rows": [{name: record.get(name) or "" for name in ROW_FIELDS} for record in records],
        **{name: first.get(name) or "" for name in COMMON},
        "sample": (first.get("dataType") or "").strip() == "sample",
    }
    return normalize_plan(raw)
