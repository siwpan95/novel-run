# novel-run · 集成路线独立验证项目

> 目的：在**不触碰** `dict-scene-engine`（DSE）与 `novel` 两个真实仓库源码的前提下，
> 用一套最小自包含项目验证「novel 生成器 ↔ DSE 运行时」的落地路线，并把**两个真实仓库的
> 内容素材复制进来**做实打实的题材对齐与内容校验。
>
> 验证结论：**路线可行，五题材已对齐，内容可校验，DSE 条件引擎已复刻**。
> 架构层互补（生成器 ↔ 运行时）成立；跨语言 JSON 接缝可用；安全性反而因「机器生成内容走
> 惰性数据而非可执行 ESM」而收敛；DSE 的 7 项内容 lint 已移植并在 novel-run 运行时跑通；
> DSE 的 `if`/`do` 条件引擎（点式嵌套路径 + 安全表达式求值 + do 增量/赋值语义）亦已复刻。

## 角色映射（验证项目 ↔ 真实仓库）

| 验证项目组件 | 对应真实仓库能力 |
|---|---|
| `gen/`（Python，零依赖） | novel 的「结构化场景输出」模式（`SceneDirector` → JSON 场景包） |
| `run/runtime.js`（Node，零依赖） | DSE 的 `scenes`/`state`/`engine` 插件（但**只加载惰性 JSON**） |
| `run/sound.js` | DSE 的 `sound.js`（事件 → 程序化 PCM） |
| `scripts/convert-dse.mjs` | 把 DSE 的 ESM 内容包（如 `reference/dse/wuxia.js`）转成本项目惰性 JSON |
| `reference/novel/*.json` | 从 novel 仓库**复制**的词库（wuxia/cultivation/infinite_flow/lowmagic 术语 + names + hook 模板） |
| `reference/dse/*.js` | 从 DSE 仓库**复制**的内容包（wuxia/changan/river） |
| `corpus/*.json` | **联网搜索补齐**的题材语料（武侠门派/唐长安坊市/修仙境界…），超出 repo 既有词库 |

## 文件结构

```
novel-run/
├── package.json     # 顶层 CLI 配置（bin + npm scripts，参考 dict-scene-engine）
├── LICENSE          # MIT
├── .gitignore       # 排除 saves/、.workbuddy/、__pycache__/、*.bak*
├── gen/
│   ├── banks.py        # 词库/语料加载 + 污染清洗（核心修复点，含 5 题材词池）
│   ├── world.py        # ⚠️ 未接线（dead module）：早期迷你模型，当前无人 import，保留仅供追溯
│   │                   #   （勿与 gen/scale.py 中同名但独立演进的 WorldState 混淆，那一套是活代码）
│   ├── generate.py     # CLI：--world wuxia|historical|cultivation|infinite_flow|lowmagic|all --seed → 题材 JSON 包
│   ├── prose.py        # 复刻 novel VoiceEngine 的程序化散文渲染器（干净词库 + 模板 → 题材对齐短文）
│   └── scale.py        # 千场景/多POV规模生成器（BeatSpine/PovThreads/Rashomon/BranchBuilder + 参数化）
├── run/
│   ├── runtime.js      # JSON 惰性加载 + 插值 + onEnter + 分支/多结局/存档 + 9 项 lint + if/do 条件引擎 + POV 展示
│   ├── sound.js        # 程序化 PCM 合成 WAV（零依赖）
│   ├── e2e_scale.js    # 千场景/多POV/多结局端到端断言（复用真实 lint + 图可达性）
│   └── package.json
├── scripts/
│   └── convert-dse.mjs # 把复制来的 DSE 内容包（ESM）转成惰性 JSON（battle→goto 摊平）
├── tests/
│   └── e2e.mjs         # 端到端验证（五题材生成→lint→info→play 双分支 + wuxia-dse 校验 + if/do 引擎验证）
├── reference/          # 上游素材（来源 / 许可 / 核验 commit 见 reference/PROVENANCE.md）
│   ├── PROVENANCE.md   # 来源仓库、上游路径、许可（均 MIT）、已知内容问题
│   ├── novel/*.json    # 复制自 novel 仓库的词库子集（已清洗）
│   ├── novel-full/     # 复制自 novel 仓库 novel_generator/（word_banks 全量 + engine 留档）
│   │                   #   word_banks/ 是 gen/prose.py 的「运行期硬依赖」
│   └── dse/*.js        # 复制自 DSE 仓库的内容包 + lint 移植说明（⚠️ 可执行 ESM，仅限可信来源）
├── corpus/*.json       # 联网搜索补齐的题材语料（含 infinite-flow-lore / lowmagic-lore）
├── packs/              # 生成产物（wuxia/historical/cultivation/infinite_flow/lowmagic/wuxia-dse + scale-pack 系列）
├── saves/              # 运行时产物（last.json + cue-*.wav）—— 已 gitignore，不入库
└── measure_prose.py    # dev 工具：散文渲染质量测量（池规模 / 污染率抽查）
```

