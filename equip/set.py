"""装备套装与共鸣系统。

规则:
1. 套装效果按 set_id 分组, 同 ID 件数达到阈值才触发;
2. 共鸣需集齐指定件数, 且仅在战斗中持续激活;
3. 同部位只能穿一件, 重复部位不叠加;
4. 套装属性按品质与等级浮动, 极品(legendary)带额外词条;
5. 互斥套装见冲突表, 同时穿戴只保留优先级高的一套;
6. 套装升级后立即按新等级重算该套全部效果;
7. 散件有少量散件加成, 但总收益低于同等级套装。
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
    # 品质 -> 基础倍率, 越稀有越强
    QUALITY_MULTIPLIER = {
        "common": 1.0,
        "uncommon": 1.2,
        "rare": 1.5,
        "epic": 2.0,
        "legendary": 3.0,
    }
    # 极品套装额外词条
    LEGENDARY_EXTRA_AFFIX = {"crit_rate": 0.15, "crit_dmg": 0.30}

    DEFAULT_RESONANCE_PIECES = 5  # 默认共鸣所需件数
    LEVEL_FACTOR = 0.3            # 每升一级效果 +30%
    MISC_PIECE_ATK = 2            # 每件散件的攻击加成(远低于套装)

    def __init__(self):
        self.equipment: dict[str, Equipment] = {}
        # set_id -> {件数阈值: 效果}
        self.set_effects: dict[str, dict[int, dict]] = {}
        # 互斥套装组: 同组内任意两套互斥
        self.exclusive_sets: list[str] = []
        # 显式冲突表: set_id -> 与其互斥的 set_id 集合
        self.conflict_table: dict[str, set[str]] = {}
        # 套装优先级, 数值越大越优先; 未配置时按 exclusive_sets 顺序
        self.set_priority: dict[str, int] = {}
        # 套装当前等级
        self.set_levels: dict[str, int] = {}
        # 各套装共鸣所需件数
        self.resonance_requirements: dict[str, int] = {}

        # 共鸣的战斗内状态: 仅在战斗中持续激活
        self.in_combat = False
        self.active_resonances: set[str] = set()

    # ---- 1. 套装效果: 按 set_id 分组 ----
    def _group_by_set(self, equipped: list[Equipment]) -> dict[str, list[Equipment]]:
        groups: dict[str, list[Equipment]] = {}
        for item in equipped:
            if item.set_id:
                groups.setdefault(item.set_id, []).append(item)
        return groups

    def check_set_bonus(self, equipped: list[Equipment]) -> dict:
        groups = self._group_by_set(equipped)
        counts = {sid: len(items) for sid, items in groups.items()}
        # 互斥套装同时穿时, 只保留优先级高的套装
        winners = self._resolve_conflicts(set(counts))

        bonus: dict[str, float] = {}
        for set_id in winners:
            piece_count = counts[set_id]
            for threshold, effect in sorted(self.set_effects.get(set_id, {}).items()):
                if piece_count >= threshold:
                    for key, value in effect.items():
                        bonus[key] = bonus.get(key, 0) + value
        return bonus

    # ---- 2. 共鸣: 件数门槛 + 战斗内持续激活 ----
    def resonance_required(self, set_id: str) -> int:
        return self.resonance_requirements.get(set_id, self.DEFAULT_RESONANCE_PIECES)

    def is_resonance_active(self, set_id: str, count: int) -> bool:
        return count >= self.resonance_required(set_id)

    def enter_combat(self, equipped: list[Equipment] | None = None) -> None:
        self.in_combat = True
        self.refresh_resonance(equipped or [])

    def refresh_resonance(self, equipped: list[Equipment]) -> None:
        """战斗中持续校验: 集齐件数的套装共鸣保持激活, 不满足则熄灭。"""
        if not self.in_combat:
            return
        counts = {sid: len(items) for sid, items in self._group_by_set(equipped).items()}
        self.active_resonances = {
            set_id
            for set_id, count in counts.items()
            if self.is_resonance_active(set_id, count)
        }

    def leave_combat(self) -> None:
        self.in_combat = False
        self.active_resonances.clear()

    # ---- 3. 同部位唯一 ----
    def can_equip_same_slot(self, slot: str, equipped: list[Equipment]) -> bool:
        return not any(item.slot == slot for item in equipped)

    # ---- 4. 品质/等级浮动属性, 极品额外词条 ----
    def get_set_stats(self, set_id: str, quality: str, level: int = 1) -> dict:
        multiplier = self.QUALITY_MULTIPLIER.get(quality, 1.0)
        level_scale = 1 + self.LEVEL_FACTOR * (max(level, 1) - 1)
        stats = {"atk": int(round(10 * multiplier * level_scale))}
        if quality == "legendary":
            stats.update(self.LEGENDARY_EXTRA_AFFIX)
        return stats

    # ---- 5. 互斥冲突表与优先级 ----
    def has_set_conflict(self, set1: str, set2: str) -> bool:
        if set1 == set2:
            return False
        if set1 in self.exclusive_sets and set2 in self.exclusive_sets:
            return True
        return set2 in self.conflict_table.get(set1, set())

    def _priority_of(self, set_id: str) -> int:
        if set_id in self.set_priority:
            return self.set_priority[set_id]
        # 未显式配置时, exclusive_sets 中越靠前优先级越高
        if set_id in self.exclusive_sets:
            return -self.exclusive_sets.index(set_id)
        return -10_000

    def _resolve_conflicts(self, set_ids: set[str]) -> set[str]:
        """互斥套装同时穿戴时, 只保留优先级最高者。"""
        winners: set[str] = set()
        for set_id in sorted(set_ids, key=lambda s: (-self._priority_of(s), s)):
            if not any(self.has_set_conflict(set_id, kept) for kept in winners):
                winners.add(set_id)
        return winners

    # ---- 6. 升级: 实时重算该套全部效果 ----
    def upgrade_set(self, set_id: str, new_level: int) -> None:
        old_level = self.set_levels.get(set_id, 1)
        if new_level < old_level:
            return
        if new_level == old_level and old_level != 1:
            return
        factor = (1 + self.LEVEL_FACTOR * (new_level - 1)) / (
            1 + self.LEVEL_FACTOR * (old_level - 1)
        )
        for effect in self.set_effects.get(set_id, {}).values():
            for key, value in list(effect.items()):
                if isinstance(value, bool):
                    continue
                if isinstance(value, int):
                    effect[key] = int(round(value * factor))
                elif isinstance(value, float):
                    effect[key] = round(value * factor, 4)
        self.set_levels[set_id] = new_level

    # ---- 7. 散件加成(低于同等级套装总收益) ----
    def get_misc_penalty(self, count: int) -> dict:
        # 散件按件给少量攻击, 无套装阈值效果, 总收益明显低于成套装备
        return {"atk": self.MISC_PIECE_ATK * max(count, 0)}
