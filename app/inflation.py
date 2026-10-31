"""공식 CPI 기준으로 과거 거래의 현재 구매력을 비교한다.

월별 지수가 없으면 연평균을 사용하며, 원본 거래 금액은 변경하지 않는다.
"""

import json
from pathlib import Path


DATA = json.loads((Path(__file__).resolve().parents[1] / "data" / "consumer_price_index.json").read_text(encoding="utf-8"))


def adjust_amount(amount_krw: int, event_date: str) -> dict:
    """거래일과 환산 정밀도를 함께 반환하며 원본 금액은 보존한다."""
    month = event_date[:7]
    reference_month = DATA["reference_month"]
    status = "unavailable"
    source_period = None
    source_index = None
    adjusted = amount_krw

    if month > reference_month:
        status = "after_reference"
    elif month in DATA["monthly"]:
        status = "monthly"
        source_period = month
        source_index = DATA["monthly"][month]
    elif month[:4] in DATA["annual"]:
        status = "annual"
        source_period = month[:4]
        source_index = DATA["annual"][month[:4]]

    if source_index is not None:
        adjusted = round(amount_krw * DATA["reference_index"] / source_index)

    return {
        "original_amount_krw": amount_krw,
        "adjusted_amount_krw": adjusted,
        "status": status,
        "source_period": source_period,
        "reference_month": reference_month,
    }