## 路线映射（每项均有代码与 e2e 证据）

### P0 — 打通管道：JSON 场景包 + 惰性加载器 + 题材对齐

| 项 | 验证证据 | 对应真实改动 |
|---|---|---|
| 生成器导出 `{id,title,text,choices,onEnter,do,audio}` 场景图 | `gen/generate.py` 三题材各 6 场景 | novel 增 `--scene-json` 导出 |
| 运行时**惰性加载**（非 `import()`） | `run/runtime.js:loadPack()` 用 `fs` 读 JSON | DSE `scenes.js` 增 JSON 分支 |
| **题材对齐（多题材并行）** | wuxia=复制词库+武侠语料；historical=唐长安语料；cultivation=修仙语料；infinite_flow=主神空间副本语料；lowmagic=骑士教会黑死病语料 | novel 增 DSE 向词库/世界观 |
| 复制内容被真正用上 + 污染清洗 | `banks.py` 把 6893 条 polluted 词表清洗为 ~3000 条干净术语；infinite_flow/lowmagic 复制词库本身干净（仅按长度/功能字过滤） | — |
| 悬空跳转校验（9 项 lint 之一） | `lint` → `0 阻断问题`（e2e 通过） | 复用 DSE `lint-content` |

### P1 — 状态插值 + 程序化音频

| 项 | 验证证据 | 对应真实改动 |
|---|---|---|
| `{var}` 插值（hero_name/world/location/mood） | play 输出含插值后的姓名与心境 | novel 注入 WorldState/CharacterSim 变量 |
| `onEnter` 改写状态，文本即时反映 | 催化场景显示「凝重」、抉择前「沉吟」（mood 随 onEnter 演变） | 镜像 DSE `onEnter` schema |
| 音频标记触发程序化合成 | 每场景 `audio` 标记 → `run/sound.js` 写出 `cue-*.wav` | DSE `sound.js` 复用 |

### P2 — 生成式分支 + 多结局 + 存档

| 项 | 验证证据 | 对应真实改动 |
|---|---|---|
| 决策点展开成 `choices` 分支 | `decision` 场景 2 选项 → `ending_a` / `ending_b` | novel 的 `BeatOrchestrator` 在决策节拍生成分支 |
| 多结局可达 | `1,1,1,1`→ending_a；`1,1,1,2`→ending_b（e2e 双路径通过） | DSE 多结局统计 |
| `do` 改写状态影响后续文本 | 选左路 → 结局插值出「灼热」 | 镜像 DSE `do` 效果 |
| 结局存档 + 统计 | play 结束写 `saves/last.json`，打印经历场景数 | DSE `save.js` |

### 移植的 DSE 内容校验（`run/runtime.js:lint`，共 9 项）

第 1–7 项移植自 DSE 的 `scripts/lint-content.mjs`；第 8–9 项是后续补充的「可玩性检查」，
用于让 lint 的「0 阻断」真正等价于「play 不会崩」。

