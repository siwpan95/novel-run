# novel-run 上线前全检报告（代码审查 + 安全审计 + QA 测试）

**日期**：2026-09-11
**场景**：上线前检查（Pre-launch Check）
**被测项目**：`G:\local\novel-run`（novel ↔ dict-scene-engine 集成路线独立验证项目）
**参与成员**：产品官（gstack-product-reviewer）+ 安全卫士（gstack-security-officer）+ 质量门神（gstack-qa-lead）
**主理人**：沽思航（gstack-lead）

---

## 📌 TL;DR（执行摘要）

- **整体结论**：🟡 **条件 Go（本机自用/演示）**；🔴 **No-Go（对外发布/开源）**
- **主路径是真的**：9 个 pack 全部 `lint` 0 阻断、`e2e_scale` 默认+压测 ALL PASS、真/暗线各精确抵达 `epilogue_true`/`epilogue_false`（各 53 场景）、**同 seed 生成字节级确定性**（重跑 SHA256 与提交版逐字节一致）。
- **但发布证据链断了**：README 旗舰证据「`tests/e2e.mjs` 62 项断言全过」**原样执行 exit 1 崩溃** —— 该文件硬编码了一个**不存在的 Node 路径**（`22.22.2-2`，本机只有 `22.22.2-3`）。`npm test` / `npm run test` 均必红。这是**唯一一条 🔴 P0**。
- **安全叙事被推翻**：`eval`/`Function` 禁用**属实**（静态+动态双证），但「场景包 = 惰性无害数据」**不成立**——一个 pack 即可**全局污染 `Object.prototype` 并绕过 `if` 剧情门控**，还可通过 `scene.audio` **在项目目录之外写出文件**（已实测落盘 17684 字节物证）。
- **下一步**：修 1 条 P0 + 3 项关键 P1（合计约 ≤40 行改动）后即可 Go；若要对公开放，另需 `git init` + `LICENSE` + README 声明订正。
- **更新（2026-09-11 追加）**：**批次 1–4 已全部完成并推送** —— 批次 1（P0 + 两项安全）、批次 2（结构校验 + 可玩性 lint + 条件死局）、批次 3（CLI 可用性 + 渲染质量 + 文档订正）、批次 4（存档按 pack 隔离 + 原子写 + 清空保护）；对外发布准备（git 初始化 + MIT LICENSE + reference/PROVENANCE）已完成。**§2.1 的 P0 1 条 + P1 12 条已全部处理** —— 详见 **§4 / §5 / §6 / §7**。仓库：https://gitee.com/siwpan/novel-run

---

## 🎯 核心结论卡片

| 项目 | 内容 |
|------|------|
| **Go / No-Go** | 🟡 **条件 Go**（本机自用）／ 🔴 **No-Go**（对外发布，缺版本控制 + LICENSE + 声明不实） |
| **严重度分布** | 🔴 **1** / 🟠 **12** / 🟡 **11** / 🟢 **8** |
| **关键行动项** | **16** 条（P0 1 条 + 上线前必修 3 条 + 其余 12 条） |
| **成员一致性** | 三方**独立交叉命中**同一批核心缺陷（原型污染 / lint 盲区 / 无 LICENSE），无结论冲突 |
| **唯一分歧** | P0 定级：产品官与安全官均判"无 P0"，QA 判 `tests/e2e.mjs` 为 P0。**主理人裁定采纳 QA 定级**（理由见 §2.0） |
| **建议负责人** | 全哥本人（单人项目）；P0/P1 修复建议按 3 个批次推进 |

---

## 1. 各成员核心结论

### 🔍 产品官（代码审查 / `review` skill 7 专家视角）
- **核心判断**：🟡 有条件可上，无 P0。运行时主干正确、无 setPath 越界、无死循环。问题集中在**"对外声明不实"与"交付卫生"**。
- **关键发现**：README 头号卖点「渲染 3400/3400 场景 **0.00% 垃圾**」与实测不符——hook 池残留 **13 条广告/版权/外链**（如 `广告投放：www.oceanengine.com`），且该 "0.00%" 是检测器自证（`measure_prose.py` 不查 URL/广告词）；另加测出**散文模板实际只 4/7 生效，45.4% 的开场是同一句兜底句**。
- **关键建议**：把 `if` 语法校验并入 lint；堵 hook 污染并订正 README 口径；修默认 pack 路径与 state 深拷贝。
- **追补**：新增 P1「模板 4/7 生效」「无 LICENSE 但声明 MIT」，并指出 `reference/novel-full`（49.8MB）是 `gen/prose.py:25` 的**运行期硬依赖**、不可当"素材"一刀切。

### 🛡️ 安全卫士（OWASP + STRIDE 安全审计）
- **核心判断**：🟡 中（偏高），**未发现 P0**；3 条 P1 需上线前修。无 RCE、无网络面、无凭证泄漏。综合评级 **C+**。
- **声明核验**：「禁用 eval/Function」✅ **证实**（静态 grep 唯一命中是正则 `exec`；动态用 `--import` 把 `globalThis.eval/Function` 换成抛错代理后跑 PoC 未触发；18 条逃逸表达式全部 exit=1，副作用文件 4 个候选路径均不存在）。「惰性 JSON ⇒ 内容无害」❌ **证伪**。
- **关键发现**：① `setPath` 未过滤 `__proto__/constructor/prototype` → 全局原型污染 + **门控绕过**（实测进入本不存在的 admin 分支）；② `scene.audio` 未消毒即拼文件名 → **项目外任意已存在目录可写 `.wav`**（实测写出 17684 字节）；③ `audio:"constructor"` 取到原型链成员 → `Buffer.alloc(NaN)` 未捕获崩溃。
- **关键建议**：按 F-01 → F-02/F-03 → F-04 顺序修完再发版；`convert-dse.mjs` 标 dev-only + 对复制内容建 SHA-256 白名单。

### ✅ 质量门神（QA 端到端实跑与发布验证）
- **核心判断**：🟡 **条件 Go**；主路径真实全绿且**完全确定性**，但**不能按现状宣布可发布**。
- **关键发现**：找到本轮**唯一 🔴 P0** —— `tests/e2e.mjs:30` 硬编码 `…/node/versions/22.22.2-2/node.exe`（本机不存在），导致 `npm test` 原样 exit 1、README「62 项断言」不可复现（临时建 junction 后实跑为 `OK=62 / X=0`）。另有 `npm run play` 脚本**自身 exit 3**、README 第 6/8 步命令在 PowerShell 不可执行。
- **关键证据**：确定性验证——同 seed 两次生成 SHA256 完全相同，**且与提交版 pack 也完全相同**；Node 26.7.0 前向兼容实跑通过；压测 `lint` 性能基线 1152ms（2MB / 2351 场景）。
- **关键建议**：`NODE` 改 `process.execPath`（改 1 行）；补 schema 校验与原型链防护；README 与 npm 脚本对齐真实可用路径。

### 🔧 排障手（调试与根因）
> 本次未上场（无独立调试/复盘诉求，缺陷根因已由三位成员在各自域内定位到 file:line），不列。

---

## 2. 综合审查发现（去重合并后按严重度排序）

