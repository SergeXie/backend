# clients/dl_api_client.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple
import requests


class DLPredictError(RuntimeError):
    pass


def call_dl_api(
    url: str,
    goods: str,
    period: str,
    begin_time: str,
    end_time: str,
    time_periodssf: List[int],
    limit: int = 500,
    is_desc: bool = True,
    timeout: float = 120.0,
) -> Tuple[List[float], List[float], Dict[str, Any]]:
    """
    调用 DL API，返回 (prices, probabilities, raw_body)
    """
    payload = {
        "goods": goods,
        "period": period,
        "beginTime": begin_time,
        "endTime": end_time,
        "TimePeriodssf": time_periodssf,
        "limit": limit,
        "isDesc": is_desc,
    }

    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()

    return data