| # | 检查 | 级别 | 说明 |
|---|---|---|---|
| 1 | 悬空跳转 dangling_goto | 阻断 | `goto` 指向不存在的场景（@ 开头为特殊跳转，免检） |
| 2 | 不可达场景 unreachable | 规范 | 从 entry BFS 无法到达（DSE 允许可选/支线场景） |
| 3 | 结局可达性 ending_reachability | 阻断 | 每个非结局场景都应能走到某结局 |
| 4 | 未定义变量 undefined_var | 阻断 | 插值 `{var}` 未在 `state` 中定义 |
| 5 | 伪分支 fake_choice | 阻断 | 多选项但 goto+if+do 完全一致（含 DSE 条件选择判重） |
| 6 | 命名规范 id_naming | 规范 | 场景 ID 非小写 snake_case（DSE 用 `wuxia.start` 点分式） |
| 7 | 内容厚度 content_thickness | 规范 | 去掉占位符后正文过薄 |
| 8 | 入口缺失 missing_entry | **阻断** | `meta.entry` 指向不存在的场景（否则可达性与结局可达性分析无从进行） |
| 9 | 可玩性 choice_shape / unsafe_path / conditional_dead_end | **阻断** | ① choice 缺 `goto`、`if` 语法错误；② `do` / `onEnter` 的键含 `__proto__` / `constructor` / `prototype`；③ 初始状态下所有选项的 `if` 均不满足（条件死局，仅当 `if` 引用的根路径都在初始 state 中时才判定，避免误伤运行时写入的标志） |

> 结构类错误（`scenes` 非对象、`choices` 非数组、`choice` 缺 `goto`、`if` 非字符串等）
> 在 `loadPack()` 阶段即被拒绝，并给出逐条问题清单。

> 真实 DSE 内容包（`wuxia-dse.json`）的 16 个场景经转换后 **0 阻断问题**，仅余 16 条
> 命名规范建议（点分式 ID）——正是移植 lint 期望暴露的差异信号，而非内容缺陷。

### 复刻的 DSE `if`/`do` 条件引擎（`run/runtime.js`）

把 DSE 内容包里 `choice.if` 门控可见性、`choice.do` 改写状态的语义完整搬进运行时：

| 能力 | 语法 | 求值/执行 |
|---|---|---|
| 点式嵌套路径 | `gold` / `flags.heardMonk` / `items.antidote` | `getPath` 逐段下钻 |
| 比较 `>= <= == != > <` | `gold >= 10` / `items.antidote >= 1` | 数值比较（undefined 参与比较按 JS 语义，均为 false） |
| 逻辑 `&&` `\|\|` `!` | `!flags.heardMonk` | 递归下降解析，优先级 `!` > 比较 > `&&` > `\|\|` |
| 括号分组 | `(gold >= 10 && !flags.x)` | 支持的 token 之一 |
| 裸路径 truthy | `flags.monkDeep`（无比较） | 按真值判定，驱动可见性 |
| `do` 嵌套赋值 | `flags.dirtyFight: true` / `items.antidote: 1` | `setPath` 逐段建对象后赋值 |
| `do` 数值增量(delta) | `gold: -10` / `karma: 1` | 数字按 `state[k] = (state[k] ?? 0) + v` 叠加 |
| `do` 布尔/字符串赋值 | `mood: "灼热"` | 非数字按原值直接赋值 |

**安全约束：禁用 `eval`/`Function`** —— 用 tokenizer + 递归下降解析器，仅从 `state` 读取数据，
任何非法 token 都会在 `tokenizeExpr`/`parseExpr` 阶段抛错并带上下文。

实玩验证（见 `tests/e2e.mjs`）：
- 路径 A「买解药 → 撒迷粉 → 胜」：`gold 20→10`、`items.antidote=1`、`flags.dirtyFight=true` → 抵达 `end-mutual`；
- 路径 B「不买解药 → 干净对决」：`items`/`flags.dirtyFight` 未置位，迷粉选项被 `if(items.antidote>=1)` 过滤 → 抵达 `end-vengeance`。

### P3 — 千场景 / 多 POV / 多结局规模生成（真实集成 novel 的数据模型）

把 P0–P2 的「线性 spine + 单决策点」升级为 **novel 的千场景级、多世界、多 POV、多结局数据模型**，
仍通过同一套 `run/runtime.js` 的 9 项 lint 与 `if`/`do` 引擎。散文由 `gen/prose.py` 渲染
（复刻 novel `VoiceEngine`，消费已清洗的 novel 全量词库 → 题材对齐短文）。

