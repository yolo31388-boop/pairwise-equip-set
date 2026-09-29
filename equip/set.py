"""装备套装与共鸣系统

修复点：
1. 套装效果按 set_id 分组计数，同套凑够件数才触发
2. 共鸣需凑齐指定件数，且在战斗中持续激活
3. 同部位只能穿一件，重复部位不叠加
4. 套装属性按品质、等级浮动，极品(传说)有额外词条
5. 互斥套装走冲突表，同时穿只取优先级高的一套
6. 套装升级后实时重新计算所有已装备效果
7. 散件有小额加成，但总收益低于同等级成套
"""
from dataclasses import dataclass


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
    # 品质倍率：极品(legendary)数值最高
    QUALITY_MULTIPLIER = {
        "common": 1.0,
        "uncommon": 1.2,
        "rare": 1.5,
        "epic": 1.8,
        "legendary": 2.5,
    }
    # 传说品质的额外词条
    LEGENDARY_EXTRA_AFFIX = {"crit": 10}

    # 共鸣所需件数
    RESONANCE_REQUIRED = 5
    # 升级每级的属性成长系数（相对1级）
    LEVEL_GROWTH = 0.2
    # 每件散件的小额加成
    MISC_BONUS_PER_PIECE = {"atk": 3, "hp": 15}

    def __init__(self):
        self.equipment: dict[str, Equipment] = {}
        self.set_effects: dict[str, dict] = {}   # set_id -> {pieces: effect}
        # 互斥冲突表：set 对组成的集合
        self.exclusive_sets: list[str] = []
        self.conflict_table: set[frozenset[str]] = set()
        # 套装优先级：数值大者在冲突中生效
        self.set_priority: dict[str, int] = {}
        # 套装当前等级
        self.set_levels: dict[str, int] = {}
        # 1级基线效果快照，升级时据此重算，避免重复放大
        self._base_effects: dict[str, dict] = {}
        # 共鸣只在战斗中持续激活
        self.in_combat: bool = True

    # ---- bug1: 按套装ID分组检查 ----
    def check_set_bonus(self, equipped: list[Equipment]) -> dict:
        groups: dict[str, list[Equipment]] = {}
        for item in equipped:
            if item.set_id:
                groups.setdefault(item.set_id, []).append(item)

        active_sets = self._resolve_conflicts(list(groups))

        bonus: dict[str, int] = {}
        for set_id in active_sets:
            count = len(groups[set_id])
            thresholds = self.set_effects.get(set_id, {})
            for pieces, effect in sorted(thresholds.items()):
                if count >= pieces:
                    for stat, value in effect.items():
                        bonus[stat] = bonus.get(stat, 0) + value
        return bonus

    # ---- bug5: 互斥套装冲突解析，只保留优先级高的 ----
    def _resolve_conflicts(self, set_ids: list[str]) -> list[str]:
        blocked: set[str] = set()
        ordered = sorted(
            set_ids,
            key=lambda sid: (self.set_priority.get(sid, 0), sid),
            reverse=True,
        )
        result = []
        for set_id in ordered:
            if set_id in blocked:
                continue
            result.append(set_id)
            for other in set_ids:
                if other != set_id and self.has_set_conflict(set_id, other):
                    blocked.add(other)
        return result

    # ---- bug2: 共鸣需凑齐指定件数且在战斗中持续激活 ----
    def is_resonance_active(self, set_id: str, count: int) -> bool:
        return self.in_combat and count >= self.RESONANCE_REQUIRED

    def enter_combat(self) -> None:
        self.in_combat = True

    def leave_combat(self) -> None:
        self.in_combat = False

    # ---- bug3: 同部位唯一，重复不叠加 ----
    def can_equip_same_slot(self, slot: str, equipped: list[Equipment]) -> bool:
        return all(item.slot != slot for item in equipped)

    def equip_item(self, item: Equipment) -> bool:
        equipped = list(self.equipment.values())
        if not self.can_equip_same_slot(item.slot, equipped):
            return False
        self.equipment[item.eid] = item
        self.recompute_all()
        return True

    # ---- bug4: 属性按品质、等级浮动，传说有额外词条 ----
    def get_set_stats(self, set_id: str, quality: str, level: int = 1) -> dict:
        multiplier = self.QUALITY_MULTIPLIER.get(quality, 1.0)
        level_factor = 1.0 + self.LEVEL_GROWTH * (level - 1)
        scale = multiplier * level_factor
        stats = {
            "atk": self._scale(10, scale),
            "hp": self._scale(50, scale),
        }
        if quality == "legendary":
            stats.update(self.LEGENDARY_EXTRA_AFFIX)
        return stats

    @staticmethod
    def _scale(base: int, factor: float) -> int:
        return int(round(base * factor))

    # ---- bug5: 冲突表检测 ----
    def has_set_conflict(self, set1: str, set2: str) -> bool:
        if set1 == set2:
            return False
        if frozenset((set1, set2)) in self.conflict_table:
            return True
        # exclusive_sets 中列出的套装两两互斥
        return bool(self.exclusive_sets) and all(
            sid in self.exclusive_sets for sid in (set1, set2)
        )

    def add_conflict(self, set1: str, set2: str) -> None:
        self.conflict_table.add(frozenset((set1, set2)))

    # ---- bug6: 升级后实时重算所有效果 ----
    def register_set_effect(self, set_id: str, pieces: int, effect: dict) -> None:
        self.set_effects.setdefault(set_id, {})[pieces] = dict(effect)
        self._base_effects.setdefault(set_id, {})[pieces] = dict(effect)

    def upgrade_set(self, set_id: str, new_level: int) -> None:
        old_level = self.set_levels.get(set_id, 1)
        if new_level <= old_level or set_id not in self.set_effects:
            return
        if set_id not in self._base_effects:
            # 兼容直接写入 set_effects 的情况：以当前效果为1级基线
            self._base_effects[set_id] = {
                pieces: dict(effect)
                for pieces, effect in self.set_effects[set_id].items()
            }
        self.set_levels[set_id] = new_level
        factor = 1.0 + self.LEVEL_GROWTH * (new_level - 1)
        rescaled: dict[int, dict] = {}
        for pieces, base_effect in self._base_effects[set_id].items():
            rescaled[pieces] = {
                stat: self._scale(value, factor)
                for stat, value in base_effect.items()
            }
        self.set_effects[set_id] = rescaled
        self.recompute_all()

    def recompute_all(self) -> dict:
        return self.check_set_bonus(list(self.equipment.values()))

    # ---- bug7: 散件小额加成，但低于同等级成套总收益 ----
    def get_misc_penalty(self, count: int) -> dict:
        return {
            stat: value * max(count, 0)
            for stat, value in self.MISC_BONUS_PER_PIECE.items()
        }
