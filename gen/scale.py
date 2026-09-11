#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scale.py —— novel-run 的「千场景 / 多 POV」规模生成器（Task #17）。

消费已清洗的 Prose 渲染器（gen/prose.py），把 novel 的题材数据模型映射为
DSE 运行时（run/runtime.js）可播放的**分支多 POV 场景图 JSON**。

组件（对应 novel 的 ASP 引擎 + VoiceEngine 数据模型）：
  · BeatSpine     —— 采用 Save the Cat! 15 拍，按 卷×章 映射到各 world；每个 (章,拍) 生成一个 spine 场景。
  · WorldState    —— NarrativeContext / PlotState / CharacterSnapshot 镜像（state 中的 beat/mood/pov/chapter/flags）。
  · PovThreads    —— 并行 POV 子图：每章主 POV 轮换；hub 章提供「切换视角」分支，跳到另一 POV 的同拍场景再汇回主线。
  · Rashomon      —— 关键拍（break_1/midpoint/all_lost/break_2）插入「同一时刻多透镜」场景，复刻 novel 的复眼叙事。
  · BranchBuilder —— 在末章插入 if/do 决策点，分叉到多结局。
  · 参数化        —— --chapters / --seed / --stress（千场景压测）/ --worlds（限用前 N 世界）/ --endings（N 路结局≥2）/ --out。