| 组件 | 对应 novel 能力 | 验证证据 |
|---|---|---|
| `BeatSpine`（Save the Cat! 15 拍 × 章 → world 映射） | ASP 引擎的拍×卷×章题材调度 | 默认 8×4=32 spine 场景；压测 300×5=1500 spine 场景 |
| `WorldState`（beat/mood/pov/chapter/flags） | NarrativeContext / PlotState / CharacterSnapshot | `state` 镜像；`onEnter` 改写即时反映 |
| `PovThreads`（并行 POV 子图 + hub 切换） | 多 POV 线；关键拍「切换视角」 | 6 条 POV 线（林朔/唐川/白夜/叶琳/墟核/玩家群体）均可达（e2e 断言通过） |
| `Rashomon`（关键拍「同一时刻多透镜」） | 复眼叙事；关键拍多视角切片 | `break_1/midpoint/all_is_lost/break_2` 均生成 `复眼` 场景（e2e 断言通过） |
| `BranchBuilder`（if/do 决策点 → N 路结局 + 真/暗线后续） | `BeatOrchestrator` 决策拍分叉 | `branch` 的 choice.do 写入 `state.resolved`（数值 1/0）；`ending_0..ending_{n-1}` 再经 `epilogue` 场景的 `if` 门控分流到 `epilogue_true`/`epilogue_false` |
| 参数化 `--chapters/--beats/--seed/--worlds/--endings/--stress` | 规模与分叉可控的批量生成 | `--worlds 3` 限 3 世界；`--endings 4` 4 路结局；`--stress` 产出 **2351** 场景，lint 仍 0 阻断 |

**`gen/prose.py` 渲染质量（可复现口径）**：对 17 个题材复制词库做「干净头 / 垃圾尾」清洗
（`HEAD_FRAC=0.70` 头切 + mojibake/`_safe_chars` 引导 + hook 教程垃圾精准剔除 +
**网页/广告/版权残留正则拦截**），词池 254,213 → **213,237** 条，hook 14,536 → **14,015**；
渲染 **3400/3400 场景 0.00% 垃圾**，mojibake 残量 **`set()`（零）**。

> **复现方式**：`python measure_prose.py`（dev 工具）。
> **口径说明**：检测项含乱码/超位字符、标签/外文词、**URL/广告/版权残留**。
> 其中最后一项是后补的 —— 早期检测器不查 URL/广告，所以当时的「0.00%」属**自证口径**；
> 补上后实测仍为 0。同一轮修复还补齐了 `scene_frame` 模板缺失的 `{auditory}` / `{adj}` 槽位：
> 此前 10 条模板中 7 条通过准入、其中 3 条因槽位缺失被 `except` 静默吞掉并回退同一句兜底文案，
> 实际生效仅 **4/7**；现在 7 条全部可用，且模板准入改为**按槽位白名单校验**（未知槽位直接剔除，
> 不再静默回退）。

**运行时 POV 展示（Task #18）**：每个场景携带顶层 `pov` 字段；`scenes` 列表打印 `[pov]`，
`play` 在标题后打印 `〔视角: pov〕`，千场景遍历中 6 条 POV 线标签全部出现。

### 千场景端到端断言（`run/e2e_scale.js`，Task #20）

复用 `run/runtime.js` 的**真实 `lint`**，并在图层面做可达性断言，默认同时测
`packs/scale-pack.json`（默认规模）与 `packs/scale-stress.json`（压测规模）：

| 断言 | 默认 | 压测 |
|---|---|---|
| 加载成功 | ✓ | ✓ |
| 9 项 lint 0 阻断 | ✓ | ✓ |
| `ending_0..ending_{n-1}`（N 路）全部可达 | ✓ | ✓ |
| `epilogue` 以 `if` 门控 `resolved`（1/0）分流 | ✓ | ✓ |
| `epilogue_true`（真线·尘埃落定）终局可达 | ✓ | ✓ |
| `epilogue_false`（暗线·余烬未冷）终局可达 | ✓ | ✓ |
| 6 条 POV 线均出现在可达场景 | ✓ | ✓ |
| Rashomon `复眼` 场景可达 | ✓ | ✓ |
| POV 切换 `线` 场景可达 | ✓ | ✓ |

实测结果：**ALL PASS**（默认 / 压测 / `--endings 4 --worlds 3` 共 3 个包，含真·暗线终局可达与 `epilogue` 的 `resolved` 门控结构断言，全部通过）。

### 结局统计（N 路）

- 生成期：每个场景包在 `meta` 写入 `worlds` / `n_endings` / `ending_stats`（每路 `id`/`label`/`pov`/`mood`/`resolved`），
  并打印摘要「共 N 路，已收束 X / 未收束 Y」。
