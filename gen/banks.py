#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""词库/语料加载器 —— 统一从 reference/novel（复制自真实仓库）与 corpus（联网搜索补齐）取词。

设计要点：
  - novel 侧词库是「从真实仓库复制」的素材（如 wuxia_terms.json 的 martial_styles/sect_names）。
    复制过来的原始文件混入大量网页正文碎片（抓取噪声），因此加载时必须清洗。
  - corpus 侧是「联网搜索补齐」的题材语料（门派/地域/历史坊市/修仙境界…），干净且题材对齐。
  - 二者合并去重，按 world（wuxia/historical/cultivation）切换，产出题材对齐的插值素材。

清洗规则（针对武侠术语这类短词）：
  - 含功能字（之乎者也的地得了在是有与和这那其为我以于中来去所而但或…）→ 判定为正文碎片，丢弃；
  - 长度 > 8 → 判定为句子/短语，丢弃；
  - 其余视为有效术语，去重后进入词池。
经验证，清洗后每个武侠词表仍保留 ~5800 条真实术语，远超生成需要。
"""

import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 武侠术语几乎不含这些“功能字”，但抓取下来的网页正文碎片大量包含
_FUNC = set('之乎者也的地得了在是有与和这那其为我以于中来去所而但或将其被把等当从对过着么什'
            '让叫比很更最又再被个们你他它她为把给虽因由则即且若乃尝曾皆俱咸尽皆诸庶')

# 干净武侠术语常见尾字（用于 sect/move 的二次提纯，进一步压制漏网碎片）
_SECT_SUFFIX = set('派门帮教宗谷堡山庄阁岛殿宫寺观寨府庄堂会盟峰')
_MOVE_SUFFIX = set('法掌拳功诀指腿步劲刀枪剑式阵术身形意旋影手鞭锤斧钩')


def _is_garbage(x):
    if not isinstance(x, str) or not x.strip():
        return True
    if any(c in _FUNC for c in x):
        return True
    if len(x) > 8:
        return True
    return False


def _sanitize(lst):
    seen = set()
    out = []
    for x in lst:
        if _is_garbage(x):
            continue
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _sanitize_with_suffix(lst, suffix_set, require_suffix=True):
    """清洗，并按尾字进一步提纯 sect/move 类词表。"""
    seen = set()
    out = []
    for x in lst:
        if _is_garbage(x):
            continue
        if require_suffix and not x.endswith(tuple(suffix_set)):
            continue
        if x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def _dedup(lst):
    return list(dict.fromkeys(lst))


def _load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


class Banks:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        # 复制自 novel 真实仓库的词库（含抓取噪声，需清洗）
        self.novel = {
            'wuxia': _load(os.path.join(ROOT, 'reference/novel/wuxia_terms.json')),
            'cultivation': _load(os.path.join(ROOT, 'reference/novel/cultivation_terms.json')),
            'infinite_flow': _load(os.path.join(ROOT, 'reference/novel/infinite_flow_terms.json')),
            'lowmagic': _load(os.path.join(ROOT, 'reference/novel/lowmagic_medieval_terms.json')),
        }
        self.names = _load(os.path.join(ROOT, 'reference/novel/names.json'))
        # 联网搜索补齐的题材语料（干净）
        self.corpus = {
            'wuxia': _load(os.path.join(ROOT, 'corpus/wuxia-lore.json')),
            'historical': _load(os.path.join(ROOT, 'corpus/historical-lore.json')),
            'cultivation': _load(os.path.join(ROOT, 'corpus/cultivation-lore.json')),
            'infinite_flow': _load(os.path.join(ROOT, 'corpus/infinite-flow-lore.json')),
            'lowmagic': _load(os.path.join(ROOT, 'corpus/lowmagic-lore.json')),
        }

        # ── 武侠词池：真实仓库清洗后 ⊕ corpus 补齐，合并去重 ──
        # 注意：存储属性用私有名，避免与下方同名取值方法冲突
        wx = self.novel['wuxia']
        corpus_wx = self.corpus['wuxia']
        # sect：要求以门派尾字结尾（苍云派/血煞门/天剑山庄…），大幅压制漏网碎片
        self._wuxia_sects = _dedup(
            _sanitize_with_suffix(wx.get('sect_names', []), _SECT_SUFFIX)
            + [s['name'] for s in corpus_wx.get('sects', [])]
        )
        # move：要求以招式尾字结尾（苍云剑法/落雁十三式…）
        self._wuxia_moves = _dedup(
            _sanitize_with_suffix(wx.get('martial_styles', []), _MOVE_SUFFIX)
            + list(corpus_wx.get('moves', []))
        )
        # weapon：短兵器名词，直接清洗即可
        self._wuxia_weapons = _dedup(
            _sanitize(wx.get('weapon_terms', []))
            + list(corpus_wx.get('weapons', []))
        )
        # jianghu：江湖术语，直接清洗即可
        self._wuxia_jianghu = _dedup(
            _sanitize(wx.get('jianghu_terms', []))
            + list(corpus_wx.get('jianghu_terms', []))
        )

        # ── 无限流词池：复制词库清洗 + corpus 补齐 ──
        ifl = self.novel['infinite_flow']
        corpus_ifl = self.corpus['infinite_flow']
        self._iflow_system = _dedup(
            _sanitize(ifl.get('system_terms', []))
            + _sanitize(ifl.get('rule_terms', []))
            + list(corpus_ifl.get('mechanics', []))
            + list(corpus_ifl.get('rules', []))
        )
        self._iflow_instance = _dedup(
            _sanitize(ifl.get('instance_terms', []))
            + list(corpus_ifl.get('instances', []))
        )
        self._iflow_reward = _dedup(
            _sanitize(ifl.get('reward_terms', []))
            + list(corpus_ifl.get('rewards', []))
        )
        self._iflow_hub = list(dict.fromkeys(corpus_ifl.get('hub', [])))
        self._iflow_role = list(dict.fromkeys(corpus_ifl.get('roles', [])))
        self._iflow_threat = list(dict.fromkeys(corpus_ifl.get('threats', [])))

        # ── 低魔中世纪词池：复制词库清洗 + corpus 补齐 ──
        low = self.novel['lowmagic']
        corpus_low = self.corpus['lowmagic']
        self._lowmagic_knights = _dedup(
            _sanitize(low.get('knight_terms', []))
            + list(corpus_low.get('knights', []))
        )
        self._lowmagic_church = _dedup(
            _sanitize(low.get('church_terms', []))
            + list(corpus_low.get('church', []))
        )
        self._lowmagic_peasants = _dedup(
            _sanitize(low.get('peasant_terms', []))
            + list(corpus_low.get('peasants', []))
        )
        self._lowmagic_creatures = _dedup(
            _sanitize(low.get('creature_terms', []))
            + list(corpus_low.get('creatures', []))
        )
        self._lowmagic_relics = _dedup(
            _sanitize(low.get('relic_terms', []))
            + list(corpus_low.get('relics', []))
        )
        self._lowmagic_threats = list(dict.fromkeys(corpus_low.get('threats', [])))
        self._lowmagic_locations = list(dict.fromkeys(corpus_low.get('locations', [])))

    # ---- 通用 ----
    def pick(self, lst):
        return self.rng.choice(lst) if lst else ''

    def gen_name(self):
        s = self.pick(self.names.get('surnames', []))
        chars = self.names.get('given_name_chars', [])
        n = self.rng.randint(1, 2)
        return s + ''.join(self.rng.choice(chars) for _ in range(n))

    # ---- 武侠（取自复制的 novel 词库 + corpus 补齐，已清洗） ----
    def wuxia_move(self):
        return self.pick(self._wuxia_moves)

    def wuxia_sect(self):
        return self.pick(self._wuxia_sects)

    def wuxia_weapon(self):
        return self.pick(self._wuxia_weapons)

    def wuxia_jianghu(self):
        return self.pick(self._wuxia_jianghu)

    # ---- 无限流（复制词库清洗 + corpus 补齐） ----
    def iflow_system(self):
        return self.pick(self._iflow_system)

    def iflow_instance(self):
        return self.pick(self._iflow_instance)

    def iflow_reward(self):
        return self.pick(self._iflow_reward)

    def iflow_hub(self):
        return self.pick(self._iflow_hub)

    def iflow_role(self):
        return self.pick(self._iflow_role)

    def iflow_threat(self):
        return self.pick(self._iflow_threat)

    # ---- 低魔中世纪（复制词库清洗 + corpus 补齐） ----
    def lowmagic_knight(self):
        return self.pick(self._lowmagic_knights)

    def lowmagic_church(self):
        return self.pick(self._lowmagic_church)

    def lowmagic_peasant(self):
        return self.pick(self._lowmagic_peasants)

    def lowmagic_creature(self):
        return self.pick(self._lowmagic_creatures)

    def lowmagic_relic(self):
        return self.pick(self._lowmagic_relics)

    def lowmagic_threat(self):
        return self.pick(self._lowmagic_threats)

    def lowmagic_location(self):
        return self.pick(self._lowmagic_locations)

    # ---- 历史（取自 corpus 唐长安语料） ----
    def hist(self, key):
        return self.pick(self.corpus['historical'].get(key, []))

    # ---- 修仙（取自 corpus 修仙语料） ----
    def cult(self, key):
        return self.pick(self.corpus['cultivation'].get(key, []))
