"""确定性随机数生成器

游戏内所有随机数必须通过 GameRandom 生成，以保证确定性。
相同 seed + 相同调用顺序 = 完全相同的结果。

设计原则：
1. 所有随机数通过统一的 GameRandom 实例生成
2. 使用 Python 标准库 random.Random（而非 random 模块），确保可复现
3. 每次调用记录 call_count，便于调试和复现
4. 支持状态序列化，用于回滚和同步
"""

from __future__ import annotations

import random
import zlib
from typing import Any, List, Optional, Sequence, TypeVar

T = TypeVar("T")

DEFAULT_SEED: int = 42
"""默认种子，确保不传seed时行为也确定"""


def stable_hash(text: str) -> int:
    """跨进程稳定的字符串哈希（替代内置 hash()）

    🔴 为什么必须用它替代内置 `hash(str)`：CPython 的 `str.__hash__` 默认按进程
    随机加盐（`PYTHONHASHSEED`），**同一字符串在不同进程会得到不同结果**。
    用它来派生「每方玩家的随机种子」会让「同一 seed 跑出的对局」随进程变化，
    直接违反 ADR-0002（确定性）——实测同一 `--seed` 在两进程出征次数不同
    （见 api/game_manager.py 的历史注释）。

    本函数用 CRC32，跨进程恒定，保证「同 seed → 同对局」。
    全项目凡「由字符串稳定派生种子」之处都应调用本函数，不要再用内置 hash()。

    Args:
        text: 待哈希文本（典型为势力键）

    Returns:
        0 ~ 2^32-1 的稳定整数
    """
    return zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF


class GameRandom:
    """确定性随机数生成器

    包装 random.Random 实例，提供统一的随机数接口。
    所有游戏内的随机操作必须通过此类完成。

    Attributes:
        seed: 当前种子值
        call_count: 已调用的随机操作次数
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        """初始化随机数生成器

        Args:
            seed: 随机种子。不传则使用固定默认种子 42。
        """
        self.seed: int = seed if seed is not None else DEFAULT_SEED
        self._rng: random.Random = random.Random(self.seed)
        self.call_count: int = 0

    def _count_call(self) -> None:
        """记录一次随机调用"""
        self.call_count += 1

    def random(self) -> float:
        """生成 [0.0, 1.0) 范围内的随机浮点数

        Returns:
            [0.0, 1.0) 范围内的浮点数
        """
        self._count_call()
        return self._rng.random()

    def randint(self, a: int, b: int) -> int:
        """生成 [a, b] 范围内的随机整数（包含两端）

        Args:
            a: 最小值
            b: 最大值

        Returns:
            [a, b] 范围内的随机整数
        """
        self._count_call()
        if a > b:
            a, b = b, a
        return self._rng.randint(a, b)

    def choice(self, seq: Sequence[T]) -> T:
        """从序列中随机选择一个元素

        Args:
            seq: 非空序列

        Returns:
            序列中的随机元素

        Raises:
            IndexError: 序列为空时抛出
        """
        self._count_call()
        return self._rng.choice(seq)

    def choices(
        self, population: Sequence[T], weights: Optional[Sequence[float]] = None, k: int = 1
    ) -> List[T]:
        """从总体中按权重随机选择 k 个元素（可重复）

        Args:
            population: 总体序列
            weights: 权重序列，长度必须与 population 一致
            k: 选择数量

        Returns:
            选择结果列表

        Raises:
            ValueError: weights 长度与 population 不匹配
        """
        self._count_call()
        return self._rng.choices(population, weights=weights, k=k)

    def shuffle(self, x: List[Any]) -> None:
        """打乱列表（原地修改）

        Args:
            x: 要打乱的列表
        """
        self._count_call()
        self._rng.shuffle(x)

    def sample(self, population: Sequence[T], k: int) -> List[T]:
        """从总体中随机抽取 k 个不重复的元素

        Args:
            population: 总体序列
            k: 抽取数量

        Returns:
            长度为 k 的不重复元素列表

        Raises:
            ValueError: k 大于 population 长度
        """
        self._count_call()
        return self._rng.sample(population, k)

    def get_state(self) -> Any:
        """获取当前随机数生成器状态

        可用于保存和恢复随机数序列。

        Returns:
            可序列化的状态对象
        """
        return {
            "seed": self.seed,
            "call_count": self.call_count,
            "rng_state": self._rng.getstate(),
        }

    def set_state(self, state: Any) -> None:
        """恢复随机数生成器状态

        Args:
            state: 由 get_state() 返回的状态对象
        """
        self.seed = state["seed"]
        self.call_count = state["call_count"]
        self._rng.setstate(state["rng_state"])

    def __repr__(self) -> str:
        return f"GameRandom(seed={self.seed}, call_count={self.call_count})"