- 运行期：每次 `play` 抵达结局时 `persist()` 累计写入 `saves/endings.json`（按结局 id 计数）；
  `node run/runtime.js stats --pack P` 打印各结局次数与总游玩数（N 路结局统计）。

### 真/暗线后续分支（N 路结局的 `resolved` 标志 → 运行时分歧）

每个 `ending_i` 不再是终局，而是带「进入尾声」选项的过渡场景；其 `do` 写入数值型 `state.resolved`
（引擎**不支持布尔字面量**，只能解析 `num`/`path`，故用 `1`/`0`）。统一的 `epilogue` 场景用
`choice.if` 门控把两条线分流到两个真终局：

| 来源 | 写入 | 运行时门控 | 真终局场景 |
|---|---|---|---|
| `branch` 的 `choice.do` | `state.resolved = 1`（偶数路）/ `0`（奇数路） | — | — |
| `epilogue` 选项 A | — | `if: "resolved == 1"` | `epilogue_true`（真线·尘埃落定 / 林朔视角 / 释然） |
| `epilogue` 选项 B | — | `if: "resolved == 0"` | `epilogue_false`（暗线·余烬未冷 / 白夜视角 / 绝望） |

`epilogue_lines` 写入 `meta`（`resolved_line`/`unresolved_line`/`note`），`stats` 按真终局 id 累计。
实测游玩（以默认 2 结局 `scale-pack.json` 为例）：

- **真线**：`52 × "1"` → 经 `ending_0`（route 0，`resolved=1`）→ `epilogue` 选 A → `epilogue_true`；
- **暗线**：`49 × "1", 2, 1, 1` → 经 `ending_1`（route 1，`resolved=0`）→ `epilogue` 选 B → `epilogue_false`。

（`ending_i` 多出的「进入尾声」选项使该路决策数比「N 路之前」+1：route 0 共 52 个决策、route 1 共 52 个决策但第 50 个选 2。）

## 复制内容时的关键修复（数据污染）

从 novel 仓库复制的 `wuxia_terms.json` 每个词表都混入约 **7000 条抓取网页正文碎片**
（如 `sect_names` 列表头几条是「苍云派/血煞门/天剑山庄」，尾几千条却是维基百科散文）。
直接 `random.choice` 几乎必中垃圾，导致早期生成的武侠包出现「凡人」「幽紫疯魔杖真解」之类错词。

`gen/banks.py` 在加载时清洗：
- 丢弃含功能字（之乎者也的地得了在是有与和…）或长度 > 8 的词条（正文碎片特征）；
- 门派/招式再按尾字（派/门/帮/教… 与 法/掌/拳/功…）二次提纯；
- 与 `corpus/wuxia-lore.json` 的干净词表合并去重。

清洗后词池仍余 ~3000 条真实术语（sect 3012 / move 1328 / weapon 5966 / jianghu 5273），武侠包输出已题材正确。

## 运行

