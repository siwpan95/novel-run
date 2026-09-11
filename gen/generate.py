#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""多题材场景包生成器（验证「从真实仓库复制 + 联网搜索补齐」后的题材对齐）。

每个 world（wuxia / historical / cultivation）都：
  - 从复制的 novel 词库 / corpus 语料取词，产出**题材对齐**的散文场景
  - 保留运行时插值占位 {hero_name}/{mood}/{world}/{location}（P1 演示）
  - 决策点展开分支 choices → 多结局（P2 演示）

用法：
    python gen/generate.py --world wuxia      --out packs/wuxia.json
    python gen/generate.py --world historical --out packs/historical.json
    python gen/generate.py --world cultivation--out packs/cultivation.json
    python gen/generate.py --world all                      # 三题材全出
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from banks import Banks  # noqa: E402

# 音频线索（映射到 run/sound.js 既有合成参数）
AUDIO = {
    'start': 'ambient', 'catalyst': 'tension', 'debate': 'suspense',
    'decision': 'choice', 'ending_a': 'resolve', 'ending_b': 'fade',
}


def build_wuxia(b, seed):
    sect = b.wuxia_sect()
    move = b.wuxia_move()
    weapon = b.wuxia_weapon()
    jianghu = b.wuxia_jianghu()
    region = b.pick(b.corpus['wuxia']['regions'])
    hero = b.gen_name()
    state = {"hero_name": hero, "world": "武侠", "location": region, "mood": "平静", "hp": 100}
    scenes = {
        "start": {
            "title": f"{region}·{sect}山门",
            "text": "{hero_name} 在 {location}的{sect}山门醒来，{mood}地握着{weapon}。".replace("{sect}", sect).replace("{weapon}", weapon).replace("{location}", region),
            "audio": AUDIO['start'],
            "choices": [{"text": "听长老讲规矩", "goto": "catalyst"}],
        },
        "catalyst": {
            "title": "立规",
            "text": f"{sect}长老言：{jianghu}不可废。{{hero_name}} 演练{move}，{weapon}在鞘中轻鸣。",
            "audio": AUDIO['catalyst'],
            "onEnter": {"mood": "凝重"},
            "choices": [{"text": "记下这一式", "goto": "debate"}],
        },
        "debate": {
            "title": "夜雨",
            "text": f"夜雨打在{region}的青石上，{{hero_name}} 思量{jianghu}与侠义，{{mood}}难平。",
            "audio": AUDIO['debate'],
            "onEnter": {"mood": "沉吟"},
            "choices": [{"text": "走向岔路", "goto": "decision"}],
        },
        "decision": {
            "title": "抉择",
            "text": f"岔路当前：左取{move}，右守{sect}。{{hero_name}} 必须选。",
            "audio": AUDIO['decision'],
            "choices": [
                {"text": f"左·以{move}了结恩怨", "goto": "ending_a", "do": {"mood": "灼热"}},
                {"text": f"右·守{sect}归隐", "goto": "ending_b", "do": {"mood": "平静"}},
            ],
        },
        "ending_a": {
            "title": "结局·剑名",
            "text": f"{{hero_name}} 以{move}了结恩怨，{sect}之名传遍{region}，{{mood}}如焰。",
            "audio": AUDIO['ending_a'],
        },
        "ending_b": {
            "title": "结局·袖手",
            "text": f"{{hero_name}} 弃{weapon}归隐，{jianghu}化作闲谈，{{mood}}地转身离去。",
            "audio": AUDIO['ending_b'],
        },
    }
    return {"meta": {"title": f"武侠·验证包（{sect}）", "version": "0.2", "seed": seed, "entry": "start", "genre": "wuxia"},
            "state": state, "scenes": scenes}


def build_historical(b, seed):
    era = b.corpus['historical']['era']
    fang = b.hist('fangs')
    market = b.hist('markets')
    office = b.hist('offices')
    landmark = b.hist('landmarks')
    foreign = b.hist('foreign')
    custom = b.hist('customs')
    food = b.hist('foods')
    hero = b.gen_name()
    state = {"hero_name": hero, "world": "唐·长安", "location": fang, "mood": "平静", "hp": 100}
    scenes = {
        "start": {
            "title": f"{fang}",
            "text": f"{{hero_name}} 自{era}的{{location}}门走出，晨鼓刚歇，{{mood}}地望向朱雀大街。",
            "audio": AUDIO['start'],
            "choices": [{"text": "往西市去", "goto": "catalyst"}],
        },
        "catalyst": {
            "title": "金市风波",
            "text": f"西市金市里，{foreign}的一桩{food}官司惹了风波，{{hero_name}} 被{office}卷入。",
            "audio": AUDIO['catalyst'],
            "onEnter": {"mood": "凝重"},
            "choices": [{"text": "随差役回衙门", "goto": "debate"}],
        },
        "debate": {
            "title": "盘诘",
            "text": f"{landmark}下，{office}差役盘问，{{hero_name}} 在{{location}}中思忖，{{mood}}难决。",
            "audio": AUDIO['debate'],
            "onEnter": {"mood": "沉吟"},
            "choices": [{"text": "走向抉择", "goto": "decision"}],
        },
        "decision": {
            "title": "去留",
            "text": f"{{location}}坊与{market}之间，{{hero_name}} 须择一落脚。",
            "audio": AUDIO['decision'],
            "choices": [
                {"text": f"留·据{era}律断案", "goto": "ending_a", "do": {"mood": "畅快"}},
                {"text": f"走·隐入{custom}", "goto": "ending_b", "do": {"mood": "淡泊"}},
            ],
        },
        "ending_a": {
            "title": "结局·扬名",
            "text": f"{{hero_name}} 据{era}律断案，名动{landmark}，{{mood}}地扬名。",
            "audio": AUDIO['ending_a'],
        },
        "ending_b": {
            "title": "结局·隐市",
            "text": f"{{hero_name}} 隐入市井，{custom}里再无此人，{{mood}}地消失在夜市灯火中。",
            "audio": AUDIO['ending_b'],
        },
    }
    return {"meta": {"title": f"历史都市·验证包（{era}）", "version": "0.2", "seed": seed, "entry": "start", "genre": "historical"},
            "state": state, "scenes": scenes}