输出包满足 run/runtime.js 的 7 项 lint（无悬空跳转、结局可达、变量已定义、无伪分支、可达、命名规范、内容厚度）。
"""

import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prose import Prose

# Save the Cat! 15 拍（题材无关的通用结构，逐章循环映射到题材）
SAVE_THE_CAT = [
    'opening', 'theme', 'catalyst', 'debate', 'break_1',
    'midpoint', 'bad_guy_closes', 'all_is_lost', 'break_2', 'final_push', 'climax',
]
# 触发 Rashomon 多透镜的关键拍（与 narrative/rashomon.json 的 triggers 对齐）
KEY_BEATS = {'break_1', 'midpoint', 'all_is_lost', 'break_2'}

# novel 的固定人物 / 多 POV 线（与 opening() 的拒绝集一致：不用金庸/古龙主角名）
POV_THREADS = ['林朔', '唐川', '白夜', '叶琳', '墟核', '玩家群体']

MOODS = ['中性', '警觉', '恐惧', '愤怒', '震惊', '决意', '悲伤', '疑惑', '绝望', '释然']


class BeatSpine:
    """Save the Cat! 拍 × 章 → (world, beat, pov, mood) 序列。"""

    def __init__(self, worlds, chapters, beats_per_chapter, seed):
        self.worlds = worlds
        self.chapters = chapters
        self.bpc = beats_per_chapter
        self.rng = random.Random(seed)

    def iter_steps(self):
        gi = 0  # 全局拍索引，用于循环 Save the Cat 拍并决定关键拍
        for c in range(1, self.chapters + 1):
            world = self.worlds[(c - 1) % len(self.worlds)]
            pov = POV_THREADS[(c - 1) % len(POV_THREADS)]
            for b in range(self.bpc):
                beat = SAVE_THE_CAT[gi % len(SAVE_THE_CAT)]
                gi += 1
                mood = self.rng.choice(MOODS)
                is_hub = (b == self.bpc - 1)  # 章末为 hub：提供切换视角
                yield {
                    'chapter': c, 'beat': beat, 'world': world,
                    'pov': pov, 'mood': mood,
                    'is_hub': is_hub, 'is_key': beat in KEY_BEATS,
                }


class WorldState:
    """NarrativeContext / PlotState / CharacterSnapshot 镜像。"""

    @staticmethod
    def initial():
        return {
            'beat': 0, 'mood': '中性', 'pov': '林朔', 'chapter': 0,
            'flags': {},
        }

    @staticmethod
    def on_enter(step):
        return {
            'beat': step['beat'],
            'mood': step['mood'],
            'pov': step['pov'],
            'chapter': step['chapter'],
        }


class PovThreads:
    """并行 POV 子图：给定主 POV，返回「切换视角」目标 POV（环形轮换）。"""

    @staticmethod
    def alternate(pov):
        i = POV_THREADS.index(pov)
        return POV_THREADS[(i + 1) % len(POV_THREADS)]


class Rashomon:
    """关键拍的多透镜片段拼接。"""

    def __init__(self, prose: Prose):
        self.prose = prose

    def fragment(self, beat):
        lens = self.prose.rashomon_for(beat)
        if not lens:
            return ''
        return '\n'.join(t for _, t in lens)


class BranchBuilder:
    """末章决策点：N 条 if/do 路线 → N 个结局（支持 ≥2）。"""

    # 每条路线的叙事收束（标签/心境/主角/拍 随路线序号循环取用）
    ROUTE_LABELS = [
        '沿主潮推进，押上一切', '转入暗线，保存火种', '借外力破局，孤注一掷',
        '退守边缘，静待轮回', '焚尽自我，换取一线', '与敌同葬，不留余地',
    ]
    ROUTE_MOODS = ['决意', '释然', '愤怒', '疑惑', '绝望', '悲伤']
    ROUTE_POVS = ['林朔', '白夜', '唐川', '叶琳', '墟核', '玩家群体']
    ROUTE_BEATS = ['climax', 'aftermath', 'climax', 'aftermath', 'climax', 'aftermath']

    @staticmethod
    def ending_id(i):
        return f'ending_{i}'

    @staticmethod
    def choices(n=2):
        out = []
        for i in range(n):
            label = BranchBuilder.ROUTE_LABELS[i % len(BranchBuilder.ROUTE_LABELS)]
            # resolved 用数值 1/0（运行时 if 引擎只认 num/path，不认布尔字面量）
            out.append({
                'text': f'路线{i + 1}：{label}',
                'goto': BranchBuilder.ending_id(i),
                'do': {'route': i, 'resolved': 1 if i % 2 == 0 else 0},
            })
        return out

    @staticmethod
    def build_endings(prose, end_world, n=2):
        """生成 N 个结局场景 + 统计信息。

        每个 ending_i 不再是终局，而是「高潮收束」场景，再经统一的 epilogue 分叉，
        按运行时 state.resolved（由 branch 的 if/do 写入）走真线 / 暗线后续分支。
        """
        scenes, stats = {}, []
        for i in range(n):
            eid = BranchBuilder.ending_id(i)
            label = BranchBuilder.ROUTE_LABELS[i % len(BranchBuilder.ROUTE_LABELS)]
            pov = BranchBuilder.ROUTE_POVS[i % len(BranchBuilder.ROUTE_POVS)]
            mood = BranchBuilder.ROUTE_MOODS[i % len(BranchBuilder.ROUTE_MOODS)]
            beat = BranchBuilder.ROUTE_BEATS[i % len(BranchBuilder.ROUTE_BEATS)]
            scenes[eid] = {
                'title': f'结局·{label}',
                'pov': pov,
                'text': prose.render_scene(end_world, beat, pov, mood=mood, chapter_end=True),
                'onEnter': {'beat': beat, 'mood': mood, 'pov': pov, 'chapter': 0},
                'choices': [{'text': '进入尾声', 'goto': 'epilogue'}],
            }
            stats.append({'id': eid, 'label': label, 'pov': pov,
                          'mood': mood, 'resolved': i % 2 == 0,
                          'line': '真线' if i % 2 == 0 else '暗线'})
        return scenes, stats

    @staticmethod
    def summary(n=2):
        resolved = sum(1 for i in range(n) if i % 2 == 0)
        return {'count': n, 'resolved_routes': resolved, 'unresolved_routes': n - resolved}


def build_pack(seed=42, chapters=8, beats_per_chapter=4, worlds=None, n_endings=2, out=None):
    prose = Prose(seed)
    if worlds is None:
        worlds = list(prose.terms.keys())

    spine = list(BeatSpine(worlds, chapters, beats_per_chapter, seed).iter_steps())
    # 用独立 rng 决定哪些章为 hub（章末），哪些拍为关键拍已由 beat 名决定
    rng = random.Random(seed + 1)

    scenes = {}
    rashomon = Rashomon(prose)

    # 预生成 spine 场景 id
    for k, step in enumerate(spine):
        step['sid'] = f's{k}'

    def prose_for(step, pov=None):
        return prose.render_scene(
            step['world'], step['beat'], pov or step['pov'],
            mood=step['mood'], chapter_end=False,
        )

    # 逐 spine 场景建图
    for k, step in enumerate(spine):
        sid = step['sid']
        next_id = spine[k + 1]['sid'] if k + 1 < len(spine) else 'branch'
        choices = []

        # Rashomon：关键拍插入「同一时刻多透镜」
        if step['is_key']:
            rid = f'r{k}'
            rf = rashomon.fragment(step['beat'])
            rtext = (f"{step['pov']}视角的这一刻——\n" + rf) if rf else prose_for(step)
            scenes[rid] = {
                'title': f'{step["world"]}·{step["beat"]}·复眼',
                'text': rtext,
                'pov': step['pov'],
                'onEnter': WorldState.on_enter(step),
                'choices': [{'text': '回到主线', 'goto': next_id}],
            }
            choices.append({'text': '从另一视角看这一刻', 'goto': rid})

        # PovThreads：hub 章提供切换视角
        if step['is_hub']:
            alt = PovThreads.alternate(step['pov'])
            pid = f'p{k}'
            scenes[pid] = {
                'title': f'{step["world"]}·{alt}线',
                'text': prose_for(step, pov=alt),
                'pov': alt,
                'onEnter': {'beat': step['beat'], 'mood': step['mood'], 'pov': alt, 'chapter': step['chapter']},
                'choices': [{'text': '回到主线', 'goto': next_id}],
            }
            choices.append({'text': f'切换视角（{alt}）', 'goto': pid})

        if not choices:
            choices.append({'text': '继续', 'goto': next_id})

        scenes[sid] = {
            'title': f'第{step["chapter"]}章·{step["world"]}·{step["pov"]}',
            'text': prose_for(step),
            'pov': step['pov'],
            'onEnter': WorldState.on_enter(step),
            'choices': choices,
        }

    # 决策点（BranchBuilder：N 路 if/do 路线）
    scenes['branch'] = {
        'title': '分歧点',
        'text': f'前路在此分作 {n_endings} 股，每一股都通向一个不同的终局。',
        'pov': '—',
        'choices': BranchBuilder.choices(n_endings),
    }

    # 多结局（N 路，带统计信息）
    end_world = worlds[0]
    end_scenes, end_stats = BranchBuilder.build_endings(prose, end_world, n_endings)
    scenes.update(end_scenes)

    # 真/暗线尾声分叉：依运行时 state.resolved（branch 的 if/do 写入，数值 1/0）
    # 走不同后续分支——这是把 N 路结局的 resolved 标志真正接入运行时的关键。
    scenes['epilogue'] = {
        'title': '尾声·分岔',
        'pov': '—',
        'text': '结局的尘埃落定之处，叙事裂成两道：一道归于秩序的真线，一道沉入阴影的暗线。',
        'choices': [
            {'text': '走向真线：尘埃落定，秩序重新咬合', 'goto': 'epilogue_true', 'if': 'resolved == 1'},
            {'text': '坠入暗线：余烬未冷，故事在阴影里继续', 'goto': 'epilogue_false', 'if': 'resolved == 0'},
        ],
    }
    scenes['epilogue_true'] = {
        'title': '真线·尘埃落定',
        'pov': '林朔',
        'text': prose.render_scene(end_world, 'aftermath', '林朔', mood='释然', chapter_end=True),
    }
    scenes['epilogue_false'] = {
        'title': '暗线·余烬未冷',
        'pov': '白夜',
        'text': prose.render_scene(end_world, 'aftermath', '白夜', mood='绝望', chapter_end=True),
    }

    # 入口
    scenes['start'] = {
        'title': '序',
        'pov': '系统',
        'text': '系统倒计时归零。十七个世界在同一帧里同时亮起，又同时熄灭。',
        'choices': [{'text': '进入故事', 'goto': spine[0]['sid']}],
    }

    pack = {
        'meta': {
            'title': f'多POV规模生成（{chapters}章×{beats_per_chapter}拍 / {len(worlds)}世界 / {n_endings}结局 / seed={seed}）',
            'entry': 'start',
            'generated_by': 'gen/scale.py',
            'worlds': len(worlds),
            'n_endings': n_endings,
            'ending_stats': end_stats,
            'epilogue_lines': {
                'resolved_line': 'epilogue_true',
                'unresolved_line': 'epilogue_false',
                'note': '真/暗线后续分支由 state.resolved（branch 的 if/do 写入 1/0）经 epilogue 场景的 if 门控分流',
            },
        },
        'state': WorldState.initial(),
        'scenes': scenes,
    }

    if out:
        os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(pack, f, ensure_ascii=False, indent=2)
    return pack


def main():
    ap = argparse.ArgumentParser(description='novel-run 规模生成器')
    ap.add_argument('--out', default='packs/scale-pack.json')
    ap.add_argument('--chapters', type=int, default=8)
    ap.add_argument('--beats', type=int, default=4, help='每章拍数')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--worlds', type=int, default=0, help='限用前 N 个世界（0=全部）')
    ap.add_argument('--endings', type=int, default=2, help='末章 N 路结局（≥2）')
    ap.add_argument('--stress', action='store_true', help='千场景压测：300 章 × 5 拍')
    args = ap.parse_args()

    if args.stress:
        args.chapters, args.beats = 300, 5

    from prose import Prose
    worlds = list(Prose(args.seed).terms.keys())
    if args.worlds and args.worlds < len(worlds):
        worlds = worlds[:args.worlds]
    n_endings = max(2, args.endings)

    pack = build_pack(seed=args.seed, chapters=args.chapters,
                      beats_per_chapter=args.beats, worlds=worlds,
                      n_endings=n_endings, out=args.out)
    s = BranchBuilder.summary(n_endings)
    print(f'已生成 {len(pack["scenes"])} 个场景（{len(worlds)} 世界 / {n_endings} 结局）-> {args.out}')
    print(f'  结局统计: 共 {s["count"]} 路，已收束 {s["resolved_routes"]} / 未收束 {s["unresolved_routes"]}')


if __name__ == '__main__':
    main()
