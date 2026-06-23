"""确定性随机数生成器单元测试"""

import pytest
from game.random import GameRandom


class TestGameRandomSeed:
    """种子确定性测试"""

    def test_same_seed_same_sequence(self):
        """相同seed应产生相同随机序列"""
        rng1 = GameRandom(seed=42)
        rng2 = GameRandom(seed=42)

        seq1 = [rng1.randint(1, 100) for _ in range(10)]
        seq2 = [rng2.randint(1, 100) for _ in range(10)]

        assert seq1 == seq2

    def test_different_seed_different_sequence(self):
        """不同seed应产生不同随机序列（概率上几乎不可能相同）"""
        rng1 = GameRandom(seed=42)
        rng2 = GameRandom(seed=123)

        seq1 = [rng1.randint(1, 100) for _ in range(10)]
        seq2 = [rng2.randint(1, 100) for _ in range(10)]

        assert seq1 != seq2

    def test_default_seed_is_deterministic(self):
        """不传seed时，应使用固定默认种子"""
        rng1 = GameRandom()
        rng2 = GameRandom()

        assert rng1.seed == rng2.seed

    def test_call_count_consistent(self):
        """相同seed下调用次数应一致"""
        rng1 = GameRandom(seed=42)
        rng2 = GameRandom(seed=42)

        rng1.randint(1, 100)
        rng1.randint(1, 100)
        rng2.randint(1, 100)
        rng2.randint(1, 100)

        assert rng1.call_count == rng2.call_count == 2


class TestGameRandomMethods:
    """随机方法功能测试"""

    def test_randint_range(self):
        """randint返回值应在指定范围内"""
        rng = GameRandom(seed=42)
        for _ in range(100):
            value = rng.randint(5, 10)
            assert 5 <= value <= 10, f"Value {value} out of range [5, 10]"

    def test_randint_reversed_range(self):
        """当min > max时，应自动交换"""
        rng = GameRandom(seed=42)
        value = rng.randint(10, 5)
        assert 5 <= value <= 10

    def test_randint_single_value(self):
        """当min == max时，应返回该值"""
        rng = GameRandom(seed=42)
        value = rng.randint(7, 7)
        assert value == 7

    def test_random_float_range(self):
        """random()返回值应在[0, 1)范围内"""
        rng = GameRandom(seed=42)
        for _ in range(100):
            value = rng.random()
            assert 0.0 <= value < 1.0

    def test_choice(self):
        """choice应从列表中返回一个元素"""
        rng = GameRandom(seed=42)
        options = ["a", "b", "c", "d"]
        for _ in range(20):
            value = rng.choice(options)
            assert value in options

    def test_choice_empty_list(self):
        """choice空列表应抛出异常"""
        rng = GameRandom(seed=42)
        with pytest.raises(IndexError):
            rng.choice([])

    def test_choice_single_element(self):
        """choice单元素列表应返回该元素"""
        rng = GameRandom(seed=42)
        assert rng.choice(["only"]) == "only"

    def test_choices_with_weights(self):
        """choices应支持权重"""
        rng = GameRandom(seed=42)
        options = ["a", "b"]
        weights = [0.9, 0.1]
        results = [rng.choices(options, weights=weights)[0] for _ in range(50)]
        # 'a' should appear more often than 'b' (weighted)
        count_a = results.count("a")
        assert count_a > 0

    def test_choices_invalid_weights(self):
        """weights长度与options不匹配应报错"""
        rng = GameRandom(seed=42)
        with pytest.raises(ValueError):
            rng.choices(["a", "b"], weights=[0.5])

    def test_shuffle(self):
        """shuffle应打乱列表（原地修改）"""
        rng = GameRandom(seed=42)
        original = [1, 2, 3, 4, 5, 6, 7, 8]
        shuffled = list(original)
        rng.shuffle(shuffled)
        # 元素应相同
        assert sorted(shuffled) == original
        # 顺序应改变（概率上几乎不可能相同）
        assert shuffled != original

    def test_shuffle_empty(self):
        """shuffle空列表不应报错"""
        rng = GameRandom(seed=42)
        empty = []
        rng.shuffle(empty)
        assert empty == []

    def test_shuffle_single(self):
        """shuffle单元素列表不应报错"""
        rng = GameRandom(seed=42)
        single = [1]
        rng.shuffle(single)
        assert single == [1]

    def test_sample(self):
        """sample应从列表中返回不重复的k个元素"""
        rng = GameRandom(seed=42)
        population = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        sample = rng.sample(population, 3)
        assert len(sample) == 3
        # 元素应不重复
        assert len(set(sample)) == 3
        # 所有元素应来自population
        for item in sample:
            assert item in population

    def test_sample_too_large(self):
        """sample的k大于population长度应报错"""
        rng = GameRandom(seed=42)
        with pytest.raises(ValueError):
            rng.sample([1, 2, 3], 5)


class TestGameRandomDeterminism:
    """确定性保障测试"""

    def test_deterministic_across_instances(self):
        """多次创建相同seed的实例应产生相同结果"""
        expected = []
        for i in range(5):
            rng = GameRandom(seed=999)
            results = [
                rng.randint(1, 6),
                rng.choice(["A", "B", "C"]),
                rng.random(),
            ]
            if i == 0:
                expected = results
            else:
                assert results == expected, (
                    f"Instance {i} differs from instance 0"
                )

    def test_deterministic_mixed_calls(self):
        """混合调用不同方法仍保持确定性"""
        rng1 = GameRandom(seed=777)
        rng2 = GameRandom(seed=777)

        # 混合调用顺序
        v1_a = rng1.randint(1, 10)
        v1_b = rng1.choice(["x", "y", "z"])
        v1_c = rng1.random()
        v1_d = rng1.randint(1, 100)
        v1_e = rng1.sample([1, 2, 3, 4, 5], 2)

        v2_a = rng2.randint(1, 10)
        v2_b = rng2.choice(["x", "y", "z"])
        v2_c = rng2.random()
        v2_d = rng2.randint(1, 100)
        v2_e = rng2.sample([1, 2, 3, 4, 5], 2)

        assert v1_a == v2_a
        assert v1_b == v2_b
        assert v1_c == v2_c
        assert v1_d == v2_d
        assert v1_e == v2_e

    def test_serialization_roundtrip(self):
        """序列化和反序列化后应保持状态一致性"""
        rng = GameRandom(seed=42)

        # 使用一些随机数
        for _ in range(5):
            rng.randint(1, 100)

        # 保存状态
        state = rng.get_state()

        # 继续使用随机数
        next_value = rng.randint(1, 100)

        # 恢复状态
        rng.set_state(state)
        restored_value = rng.randint(1, 100)

        assert next_value == restored_value, (
            "State roundtrip should preserve random sequence"
        )


class TestGameRandomEdgeCases:
    """边界情况测试"""

    def test_large_range(self):
        """大范围随机数"""
        rng = GameRandom(seed=42)
        value = rng.randint(0, 1000000)
        assert 0 <= value <= 1000000

    def test_negative_range(self):
        """负范围随机数"""
        rng = GameRandom(seed=42)
        value = rng.randint(-100, -1)
        assert -100 <= value <= -1

    def test_cross_zero_range(self):
        """跨零范围"""
        rng = GameRandom(seed=42)
        value = rng.randint(-50, 50)
        assert -50 <= value <= 50