def build_cultivation(b, seed):
    realm = b.cult('realms')
    root = b.cult('spirit_roots')
    sect = b.cult('sects')
    treasure = b.cult('treasures')
    resource = b.cult('resources')
    conflict = b.cult('conflicts')
    hero = b.gen_name()
    state = {"hero_name": hero, "world": "诸天", "location": sect, "mood": "平静", "hp": 100}
    scenes = {
        "start": {
            "title": f"{sect}外门",
            "text": f"{{hero_name}} 身为{root}修士，于{{location}}外门起步，{{mood}}地吐纳灵气。",
            "audio": AUDIO['start'],
            "choices": [{"text": "入秘境", "goto": "catalyst"}],
        },
        "catalyst": {
            "title": "秘境开",
            "text": f"{{location}}秘境开启，{treasure}现世，{{hero_name}} 随队入{resource}探夺。",
            "audio": AUDIO['catalyst'],
            "onEnter": {"mood": "凝重"},
            "choices": [{"text": "深入", "goto": "debate"}],
        },
        "debate": {
            "title": "心魔",
            "text": f"{conflict}当前，{{hero_name}} 在瓶颈前犹豫，{{mood}}难平。",
            "audio": AUDIO['debate'],
            "onEnter": {"mood": "沉吟"},
            "choices": [{"text": "走向抉择", "goto": "decision"}],
        },
        "decision": {
            "title": "夺或守",
            "text": f"夺{treasure} 还是 守{{location}}？{{hero_name}} 须抉择。",
            "audio": AUDIO['decision'],
            "choices": [
                {"text": f"夺·结{treasure}道果", "goto": "ending_a", "do": {"mood": "炽烈"}},
                {"text": f"守·退归{sect}", "goto": "ending_b", "do": {"mood": "淡然"}},
            ],
        },
        "ending_a": {
            "title": "结局·飞升",
            "text": f"{{hero_name}} 结{treasure}道果，渡雷劫飞升，{{mood}}地冲霄。",
            "audio": AUDIO['ending_a'],
        },
        "ending_b": {
            "title": "结局·散功",
            "text": f"{{hero_name}} 散功归田，{conflict}中抽身，{{mood}}地归于平凡。",
            "audio": AUDIO['ending_b'],
        },
    }
    return {"meta": {"title": f"修仙·验证包（{sect}）", "version": "0.2", "seed": seed, "entry": "start", "genre": "cultivation"},
            "state": state, "scenes": scenes}


def build_infinite_flow(b, seed):
    hub = b.iflow_hub()
    system = b.iflow_system()
    instance = b.iflow_instance()
    reward = b.iflow_reward()
    role = b.iflow_role()
    threat = b.iflow_threat()
    hero = b.gen_name()
    state = {"hero_name": hero, "world": "无限流", "location": hub, "mood": "平静", "hp": 100, "points": 20}
    scenes = {
        "start": {
            "title": f"{hub}",
            "text": f"{{hero_name}} 在 {{location}} 的冷光下面板亮起，{{mood}}地望向刚弹出的任务。",
            "audio": AUDIO['start'],
            "choices": [{"text": f"进入{instance}", "goto": "catalyst"}],
        },
        "catalyst": {
            "title": "副本开启",
            "text": f"{instance}的门在身后合拢，{threat}的轮廓在暗处成形，{{hero_name}} 握紧刚兑换的{reward}。",
            "audio": AUDIO['catalyst'],
            "onEnter": {"mood": "紧绷"},
            "choices": [{"text": f"按{system}推进", "goto": "debate"}],
        },
        "debate": {
            "title": "抉择前夜",
            "text": f"{role}低声争执：是靠{reward}硬闯，还是留一手？{{hero_name}} 在{{location}}里{{mood}}难决。",
            "audio": AUDIO['debate'],
            "onEnter": {"mood": "沉吟"},
            "choices": [{"text": "走向抉择", "goto": "decision"}],
        },
        "decision": {
            "title": "生或死",
            "text": f"前方岔开：左夺{reward}，右守{{location}}。{{hero_name}} 必须选。",
            "audio": AUDIO['decision'],
            "choices": [
                {"text": f"左·以{reward}了结", "goto": "ending_a", "do": {"mood": "灼热", "points": 10}},
                {"text": f"右·守{{location}}归队", "goto": "ending_b", "do": {"mood": "平静"}},
            ],
        },
        "ending_a": {
            "title": "结局·通关",
            "text": f"{{hero_name}} 以{reward}了结{instance}，{threat}退去，{{mood}}如焰地回到{{location}}。",
            "audio": AUDIO['ending_a'],
        },
        "ending_b": {
            "title": "结局·退场",
            "text": f"{{hero_name}} 弃{reward}归队，{role}的喧声远了，{{mood}}地隐入{hub}的白光。",
            "audio": AUDIO['ending_b'],
        },
    }
    return {"meta": {"title": f"无限流·验证包（{hub}）", "version": "0.2", "seed": seed, "entry": "start", "genre": "infinite_flow"},
            "state": state, "scenes": scenes}