### 2.0 主理人定级裁定
三方对 P0 的判断出现分歧：产品官与安全官各自域内均判"无 P0"，QA 判 `tests/e2e.mjs` 为 P0。
**裁定：采纳 QA 定级。** 理由：本项目 README 把「62 项断言全过」作为**核心对外证据**，而 `npm test` 是任何新使用者/CI 的**第一入口**；入口必红 = 发布证据链断裂，符合"阻断上线"的定义。产品官/安全官的"无 P0"是针对**运行主干**与**安全域**的局部判断，二者不矛盾，合并后取最严。

### 2.1 发现清单

| # | 严重度 | 类别 | 位置 | 问题 | 证据 | 来源 |
|---|--------|------|------|------|------|------|
| 1 | 🔴 **P0** | 发布证据链 | `tests/e2e.mjs:30` | 硬编码 Node 路径 `…/node/versions/22.22.2-2/node.exe`，**本机不存在**（实际只有 `-3`）→ `npm test` / `npm run test` 原样失败，README 旗舰证据「62 项断言全过」不可复现 | `npm test` → **exit 1**；`[X] wuxia: lint 0 阻断问题` 后 `SyntaxError: Unexpected end of JSON input @ e2e.mjs:72`（`spawnSync` 对不存在可执行文件返回空 stdout）。临时建 junction 后 → `OK=62 / X=0 / exit 0` | QA #1 |
| 2 | 🟠 P1 | 安全·注入 | `run/runtime.js:172-181`（setPath）、`:310-319`（applyDo）、调用点 `:374` `:409` | `do`/`onEnter` 的点式键**未做危险段名过滤**：含 **`__proto__` 段**的键名（如 `"__proto__.x"`）会命中**全局 `Object.prototype`**，并被 `choice.if` 真值判定采信 ⇒ **剧情门控可绕过**。**精度附注（防过度声明）**：`"constructor.prototype.x"` 经实测**不**污染全局（`:177` 的 `typeof cur[p] !== 'object'` 会新建 `state.constructor` 将其遮蔽）——即**并非任何原型链键名都危险，但 `__proto__` 段已足以致命** | PoC `onEnter={"__proto__.hero_name":"PWNED","__proto__.isAdmin":true}`：`lint` 报 `[未定义变量]`（证其不在 state），`play` 却输出 `PWNED` / `继承判定: true` 并 `[结局] 抵达 admin`，exit 0。QA 侧独立复现 `do:{"__proto__.leaked":1}` → 后续场景 `{leaked}` 渲染为 `1` | 安全 F-01 + QA #2（产品官精度复核） |
| 3 | 🟠 P1 | 安全·任意写 | `run/sound.js:57-58`（`mkdirSync(dir)` + `resolve(dir, \`cue-${cue}.wav\`)`）；数据源 `run/runtime.js:378` | `scene.audio` 来自不可信 pack 且**未消毒即拼入文件名**，`resolve()` 规范化 `..` ⇒ 可写到**项目目录之外已存在的目录**。**两条硬约束**：① 目标目录**必须已存在**（`:57` 只 `mkdirSync` 了 `saves`，穿越目标不存在则 `ENOENT`——安全官首版 PoC 即撞此）；② 文件名后缀**固定 `.wav`**（由 `:58` 的 `cue-${cue}.wav` 决定，不可任意扩展名） | `audio="../../../../_sec_probe/pwned"` 实跑 → `G:\local\_sec_probe\pwned.wav` **确被创建 17684 bytes**（物证已由主理人复核存在）。主理人复核：探针目录事后已清理，项目内 0 残留 | 安全 F-02（产品官约束补正） |
| 4 | 🟠 P1 | 安全·崩溃 | `run/sound.js:33`（`CUES[cue] ?? {}`）、`:35-36` | `CUES[cue]` 走**原型链**：`audio:"constructor"` 取到构造函数 → `freq/dur` 为 undefined → `Buffer.alloc(NaN)` 抛 `ERR_OUT_OF_RANGE`，且该行在 `try` 之外 ⇒ **未捕获崩溃** | 实跑 `RangeError [ERR_OUT_OF_RANGE] … Received NaN`，栈顶 `at render (sound.js:36:23)`，exit 1 | 安全 F-03 |
| 5 | 🟠 P1 | lint 盲区·schema | `run/runtime.js:26-33`（loadPack）、`:49-149`（lint） | **无 schema/类型校验**，lint 的 7 项**不覆盖 `if`/`do`/`choice.goto` 与字段类型** ⇒ 「0 阻断」≠「play 不崩」 | `{"if":123}` → `lint` **exit 0「0 阻断」**但 `play` exit 1；`choices:"abc"` → **lint 直接 TypeError 崩**；`goto:5` → lint TypeError 崩；`scenes:{...}` 为数组 → lint exit 0 静默通过 | 安全 F-04 + 产品官 #1/#3/#10 + QA #4 |
| 6 | 🟠 P1 | lint 盲区·结构 | `run/runtime.js:76-90`、`:105-109` | `meta.entry` 悬空时**整段可达性 + 结局可达性检查被静默跳过**，只留 1 条警告 ⇒ 结构损坏的包仍报「0 阻断」 | 造包 `meta.entry="zzz"` → `errors=0`；`scenes:{}` → `errors=0`；QA 侧 `entry: no_such_scene` → lint exit 0（仅 1 条规范建议），play exit 2 | 产品官 #3 + QA B3 |
| 7 | 🟠 P1 | 逻辑缺陷·死局 | `run/runtime.js:387` 附近；lint `reachesEnding` | ① `play` 遇**所有选项被 `if` 隐藏**时打印 `[死局]` 却 **exit 0**，并把当前场景**当作结局计入 stats**；② lint **检测不到 if 门控死局**（`reachesEnding` 无视 `if`） | D1：gold=0 门控 `gold>=10` → 输出 `[死局]` 但 exit 0、`结局计数 start = 1`；D2：同包 `lint` exit 0 / 0 阻断 | QA #6 |
| 8 | 🟠 P1 | 可用性·脚本 | `package.json:14` | `npm run play` 自带 `--input "1,1,1,1"`，但默认包 `scale-pack.json` 决策链需 **52** 个输入 ⇒ **脚本自身 exit 3**（README「默认包统一指向 scale-pack」的承诺失效） | `npm run play` → **exit 3** + `[无输入] 需 --input "1,2,..."` | QA #3 |
| 9 | 🟠 P1 | 内容质量·模板 | `gen/prose.py:347-348`（准入过宽）、`:463-464`（渲染与异常） | **模板准入过宽**：只查 `{`/`}` → 10 条中 7 条通过，其中 **3 条使用 slots 中不存在的 `{auditory}`/`{adj}`** ⇒ 实际生效仅 **4/7**；且 `:463` 的 `str.format` 是**唯一未捕获点**，`:464` 只 catch 2/5 类异常（`AttributeError`/`ValueError` 未覆盖，见 #21） | `Prose(42)`：`admitted: 7 → effective: 4/7`；**结构期望**回退率 3/7 ≈ **42.9%**，**实测** 500 次 `opening()` 中 227 次命中 `:468` 兜底句「…在视野尽头浮现，空气里有一种说不清的滞重。」= **45.4%**（z≈1.15、p≈0.25，属独立验证而非新数）；判定方法 = 匹配兜底句字符串 | 产品官 #18a/#18b + 安全 F-13 |
| 10 | 🟠 P1 | 声明不实·内容 | `gen/prose.py:297-317`；`reference/novel-full/word_banks/narrative/hook_templates.json:9870` | hook 池**残留 13 条广告/版权/外链垃圾**，直接打脸 README「0.00% 垃圾」；该指标系检测器自证（`measure_prose.py` 不查 URL/广告词） | 实跑：`hooks total 14036 / suspect 13 / AD line in pool: True`；样例 `广告投放：www.oceanengine.com`、`2006-2022www.17k.comAllRightsReserved…` | 产品官 #2 |
| 11 | 🟠 P1 | 声明不实·运维 | `README.md:281` | README 称「已创建 WorkBuddy 自动化（id 72e6b4ca-…），每小时非破坏性地跑一遍」（暗示运行中），**实际该自动化 status=PAUSED** | 主理人独立复核：`automation view 72e6b4ca-…` → `"status":"PAUSED"`，`rrule=FREQ=HOURLY;INTERVAL=1`，cwd `G:/local/novel-run` | 产品官 #5（主理人已复核） |
| 12 | 🟠 P1 | 合规·供应链 | `package.json:25-30`；`reference/**` | ① 声明 `"license":"MIT"` 但仓库**无 LICENSE/NOTICE/COPYING**；② 复制内容（`reference/novel-full` **49.8–56.4MB**、`reference/novel` 6.5MB、`reference/dse/*.js`）**无许可与出处标注**；③ 抓取文本混有 `本文版权属于`/`未经许可`；④ `repository` 指向 `gitee.com/siwpan/allin` 与本项目不对应 | 三方独立复核：`LICENSE/LICENSE.md/LICENSE.txt/NOTICE/COPYING` 全 `exists=False`；grep 命中版权残留（`infinite_flow_terms.json:14488` 等） | 安全 F-08 + 产品官 #19 + QA #15 |
| 13 | 🟠 P1 | 状态污染·计数 | `run/runtime.js:427-431`（读-改-写无锁）；`tests/e2e.mjs:104` | `saves/endings.json` **全局共享、无 pack 隔离、无并发保护**；`persist()` 用 `catch { tally = {} }` 静默吞解析错误后**覆盖写回** ⇒ 一次坏读即**清零全部历史** | 实测该文件一度为 `{"ending_0":3,…,"admin":2,"fin":1,"gateA":4,"gateB":2}` —— `admin/fin/gateA/gateB` 在本仓库 **grep 无任何匹配**，只可能来自其他 pack 的 `play`；随后被外部进程改写为 `{}`。**本次审计期间该文件被并发改写至少 2 次**（主理人复核：现为 115B，已偏离 16:11 基线 81B） | QA #5 + 安全 F-11 |
| 14 | 🟡 P2 | 可用性·默认值 | `run/runtime.js:459`、头注释 `:10-14`；`README.md:279` | 默认 pack 仍指向**已删除的** `packs/demo-pack.json`，且 `loadPack` 用 `resolve(path)` 相对 **CWD** ⇒ 任何不带 `--pack` 的调用必崩 | `node run/runtime.js info`（无参）→ `Error: ENOENT … packs\demo-pack.json`，exit 1 | 产品官 #4 + QA #10 |
| 15 | 🟡 P2 | 可用性·错误面 | 全 CLI 错误路径 | 所有错误路径**裸露完整 Node 堆栈 + 本机绝对路径**（缺失 pack / 传目录 / 非 JSON / 空串 / 结构错误 / if 语法错误） | A1–A5：`EISDIR`、`SyntaxError: Unexpected token '#'`、`ERR_INVALID_ARG_TYPE` 等均带完整栈 | QA #11 |
| 16 | 🟡 P2 | 文档·shell 差异 | `README.md` 第 6/8 步 | 4 条 `$(python -c …)` 命令在 **PowerShell 下不做命令替换** → 原样粘贴得 `[无效选择]` exit 3 | M1 实跑记录 | QA #7 + 产品官 |
| 17 | 🟡 P2 | 死代码 | `gen/world.py:1-78` | WorldState/CharacterSim/BeatOrchestrator 迷你模型**全项目无人 import**，仅被 README 文件结构列出。**防误判**：`gen/scale.py:68` 存在**同名 `WorldState` 且是活的**（`scale.py:208` 在用），清理时勿波及 scale.py 那一套 | 全仓 grep `import world` / `BeatOrchestrator` → 仅命中 README 与自身 docstring | 产品官 #6（含防误判补正） |
| 18 | 🟡 P2 | 状态共享 | `run/runtime.js:359` | `const state = { ...(pack.state ?? {}) }` 为**浅拷贝**，`flags/items` 等嵌套对象与 pack **共享引用**，`setPath` 就地改写会污染 pack 对象 | 复现：`{...pack.state}.flags.x=1` → `pack.state.flags=={"x":1}` | 产品官 #11 |
| 19 | 🟡 P2 | 输入容错 | `run/runtime.js:405-407` | `--input` 解析**静默容错**：`split(',').filter(Boolean)` 丢空 token、`parseInt` 截断小数 ⇒ 索引与决策点**错位**，错误延后暴露 | C6 `" 1 , , 2 "` → 静默丢 token；C8 `1.5` → 静默当 `1` | QA #9 |
| 20 | 🟡 P2 | 测试可信度 | `run/e2e_scale.js:80-81,90,91-92`；`run/runtime.js:59-63 vs :303-307` | ① `e2e_scale.js` 内 **2 条断言重复**（80-81 与 91-92）⇒ 断言数虚高；② `isEnding` **定义两遍**；③ 断言依赖精确字符串 `'resolved == 1'`，生成器改空格即断 | 源码逐行对照；QA 实测断言数为 **34**（2 pack × 17），非简报所称 24 | 产品官 #12/#13 + QA #12 |
| 21 | 🟡 P2 | 注入面 | `gen/prose.py:463-464` | 对模板做 `str.format(**slots)` 且 `except` **未覆盖 `AttributeError`/`ValueError`** ⇒ ① `{char.__class__.__mro__}` 把对象内省渲染进正文；② `{char.nope}` / `{char:bad^spec}` **未捕获直接崩掉整个生成器** | PoC 实跑：`{char.__class__.__mro__}` → `(<class 'str'>, <class 'object'>)`；`{char.nope}` → `AttributeError … 是否捕获: 否` | 安全 F-07 |
| 22 | 🟡 P2 | 供应链·自相矛盾 | `scripts/convert-dse.mjs:34`；`README.md:19` vs `:292` | 转换器用 **`await import()` 真加载执行**复制来的 ESM（内容即代码，无哈希校验）；而 README 一处把它列为项目组件、另一处又宣称「绝不把生成内容当 `.js` 导入」——**同文档自相矛盾** | 同构 PoC：被 import 模块顶层代码立即执行并落盘；`reference/dse/wuxia.js:2` 自注「加载即执行」 | 安全 F-06 + 产品官 |
| 23 | 🟡 P2 | 交付卫生 | `reference/novel-full/**`；`README.md:44-50` | 未在 README 声明的 vendored 子树（**49.8–56.4MB**），含 7 个真实 `engine/*.py`（`beat_orchestrator.py` 还 import 不存在的 `.voice_engine`）、**1.15MB `.bak_20260811_224131` 备份**；README 文件结构**遗漏**它却列了死模块 `gen/world.py` | `reference` 实测 56,421,033 bytes；py=7；`.bak` 1,153,504 bytes | 产品官 #9 + 安全 F-08 |
| 24 | 🟡 P2 | 可追溯性 | 仓库根 | **非 git 仓库 + 无 `.gitignore` + 无 lockfile/哈希清单**；`packs/`（生成产物）、`saves/`（运行态）、`.workbuddy/memory/` 与源码同目录且无 ignore 规则 | 主理人复核：`git rev-parse --is-inside-work-tree` → `fatal: not a git repository`；`.gitignore` `exists=False` | 三方一致 |
| 25 | 🟢 P3 | 可移植性 | `tests/e2e.mjs:30` | Node 路径硬编码机器绝对路径，本机仅因 `-2` 是 junction→`-3` 侥幸可用；Python 侧有 fallback 列表，**Node 侧没有** | `Test-Path` → `-2` 为 Junction target `…22.22.2-3`；`.workbuddy/…/memory.md:10` 写的是 `-3`，与代码 `-2` 不一致 | 产品官 #7 |
| 26 | 🟢 P3 | 组织 | `measure_prose.py`（根目录） | 开发期测量脚本散落根目录，README 与 npm scripts 均未收录（自述 "Task #16 复测 v2"）。**定性**：属**可运行的 dev 脚本，非死码**（与 #17 的 `gen/world.py` 性质不同，勿合并处理） | 文件存在于根目录，无任何引用 | 产品官 #8（含定性补正） |
| 27 | 🟢 P3 | 交付卫生·发布排除 | `.workbuddy/`（含 `memory/` 与 `automations/…/memory.md`） | 含**本机绝对路径与自动化调度记录**，随源码树混放。**主理人复核：已确认无凭证泄漏**（凭据存放在 `~/.workbuddy/` 而非项目内）；但对外发布时应排除 | 目录内 `automations/72e6b4ca-…/memory.md` 记录了 node 绝对路径与执行流水 | 安全 Info + 主理人复核 |
| 27 | 🟢 P3 | 一致性 | `gen/generate.py:42` vs `banks.py:15` | ① 同包混用两套插值（生成期 `.replace` vs 运行时 `{{var}}`）；② banks docstring「保留 ~5800 条」与 README「~3000 条」两个数，且 "~3000" 与 weapon 5966 自相矛盾 | 源码对照；实测 `sect=3012 move=1328 weapon=5966 jianghu=5273`（与 README 数值一致，仅 "~3000" 概括失真） | 产品官 #14/#16 |
| 28 | 🟢 P3 | 引擎边界 | `run/runtime.js:234-241` | `pCmp` 允许链式比较 `1<g<5` → 左结合求值成 `(1<g)<5`，语义错误（当前无包使用） | 源码阅读 | 产品官 #17 |
| 29 | 🟢 P3 | 性能 | `run/runtime.js:27-28`、`:76-104` | 加载无体积上限；lint 中 `q.shift()` 为 O(n) 搬移，整体复杂度超线性。**实测未构成 DoS**（如实降级） | V=8000/16000/32000 → 420/525/772ms；压测包 2351 场景/2MB → lint 1135–1152ms | 安全 F-10 + QA 性能基线 |
| 30 | 🟢 P3 | 路径约束 | `run/runtime.js:459-465`（`--pack`）、`gen/scale.py:307`（`--out`） | 接受任意绝对路径与 `..` 穿越，**无目录白名单/扩展名校验**（CLI 语义下属 by design，但缺单一收口） | `--pack ..\..\package.json` → 解析到 `G:\package.json`；`--pack C:\Windows\win.ini` 被读入 | 安全 F-09 + QA A4 |

