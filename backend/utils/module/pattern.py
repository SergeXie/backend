from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, Callable
from utils.module.zigzag_point import ZigZagPoint

@dataclass
class Pattern:
    pattern_type: str
    points: List[ZigZagPoint]
    start_timestamp: int
    end_timestamp: int
    meta: Dict = field(default_factory=dict)