```bash
# 1) 生成五题材场景包（P0）
python gen/generate.py --world all --seed 42
#   或单题材：--world wuxia | historical | cultivation | infinite_flow | lowmagic

# 2) 把复制来的 DSE 内容包转成惰性 JSON（battle→goto 摊平）
node scripts/convert-dse.mjs

# 3) 运行时只读查询
node run/runtime.js info   --pack packs/wuxia.json
node run/runtime.js scenes --pack packs/wuxia.json
node run/runtime.js lint   --pack packs/wuxia.json        # 9 项检查
node run/runtime.js lint   --pack packs/wuxia-dse.json    # 真实 DSE 内容：0 阻断
node run/runtime.js lint   --pack packs/infinite_flow.json # 新题材：0 阻断
node run/runtime.js lint   --pack packs/lowmagic.json     # 新题材：0 阻断

# 4) 交互/脚本化游玩（P1/P2 + if/do 条件引擎）
node run/runtime.js play --pack packs/wuxia.json --input "1,1,1,1"   # → ending_a
node run/runtime.js play --pack packs/wuxia.json --input "1,1,1,2"   # → ending_b
# wuxia-dse 条件分支（买解药→撒迷粉 dirtyFight→end-mutual）
node run/runtime.js play --pack packs/wuxia-dse.json --input "2,1,1,1,2,1,1"
# wuxia-dse 条件分支（不买→干净对决→end-vengeance；迷粉选项被 if 门控隐藏）
node run/runtime.js play --pack packs/wuxia-dse.json --input "1,2,1,1,1,1"

# 5) 端到端验证（五题材 + wuxia-dse + if/do 引擎）
node tests/e2e.mjs

# 6) 千场景 / 多 POV / 多结局规模生成（P3）+ 9 项 lint
python gen/scale.py --out packs/scale-pack.json --chapters 8 --beats 4 --seed 42
node run/runtime.js lint   --pack packs/scale-pack.json     # 0 阻断（默认 2 结局 / 全 17 世界）
node run/runtime.js info   --pack packs/scale-pack.json     # 显示 n_endings / worlds
node run/runtime.js scenes --pack packs/scale-pack.json     # 每场显示 [pov]
#    N 路结局（≥2）+ 部分世界限定
python gen/scale.py --out packs/scale-4e3w.json --chapters 6 --beats 4 --seed 7 --endings 4 --worlds 3
#    → 打印「已生成 47 个场景（3 世界 / 4 结局）」「结局统计: 共 4 路，已收束 2 / 未收束 2」
node run/runtime.js lint   --pack packs/scale-4e3w.json     # 0 阻断
#    游玩（N 路结局 → 真/暗线分流）：
#    ⚠️ 下面两条用了 bash 的命令替换 "$(…)"，Windows PowerShell 不支持 —— 等价写法见本节末尾「Shell 兼容」
#    真线：52×"1" → ending_0(resolved=1) → epilogue 选 A → epilogue_true
node run/runtime.js play   --pack packs/scale-pack.json --input "$(python -c 'print(",".join(["1"]*52))')"   # → epilogue_true（真线·尘埃落定）
#    暗线：49×"1",2,1,1 → ending_1(resolved=0) → epilogue 选 B → epilogue_false
node run/runtime.js play   --pack packs/scale-pack.json --input "$(python -c 'print(",".join(["1"]*49)+",2,1,1")')"   # → epilogue_false（暗线·余烬未冷）
#    千场景压测（300 章 × 5 拍，约 2351 场景）
python gen/scale.py --stress --out packs/scale-stress.json
node run/runtime.js lint   --pack packs/scale-stress.json   # 0 阻断

# 7) 规模生成端到端断言（复用真实 lint + 图可达性，可指定任意包）
node run/e2e_scale.js                                    # 默认测 default + stress
node run/e2e_scale.js packs/scale-4e3w.json              # 4 结局 / 3 世界 组合

# 8) N 路结局统计 + 真/暗线分流累计（来自 saves/endings.json）
node run/runtime.js play  --pack packs/scale-pack.json --input "$(python -c 'print(",".join(["1"]*52))')"   # 累计 epilogue_true +1
node run/runtime.js play  --pack packs/scale-pack.json --input "$(python -c 'print(",".join(["1"]*49)+",2,1,1")')"   # 累计 epilogue_false +1
node run/runtime.js stats --pack packs/scale-pack.json   # 打印真/暗线终局次数 + 总游玩数
#   示例输出（截至本验证，累计多次游玩后）：
#     epilogue_true  [林朔]  「真线·尘埃落定」  次数=4
#     epilogue_false  [白夜]  「暗线·余烬未冷」  次数=4
  #     总游玩次数 = 8
  ```

> **Shell 兼容（Windows PowerShell）**：第 6 / 8 步里的 `"$(python -c '…')"` 是 **bash 的命令替换**，
> PowerShell 不做命令替换，原样粘贴会得到 `[无效选择]`（退出码 3）。等价写法：
>
> ```powershell
> # 真线：52 个 1
> $inputTrue = ((1..52) | ForEach-Object { '1' }) -join ','
> node run/runtime.js play --pack packs/scale-pack.json --input $inputTrue
>
> # 暗线：49 个 1 + 2,1,1
> $inputDark = (((1..49) | ForEach-Object { '1' }) -join ',') + ',2,1,1'
> node run/runtime.js play --pack packs/scale-pack.json --input $inputDark
>
> node run/runtime.js stats --pack packs/scale-pack.json
> ```

## CLI / npm 脚本 & 自动化（参考 dict-scene-engine）

