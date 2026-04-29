from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, Callable

@dataclass
class ZigZagPoint:
    timestamp: int
    price: float
    index: int
    hloc: List[float]
    kLineId: int
