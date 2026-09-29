"""装备套装与共鸣系统 - 红态测试"""
import pytest, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from equip.set import SetSystem, Equipment

class TestSetGrouping:
    def test_mixed_sets_dont_trigger_5piece(self):
        ss = SetSystem()
        equipped = [
            Equipment("e1", "a1", "head", set_id="setA"),
            Equipment("e2", "a2", "chest", set_id="setA"),
            Equipment("e3", "a3", "legs", set_id="setA"),
            Equipment("e4", "b1", "hands", set_id="setB"),
            Equipment("e5", "b2", "feet", set_id="setB"),
        ]
        result = ss.check_set_bonus(equipped)
        assert result == {} or "atk" not in result or result["atk"] < 100  # bug1: 触发5件

class TestResonanceCondition:
    def test_resonance_needs_enough_pieces(self):
        ss = SetSystem()
        assert ss.is_resonance_active("setA", 1) == False  # bug2: True
        assert ss.is_resonance_active("setA", 5) == True

class TestSameSlot:
    def test_cannot_equip_two_same_slot(self):
        ss = SetSystem()
        equipped = [Equipment("e1", "helm", "head")]
        assert ss.can_equip_same_slot("head", equipped) == False  # bug3: True

class TestQualityStats:
    def test_legendary_set_better_than_common(self):
        ss = SetSystem()
        common = ss.get_set_stats("setA", "common")
        legendary = ss.get_set_stats("setA", "legendary")
        assert legendary["atk"] > common["atk"]  # bug4: 都是10

class TestSetConflict:
    def test_exclusive_sets_cannot_equip_together(self):
        ss = SetSystem()
        ss.exclusive_sets = ["setA", "setB"]
        assert ss.has_set_conflict("setA", "setB") == True  # bug5: False

class TestSetUpgrade:
    def test_upgrade_updates_effects(self):
        ss = SetSystem()
        ss.set_effects["setA"] = {3: {"atk": 10}}
        ss.upgrade_set("setA", 5)
        assert ss.set_effects["setA"][3]["atk"] > 10  # bug6: 不更新

class TestMiscPenalty:
    def test_misc_equipment_has_lower_bonus(self):
        ss = SetSystem()
        penalty = ss.get_misc_penalty(5)
        assert penalty != {}  # bug7: 空