顶层 `package.json` 已接入 `bin` 与 `scripts`，可像 dict-scene-engine 的 `dse` 那样用 npm 脚本驱动运行时。查询类脚本（`info` / `scenes` / `lint` / `stats`）默认指向 `packs/scale-pack.json`；**`play` 是个例外，指向 `packs/wuxia.json`** —— `scale-pack` 的决策链需要 52 个输入，不适合作为开箱示例：

| 脚本 | 等价命令 |
|---|---|
| `npm run info` | `node run/runtime.js info --pack packs/scale-pack.json` |
| `npm run scenes` | `node run/runtime.js scenes --pack packs/scale-pack.json` |
| `npm run lint` | `node run/runtime.js lint --pack packs/scale-pack.json` |
| `npm run play` | `node run/runtime.js play --pack packs/wuxia.json --input "1,1,1,1"`（开箱可通关） |
| `npm run stats` | `node run/runtime.js stats --pack packs/scale-pack.json` |
| `npm run gen` | `python gen/scale.py --out packs/scale-pack.json --chapters 8 --beats 4 --seed 42` |
| `npm run gen:4e3w` | `python gen/scale.py --out packs/scale-4e3w.json --chapters 6 --beats 4 --seed 7 --endings 4 --worlds 3` |
| `npm run gen:stress` | `python gen/scale.py --stress --out packs/scale-stress.json` |
| `npm run e2e` | `node run/e2e_scale.js && node run/e2e_scale.js packs/scale-4e3w.json` |
| `npm run test` | `node tests/e2e.mjs && node run/e2e_scale.js` |

> 注：`run/package.json` 的示例脚本原指向不存在的 `packs/demo-pack.json`，现 `info`/`lint` 指向 `packs/scale-pack.json`，`play` 指向 `packs/wuxia.json`（4 个输入即可通关；`scale-pack` 需 52 个）。`run/runtime.js` 内置默认包同样已改为 `packs/scale-pack.json`，且 **`--pack` 路径以仓库根为基准解析**（不再依赖当前工作目录），因此 `run/` 下的脚本写 `packs/scale-pack.json` 而非 `../packs/…`（绝对路径亦可用）。`run/runtime.js` 已加 `#!/usr/bin/env node` shebang，可经 `bin: { "novel-run": "./run/runtime.js" }` 直接调用。

**每小时自动化校验**：已配置 WorkBuddy 自动化（id `72e6b4ca-…`，工作目录 `G:/local/novel-run`），规则为每小时跑一遍 `e2e_scale.js`（默认包 + `--endings 4 --worlds 3`）与真/暗线实玩（`52×"1"` → `epilogue_true`、`49×"1",2,1,1` → `epilogue_false`），再用 `node run/runtime.js stats` 汇报；执行记录追加到 `.workbuddy/memory/automations/72e6b4ca-…/memory.md`。首次已实跑干验证（5 步全部退出码 0，e2e 全过、真/暗线均抵达对应终局）。

> ⚠️ **当前状态：PAUSED（未在运行）**。本文档此前表述为「每小时跑一遍」（暗示运行中），与实况不符，已订正。需要恢复请到 WorkBuddy 自动化面板启用该条目。

## 验证结果与遗留风险（诚实标注）

- ✅ **上线前全检（代码审查 / 安全审计 / QA 端到端）已执行并完成修复**：已修复
  ① `tests/e2e.mjs` 硬编码的 Node 绝对路径（该路径本机不存在，导致 `npm test` 必失败）；
  ② `do`/`onEnter` 的点式键可经 `__proto__` 污染全局 `Object.prototype` 并据此绕过 `if` 门控；
  ③ `scene.audio` 未经白名单即拼入文件名，可经 `..` 越界写 `.wav`，且 `audio:"constructor"` 会触发未捕获崩溃；
  ④ lint 不校验结构与 `if` 语法、`meta.entry` 悬空被降级为警告、条件死局检测缺失。
  当前 9 个 pack 全部 **0 阻断**、`npm test` 全绿（62/62 断言）。