def build_lowmagic(b, seed):
    knight = b.lowmagic_knight()
    church = b.lowmagic_church()
    peasant = b.lowmagic_peasant()
    creature = b.lowmagic_creature()
    relic = b.lowmagic_relic()
    threat = b.lowmagic_threat()
    loc = b.lowmagic_location()
    hero = b.gen_name()
    state = {"hero_name": hero, "world": "低魔中世纪", "location": loc, "mood": "平静", "hp": 100, "gold": 12}
    scenes = {
        "start": {
            "title": f"{loc}",
            "text": f"{{hero_name}} 在 {{location}}的茅屋里醒来，{threat}的传闻已沿商道传来，{{mood}}地攥紧柴刀。",
            "audio": AUDIO['start'],
            "choices": [{"text": f"往{church}去", "goto": "catalyst"}],
        },
        "catalyst": {
            "title": "钟声",
            "text": f"{church}的钟在雾里敲响，{creature}的爪痕出现在圣坛上，{{hero_name}} 被{knight}唤去。",
            "audio": AUDIO['catalyst'],
            "onEnter": {"mood": "惊惧"},
            "choices": [{"text": f"随{knight}查看", "goto": "debate"}],
        },
        "debate": {
            "title": "密室",
            "text": f"{relic}在暗处微光流转，{peasant}们低声争执该信{church}还是弃村而走，{{hero_name}} {{mood}}难决。",
            "audio": AUDIO['debate'],
            "onEnter": {"mood": "沉吟"},
            "choices": [{"text": "走向抉择", "goto": "decision"}],
        },
        "decision": {
            "title": "守或逃",
            "text": f"守{relic} 还是 避{threat}？{{hero_name}} 须抉择。",
            "audio": AUDIO['decision'],
            "choices": [
                {"text": f"左·以{relic}镇邪", "goto": "ending_a", "do": {"mood": "肃然"}},
                {"text": f"右·弃村避走", "goto": "ending_b", "do": {"mood": "黯然"}},
            ],
        },
        "ending_a": {
            "title": "结局·镇守",
            "text": f"{{hero_name}} 以{relic}镇住{creature}，{church}记其名，{{mood}}地立于{{location}}。",
            "audio": AUDIO['ending_a'],
        },
        "ending_b": {
            "title": "结局·流亡",
            "text": f"{{hero_name}} 弃{loc}避{threat}，{peasant}的炊烟散入雾里，{{mood}}地走入荒野。",
            "audio": AUDIO['ending_b'],
        },
    }
    return {"meta": {"title": f"低魔中世纪·验证包（{loc}）", "version": "0.2", "seed": seed, "entry": "start", "genre": "lowmagic"},
            "state": state, "scenes": scenes}


BUILDERS = {"wuxia": build_wuxia, "historical": build_historical, "cultivation": build_cultivation,
            "infinite_flow": build_infinite_flow, "lowmagic": build_lowmagic}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser(description="多题材场景包生成器（novel-run 验证）")
    ap.add_argument("--world", choices=["wuxia", "historical", "cultivation", "infinite_flow", "lowmagic", "all"], default="all")
    ap.add_argument("--out", default=None, help="输出路径（all 时忽略，按 packs/<world>.json）")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    worlds = BUILDERS.keys() if args.world == "all" else [args.world]
    packs = []
    for w in worlds:
        b = Banks(seed=args.seed)
        pack = BUILDERS[w](b, args.seed)
        out = args.out or os.path.join(here, "..", "packs", f"{w}.json")
        out = os.path.abspath(out)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(pack, f, ensure_ascii=False, indent=2)
        n_end = sum(1 for s in pack["scenes"].values() if "choices" not in s)
        print(f"生成 [{w}] {out}  场景={len(pack['scenes'])} 结局={n_end} 题={pack['meta']['title']}")
        packs.append(out)

    print(f"共生成 {len(packs)} 个题材包")


if __name__ == "__main__":
    main()
