#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""迷你世界/角色/节拍模型 —— 对应 novel 的 WorldState / CharacterSim / BeatOrchestrator。

仅用标准库，零依赖。目的是在独立项目里验证「novel 生成 → DSE 运行时」路线中
生成侧需要的能力：
  - WorldState：空间模型（地点 + 描述），可切换当前地点
  - CharacterSim：角色（姓名 + 情绪 + 目标），情绪随事件变化
  - BeatOrchestrator：把情节骨架拆成有序节拍（P2 中部分节拍成为「决策点」）
"""

import random


class WorldState:
    """对应 novel 的 WorldStateManager —— 莲花式地图诸天的简化版。"""

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.locations = {
            "core": {"name": "中心祭坛", "desc": "混沌海方向飘来的海腥留在舌上"},
            "gate": {"name": "星渊传送门旧址", "desc": "蓝光映着孤零零的一团影子"},
        }
        self.active = "core"

    def current(self) -> dict:
        return self.locations[self.active]

    def unlock(self, key: str) -> None:
        if key in self.locations:
            self.active = key


class CharacterSim:
    """对应 novel 的 CharacterSim —— 位置/目标/情绪/自主反应。"""

    # 事件 → 情绪的极简映射（P1 插值变量 mood 的来源）
    MOOD_TABLE = {
        "calm": "平静",
        "danger": "紧绷",
        "loss": "黯然",
        "hope": "灼热",
        "resolve": "决绝",
    }

    def __init__(self, name: str = "林朔", seed: int = 42):
        self.name = name
        self.mood = "平静"
        self.goals = ["寻回源界碎片"]

    def react(self, event: str) -> None:
        if event in self.MOOD_TABLE:
            self.mood = self.MOOD_TABLE[event]


class BeatOrchestrator:
    """对应 novel 的 BeatOrchestrator —— Save the Cat! 15 拍的简化有序骨架。

    每个节拍有：id / 标题 / 默认情绪事件 / 是否决策点(decision)。
    P2 中 decision=True 的节拍会被生成器展开成带 choices 的分支。
    """

    SPINE = [
        ("start",     "开场",     "calm",    False),
        ("catalyst",  "催化",     "danger",  False),
        ("debate",    "抉择前夜", "loss",    False),
        ("decision",  "决策",     "choice",  True),   # ← P2 分支点
        ("ending_a",  "结局·星归", "hope",   False),
        ("ending_b",  "结局·尘落", "calm",   False),
    ]

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.beats = list(self.SPINE)

    def decisions(self):
        return [b for b in self.beats if b[3]]