- ✅ **散文渲染质量已复核**：`scene_frame` 模板生效数由 **4/7 修复为 7/7**（补齐 `{auditory}`/`{adj}` 槽位 + 准入改为槽位白名单校验）；hook 与术语池补 URL/广告/版权过滤；`measure_prose.py` 检测口径补齐后，实测污染率仍为 **0.00%**。
- ✅ **已纳入版本控制**：`https://gitee.com/siwpan/novel-run`（MIT）。`.gitignore` 排除 `saves/`、`.workbuddy/`、`__pycache__/`、`*.bak*`；上游素材来源与许可见 `reference/PROVENANCE.md`。
- ✅ P0/P1/P2 全跑通；**五题材 + 真实 DSE 内容包共 6 个包 lint 0 阻断问题**；e2e 全断言通过（五题材各 10 项 + wuxia-dse 校验 + if/do 引擎 10 项）。
- ✅ **题材未对齐（原风险）已解决**：多题材并行（武侠/历史/修仙/无限流/低魔中世纪）+ 联网搜索语料补齐，散文风格与 DSE 向题材一致。
- ✅ **数据污染（新发现）已修复**：复制词库经清洗后输出题材正确；infinite_flow/lowmagic 复制词库本身干净，仅按长度/功能字过滤。
- ✅ **全题材覆盖（原 ⚠️）已解决**：`infinite_flow`/`lowmagic` 词库已接入 `banks.py` 与 `generate.py`，`--world all` 一次产出 5 个题材包。
- ✅ **DSE 条件/战斗语义（原 ⚠️）已复刻**：`if`/`do` 条件引擎在 `run/runtime.js` 实装——`if` 走安全表达式求值（tokenizer+递归下降，禁用 eval）控制可见分支，`do` 支持点式嵌套路径 + 数值增量/布尔赋值；wuxia-dse 实玩双路径已验证。
- ✅ **千场景/多POV 规模（原 ⚠️）已实现**：`gen/scale.py` 把 novel 的 BeatSpine / WorldState / PovThreads / Rashomon / BranchBuilder 数据模型映射到分支图——默认 59 场景、压测 **2351** 场景，两个包均 **9 项 lint 0 阻断**；6 条 POV 线 + Rashomon 复眼 + N 路结局（`--endings`≥2，e2e 已验证 `--endings 4 --worlds 3`）在 `run/e2e_scale.js` 图可达性断言中全部 PASS；运行期 `stats` 命令累计各结局游玩次数。
- ✅ **真/暗线后续分支（新增）已实现**：N 路结局的 `resolved` 标志（数值 1/0，规避引擎不支持布尔字面量）经 `epilogue` 场景 `if` 门控（`resolved == 1` / `resolved == 0`）分流到 `epilogue_true`（真线·尘埃落定/林朔）与 `epilogue_false`（暗线·余烬未冷/白夜）；e2e 断言两路终局均可达且 `epilogue` 门控结构正确；实玩真线（52×"1"）与暗线（49×"1",2,1,1）分别精确抵达两路，`stats` 累计无误。
- ✅ **安全边界（经安全审计静态 + 动态实测复核）**：
  - **`if` 条件求值禁用 `eval`/`Function`** —— 仅 tokenizer + 递归下降解析器从 `state` 读取。已用静态检索 + 运行时探针（替换 `globalThis.eval`/`Function` 为抛错代理）+ 18 条逃逸表达式复验，全部被拒。
  - **运行时只把内容当惰性 JSON 数据加载**（`fs.readFileSync` + `JSON.parse`），不走 `import()`。
  - ⚠️ **但「惰性数据 = 无副作用」并不成立**：`packs/*.json` 应始终视为**不可信输入**。已加固三处：
    ① `loadPack()` 拒绝结构非法的包（`scenes` 非对象 / `choices` 非数组 / `choice` 缺 `goto` 等）；
    ② `do` / `onEnter` 的点式键拒绝 `__proto__` / `constructor` / `prototype` —— 否则可污染全局 `Object.prototype` 并据此**绕过 `if` 剧情门控**；
    ③ `scene.audio` 先经 cue 白名单才拼文件名 —— 否则可经 `..` 把 `.wav` **写到项目目录之外**。
  - ⚠️ **唯一例外**：`scripts/convert-dse.mjs` 会 `await import()` **真正执行** `reference/dse/*.js`（上游对 `content/` 的标注即「可执行 ESM 模块，只装可信来源」）。该脚本应视为 dev-only 工具，不要对来源不明的文件运行。
- 📄 **上游素材来源与许可**：见 `reference/PROVENANCE.md`（`siwpan/novel` 与 `siwpan/dict-scene-engine`，均为 MIT）。
