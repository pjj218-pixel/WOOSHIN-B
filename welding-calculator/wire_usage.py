"""구간별 GMAW 솔리드 와이어 송급량과 실측 사용량 비교."""

import math


WIRE_ROW_FIELDS = (
    "wireName", "wireDiameter", "wireFeedSpeed", "wireFeedLength",
    "wireDensity", "wireActualArcTime", "wireExtraFeedLength",
    "wireScrap", "wireDepositionEfficiency", "wirePrice",
)
WIRE_COMMON_FIELDS = ("wireStartKg", "wireEndKg", "wireMeasuredCycles")


def _optional_number(value, label, *, zero=False):
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError as exc:
        raise ValueError(f"{label}은(는) 숫자로 입력해 주세요.") from exc
    if not math.isfinite(number) or number < 0 or (number == 0 and not zero):
        raise ValueError(f"{label}은(는) {'0 이상' if zero else '0보다 큰 값'}이어야 합니다.")
    return number


def calculate_wire_usage(plan, production):
    """입력한 송급 길이 기준 구매 소요량 추정과 저울 실측을 구분한다."""
    rows = plan["rows"]
    active = any(str(row.get(field) or "").strip() for row in rows for field in WIRE_ROW_FIELDS)
    active |= any(str(plan.get(field) or "").strip() for field in WIRE_COMMON_FIELDS)
    if not active:
        return {"status": "미입력", "missing": []}

    missing = []
    details = []
    omitted_extras = False
    omitted_scrap = False
    for index, row in enumerate(rows, 1):
        label = f"{index}번 구간"
        diameter = _optional_number(row.get("wireDiameter"), f"{label} 와이어 직경")
        speed = _optional_number(row.get("wireFeedSpeed"), f"{label} 송급 속도")
        measured_length = _optional_number(row.get("wireFeedLength"), f"{label} 실측 송급 길이")
        density = _optional_number(row.get("wireDensity"), f"{label} 와이어 밀도")
        actual_time = _optional_number(row.get("wireActualArcTime"), f"{label} 실측 아크 시간")
        extra = _optional_number(row.get("wireExtraFeedLength"), f"{label} 추가 송급 길이", zero=True)
        scrap = _optional_number(row.get("wireScrap"), f"{label} 절단·폐기량", zero=True)
        deposition = _optional_number(row.get("wireDepositionEfficiency"), f"{label} 용착 효율")
        price = _optional_number(row.get("wirePrice"), f"{label} 와이어 단가", zero=True)
        if deposition is not None and deposition > 100:
            raise ValueError(f"{label} 용착 효율은 100% 이하여야 합니다.")
        if diameter is None:
            missing.append(f"{label} 와이어 직경")
        if density is None:
            missing.append(f"{label} 와이어 밀도")
        if measured_length is None and speed is None:
            missing.append(f"{label} 송급 속도 또는 실측 송급 길이")
        base_length = measured_length if measured_length is not None else speed * (actual_time or row["time"]) / 60 if speed is not None else None
        omitted_extras |= extra is None
        omitted_scrap |= scrap is None
        if diameter is None or density is None or base_length is None:
            details.append({"name": str(row.get("wireName") or "미입력"), "status": "자료 부족"})
            continue
        # mm² × m × g/cm³ = g (m→mm와 mm³→cm³ 변환이 상쇄됨).
        area_mm2 = math.pi * diameter ** 2 / 4
        fed_g = area_mm2 * (base_length + (extra or 0)) * density
        scrap_g = scrap or 0
        details.append({
            "name": str(row.get("wireName") or "미입력"),
            "source": "실측 송급 길이" if measured_length is not None else "송급 속도 × 아크 시간",
            "arc_time": actual_time or row["time"],
            "base_length": base_length,
            "extra_length": extra or 0,
            "diameter": diameter,
            "density": density,
            "fed_g": fed_g,
            "scrap_g": scrap_g,
            "used_g": fed_g + scrap_g,
            "deposited_g": fed_g * deposition / 100 if deposition is not None else None,
            "cost": (fed_g + scrap_g) / 1000 * price if price is not None else None,
        })

    result = {
        "status": "계산 가능" if not missing else "자료 부족",
        "missing": missing, "rows": details,
        "omitted_extras": omitted_extras, "omitted_scrap": omitted_scrap,
    }
    if not missing:
        cycle_g = sum(item["used_g"] for item in details)
        part_g = cycle_g / plan["batch"]
        result.update({
            "cycle_g": cycle_g,
            "part_g": part_g,
            "hour_kg": part_g * production["uph"] / 1000,
            "day_kg": part_g * production["day"] / 1000,
            "month_kg": part_g * production["month"] / 1000,
            "year_kg": part_g * production["year"] / 1000,
        })
        if all(item["deposited_g"] is not None for item in details):
            result["deposited_g"] = sum(item["deposited_g"] for item in details)
        if all(item["cost"] is not None for item in details):
            result["cost_cycle"] = sum(item["cost"] for item in details)
            result["cost_part"] = result["cost_cycle"] / plan["batch"]

    start = _optional_number(plan.get("wireStartKg"), "실측 시작 와이어 잔량", zero=True)
    end = _optional_number(plan.get("wireEndKg"), "실측 종료 와이어 잔량", zero=True)
    cycles = _optional_number(plan.get("wireMeasuredCycles"), "실측 생산 사이클 수")
    if any(value is not None for value in (start, end, cycles)):
        if start is None or end is None or cycles is None:
            raise ValueError("실측 비교에는 시작·종료 와이어 잔량과 생산 사이클 수를 모두 입력해 주세요.")
        if end > start:
            raise ValueError("실측 종료 와이어 잔량은 시작 잔량보다 클 수 없습니다.")
        if not cycles.is_integer():
            raise ValueError("실측 생산 사이클 수는 정수여야 합니다.")
        actual_g = (start - end) * 1000 / cycles
        result["measured_g_cycle"] = actual_g
        result["measured_g_part"] = actual_g / plan["batch"]
        if "cycle_g" in result:
            result["difference_g"] = actual_g - result["cycle_g"]
            result["difference_pct"] = (actual_g / result["cycle_g"] - 1) * 100 if result["cycle_g"] else None
    return result
