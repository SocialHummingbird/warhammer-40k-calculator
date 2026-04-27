from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional


EngagementMode = Literal["ranged", "melee"]


@dataclass
class EngagementContext:
    attacker_moved: bool = False
    attacker_advanced: bool = False
    target_within_half_range: bool = False
    target_in_cover: bool = False
    target_model_count: Optional[int] = None

    def __post_init__(self) -> None:
        if self.attacker_advanced and not self.attacker_moved:
            self.attacker_moved = True
        if self.target_model_count is not None and self.target_model_count <= 0:
            self.target_model_count = None
