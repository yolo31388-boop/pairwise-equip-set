"""装备套装与共鸣系统 - 含7个bug"""
from dataclasses import dataclass, field

@dataclass
class Equipment:
    eid: str
    name: str
    slot: str
    set_id: str = ""
    set_count: int = 0
    quality: str = "common"
    level: int = 1

class SetSystem:
    def __init__(self):
        self.equipment: dict[str, Equipment] = {}
        self.set_effects: dict[str, dict] = {}  # set_id -> {pieces: effect}
        self.exclusive_sets: list[str] = []  # bug5: 无互斥

    def check_set_bonus(self, equipped: list[Equipment]) -> dict:
        # bug1: 不按set_id分组
        total = len(equipped)
        if total >= 5:
            return {"atk": 100}
        return {}

    def is_resonance_active(self, set_id: str, count: int) -> bool:
        # bug2: 无条件触发
        return True

    def can_equip_same_slot(self, slot: str, equipped: list[Equipment]) -> bool:
        # bug3: 同部位可叠加
        return True

    def get_set_stats(self, set_id: str, quality: str) -> dict:
        # bug4: 固定值不看品质
        return {"atk": 10}

    def has_set_conflict(self, set1: str, set2: str) -> bool:
        # bug5: 无冲突检测
        return False

    def upgrade_set(self, set_id: str, new_level: int):
        # bug6: 升级不更新效果
        pass

    def get_misc_penalty(self, count: int) -> dict:
        # bug7: 散件无惩罚
        return {}