**统计**：🔴 1 · 🟠 12 · 🟡 11 · 🟢 8（表格 31 条，含主理人合并与精度补正后的条目）

---

## 3. 交付与回滚预案（上线前检查专属段落）

### 3.1 阻塞项清单（Go 之前必须清零）

| # | 阻塞项 | 归属 | 判定依据 |
|---|--------|------|---------|
| B1 | `tests/e2e.mjs:30` 硬编码不存在的 Node 路径 → `npm test` 必红 | 发布入口 | `npm test` exit 1 实测；README 旗舰证据不可复现 |
| B2 | 原型污染（`setPath` 无危险键过滤）→ 可说谎的 `if` 门控 | 安全 | PoC 实跑进入不存在的 admin 分支 |
| B3 | `scene.audio` 数据驱动任意路径写文件 | 安全 | 项目外落盘 17684 字节物证（主理人已复核） |
| B4 | lint 报「0 阻断」≠ play 不崩（schema + if/do + entry 悬空） | 正确性 | 3 类崩栈 + 1 类静默跳过均已复现 |

### 3.2 回滚预案

- **本轮为只读检查，被测项目源码零改动**：三方各自核对了 14 个源文件的 mtime 与哈希，**未修改任何源码/pack**（QA 用 SHA256 前后比对证明重生成的 pack 逐字节等同原文件）。
- **唯一副作用在 `saves/`（运行态数据）**：审计期间 `saves/last.json`、`saves/endings.json` 被并发改写多次。
  - `last.json`：基线 802B → 现 797B
  - `endings.json`：基线 81B → 一度出现陌生键（`admin`/`fin`/`gateA`/`gateB`）→ 一度被清为 `{}` → 现 115B
  - **它只是游玩计数，不含业务数据，删除或保留均可**；若要还原，QA 已备份至 `_qa_tmp\saves_backup\`。
- **回滚动作**：若需恢复到检查前状态，执行 `删除 G:\local\novel-run\saves\*.json` 即可（下次 `play` 会重建）；pack 无需回滚（哈希已证明未变）。
- **环境侧**：QA 为验证 62 条断言临时创建的 `node/versions/22.22.2-2` junction **已删除并还原**（还原后 `npm test` 仍复现 exit 1）；安全卫士的自检目录与 PoC 已清理，项目内探针残留 = 0（主理人复核）。

### 3.3 建议补丁批次（供修复阶段使用，本轮未执行）

| 批次 | 内容 | 预估改动量 |
|---|---|---|
| **批次 1（阻塞）** | ① `tests/e2e.mjs:30` → `process.execPath`；② `setPath/getPath` 拒 `__proto__/constructor/prototype`；③ `sound.js` 用 `Object.hasOwn(CUES,cue)` + `path.basename()` 白名单 | ≈ 10 行 |
| **批次 2（一致性）** | ④ `loadPack()` 增 schema 校验、`meta.entry` 悬空升为**阻断**；⑤ lint 增 `if` 语法 / `choice.goto` 必填 / `unsafe_path` 检查；⑥ `reachesEnding` 计入 `if` 门控；⑦ 死局改为非零退出且不计结局 | ≈ 30 行 |
| **批次 3（声明与卫生）** | ⑧ `npm run play` 输入改成可通关或改指 `wuxia.json`；⑨ 默认 pack 改 `scale-pack.json` + `loadPack` 以仓库为基准；⑩ hook 过滤补 URL/广告词正则并订正 README「0.00% 垃圾」；⑪ README 第 6/8 步补 PowerShell 写法；⑫ 自动化恢复 ACTIVE 或 README 改述；⑬ 补 `LICENSE` + `reference/PROVENANCE.md`；⑭ `git init` + `.gitignore`；⑮ `gen/world.py` 删除或在 README 标注未接线；⑯ `prose.py` 模板占位符白名单 + `except` 扩宽 | ≈ 80 行 + 文档 |

> 注：批次 3 涉及的 README 订正（①声明取证 ②文件结构 ③安全措辞三块）已由产品官产出改写稿要点，作为**修复阶段的建议稿**归档，**本轮不落地**（上线前检查约定只诊断不改文件）。

**批次 3 · README 订正建议稿要点（产品官产出，仅归档）**

| 块 | 目标位置 | 要点 |
|---|---|---|
| 1 | `README.md:8-9` | **删除**「安全性反而因惰性数据而收敛」这一整体断言——它被 F-06（`scripts/convert-dse.mjs:34` 真 `await import()` 执行复制的 ESM）反向削弱，且 `README.md:19` 又把该脚本列为项目组件，属同文档自相矛盾。只保留可证事实。**可选非阻断**：在 `README.md:19` 给该脚本补半句「（真加载执行 ESM 内容，仅限可信来源）」。 |
| 2 | `README.md:292-293` | 改为：「`packs/*.json` 是**不可信输入**；`scene.audio` 可写出到**项目目录之外**已存在的目录（文件名**固定 `.wav` 后缀**）；含 `__proto__` 段的 `do`/`onEnter` 键名会命中**全局 `Object.prototype`**；运行时**不做类型/路径/体积校验**——即**数据通道 ≠ 无副作用通道**」。代码依据：`run/sound.js:57-58`、`run/runtime.js:172-181`(setPath)。**表述要求**：① 不写"任何原型链键名"（`constructor.prototype.x` 实测被遮蔽）；② `getPath` 面应写「仅从 `state`（含其原型链）**读取**，**无写入、无调用**」；③ **删除**"详见 F-01/F-02"式悬空指针（报告在仓库外、项目非 git，读者无法解析），改为自包含描述。 |
| 3 | `README.md:24-50` | 新增「规模与来源」段——`reference/` 占全仓约 **96%**（≈58.8MB），区分**运行期硬依赖**（`word_banks/**`，被 `gen/prose.py:25` 消费）与**素材留档**（`engine/*.py`、`.bak*`）；文件树补 `reference/novel-full/`、`measure_prose.py`；`gen/world.py` 标注为死模块。**防误判**：仅限 `gen/world.py` 这一个模块，**不得波及** `gen/scale.py:68` 的同名 `WorldState`（活代码，`:208` 在用）；`measure_prose.py` 应表述为"可运行的 dev 脚本"而非死码。呼应 F-08，补 `LICENSE` + `reference/` 出处标注 + `reference/dse/lint-content-notes.md:3` 的本机路径改仓库 URL+commit。 |
| — | **保留不动** | `README.md:111-112/289/293`「禁用 eval/Function」、`:61`「零依赖」——两项均经安全审计**证实成立**，无须改动。 |

---

## ✅ 行动清单（Top 5）

| # | 行动 | 负责方 | 紧急度 | 期望完成 |
|---|------|--------|--------|---------|
| 1 | `tests/e2e.mjs:30` 的 `NODE` 常量改为 `process.execPath`（或按候选列表探测），恢复 `npm test` 绿 | 全哥 | **P0** | 发版前立即（改 1 行） |
| 2 | `run/runtime.js` 的 `setPath`/`getPath` 增加段名黑名单（`__proto__`/`constructor`/`prototype`），杜绝原型污染与门控绕过 | 全哥 | **P0** | 批次 1 |
| 3 | `run/sound.js` 输出路径与文件名不得由数据决定：`Object.hasOwn(CUES,cue)` 白名单 + `path.basename()` + 固定写入 `saves/` | 全哥 | **P0** | 批次 1 |
| 4 | `loadPack()` 增 schema 校验并把 `meta.entry` 悬空升为阻断；lint 增 `if` 语法 / `choice.goto` 必填检查，使「0 阻断」=「play 不崩」 | 全哥 | **P1** | 批次 2 |
| 5 | 订正 README 四处不实声明（「0.00% 垃圾」「每小时自动化在跑」「默认包统一指向 scale-pack」「62 项断言可复现」），并补 `LICENSE` + `git init` + `.gitignore` | 全哥 | **P1** | 批次 3（若对外发布则为前置） |

其余 11 条（P2/P3）见 §2.1 表格，建议按批次 3 一并消化。

---

## 4. 修复与发布执行记录（2026-09-11 追加）

> 本节记录报告交付**之后**执行的动作（批次 1 修复 + 对外发布准备）。§1–§3 保持原样，作为修复前的检查基线。

### 4.1 批次 1 修复（已落地并验证）

| 编号 | 位置 | 改动 | 状态 |
|---|------|------|------|
| P0-1 | `tests/e2e.mjs:30` | `const NODE = process.env.NODE_BIN \|\| process.execPath`（原为硬编码的 `.../node/versions/22.22.2-2/node.exe`，该路径本机不存在） | ✅ 已修复 |
| P1-2 | `run/runtime.js`（getPath/setPath 前） | 新增 `UNSAFE_PATH_SEGMENTS` + `assertSafePath`，`getPath`/`setPath` 在入口拒绝 `__proto__` / `constructor` / `prototype` 段名 | ✅ 已修复 |
| 配套 | `run/runtime.js`（interpolate） | `k in state` → `Object.hasOwn(state, k)`，避免 `{constructor}` 渲染出原型链成员的 native code | ✅ 已修复 |
| P1-3 | `run/sound.js`（render 开头） | 增加 cue 白名单 `Object.hasOwn(CUES, key)`，未知 cue 直接跳过合成（不再拼入文件名） | ✅ 已修复 |

### 4.2 验证证据（全部实跑）

| 项 | 命令 | 结果 |
|---|---|---|
| 端到端 | `node tests/e2e.mjs` | **exit 0**，62/62 断言通过（修复前 **exit 1**） |
| 规模 e2e | `node run/e2e_scale.js` 与 `... packs/scale-4e3w.json` | 均 **exit 0**，ALL PASS |
| lint 全包 | 9 个 pack 逐个 `lint` | 全部 **exit 0 / 0 阻断**（无回归） |
| PoC 复测 | 6 项（下表） | 4 项 **FIXED** + 2 项回归 **OK** |

| PoC | 场景 | 结果 | 证据 |
|---|---|---|---|
| 1 | `onEnter:{"__proto__.hero_name":"PWNED"}` | **FIXED** | exit 1，`Error: 非法路径段 "__proto__"（禁止原型链访问）` @ `runtime.js:172`；输出不再含 `PWNED` |
| 2 | `audio:"../../../../_fix_probe/pwned"` | **FIXED** | exit 0，`[音效] … (未知 cue，跳过合成)`；项目外落盘文件数 **0** |
| 3 | `audio:"constructor"` | **FIXED** | exit 0，跳过合成；不再 `ERR_OUT_OF_RANGE` 崩溃 |
| 4 | `audio:"ambient"`（正常） | OK | 正常写出 `saves/cue-ambient.wav` |
| 5 | 正文含 `{constructor}` | **FIXED** | 原样输出 `{constructor}`，不再泄露 native code |
| 6 | 合法嵌套 `do` + `if` 门控 | OK | `gold 20 → 10`、`items.antidote` 正常写入（无回归） |

### 4.3 发布准备与仓库

- **`.gitignore`**：排除 `saves/`、`.workbuddy/`、`__pycache__/`、`*.bak*`、临时验证目录 —— 远程泄漏检查 **0**。
- **`LICENSE`**：MIT（`Copyright (c) 2026 siwpan (全哥)`）。
- **首次提交**：`89e57b6`，112 files（压缩后 9.47 MiB）。
- **Gitee**：`siwpan/novel-run` —— 按你的要求执行「**先建私有 → 推送 → 转公开**」。最终 `private=false`，**匿名可读验证通过**；远程 tree 112 blobs，与本地 HEAD 一致。
- 仓库地址：https://gitee.com/siwpan/novel-run

### 4.4 批次 1 后仍未处理（其中 #5/#6/#7 已在 §5 的批次 2 修复）

- **P1**：~~#5/#6/#7（lint 无 schema 校验、`meta.entry` 悬空被降级、`if` 门控死局检测不到）~~ → **见 §5 已修复**；#8（`npm run play` 自身 exit 3）、#9（模板 4/7 生效）、#10（hook 池 13 条垃圾）、#11（README 声明不实）、#12（合规标注）→ **已由 §5 的 PROVENANCE 部分覆盖**、#13（`saves/` 全局共享）。
- **P2/P3**：#14（默认 pack 指向已删除的 `demo-pack.json`）、#15（错误路径裸露堆栈）、#16（README 第 6/8 步 PowerShell 兼容）、#17（`gen/world.py` 死模块）、#22（`convert-dse.mjs` 真 import ESM）等。

---

## 5. 批次 2 修复 + PROVENANCE（2026-09-11 追加）

### 5.1 批次 2 改动（`run/runtime.js`，+107 / −14）

| §2.1 编号 | 改动 | 目的 |
|---|---|---|
| P1-5 | 新增 `validatePack()`：`scenes` 必须是普通对象；每场景 `choices` 必须是数组、`text`/`audio` 必须是字符串、`onEnter` 必须是对象；每个 choice 必须有字符串 `goto`、`if` 必须是字符串、`do` 必须是对象。`loadPack()` 校验失败即抛出**带问题清单的可读错误** | 此前结构非法会让 lint/play 以 `TypeError` 崩栈 |
| P1-6 | lint：`meta.entry` 悬空由 **warning 升为 error** | 此前整段「可达性 + 结局可达性」检查被静默跳过 |
| P1-5/6 | lint：新增 choice 形态 / `if` 语法 / **不安全路径**（`__proto__` / `constructor` / `prototype`）三类检查 | 使「0 阻断」等价于「play 不崩」 |
| P1-7 | lint：新增**条件死局**检测（初始 state 下所有选项的 `if` 均不满足即阻断）。**仅当** `if` 引用的根路径全部存在于初始 state 时才判定 | 避免误伤运行时才写入的标志（如 epilogue 依赖的 `resolved`） |
| P1-7 | `cmdPlay`：死局**不再计为结局**，退出码 0 → **4**，且不写 `saves/endings.json` | 修正「死局被计入 stats」 |
| — | lint 输出文案：「7 项检查」→「9 项检查」 | 与实现同步 |

### 5.2 新增 `reference/PROVENANCE.md`

标注 `reference/` 全部上游素材的来源仓库 / 上游路径 / 许可 / 核验 commit：

| 上游仓库 | 许可 | 核验 HEAD（2026-09-11） |
|---|---|---|
| `siwpan/novel`（《万界归墟》小说生成器） | **MIT** | `d33c1aeb78e47ac976e76918b63fd8190a4f965e` |
| `siwpan/dict-scene-engine`（字典场景引擎） | **MIT** | `dfd2300f9fd3720518903adbc2278b1780f39a8f` |

如实标注两项已知问题：① 词库中混有抓取网页残留（`AllRightsReserved` / 广告 / `本文版权属于` 等），本项目清洗**非 100%**，建议在**上游**清理；② `novel-full/engine/*.py` 仅为留档、不可运行。同时警示 `dse/*.js` 是**可执行 ESM**，`scripts/convert-dse.mjs` 会真 `import()` 它们，应视为 dev-only 工具。

### 5.3 验证证据（实跑）

| 项 | 结果 |
|---|---|
| 9 个 pack `lint` | 全部 **exit 0 / 0 阻断**（**epilogue 无误报**） |
| `tests/e2e.mjs` | **exit 0**，62/62 通过 |
| `e2e_scale` 默认 / `scale-4e3w` | 均 **ALL PASS** |
| 批次 2 PoC C1–C8 | **全部 FIXED** |
| 批次 2 PoC C9（误报检查） | **无误报** |

| PoC | 场景 | 结果 |
|---|---|---|
| C1 | `choices` 为字符串 | exit 1 + `结构校验失败: start: choices 必须是数组`（无 TypeError） |
| C2 | `scenes` 为数组 | exit 1 + `场景包缺少 scenes 字段（或类型不是普通对象）` |
| C3 | `entry` 悬空 | exit 1 + `[无入口]`（**原为 warning，lint exit 0**） |
| C4 | `if` 非字符串 | exit 1 + `if 必须是字符串` |
| C5 | `if: "gold @@ 10"` | exit 1 + `[if语法]`（**原 lint exit 0、直到 play 才崩**） |
| C6 | choice 缺 `goto` | exit 1 + `缺少 goto（必须是字符串）` |
| C7 | `onEnter: {"__proto__.x":1}` | exit 1 + `[不安全路径]` |
| C8 | 条件死局（`gold=0` 门控 `gold>=10`） | lint exit 1 + `[条件死局]`；play **exit 4** + `[死局]`，**endings.json 无变化** |
| C9 | epilogue 的 `resolved` 门控 | **无误报**（`resolved` 不在初始 state，检查自动跳过） |

> 说明：C8 首轮用例我自己写错了（把 `goto` 写成 `@end`，该场景被判为结局，自然不进死局分支）；修正为指向真实普通场景后通过。此过程一并计入验证记录，以防误判为"实现失效"。

### 5.4 提交与推送

- 提交 **`f2c81f5`**（2 files changed, +206 / −14）：`run/runtime.js`、`reference/PROVENANCE.md`
- 已推送：`89e57b6..f2c81f5  master -> master`；远程 HEAD 校验一致
- `packs/` **无变化** —— e2e 会重跑生成器，同 seed 产物字节一致，再次印证生成器确定性

### 5.5 批次 2 后仍未处理（其中多数已在 §6 修复）

- **P1**：~~#8~~、~~#9~~、~~#10~~、~~#11~~ → **见 §6 已修复**；**#13（`saves/` 全局共享）仍未处理**。
- **P2/P3**：~~#14（默认 pack）~~、~~#15（错误路径裸露堆栈）~~、~~#16（README PowerShell）~~、~~#17（`gen/world.py` 死模块，已在 README 标注）~~ → **见 §6**；#22（`convert-dse.mjs` 真 import ESM —— 已在 PROVENANCE 与 README 中警示，代码未改）。
- ⚠️ `reference/` 的词库抓取残留：**已在渲染层过滤**（`gen/prose.py` 正则），但**上游词库文件本身未清理**（按 PROVENANCE 建议应在上游 `siwpan/novel` 处理）。

---

## 6. 批次 3 修复与文档订正（2026-09-11 追加）

### 6.1 CLI 可用性（`run/runtime.js` / `package.json` / `run/package.json`）

| §2.1 编号 | 改动 | 效果 |
|---|---|---|
| P2-14 | 默认 pack 由已删除的 `packs/demo-pack.json` 改为 `packs/scale-pack.json` | 省略 `--pack` 不再 ENOENT；实测 `info` 输出 59 场景 |
| 新增 | `loadPack()` 以**仓库根**为基准解析 `--pack`（原先依赖 CWD） | 从任意目录调用均可解析；绝对路径仍原样生效 |
| P1-8 | `npm run play` 由 `scale-pack`（决策链需 52 输入，实测 **exit 3**）改为 `packs/wuxia.json`（4 输入通关） | `npm run play` 不再失败 |
| P2-15 | 错误信息可读化：不存在 / 为目录 / 非 JSON / 结构非法 → 一行提示；完整堆栈需 `NOVEL_RUN_DEBUG=1` | 不再裸露 Node 堆栈与本机绝对路径 |
| — | `run/package.json` 脚本路径 `../packs/…` → `packs/…` | 与新的路径基准保持一致 |

### 6.2 渲染质量（`gen/prose.py` / `measure_prose.py`）

| §2.1 编号 | 改动 | 效果 |
|---|---|---|
| P1-9 | 模板准入改为**槽位白名单校验**（`string.Formatter` 解析字段名）+ 补齐 `{auditory}`/`{adj}` 槽位；新增加载 `sense_fallbacks` 作为 `{auditory}` 词源 | `scene_frame` 由「生效 **4/7**」→「**7/7**」；未知槽位不再静默回退 |
| P1-9 | `except` 由 `(KeyError, IndexError)` 扩宽为含 `AttributeError`/`ValueError`/`TypeError` | 渲染异常不再被吞成兜底句 |
| P1-10 | hook 池 **+** 术语池补 URL/广告/版权**正则**过滤 | hook 14,536 → **14,015**；术语池 213,341 → **213,237** |
| P1-10 | `measure_prose.py` 检测器补 URL/AD 检查 | 「0.00% 垃圾」由**检测器自证口径**变为**可复现口径** |

### 6.3 验证证据（实跑）

| 项 | 结果 |
|---|---|
| 9 个 pack `lint` | 全部 **exit 0 / 0 阻断** |
| `tests/e2e.mjs` | **exit 0**，62/62 通过 |
| `e2e_scale` 默认 / `scale-4e3w` | 均 **ALL PASS** |
| `python measure_prose.py` | 3400 场景 **污染 0 / 0.00%**；`scene_frame` **7/7**；超 BMP 残留 `set()` |

| CLI 用例 | 结果 |
|---|---|
| 省略 `--pack` 的 `info` | exit 0，`"scenes": 59`（默认包生效） |
| 从 `C:/` 调用 `lint` | exit 0（路径与 CWD 无关） |
| `--pack packs/__nope__.json` | exit 1，`[错误] 场景包不存在: …`，**无堆栈** |
| `--pack packs`（目录） | exit 1，`[错误] --pack 指向的是目录而非文件: …` |
| `--pack README.md`（非 JSON） | exit 1，`[错误] 场景包不是合法 JSON（…）` |
| `NOVEL_RUN_DEBUG=1` | exit 1，**含完整堆栈** |
| 在 `run/` 目录下执行 | exit 0（脚本路径修正生效） |

| README 中新增的 PowerShell 命令 | 结果 |
|---|---|
| 真线 `$inputTrue`（52×1） | exit 0，抵达 **epilogue_true**（53 场景） |
| 暗线 `$inputDark`（49×1,2,1,1） | exit 0，抵达 **epilogue_false**（53 场景） |
| `npm run play` 等价命令 | exit 0，抵达 **ending_a** |
| 省略 `--pack` 的 `info` | exit 0，59 场景 |

### 6.4 文档订正（`README.md`）

- 文件结构补齐 `LICENSE` / `.gitignore` / `reference/PROVENANCE.md` / `reference/novel-full/` / `measure_prose.py`；`gen/world.py` 标注为**未接线**（并提示勿与 `scale.py` 的同名类混淆）。
- lint 章节 **7 项 → 9 项**（新增「入口缺失」与「可玩性三合一」）。
- 渲染质量段落改为**可复现口径**（说明检测项、4/7→7/7 的修复、以及旧「0.00%」为何属自证）。
- 「每小时自动化校验」订正为 **当前 PAUSED（未在运行）**。
- 运行章节补 **PowerShell 等价写法**（原 `$(python -c …)` 在 PowerShell 下不做命令替换）。
- 安全边界改写为**经实测复核**的版本：pack 是不可信输入 + 三处加固 + `convert-dse.mjs` 的 ESM 执行例外。
- 验证结果章节补录本轮全检修复与「已纳入版本控制（MIT）」；全文 `7 项 lint` → `9 项 lint`。

### 6.5 提交与推送

- 提交 **`18cac1d`**（10 files changed, +2430 / −2281）
- 已推送：`f2c81f5..18cac1d  master -> master`；本地 HEAD 与远程一致
- `packs/` 仅 scale 三包重新生成（场景数不变：59 / 47 / 2351，仅**文本内容**更新）；五题材包与 `wuxia-dse` 不受影响（它们不经 `prose.py`）

### 6.6 批次 3 后仍未处理

- **P1-13**：~~`saves/endings.json` 全局共享、无 pack 隔离、解析失败会静默清空后覆盖写回~~ → **见 §7 已修复**。
- **P2-22**：`convert-dse.mjs` 真 `import()` 执行 ESM —— 已在 PROVENANCE 与 README 明确警示，**代码未改**（保留原设计，标注 dev-only）。
- ⚠️ `reference/` 词库文件本身的抓取残留未清理（建议在上游 `siwpan/novel` 处理）。

---

## 7. 批次 4 修复：存档隔离 / 原子写 / 清空保护（2026-09-11 追加）

### 7.1 问题（P1-13 展开）

| 问题 | 表现 |
|---|---|
| **无隔离** | 所有 pack 共用 `saves/endings.json`，结局计数互相污染（实测出现过 `admin` / `gateA` / `fin` 等**只可能来自其他 pack** 的键） |
| **无原子性** | 读-改-写，读到写了一半的文件会解析失败 |
| **静默清零** | `catch { tally = {} }` → 一次坏读就把历史清零并**覆盖写回** |
| **共享可变状态** | 存档路径完全共享，e2e 与手工游玩互相干扰（本次全检期间被并发改写多次） |

### 7.2 改动

| 位置 | 改动 |
|---|---|
| `run/runtime.js` | 新增 `NOVEL_RUN_SAVES` 环境变量覆盖存档根（默认 `<repo>/saves`） |
| `run/runtime.js` | 新增 `packKey()`：以 pack 文件名（去扩展名、非法字符替换）作命名空间 → 存档落到 `saves/<packKey>/{last.json,endings.json}`；音效 WAV 仍写根目录 |
| `run/runtime.js` | 新增 `writeJsonAtomic()`：先写 `.tmp` 再 `rename`（同目录 rename 为原子操作） |
| `run/runtime.js` | `persist()`：按 pack 写入；计数文件 `ENOENT` 视为首次；**解析失败或结构非法时抛错并跳过写入**（打印 `[存档跳过] <原因>`），不再清空历史 |
| `run/runtime.js` | `cmdStats()`：读 `saves/<packKey>/endings.json`；损坏时打印 ⚠️ 警告并 exit 0（仅显示包内结局定义） |
| `tests/e2e.mjs` | `dseState()` 路径同步为 `saves/wuxia-dse/last.json` |
| `README.md` | 文件结构 / P2 存档说明 / 第 8 步注释改为 `saves/<pack名>/…`；新增存储细节与已知限制 |

### 7.3 验证证据（实跑；隔离用例全部走 `NOVEL_RUN_SAVES` 临时目录，未触碰真实 `saves/`）

| 项 | 结果 |
|---|---|
| 回归：`tests/e2e.mjs` | **exit 0**，62/62 通过 |
| 回归：`e2e_scale` 默认 / 4e3w | 均 **ALL PASS** |
| 回归：`lint(scale-pack)` | exit 0 / 0 阻断 |
| B1 隔离（wuxia） | `saves/wuxia/endings.json` = `{"ending_a":1}` |
| B2 隔离（wuxia-dse） | `saves/wuxia-dse/endings.json` = `{"wuxia.end-vengeance":1}` —— 两包互不干扰 |
| B3 stats 隔离 | 分别显示 `saves/wuxia/…` 与 `saves/wuxia-dse/…` |
| B4 **清空保护（非法 JSON）** | 文件写成 `{ BAD JSON` 后再 play → **文件保持原样**，输出 `[存档跳过] 计数文件损坏（…）：… —— 已跳过写入，避免清空历史` |
| B5 **清空保护（结构非法）** | 写成 `[1,2,3]` → **保持原样** |
| B6 stats 遇损坏 | exit 0 + `⚠️ 计数文件无法解析（…）` 警告，不崩 |
| B7 原子写 | 存档目录 **无 `.tmp` 残留** |
| B8 串行 10 次 | 计数 **精确 = 10**（无丢更新） |
| B9 **并发 8 进程** | 文件**合法未损坏**；计数 = 3 → 无文件锁导致的丢更新，属**已知限制**（已在 README 标注） |
| B10 旧扁平存档 | 不再被读取（stats 不显示历史陌生键） |

### 7.4 提交与推送

- 提交 **`788bb5a`**（3 files changed, +79 / −27）：`run/runtime.js`、`tests/e2e.mjs`、`README.md`
- 已推送：`18cac1d..788bb5a  master -> master`；本地 HEAD 与远程一致

### 7.5 遗留（诚实标注）

- **并发丢更新**：未引入文件锁（本地 CLI 场景性价比低），已作为**已知限制**写入 README。若将来要跑并行批量游玩，需改为 append-only 日志或加锁。
- `reference/` 词库文件本身的抓取残留仍未清理（建议在上游 `siwpan/novel` 处理）。
- 至此本报告 §2.1 的 **P0 1 条 + P1 12 条已全部处理**；剩余仅为 `convert-dse.mjs` 的 dev-only 设计保留，与上游词库清理建议。

---

## ⚠️ 待完善 / 已知局限

- **"上线"口径未定**：本报告按**最严口径（拟对外发布）**定级。若"上线"仅指本机自用/演示，则 #12（LICENSE）、#23（vendored 子树）、#24（版本控制）可降为 P2/P3；但 #1–#4 与 #5–#11 仍为必修。
- **未覆盖项（诚实标注）**：
  - 未找到把原型污染**升级为 RCE** 的攻击链（本仓库零依赖、无 `eval`/`vm`/`child_process`/网络，缺 gadget）→ 严重度维持 P1 而非 P0。
  - F-10 的 OOM 未做实跑（会损伤环境），仅代码层证据 + 复杂度实测。
  - `saves/` 并发丢失更新 24 次实测**未复现**，故只列 P3；但本次审计中的并发争用**真实发生**（同一文件被多方交替覆写）。
  - 交互式 `readline` 分支（`run/runtime.js:365-399`）未做交互用例，仅以 `--input` 覆盖。
  - 三方均未对 `reference/` 下约 56MB 词库做**逐条内容审查**，只做了污染抽样（hook 池 13 条垃圾）。
- **审计过程副作用披露**：
  - 安全卫士自查披露：其 `saves/` 备份时序做反（在首次 PoC `play` **之后**才备份），发现后用原始内容重写并校验（`last.json` 802B、`endings.json` 81B）。属流程失误，非项目问题。
  - 安全卫士的 PoC 与 QA 的 e2e **并发争用了 `saves/`**，该目录内容被交替覆写——这本身成为 #13 的实证。
  - QA 为验证 62 条断言临时创建了 Node 目录 junction，**验证后已删除并还原环境**。
- **未做修复**：按上线前检查的边界，本轮**只诊断不改代码**。所有修复建议仅为建议，未落地。

---

## 📚 成员产出索引

- **gstack-product-reviewer（产品官）**：对话内交付完整 findings 表（17 + 追补 2 条）、README 声明核验表（12 行）、Top 3 必改项；追补报告含与安全官的交叉核验对照表。临时核验产物在 `%TEMP%`。
- **gstack-security-officer（安全卫士）**：完整报告 `C:\Users\13122\WorkBuddy\2026-09-11-16-11-48\_sec_out\security-audit-report.md`；PoC 源码 `_sec_poc\`；原始输出 `_sec_out\poc_results*.txt` / `py_results.txt` / `misc.txt` / `integrity.txt`；越界写文件物证 `_sec_out\evidence-pwned-traversal.wav`（17684B，主理人已复核）。
- **gstack-qa-lead（质量门神）**：全部证据 `C:\Users\13122\WorkBuddy\2026-09-11-16-11-48\_qa_tmp\`（`main_summary.txt` / `boundary_part1-3.txt` / `cmd_run_*.txt` / `r_e2e*.txt` / `r_e2escale_*.txt` / `lint_all9.txt` / `determinism.txt` / `stress.txt` / `final_state.txt` / `env_release.txt` / `perf.txt`）；`saves/` 备份 `_qa_tmp\saves_backup\`。
- **主理人独立复核**：基线 `_baseline.txt`、物证复核 `_verify.txt`（F-02 物证存在 / 探针已清理 / 项目内 0 残留 / automation `72e6b4ca-…` = PAUSED）。

---

> 本报告由软件工坊 AI 协作生成，关键决策请由工程负责人复核。
