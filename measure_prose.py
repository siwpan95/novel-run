#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Task #16 复测 v2：保守检测器 + 人工可核对的样本。"""
import sys, os, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gen'))
from prose import Prose

p = Prose(42)

print("=== 池规模 ===")
total = sum(len(v) for v in p.terms.values())
print(f"  总术语: {total} | 世界: {len(p.terms)} | hooks: {len(p.hooks)} | scene_frame: {len(p.scene_frame)} | body_reaction: {len(p.body_reaction)}")
rare = set()
for pool in p.terms.values():
    for t in pool:
        for c in t:
            if ord(c) > 0x9FFF: rare.add(c)
print(f"  超 BMP 残留: {repr(''.join(sorted(rare))) if rare else 'set() (无)'}")

# 保守检测器：只抓真垃圾
MOJI = set('乴乥乩乲乮丬乣乨乬')
# 注意：全角标点（，；（）：等，码点 > 0x9FFF）不算乱码，必须排除，否则会误报 100%
FULLWIDTH_PUNCT = set(range(0xFF01, 0xFF61)) | set(range(0x3000, 0x3040)) | {0x2018,0x2019,0x201C,0x201D,0x300C,0x300D,0x3001,0x3002,0xFF1F,0xFF01}
LABEL = ('模板','复制','汉语描写词汇','素材','虚拟世界','百度百科','标签','去AI','知识星球','跳至内容','维基','百科')
FOREIGN = ('康拉德','迈克尔','瑪利亞','蘇珊','冉阿让','珂赛特')
# 网页/广告/版权残留：此前检测器只查乱码与标签，不查 URL/广告词，
# 导致 README 的「0.00% 垃圾」成为检测器自证口径。补上后口径才可复现。
URL_AD = re.compile(
    r'(www\.|https?://|\.com|\.cn|\.net|allrights|copyright|版权|广告|投放|招商|投稿|知识星球|公众号|微信号)',
    re.I,
)
# 仅保留「铁证级」垃圾信号：乱码/超位异常字符 + 明确标签/外文 + 网页广告残留。
# 不再用 DISCOURSE 常见词集（虚拟/市场/经济/意识/小说/读者 等都是合法题材词，会误杀）。

def junk_reason(s):
    for c in s:
        o = ord(c)
        if c in MOJI: return ('MOJI', c)
        if 0x3400 <= o <= 0x4DBF: return ('ExtA', c)
        if 0x9FA6 <= o <= 0x9FFF: return ('BMPTail', c)
        if o > 0x9FFF and o not in FULLWIDTH_PUNCT: return ('codepoint', c)
    for w in LABEL + FOREIGN:
        if w in s: return ('LABEL/FOREIGN', w)
    m = URL_AD.search(s)
    if m: return ('URL/AD', m.group(0))
    return None

def is_junk(s):
    return junk_reason(s) is not None

worlds = list(p.terms.keys())
beats = ['break_1','midpoint','all_lost','break_2']
moods = ['中性','警觉','恐惧','愤怒','决意']
N = 200
junk=0; clean=0; samples=[]
for w in worlds:
    for i in range(N):
        s = p.render_scene(w, beat=beats[i%len(beats)], pov='林朔',
                           mood=moods[i%len(moods)], chapter_end=(i%5==0))
        if is_junk(s):
            junk+=1
            if len(samples)<66: samples.append((w, junk_reason(s), s.replace('\n',' / ')))
        else: clean+=1
print(f"\n=== 渲染污染率（保守检测器，{junk+clean} 场景）===")
print(f"  干净: {clean} | 污染: {junk} | 污染率: {100*junk/max(1,junk+clean):.2f}%")

print(f"\n=== 污染样本（{len(samples)} 例，按触发原因分类）===")
from collections import Counter
rc = Counter(r for _,r,_ in samples)
print("  触发原因分布:", dict(rc))
for w,r,s in samples:
    print(f"  [{w}][{r}] {s[:120]}")

print("\n=== 干净样本抽查（每世界 1 例）===")
for w in worlds:
    s=p.render_scene(w, beat='midpoint', pov='白夜', mood='警觉', chapter_end=True)
    print(f"  [{w}] {s.replace(chr(10),' / ')}")
