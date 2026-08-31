from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

@dataclass(frozen=True)
class ProductionRule:
    server: str
    city: str
    crafting_category: str | None
    tier: int | None
    base_production_bonus: float | None
    specialty_production_bonus: float | None
    focus_production_bonus: float | None
    daily_production_bonus: float | None
    station_fee_per_output: float | None
    source: str
    source_version: str | None = None
    def return_rate(self, *, use_focus: bool, daily_bonus: float | None = None) -> float | None:
        components=[self.base_production_bonus,self.specialty_production_bonus]
        if use_focus: components.append(self.focus_production_bonus)
        components.append(self.daily_production_bonus if daily_bonus is None else daily_bonus)
        if any(value is None for value in components): return None
        total=sum(float(value) for value in components)
        return total/(1.0+total)

class ProductionRuleProvider:
    def __init__(self, path: str | Path): self.path=Path(path); self._rules=None
    def load(self) -> list[ProductionRule]:
        if self._rules is None: self._rules=[ProductionRule(**row) for row in json.loads(self.path.read_text(encoding='utf-8'))]
        return self._rules
    def find(self, *, server: str, city: str, category: str | None, tier: int | None) -> ProductionRule | None:
        candidates=[r for r in self.load() if (r.server==server or r.server=='*') and r.city==city and (r.tier is None or r.tier==tier)]
        for rule in candidates:
            if rule.crafting_category is None or rule.crafting_category==category:return rule
        return None
