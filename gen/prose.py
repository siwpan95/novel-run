#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prose.py —— 复刻 novel 的「voice」短散文渲染器（仅取词库与模板，不引入 novel 任何可执行逻辑）。

设计要点（对应 novel_generator 的 ASP 引擎 + VoiceEngine）：
  - 词库来自 reference/novel-full/word_banks（从 G:/repos/novel 复制的 30 个 JSON 词库全集）。
  - 世界术语按 world 名映射到 genre_terms/<world>_terms.json，扁平化 + 清洗后得到题材词池。
  - 渲染短散文：氛围开场（world_openings）→ 事件/动作（世界术语 + 形容词）→ 情绪身体反应
    （voice body_reaction，复刻 novel「用身体反应而非直接命名情绪」）→ 可选章末钩子（hook_templates）。
  - Rashomon 多视角：直接消费 narrative/rashomon.json 的 triggers/lenses/scenes，在关键节拍产出
    「同一时刻」多透镜片段，复刻 novel 的复眼叙事。

本模块是 novel-run 与 novel 真实集成的一部分：novel 产出线性散文 .txt，本模块把同一套
词库/模板用于**分支场景图**的逐场景短散文，使 runtime 播放时具有 novel 的题材语气。

全部随机受 seed 控制，保证可复现（对齐 novel 的 derive_seed/sub_rng 思路）。
"""

import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WB = os.path.join(ROOT, 'reference', 'novel-full', 'word_banks')

# novel 的世界名 → genre_terms 文件名前缀（与 BEAT_TO_WORLD / WORLD_PROSE_NAMES 对齐）
WORLD_TO_TERM = {
    '归墟': 'infinite_flow',
    '武侠·苍云之殇': 'wuxia',
    '末日废土': 'post_apocalyptic',
    '低魔中世纪': 'lowmagic_medieval',
    '剑与魔法': 'sword_magic',
    '星际殖民': 'scifi',
    '东方修仙': 'cultivation',
    '赛博都市': 'cyberpunk',
    '诸神黄昏': 'ragnarok',
    '克苏鲁深渊': 'cthulhu',
    '造物主遗迹': 'creator_ruins',
    '近代乱世': 'modern_china',
    '深海遗迹': 'deep_sea_ruins',
    '高等文明实验场': 'high_civ_lab',
    '魔导学院': 'magic_academy',
    '蒸汽朋克': 'steampunk',
    '机神': 'mech_divinity',
}

# 干净术语常见尾字/功能字（复用 novel-run 既有清洗思路；genre_terms 本身较干净，此处仅做兜底）
# _FUNC 用于【术语】清洗：包含 的/了/是/在… 等，因合法术语绝不含这些字。
# 注意：以下字符集刻意「只增不减」——新增的均为现代/网页/论文用字，绝不会出现在任一世界的合法术语里；
# 而电/数/西/结/本/文/修/统/化/重/經/自/真/道/氣/東/世/界 等虽也出现在垃圾里，但会误杀 scifi 系统、xianxia
# 本源/结界/经脉、修仙、东方 等合法术语，因此**不**放入垃圾集，仅靠其余字符兜底。
_FUNC = set('之乎者也的地得了在是有与和这那其为我以于中来去所而但或将其被把等当从对过着么什'
            '让叫比很更最又再被个们你他它她为把给虽因由则即且若乃尝曾皆俱咸尽皆诸庶'
            '您页史产研究采据析班牙字幕译含颇略策类往此')

# 术语级垃圾【子串】黑名单（多字垃圾比单字更精准，避免误伤合法术语）
_TERM_JUNK_SUBS = (
    '扑街', '描', '写', '性别', '配音', '书籍', '托管', '播报', '广播', '提示框', '提示光',
    '制裁', '尖脸', '桃花脸', '粗心大意', '节奏', '乌丝', '陳冠', '阿雀', '创作窝', '沙龙',
    '生产', '小说', '读者', '作者', '更新', '连载', '虽然', '但是', '因为', '所以', '这个', '那个',
    '什么', '我们', '你们', '他们', '真的', '觉得', '知道', '时候', '东西', '开始', '结果', '问题',
    '世界观', '剧情', '角色', '为了', '一种', '可以', '已经', '自己', '这样', '那样', '现在',
    '经营', '企业', '系统托管', '系统播报', '系统广播', '系统制裁', '篇篇', '人卫', '人文', '书本',
    '医院', '剧情线', '脸', '桃花', '页面', '网盘', '图片', '巨头企业', '致力', '面漆',
    '軟體', '資訊', '購物', '訂單', '點擊', '於', '發揮', '個', '來', '國', '會', '時', '術', '語',
    '網', '圖', '載', '選', '項', '確', '認', '取', '消', '錯', '誤', '成', '功', '登', '錄', '註',
    '冊', '首', '導', '航', '單', '按', '鈕', '鏈', '結', '下', '提', '繳', '驗', '證', '碼', '密',
    '帳', '號', '員', '購', '物', '車', '訂', '陳', '沙', '龍', '創', '作', '窩', '生', '產', '讀',
    '者', '作', '連', '載', '雖', '然', '因', '為', '所', '以', '這', '個', '那', '什', '麼', '們',
    '覺', '得', '東', '開', '始', '結', '果', '問', '題', '觀', '劇', '情', '角', '色', '為',
    '了', '種', '可', '已', '樣', '現', '看', '想', '做', '說', '企', '業',
    '托', '管', '播', '報', '廣', '播', '提', '示', '框', '制', '裁', '尖', '桃', '粗', '心', '大',
    '意', '節', '奏', '烏', '絲', '性', '別', '配', '音', '書', '籍', '撲', '街',
    '分钟阅读', '截稿', '起点', '签约', '玄幻', '仙侠', '公元', '病毒', '丧尸', '湖南省',
    '少女一身', '阅读', '冉阿让', '珂赛特', '塔尼斯', '马留斯', '泰纳', '20XX', '西方人名',
    '英雄在', '•', 'X分钟', '敬请', '转载', '版权', '代表作', '连载中', '未完待续',
    # 真正的「标签/网页/外文」垃圾（注意：四字成语式形容词如 诡计多端/刚正不阿 不算垃圾，是合法描写）
    '模板', '复制', '汉语描写词汇', '素材', '推荐', '商业', '台灣', '學歷', '苏珊', '林格立',
    '興府', '攝', '吴明益', '费尔兹', '瑞潘', '牛津', '三藩市', '彰化', '淡水', '同志', '專名',
    '示例', '读者', 'qq.com', 'jijiaoa', '知识星球', '投稿邮箱', 'vx', '去AI', '自动化', '跳至内容',
    '夾雜', '乡野', '蒸氣', '龐克', '學習', '著春天', '我的文本', '新手', '去AI化', '商业合作',
    '汉语', '描写词汇', ' Nev', '沉渊白骨会', '口头', '例如', '指南', '政治',
)

# novel body_reaction 用英文字典键；渲染时传入的中文字境需映射到英文键
MOOD_MAP = {
    '中性': 'calm', '警觉': 'suspicion', '恐惧': 'fear', '愤怒': 'anger',
    '震惊': 'shock', '悲伤': 'grief', '疑惑': 'confusion', '决意': 'resolve',
    '羞耻': 'shame', '喜悦': 'joy', '恐慌': 'panic', '释然': 'relief',
    '厌恶': 'disgust', '内疚': 'guilt', '疲惫': 'exhaustion', '敬畏': 'awe',
    '痛苦': 'pain', '绝望': 'despair', '渴望': 'longing', '兴奋': 'excitement',
}

# world_openings 中少数条目混入了金庸/古龙/修仙经典主角名或元叙事框，会破坏本作沉浸感，
# 这里在加载时剔除这些条目（本作人物固定为 林朔/唐川/白夜/叶琳/墟核/玩家群体）。
OPENING_DENY = set(
    '郭靖 黄蓉 洪七公 黄药师 欧阳锋 段誉 虚竹 乔峰 慕容复 令狐冲 任盈盈 杨过 小龙女 '
    '张无忌 赵敏 韦小宝 狄云 胡斐 苗人凤 袁承志 陈家洛 胡一刀 苗若兰 王语嫣 阿紫 阿朱 '
    '周伯通 郭芙 郭襄 张翠山 殷素素 谢逊 灭绝师太 东方不败 岳不群 林平之 仪琳 田伯光 '
    '游坦之 丁春秋 慕容博 萧远山 玄慈 扫地僧 萧炎 林动 唐三 叶凡 石昊 秦羽 苏铭 孟浩 '
    '王林 白小纯 张小凡 陆雪琪 碧瑶 鬼厉 傅红雪 李寻欢 楚留香 陆小凤 西门吹雪 叶孤城 '
    '花满楼 司空摘星 上官金虹 荆无命 孙小红 林诗音 小李飞刀'.split()
)
# 元叙事框（不匹配本作沉浸式场景散文）
OPENING_META_PREFIX = ('小说中', '故事里', '话说', '却说', '且说', '闲话少叙', '书接上文')

# world_openings 是整句散文，不能套用 term 的「含 的/了/是 即弃」规则（合法开场常含 的/了/是），
# 只能剔除「现代/网页/论文/繁体 UI」用字——这些绝不出现在合法氛围散文中；同时附少量垃圾子串兜底。
OPENING_JUNK = set(
    '您页产研究采据析班牙字幕译含颇略策网图點擊頁載軟體資訊選項確認取消錯誤成功登錄註冊首導航單按鈕'
    '鏈結下提繳驗證碼密帳號會員購物車訂發揮於個這們來國會時術語網盤圖片企業致力面漆'
)
OPENING_JUNK_SUB = ('网盘', '图片', '巨头企业', '致力', '面漆', '軟體', '資訊', '購物', '訂單', '點擊')

# ── 头部截取比例 ──
# 实测：每个 genre_terms / vocab / world 词库类别的列表，前 ~70% 是干净的「程序化生成术语」，
# 后 ~30% 是被抓取的网页/书籍散文碎片（含乱码、外文、论文体）。按此比例只保留头部，可一次性
# 剔除绝大多数污染（含聚类乱码——乱码字符虽反复出现、逃过频率离群剔除，但只存在于尾部）。
HEAD_FRAC = 0.70

# 钩子/hook 池中的「写作教程/元评论」垃圾（从 hook_templates.json 混入的网文教学文本）。
# 用精准短语而非单字，避免误杀合法钩子（如含「第48次循环」「第47次锚定者」的剧情钩子）。
HOOK_JUNK = (
    '写小说', '钩子、悬念', '##钩', '#写', '章节末', '回马枪', '开头不吸引人',
    '读者会直接弃文', '争夺读者', '放钩子', '保持期待感', '文学诱饵', '开场白',
    '悬念和紧张', '激励读者', '激起读者', '引人注目的角色', '深入了解你的故事',
    '断章', '营造悬念', '结果的不确定性', '这样一来，读者', '在章节末尾', '你可以加入',
    '最重要的一个秘诀', '我换句话说', '我就不多说了', '钩子是文学', '吸引读者从第一句话',
    '迫使读者继续', '激发好奇心', '提出问题并迫使', '读者从第一句话', '读者就会一直惦记',
    '读者会一直', '如何发展', '怎么放钩子', '钩子怎么', '悬念和曲折', '长期悬念',
    '吸引读者', '弃文', '爽点', '代入感', '钩子定下', '钩子要', '放钩子的', '写钩子',
    '感情线第五期', '如何塑造有变化的人物', '发展节奏', '代表作', '未完待续', '连载中',
    '百度百科', '虚拟宇宙', '维基', '维基百科', '百科·', '百科·TA',
    # 写作教程/素材类垃圾钩子（如「速成模板」「作文素材」「爆款开头」「淘宝作文模板」）
    '模板', '素材', '爆款', '作文', '淘宝', '淘寶', '速成', '開頭', '开头', '鉤子', '钩子',
    '文案', '起號', '起号', '教程', '写小说', '怎麼', '怎么用', '新手', '提供', '扔进事件',
    '情节片段', '串联成故事', '存储成了', '通用模板', '好物網', '好物网',
)

# 钩子/hook 中需剔除的「异常字符」（超位码点且非全角标点 → 如 𝕏 U+1D54F 等抓取残留）
_HOOK_BAD_CHARS = set('乴乥乩乲乮丬乣乨乬𝕏𝕐𝕒𝕓')


def _is_garbage(x):
    if not isinstance(x, str) or not x.strip():
        return True
    if any(c.isdigit() for c in x):  # 编号/时间戳/年份（2026-06-29、20XX、1.英雄）一律视为垃圾
        return True
    if any(c in _FUNC for c in x):
        return True
    for sub in _TERM_JUNK_SUBS:
        if sub in x:
            return True
    if len(x) > 14:  # 词库术语允许较长组合词，但过长的多为整句/碎片
        return True
    return False


def _flatten_terms(obj):
    """递归收集 genre_terms JSON 中所有字符串词条。"""
    out = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, list):
        for v in obj:
            out.extend(_flatten_terms(v))
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(_flatten_terms(v))
    return out


def _head(lst, frac=HEAD_FRAC):
    """截取列表前 frac 部分（保留原始顺序），剔除非字符串。词库类别列表的污染集中在尾部。"""
    if not isinstance(lst, list):
        return []
    thr = max(1, int(len(lst) * frac))
    return [x for x in lst[:thr] if isinstance(x, str)]


def _load_head_cut(obj, frac=HEAD_FRAC):
    """从 dict/list 结构中按 frac 截取每个【顶层 list】的前 frac 部分，收集所有字符串（保留顺序）。

    适用于：genre_terms（dict→category:list）、vocab（dict→subkey:list）、locations 等同构词库。
    'description' 等字符串元数据被自然跳过（非 dict/list）。
    """
    out = []
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(_load_head_cut(v, frac))
    elif isinstance(obj, list):
        out.extend(_head(obj, frac))
    return out


def _clean(lst):
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


class Prose:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.terms = {}          # world -> 清洗后的题材词池
        self.vocab = {}          # 形容词/部位/装备/地点等
        self.world_openings = {} # world -> [开场散文]
        self.hooks = []          # 章末钩子池
        self.body_reaction = {}  # 情绪 -> [身体反应短语]
        self.rashomon = {'triggers': {}, 'lenses': {}, 'scenes': {}}
        self._load()

    # ── 加载 ──
    def _load(self):
        # 1) 世界术语（genre_terms/*_terms.json）
        gt_dir = os.path.join(WB, 'genre_terms')
        for world, prefix in WORLD_TO_TERM.items():
            p = os.path.join(gt_dir, f'{prefix}_terms.json')
            if not os.path.exists(p):
                continue
            try:
                d = json.load(open(p, encoding='utf-8'))
            except Exception:
                continue
            # 头部截取：只保留每个类别前 HEAD_FRAC 的干净术语，剔除尾部抓取散文碎片/乱码
            self.terms[world] = _clean(_load_head_cut(d, HEAD_FRAC))
        # 兜底：任意已加载词库都能给未知世界一个默认池
        self._default_terms = []
        for v in self.terms.values():
            self._default_terms.extend(v)
        self._default_terms = list(dict.fromkeys(self._default_terms))

        # 自举「合法字符字母表」：从短（2-6字）且已过基础清洗的术语中收集字符，作为术语合法字符集；
        # 垃圾术语常含 建/築/專/家、传统异体（進/項/羽）、乱码（乹/乥）等，这些字符不会出现在合法术语里，
        # 故用该字母表二次过滤可一次性剔除绝大多数垃圾，无需穷举黑名单。
        safe_chars = set()
        for v in self.terms.values():
            for t in v:
                if 2 <= len(t) <= 6:
                    safe_chars.update(t)
        # 显式剔除少量现代/描述性字符，避免它们污染合法集
        safe_chars -= set('的了我你他她们这那就都也还页面您史记国产电影研究数据采用分析西班牙字幕翻译学者'
                          '因此往往包含修正略作本文术语网盘图片企业致力面漆軟體資訊點擊於發揮個來國會時'
                          '撲街陳沙龍創作窩連載讀者生產小說')
        self._safe_chars = safe_chars
        for w in list(self.terms.keys()):
            self.terms[w] = [t for t in self.terms[w]
                             if 2 <= len(t) <= 10 and all(c in safe_chars for c in t)]
        # 频率离群剔除：全池仅出现 1-2 次的字符（乱码/生僻异体/偶发网页字）视为噪声，
        # 含这些字符的术语一律剔除；合法常用字（气/時/術 等）出现次数多，得以保留。
        from collections import Counter
        char_freq = Counter()
        for v in self.terms.values():
            for t in v:
                char_freq.update(t)
        rare = {c for c, n in char_freq.items() if n < 3}
        for w in list(self.terms.keys()):
            self.terms[w] = [t for t in self.terms[w] if not any(c in rare for c in t)]
        self._default_terms = list(dict.fromkeys([t for v in self.terms.values() for t in v]))

        # 2) vocab（形容词/部位/装备/地点/名字）—— 同样头部截取 + 安全字符过滤
        vb = os.path.join(WB, 'vocab')
        if os.path.exists(os.path.join(vb, 'adjectives.json')):
            adj = json.load(open(os.path.join(vb, 'adjectives.json'), encoding='utf-8'))
            self.vocab['adjectives'] = self._safe_filter(_clean(_load_head_cut(adj, HEAD_FRAC)))
        if os.path.exists(os.path.join(vb, 'body_parts.json')):
            bp = json.load(open(os.path.join(vb, 'body_parts.json'), encoding='utf-8'))
            self.vocab['body_parts'] = self._safe_filter(_clean(_load_head_cut(bp, HEAD_FRAC)))
        if os.path.exists(os.path.join(vb, 'equipment.json')):
            eq = json.load(open(os.path.join(vb, 'equipment.json'), encoding='utf-8'))
            self.vocab['equipment'] = self._safe_filter(_clean(_load_head_cut(eq, HEAD_FRAC)))
        if os.path.exists(os.path.join(vb, 'locations.json')):
            loc = json.load(open(os.path.join(vb, 'locations.json'), encoding='utf-8'))
            self.vocab['locations'] = self._safe_filter(_clean(_load_head_cut(loc, HEAD_FRAC)))
        if os.path.exists(os.path.join(vb, 'names.json')):
            self.vocab['names'] = _head(json.load(open(os.path.join(vb, 'names.json'), encoding='utf-8')))

        # 3) world_openings（仅作兜底；主开场改为 templates/scene_frame 模板，见 opening()）
        wo = os.path.join(WB, 'world', 'world_openings.json')
        if os.path.exists(wo):
            d = json.load(open(wo, encoding='utf-8'))
            for k, v in d.items():
                if isinstance(v, list):
                    self.world_openings[k] = [
                        x for x in v
                        if isinstance(x, str) and self._clean_opening(x)
                    ]

        # 4) 章末钩子（剔除写作教程/元评论垃圾；保留含「第N次循环」等合法剧情钩子，故不按数字剔除）
        ht = os.path.join(WB, 'narrative', 'hook_templates.json')
        if os.path.exists(ht):
            d = json.load(open(ht, encoding='utf-8'))
            for v in d.values():
                if not isinstance(v, list):
                    continue
                for x in v:
                    if not isinstance(x, str) or not x.strip():
                        continue
                    if any(j in x for j in HOOK_JUNK):
                        continue
                    if any(c in _HOOK_BAD_CHARS for c in x):
                        continue
                    # 剔除含异常超位字符（非全角标点）的钩子（如 𝕏 U+1D54F 抓取残留）
                    if any(ord(c) > 0x9FFF and not (0xFF01 <= ord(c) <= 0xFF60
                               or 0x3000 <= ord(c) <= 0x303F) for c in x):
                        continue
                    if len(x) > 80:
                        continue
                    self.hooks.append(x)

        # 5) 情绪身体反应（复刻 novel 用身体反应表达情绪）
        br = os.path.join(WB, 'voice', 'voice_helpers_body_reaction.json')
        if os.path.exists(br):
            d = json.load(open(br, encoding='utf-8'))
            # 结构：{'body_reaction': {mood_key: <str或[str]>}}
            inner = d.get('body_reaction', d)
            if isinstance(inner, dict):
                for k, v in inner.items():
                    if isinstance(v, list):
                        self.body_reaction[k] = [x for x in v if isinstance(x, str)]
                    elif isinstance(v, str) and v.strip():
                        # novel 实际存的是单条字符串，统一规范为列表
                        self.body_reaction[k] = [v]

        # 6) Rashomon 多视角
        rj = os.path.join(WB, 'narrative', 'rashomon.json')
        if os.path.exists(rj):
            d = json.load(open(rj, encoding='utf-8'))
            self.rashomon['triggers'] = d.get('triggers', {})
            self.rashomon['lenses'] = d.get('lenses', {})
            self.rashomon['scenes'] = d.get('scenes', {})

        # 7) 场景框架模板（novel 的 voice 主来源，保证开场语法正确，不受词库污染影响）
        #    只保留含 {slot} 占位符的真实模板；source 中有 '复制'/'汉语描写词汇'/'模板' 等孤立标签条目需剔除。
        sf = os.path.join(WB, 'templates', 'scene_frame.json')
        if os.path.exists(sf):
            d = json.load(open(sf, encoding='utf-8'))
            tmpls = d.get('templates', d if isinstance(d, list) else [])
            self.scene_frame = [x for x in tmpls
                                if isinstance(x, str) and '{' in x and '}' in x]
        else:
            self.scene_frame = []

        # 8) 地点/形容词词库（用于填充模板 slot，需清洗）—— 各子列表同样头部截取
        vb = os.path.join(WB, 'vocab')
        loc_path = os.path.join(vb, 'locations.json')
        if os.path.exists(loc_path):
            loc = json.load(open(loc_path, encoding='utf-8'))
            self.vocab['landmark_prefix'] = self._safe_filter(_clean(_head(loc.get('landmark_prefix', []))))
            self.vocab['landmark_type'] = self._safe_filter(_clean(_head(loc.get('landmark_type', []))))
            self.vocab['terrain_prefix'] = self._safe_filter(_clean(_head(loc.get('terrain_prefix', []))))
            self.vocab['terrain_type'] = self._safe_filter(_clean(_head(loc.get('terrain_type', []))))
        adj_path = os.path.join(vb, 'adjectives.json')
        if os.path.exists(adj_path):
            adj = json.load(open(adj_path, encoding='utf-8'))
            self.vocab['appearance'] = self._safe_filter(_clean(_head(adj.get('appearance', []))))
            self.vocab['scene'] = self._safe_filter(_clean(_head(adj.get('scene', []))))

        # 9) 频率离群最终剔除：对 terms + vocab 统一统计字符频次，仅出现 1-2 次的字符
        #    （乱码/生僻异体/偶发网页字）视为噪声，含这些字符的条目一律剔除。
        #    合法常用字（气/時/術 等）出现次数多，得以保留。
        from collections import Counter
        cf = Counter()
        for v in self.terms.values():
            cf.update(''.join(v))
        for v in self.vocab.values():
            if isinstance(v, list):
                cf.update(''.join(x for x in v if isinstance(x, str)))
        rare = {c for c, n in cf.items() if n < 3}
        for w in list(self.terms.keys()):
            self.terms[w] = [t for t in self.terms[w] if not any(c in rare for c in t)]
        for k in list(self.vocab.keys()):
            v = self.vocab[k]
            if isinstance(v, list):
                self.vocab[k] = [x for x in v if isinstance(x, str) and not any(c in rare for c in x)]
        self._default_terms = list(dict.fromkeys([t for v in self.terms.values() for t in v]))

    @staticmethod
    def _clean_opening(s):
        if not s or len(s) > 200:  # 过长多为整段情节而非氛围开场
            return False
        for meta in OPENING_META_PREFIX:
            if s.startswith(meta):
                return False
        for name in OPENING_DENY:
            if name in s:
                return False
        for ch in OPENING_JUNK:
            if ch in s:
                return False
        for sub in OPENING_JUNK_SUB:
            if sub in s:
                return False
        for sub in _TERM_JUNK_SUBS:
            if sub in s:
                return False
        return True

    # ── 取值 ──
    def _safe_filter(self, lst):
        """仅保留「全字符都在合法字母表内、长度 2-10、且不含标签/网页垃圾子串」的条目。"""
        out = []
        for x in lst:
            if (isinstance(x, str) and 2 <= len(x) <= 10
                    and all(c in self._safe_chars for c in x)
                    and not any(s in x for s in _TERM_JUNK_SUBS)):
                out.append(x)
        return out

    def term(self, world, n=1):
        pool = self.terms.get(world) or self._default_terms
        if not pool:
            return [''] * n
        return [self.rng.choice(pool) for _ in range(n)]

    def adj(self):
        pool = self.vocab.get('appearance') or self.vocab.get('scene') or self.vocab.get('adjectives', [])
        return self.rng.choice(pool) if pool else ''

    def loc(self):
        lp = self.vocab.get('landmark_prefix', [])
        lt = self.vocab.get('landmark_type', [])
        if lp and lt:
            return self.rng.choice(lp) + self.rng.choice(lt)
        return self.rng.choice(self.vocab.get('locations', ['此处'])) if self.vocab.get('locations') else '此处'

    def _landmark(self):
        return self.loc()

    def _adj_phrase(self):
        return self.adj() or '沉静'

    def opening(self, world, hero='他'):
        """用 novel 的 scene_frame 模板生成语法正确的开场；slot 由清洗后的词库填充，不受词库污染影响。"""
        if self.scene_frame:
            slots = {
                'world': world,
                'char': hero,
                'landmark': self._landmark(),
                'visual': self.term(world, 1)[0] + '在视野中铺展',
                'weather': self._adj_phrase(),
                'crowd': self._adj_phrase(),
                'ambient': self.term(world, 1)[0],
                'body_reaction': self.body_reaction_for('calm') or '沉默',
                'expression': self._adj_phrase(),
                'attacker': hero,
                'defender': '对手',
                'terrain': self._landmark(),
                'modifier': self._adj_phrase(),
                'aura': self.term(world, 1)[0],
                'scope': self.term(world, 1)[0],
                'name': hero,
            }
            try:
                return self.rng.choice(self.scene_frame).format(**slots)
            except (KeyError, IndexError):
                pass
        # 兜底：用题材术语拼一句
        t = self.term(world, 1)[0]
        return f'{t}在视野尽头浮现，空气里有一种说不清的滞重。'

    def body_reaction_for(self, mood):
        key = MOOD_MAP.get(mood, mood)
        pool = (self.body_reaction.get(key)
                or self.body_reaction.get('neutral')
                or self.body_reaction.get('calm') or [])
        return self.rng.choice(pool) if pool else ''

    def hook(self):
        return self.rng.choice(self.hooks) if self.hooks else ''

    # ── Rashomon 多视角 ──
    def rashomon_for(self, beat):
        """返回 [(pov, text), ...]，复刻 novel 关键节拍的多透镜片段。"""
        triggers = self.rashomon['triggers']
        lenses = self.rashomon['lenses']
        scenes = self.rashomon['scenes']
        if beat not in triggers:
            return []
        out = []
        for pov in triggers[beat]:
            frag_pool = scenes.get(beat, {}).get(pov, [])
            lens = lenses.get(pov, {})
            if not frag_pool:
                continue
            content = self.rng.choice(frag_pool)
            template = lens.get('template', f'[{pov}视角]\n{{content}}')
            out.append((pov, template.replace('{content}', content)))
        return out

    def rashomon_active(self, beat):
        return beat in self.rashomon['triggers']

    # ── 单场景散文渲染（复刻 voice）──
    def render_scene(self, world, beat, pov=None, mood='中性', chapter_end=False, hero='他'):
        """产出一段短散文（3-5 句），贴合题材与情绪。"""
        lines = []
        # 1) 氛围开场
        lines.append(self.opening(world))
        # 2) 事件/动作（世界术语 + 形容词 + 地点）
        t1, t2 = self.term(world, 2)
        a = self.adj()
        loc = self.loc()
        lines.append(f'{loc}上，{a}{t1}正在发生；{hero}的目光落在{t2}上，呼吸不自觉慢了半拍。')
        # 3) 情绪用身体反应表达（复刻 novel 手法）
        br = self.body_reaction_for(mood)
        if br:
            lines.append(br)
        # 4) POV 透镜后缀
        if pov and pov in self.rashomon['lenses']:
            style = self.rashomon['lenses'][pov].get('style', '')
            if style:
                lines.append(f'（{pov}的视角：{style}）')
        # 5) 章末钩子
        if chapter_end:
            h = self.hook()
            if h:
                lines.append(h)
        return '\n'.join(lines)
