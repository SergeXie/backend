# clients/dl_api_client.py
from __future__ import annotations

from typing import Any, Dict, List, Tuple
import requests


class DLPredictError(RuntimeError):
    pass


def call_dl_api(
    url: str,
    task: str,
    goods: str,
    period: str,
    begin_time: str,
    end_time: str,
    time_periodssf: List[int],
    timeout: float = 120.0,
) -> Tuple[List[float], List[float], Dict[str, Any]]:
    """
    调用 DL API，返回 (prices, probabilities, raw_body)
    """
    payload = {
        "task": task,
        "goods": goods,
        "period": period,
        "beginTime": begin_time,
        "endTime": end_time,
        "data": {
            "TimePeriodssf": time_periodssf,
            # 未来如果有其他任务特定的参数，也应该放在这里
            # "other_param": value
        },
    }

    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    resp_data = resp.json()

    return resp_data

def call_dl_api2(
    url: str,
    task: str,
    goods: str,
    period: str,
    begin_time: str,
    end_time: str,
    timeout: float = 120.0,
    data: Dict[str, Any] = {},
) -> Tuple[List[float], List[float], Dict[str, Any]]:
    """
    调用 DL API，返回 (prices, probabilities, raw_body)
    """
    payload = {
        "task": task,
        "goods": goods,
        "period": period,
        "beginTime": begin_time,
        "endTime": end_time,
        "data": data,
    }

    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    resp_data = resp.json()

    return resp_data