# novel-run 上线前安全审计报告

- **审计模式**：Comprehensive（14 阶段全执行）
- **日期**：2026-09-11
- **被审对象**：`G:\local\novel-run`（121 文件 / 58.85 MB，非 git 仓库）
- **运行时**：Node 22.22.2-3 · Python 3.14（`F:\Python314\python.exe`）
- **原则**：每条结论均配 `file:line` + 可复现实跑 PoC；只读审计，未修改任何源码文件
- **只读性证据**：14 个源文件 mtime 与审计开始时逐项一致（`_sec_out\integrity.txt`），差异仅来自 `saves/`（运行时产物，被 play/e2e 覆写，已复原为 802B/81B）

---

## 1. 核心判断

运行时的**表达式求值器本身是安全的**（`eval`/`Function` 声明经静态+动态双重证实），但**「场景包 = 惰性无害数据」这一核心安全前提不成立**：`packs/*.json` 的内容可以（a）全局污染 `Object.prototype` 并据此**绕过 `if` 门控**，（b）通过 `scene.audio` **把文件写到项目之外任意路径**。此外仓库整体存在「执行复制来的 ESM 内容」通道与许可/出处缺失问题。

**安全风险等级：🟡 中（偏高）** — 未发现 P0；2 条 🟠P1 需上线前修复；无 RCE、无网络面、无凭证泄漏。

---

## 2. 被审方安全声明核验

### 声明 A：`README.md:111-112`、`README.md:289/293`、`run/runtime.js:157`
> 「安全约束：禁用 `eval`/`Function` —— 用 tokenizer + 递归下降解析器，仅从 `state` 读取数据」

**结论：✅ 证实（高置信，静态 + 动态双证）**

| 证据类型 | 证据 |
|---|---|
| 静态 | `run/` 全目录 grep `eval\s*\(`、`new\s+Function`、`Function\s*\(`、`node:vm`、`process\.binding`、`require\s*\(`、`child_process` → **仅 1 条命中**：`run/runtime.js:117` 的 `VAR_RE.exec(t)`（正则 `exec`，非 `eval`） |
| 静态 | `run/runtime.js:16-20` 仅 5 个静态 import：`node:fs`/`node:path`/`node:url`/`node:readline/promises`/`./sound.js`；无 `node:vm`、无 `child_process`、无 `require`、无动态 `import(`（`run/` 内 `import\s*\(` 零命中，唯一出现在注释 `runtime.js:4`） |
| 静态 | 语法层无「调用表达式」：`parseExpr` 只有 `num`/`path`/`not`/`and`/`or`/`cmp` 六种节点（`runtime.js:219-292`），`evalNode` 无任何动态求值分支 |
| **动态①** | 用 `--import` 注入探针把 `globalThis.eval` / `globalThis.Function` 替换为抛错代理后跑 POC1（`_sec_poc/no-eval-guard.mjs`）：**探针未触发，exit 0**（`poc_results.txt §2c`）；同时正常包 lint 在探针下仍 exit 0（`§2d`） |
| **动态②** | 18 条逃逸表达式实跑：`process.exit(99)`、`require('fs').writeFileSync('PWNED_EXPR','x')`、`1; process.exit(99)`、`globalThis.process.exit(99)`、`constructor.constructor('return 1')()`、`import('node:fs')`、`eval('1')`、`` `${1}` ``、`constructor["constructor"]`、`gold >>>> 1`、`gold === 1`、`1\nprocess.exit(99)`、`1 && (2`、全角 `＞` — **全部 exit=1**（被 tokenizer/parser 拒绝），且副作用文件 `PWNED_EXPR` 在 4 个候选路径**均不存在**（`poc_results2.txt §D`） |

**唯一例外（非执行面，属读取面）**：`tokenizeExpr` 的 `isIdent` 把 `.` 纳入标识符字符（`runtime.js:187`），因此表达式可**读取原型链**：`if: "__proto__ != null"`、`if: "toString"` 实测 exit 0（真值判定）——只有读，无写与调用。

### 声明 B：`README.md:292`、`run/runtime.js:4`、`scripts/convert-dse.mjs:5`
> 「坚持 JSON 惰性数据通道，绝不把生成内容当 `.js` 导入，避免『内容=可执行代码』风险」

**结论：⚠️ 部分成立 —— 运行时侧成立，仓库整体与「惰性=无害」推断不成立**

| 子断言 | 结论 | 证据 |
|---|---|---|
| 运行时用 `fs` 读 JSON，不走 `import()` | ✅ 成立 | `run/runtime.js:26-33` 仅 `readFileSync(resolve(path),'utf8')` + `JSON.parse`；`run/` 无动态 import |
| 「绝不把内容当 .js 导入」在仓库整体成立 | ❌ 证伪 | `scripts/convert-dse.mjs:34` `const mod = await import(pathToFileURL(src).href)` —— **真加载执行** `reference/dse/*.js`；该文件自身注释 `reference/dse/wuxia.js:2` 亦自证「ESM 模块，加载即执行」。同构 PoC 实测：被导入模块的**顶层代码在 import 时即执行并落盘**（`poc_results2.txt §C1`，`PWNED_BY_IMPORT.txt` 由 import 直接创建） |
| 「惰性 JSON ⇒ 内容无害（无副作用）」 | ❌ 证伪 | pack 数据可全局污染 `Object.prototype` 并使 `if` 门控失效（F-01，`poc_results.txt §2b`）；可通过 `scene.audio` 越界写文件（F-02，`poc_results2.txt §A1`）。**数据通道 ≠ 无副作用通道** |

---

## 3. STRIDE 威胁建模

| 类别 | 适用性 | 威胁场景 | 对应 Finding |
|---|---|---|---|
| **Spoofing 伪装** | 弱适用 | 无身份体系（本地 CLI，无账号/会话）。但 `meta.entry`/`choice.goto` 可指向原型链成员（`constructor`/`__proto__`），被当作「合法场景」通过 `pack.scenes[cur]` 查表并呈现给用户 | F-05 |
| **Tampering 篡改** | **适用（高）** | ① `do`/`onEnter` 的点式路径 `__proto__.x` 全局改写 `Object.prototype`；② `saves/endings.json` 可被写入 `constructor` 等非预期键；③ 任意路径 `.wav` 覆写 | F-01 / F-05 / F-02 |
| **Repudiation 抵赖** | 适用（低） | 非 git 仓库、无 `.gitignore`、无哈希清单、无审计日志；`saves/*` 被每次 play 无条件覆写，无法回溯「谁在何时以哪个包跑出了什么」 | F-12 / F-11 |
| **Information Disclosure 信息泄露** | 适用（低） | ① 原型链成员被当作结局 id，其 `String()` 结果（含 native 函数源码）写入存档；② Python `str.format` 属性遍历结果写入生成正文 | F-05 / F-07 |
| **Denial of Service 拒绝服务** | 适用（低） | ① 畸形 pack 触发未捕获 `TypeError`/`RangeError`/`Error`，play 以 exit 1 崩栈；② 输入体积无上限；③ 深嵌套表达式 → RangeError（**被 `evalCond` 捕获**，不逃逸，仅 exit 1） | F-03 / F-04 / F-10 |
| **Elevation of Privilege 提权** | **适用（中）** | 原型污染 ⇒ `if` 门控绕过（实测可进入本应隐藏的「管理员分支」）；任意路径文件写入；`runtime.js` 明确支持被 import 复用（`runtime.js:479-484`），若嵌入长生命周期进程则全局污染面放大。**本仓库内未找到可升级为 RCE 的链**（无 eval/vm/child_process/网络） | F-01 / F-02 |

---

## 4. OWASP Top 10 (2021) 对照

| 条目 | 适用性 | 理由与证据 |
|---|---|---|
| **A01 Broken Access Control** | 适用（弱） | 无服务端授权概念；但存在「内容图内的访问控制」——`choice.if` 门控可被 F-01 绕过（实测进入 admin 分支，而 `isAdmin` 从未在 state 中定义）。IDOR 不适用（无对象归属概念） |
| **A02 Cryptographic Failures** | **不适用** | 无口令、无会话、无 TLS、无加解密、无随机数安全用途（`sound.js` 只做 PCM 合成）。唯一相关是内容完整性 → 归 A08 |
| **A03 Injection** | **适用** | ① 原型链路径注入（`do`/`onEnter` 键的 `__proto__.x`，`runtime.js:172-181`）；② Python format-string 注入（`gen/prose.py:463`）。**无** SQL/OS 命令注入面：Python 侧 `banks/generate/prose/scale/world` 的 AST 扫描 `risky_calls=无`（无 `eval/exec/compile/__import__/pickle/yaml/subprocess/os.system`），Node 侧无 `child_process` |
| **A04 Insecure Design** | **适用（主因）** | 信任边界「pack = 惰性数据」未在任何代码层强制：无 schema 校验、无路径收口、无体积上限、无原型链防护 |
| **A05 Security Misconfiguration** | 适用（弱） | 无默认凭证（N/A）；无 debug 端点（N/A）；实际问题是**无输入上限**（`runtime.js:27-28`）与**错误信息回显整条表达式**（`runtime.js:299`、`:212`，长表达式会造成日志放大） |
| **A06 Vulnerable & Outdated Components** | **不适用** | 「零依赖」实证成立：根 `package.json` 无 `dependencies`/`devDependencies` 字段且无 `node_modules`；`run/package.json` 仅 6 个元数据字段；Python 仅标准库（`argparse/json/os/random/sys/collections`）。保留意见：复制来的内容无版本号/哈希可核 → 归 A08 |
| **A07 Identification & Authentication Failures** | **不适用** | 无账号、认证、会话、口令恢复流程 |
| **A08 Software & Data Integrity Failures** | **适用** | ① 对复制来的 ESM 直接 `import()` 执行且无哈希/签名校验（`convert-dse.mjs:34`）；② 无 lockfile、无 SHA 清单、非 VCS；③ 存档文件可被内容键污染（`saves/endings.json` 出现 `constructor` 键） |
| **A09 Security Logging and Monitoring Failures** | 不适用（基本） | 本地 CLI，无日志采集/告警管道，无敏感数据落日志（`last.json` 只存 state/visited）。部分相关：异常直接抛栈、无结构化审计 → 已并入 A04/A05 |
| **A10 SSRF** | **不适用** | 零网络能力：不 import `http/https/net/dns/tls`，无 `fetch`，无 URL 取数逻辑（全仓 grep 无命中）。无云元数据访问面 |

---

## 5. Findings

| # | 严重度 | 类别 | 位置 | 漏洞描述 | PoC / 证据 | 修复建议 |
|---|---|---|---|---|---|---|
| **F-01** | 🟠 **P1** | A03/A04 · Tampering / EoP | `run/runtime.js:172-181`（`setPath`）、`:310-319`（`applyDo`）、调用点 `:374`、`:409` | `do`/`onEnter` 的键支持点式嵌套路径且**未过滤 `__proto__`/`constructor`/`prototype`**：`setPath(state,"__proto__.x",v)` 会走到 `cur = Object.prototype` 并把 `x` 挂到**全局原型**上。后果：① 全局原型污染；② 污染值可满足 `choice.if` 的真值判定，**绕过内容作者的门控** | 恶意包 `onEnter={"__proto__.hero_name":"PWNED-BY-PACK","__proto__.isAdmin":true}`（`_sec_poc/p1-proto-pack.json`）。静态对照：`lint` 报 `[未定义变量] start: {hero_name} 不在 state 中` + `{isAdmin} 不在 state 中`，exit 1（`poc_results.txt §2a`）→ 证明二者**确实不在 state**；实跑 `play --input 2`：输出 `文本插值: PWNED-BY-PACK / 继承判定: true`，并**抵达 admin 分支**（`[结局] 抵达 admin`），exit 0（`§2b`） | 在 `setPath`/`getPath` 逐段校验：段名命中 `__proto__|constructor|prototype` 即抛错拒绝（或用 `Object.hasOwn` 只允许已声明键）；更彻底：`state` 用 `Object.create(null)` 承载；另加 `Object.freeze(Object.prototype)` 启动自检 |
| **F-02** | 🟠 **P1** | A01/A04 · Tampering / EoP | `run/sound.js:58`（`resolve(dir, \`cue-${cue}.wav\`)`）、`:68`（`play(cue,…)`）、数据源 `run/runtime.js:378` | `scene.audio` 来自**不可信 pack**，未经消毒即拼进文件名，`resolve()` 会规范化 `..` → **可写到项目之外任意已存在目录**（文件名固定 `.wav` 后缀）。等于「惰性数据包具备任意路径写入副作用」，直接违反 README 安全声明 | `audio="../../../../_sec_probe/pwned"`（`_sec_poc/p2b-audio-traversal-pack.json`）实跑：`[音效] ../../../../_sec_probe/pwned → G:\local\_sec_probe\pwned.wav`，**文件确被创建，17684 bytes，位于被审项目之外**（`poc_results2.txt §A1`；物证副本 `_sec_out\evidence-pwned-traversal.wav`）。纯路径推导同证：`§A2` 输出 `G:\local\_sec_probe\pwned.wav` | `render()` 禁止由数据决定文件名：先用 `Object.hasOwn(CUES, cue)` 白名单校验，再 `path.basename()` 且只允许 `[a-z]+`；输出路径固定为 `saves/` 下的映射表，禁止接受任意 cue 串 |
| **F-03** | 🟠 **P1** | A04/A05 · DoS | `run/sound.js:33`（`const cfg = CUES[cue] ?? {...}`）、`:35-36` | `CUES[cue]` 是普通对象属性查找，**走原型链**：`audio="constructor"` 取到 `Object` 构造器 → `cfg.freq`/`cfg.dur` 为 `undefined` → `n = Math.floor(sr*undefined) = NaN` → `Buffer.alloc(NaN)` 抛 `ERR_OUT_OF_RANGE`，且该行在 `try`（`:56` 起）之外 → **未捕获，play 异常终止**。`"__proto__"`/`"toString"` 同理 | `audio="constructor"`（`_sec_poc/p6-audio-constructor-pack.json`）实跑：`RangeError [ERR_OUT_OF_RANGE]: … Received NaN`，栈顶 `at render (sound.js:36:23)`，exit 1（`poc_results.txt §4f`） | 改为 `Object.hasOwn(CUES, cue) ? CUES[cue] : DEFAULT`；并把 `Buffer.alloc` 纳入 `try`；对 `cue` 做强类型校验（`typeof cue === 'string'`） |
| **F-04** | 🟡 **P2** | A04/A05 · Tampering | `run/runtime.js:26-33`（`loadPack` 只校验 `scenes` 是对象）、`:58`/`:69`/`:306`（无类型守卫）、`:49-149`（lint 不校验 `if`/`do`）、`:294-301` | **无 schema/类型校验**，且 `lint` 宣称的「7 项检查」**不覆盖 `if`/`do` 表达式与字段类型**。后果：`lint` 报「0 阻断问题」的包在 `play` 时崩溃 —— 发布门槛证据链断裂 | ① `{"choices":"abc"}` → `lint` exit 1 `TypeError: (sc.choices ?? []).map is not a function @ runtime.js:58`（`§4c`）；`play` exit 1 `TypeError: scene.choices.every is not a function @ :306`（`§4d`）。② `{"goto":5}` → `lint` exit 1 `TypeError: g.startsWith is not a function @ :69`（`§4e`）。③ `{"if":123}` → `lint` **exit 0「0 阻断问题」**（`§4b`）但 `play` exit 1 `Error: if 条件求值失败 "123": 条件表达式意外结束 @ :299`（`§4a`） | 引入显式 schema 校验（`scenes` 对象、`choices` 数组、`goto` 字符串、`text` 字符串、`if` 字符串、`do` 值为 string/number/bool/null、`audio` 字符串），失败即阻断加载；把 `if`/`do` 的语法与类型校验并入 `lint`，使「0 阻断问题」等价于「play 不崩」 |
| **F-05** | 🟡 **P2** | A01/A09 · Info Disclosure / Tampering | `run/runtime.js:371`（`pack.scenes[cur]`）、`:442`（`Object.entries` 后按 id 取）、`:430`、`:432`（`tally[ending]`） | 场景查表用**原型链可达**的普通对象索引，`cur` 又来自不可信 `goto`/`meta.entry`：指向 `__proto__`/`constructor` 时被判定为「存在的场景/结局」，其 `String()`（含 native 函数源码）被写入存档；且 `persist` 直接以结局 id 作 `tally` 键 | ① `goto:"__proto__"` → `play` exit 0，输出 `# __proto__` 与 `[结局] 抵达 __proto__`，存档行 `结局计数 __proto__ = [object Object]`（`poc_results2.txt §B1`）。② `meta.entry:"constructor"` → `play` exit 0，`[结局] 抵达 constructor`，**`saves/endings.json` 被写入 `"constructor": "function Object() { [native code] }1"`**（`§B3` + `poc_results3.txt` 末段） | 用 `Object.hasOwn(pack.scenes, cur)` 判定存在性；`tally` 用 `Object.create(null)`；对 `ending` 做 id 白名单校验（仅允许 `[a-z0-9_.-]`）后再写盘 |
| **F-06** | 🟡 **P2** | A08 · Tampering / EoP | `scripts/convert-dse.mjs:34`（`await import(pathToFileURL(src).href)`）、`:49-53`（src 硬编码 `reference/dse/wuxia.js`） | 转换器**真加载执行**复制来的 ESM 内容（「内容即代码」），且对 `reference/dse/*.js` **无哈希/签名/来源校验**。风险窗口＝任何一次「从上游重新复制/更新」`reference/` 的动作；README 的「绝不把内容当 .js 导入」在此被绕过 | 语义 PoC（与项目脚本逐行同构、仅改路径）：`_sec_poc/convert-dse-copy.mjs` + `_sec_poc/evil-content-pack.js` 实跑 → 顶层代码执行、`PWNED_BY_IMPORT.txt` 由 import 直接落盘（`poc_results2.txt §C1`）。`reference/dse/wuxia.js:2` 注释自证「加载即执行」 | 将该脚本标注为 dev-only 并移出发布物；对 `reference/dse/*.js` 建 SHA-256 白名单校验（不匹配即拒绝执行）；或改为纯文本解析（不用 `import()`） |
| **F-07** | 🟡 **P2** | A03 · Info Disclosure / DoS | `gen/prose.py:463`（`self.rng.choice(self.scene_frame).format(**slots)`）、`:464`（`except (KeyError, IndexError)`）、`:347-348`（模板准入条件仅要求含 `{`、`}`） | 对**内置/抓取模板**做 `str.format` 且有未覆盖的异常类型：① `{char.__class__.__mro__}` 之类**属性遍历**将对象内省结果渲染进正文（注入）；② `{char.nope}` → `AttributeError`、`{char:bad^spec}` → `ValueError` **均未被捕获** → 整个生成器崩栈；③ 模板准入过宽，任何含 `{...}` 的抓取碎片都会进入渲染面 | `_sec_poc/py-poc.py` 实跑（`py_results.txt §1`）：`{char.__class__.__mro__}` → `(<class 'str'>, <class 'object'>)`（泄漏成立）；`{char.nope}` → `AttributeError: 'str' object has no attribute 'nope'  <== prose.py:464 是否捕获: 否`；`{char:bad^spec}` → `ValueError … 否`。`§0` 证实真实 `scene_frame.json` 的 10 条模板中 7 条通过准入过滤 | 模板准入改为**白名单占位符**：只接受 `slots` 已知键的 `{key}` 形（用 `string.Formatter().parse()` 校验 field_name ∈ slots 且无 `!`/`:`/`.`/`[`）；`except` 扩为 `except (KeyError, IndexError, AttributeError, ValueError, TypeError)`；对模板做一次加载期 dry-run |
| **F-08** | 🟡 **P2** | 合规 / 供应链 | `package.json:25`（`"license":"MIT"`）、`:26-30`（author/repository）、`reference/**`、`reference/dse/lint-content-notes.md:3` | ① 声明 MIT 但**仓库无 `LICENSE` 文件**（亦无 `NOTICE`）；② 复制进来的第三方内容（`reference/novel-full` 49.8 MB / 73 文件、`reference/novel` 6.5 MB、`reference/dse/*.js`）**无许可与出处标注**；③ 抓取文本中混有 `本文版权属于` / `未经许可` / `此内容版权归` 等版权痕迹；④ `repository` 指向 `https://gitee.com/siwpan/allin`，与项目名/内容不对应（provenance 不一致） | `_sec_out\misc.txt`（LICENSE/NOTICE/.gitignore 全 `exists=False`）；`misc.txt` 体积统计；`reference/dse/lint-content-notes.md:3` 标注来源为外部路径 `G:/local/run_and_run/dict-scene-engine/scripts/lint-content.mjs`；grep `版权|来源|许可` 命中 `reference/novel/infinite_flow_terms.json:14488`（`此内容版权归`）、`wuxia_terms.json:5479`（`本文版权属于`）、`:6103`（`未经许可`） | 补齐 `LICENSE`；对 `reference/` 逐目录加 `PROVENANCE.md`（来源 URL/commit/许可）；把纯抓取噪声词库移出发布物或仅保留清洗后子集；确认 MIT 声明对复制内容是否具备分发权 |
| **F-09** | 🟢 P3 | A04 | `run/runtime.js:26-33`、`:459-465`（`--pack`）、`gen/scale.py:307`（`--out`） | `--pack`/`--out` 接受任意绝对路径与 `..` 穿越，**无目录白名单/扩展名校验**。CLI 语义下属 by design，但项目缺少单一收口点：读（pack）与写（saves/audio）各自为政，任意一条被上游自动化拼装即失控 | `poc_results.txt §6a`：`--pack <项目外绝对路径>` exit 0 并完整回显包内容；`§6b`：6 级 `..` 穿越 exit 0；`§6c`：`--pack C:\Windows\win.ini` 能读到文件（`SyntaxError … is not valid JSON` 证明已读取内容） | 提供 `--pack-dir` 收口或默认限定 `packs/`；对 `--out`/`--pack` 做 `path.resolve` 后前缀校验；文档明确「pack 是不可信输入」 |
| **F-10** | 🟢 P3 | A05 | `run/runtime.js:27-28`（全量读入 + `JSON.parse`）、`:76-104`（BFS 用 `q.shift()`） | ① 加载无体积上限：`readFileSync` 全量入内存再 `JSON.parse`，超大 pack ⇒ OOM；② `lint` 复杂度超线性（每场景一次 BFS + `Array#shift` 的 O(n) 搬移） | 实测复杂度：`poc_results.txt §7`（`scale-stress` 2351 场景 / 2.0 MB → lint 1135 ms）；`poc_results2.txt §E` 高扇出图 V=8000/16000/32000 → **420 / 525 / 772 ms**（单次约 +2 倍规模 → +1.4x 时间，常数项主导，**未构成实际 DoS**）。结论：如实标注为低危，不夸大 | 加载前 `statSync` 校验大小上限（如 64 MB）并给出明确报错；把 BFS 的 `q.shift()` 换成索引游标（`for (let i=0;i<q.length;i++)`）以消除 O(n²) |
| **F-11** | 🟢 P3 | A08/A09 | `run/runtime.js:427-431`（读-改-写 `endings.json` 无锁）、`tests/e2e.mjs:104`（`dseState()` 读 `saves/last.json` 作断言源） | `endings.json` 的读-改-写非原子（经典 lost update）；更现实的问题是 `saves/` 是**全局共享可变状态**，e2e 断言直接依赖它 → 并发/重复运行互相干扰 | 24 次并发 play 实测 **合计 24 / 期望 24 / 丢失 0，未复现**（`poc_results3.txt`），故降级为 P3。但共享文件冲突在本次审计中**实际发生**：我的 PoC `play` 与 QA 的 e2e 并发交替覆写 `saves/`，导致我的一次快照恢复动作失效（见 §7 说明） | 计数写入改为「读-改-写 + 唯一临时文件原子 rename」或直接追加式日志（append-only）；e2e 断言改用临时隔离目录（如 `--saves-dir` 指向 tmp），避免测试依赖仓库内共享文件 |
| **F-12** | 🟢 P3 | A08 · Repudiation | 仓库根（无 `.git`、无 `.gitignore`、无 lockfile/哈希清单） | 非版本控制仓库 ⇒ 无审计轨迹、无法检测复制内容（`reference/**`）被替换、无法定位「哪次改动引入了哪条内容」；MIT 声明与发布物也不可追溯 | `_sec_out\misc.txt`：`.git` / `.gitignore` / `package-lock.json` / `requirements.txt` 均 `exists=False` | 上线前 `git init` 并提交基线；为 `reference/**` 生成 SHA-256 清单纳入仓库；补 `.gitignore`（`saves/`、`__pycache__`、临时产物） |
| **F-13** | ℹ️ Info | 质量/QA（非安全） | `gen/prose.py:347-348`、`:443-465`；数据 `reference/novel-full/word_banks/templates/scene_frame.json` | 模板系统**静默半失效**：10 条模板中 7 条通过「含 `{`/`}`」准入，但其中 3 条使用 `slots` 中**不存在**的 `{auditory}`/`{adj}` → 每次都 `KeyError` 被 `:464` 吞掉并回退到兜底句 ⇒ 实际生效模板仅 **4/7** | `py_results.txt §0` 逐条列出模板并通过 `slots` 键比对（`slots` 定义于 `prose.py:444-461`，无 `auditory`/`adj`） | 补齐 `slots` 的 `auditory`/`adj` 映射，或清理这 3 条模板；加载期对每条模板做 dry-run 并统计命中率（把静默回退变成显式告警） |

### 严重度统计
🔴 P0 = **0** · 🟠 P1 = **3**（F-01/F-02/F-03） · 🟡 P2 = **5**（F-04~F-08） · 🟢 P3 = **4**（F-09~F-12） · ℹ️ Info = 1（F-13）
**综合评级：🟡 中偏高（C+）** —— 无 P0、无 RCE、无网络面、无凭证泄漏；但 3 条 P1 均有可复现实跑 PoC，且集中在「不可信 pack 输入」这一核心信任边界上。

---

## 6. Top 3 必改项（上线前）

1. **给路径求值加原型链防护（F-01，最高优先）** — `runtime.js:172-181` 的 `setPath`/`getPath` 拒绝 `__proto__|constructor|prototype` 段名，或让 `state` 用 `Object.create(null)`。当前状态：一个 pack 文件即可全局改写 `Object.prototype` 并绕过 `if` 门控，这是「内容=惰性数据」这一安全前提的直接反例。
2. **斩断 `scene.audio` → 文件名的数据流（F-02 + F-03）** — `sound.js:58` 不得由数据决定输出路径；`sound.js:33` 改用 `Object.hasOwn(CUES, cue)`。当前状态：项目外的任意已存在目录可被写入 `.wav`（已实测写出 17684 字节物证），且 `audio:"constructor"` 可让进程异常终止。
3. **补 pack schema 校验，并让 `lint` 覆盖 `if`/`do`（F-04）** — 使「0 阻断问题」真正等价于「play 不崩」。当前状态：`lint` exit 0 的包在 `play` 时以 `Error`/`TypeError`/`RangeError` 崩栈（3 类均已复现），发布门槛形同虚设。

**附加（低成本高收益）**：`scripts/convert-dse.mjs` 标注 dev-only + 对 `reference/dse/*.js` 做 SHA-256 白名单（F-06）；`gen/prose.py` 模板改为白名单占位符校验并扩宽 `except`（F-07）；补 `LICENSE` 与 `reference/` 出处标注（F-08）。

---

## 7. 审计过程与取证说明（可复核）

**证据产物目录**：`C:\Users\13122\WorkBuddy\2026-09-11-16-11-48\`
- `_sec_out\poc_results.txt` — 批次①：声明核验 lint/探针、类型未校验、表达式逃逸 24 例、`--pack` 任意路径、lint 复杂度
- `_sec_out\poc_results2.txt` — 批次②：路径穿越写文件、`goto`/`entry` 原型链、供应链 `import()` 执行、副作用文件核查、复杂度缩放
- `_sec_out\poc_results3.txt` — 批次③：并发计数、存档键污染
- `_sec_out\py_results.txt` — Python 侧：format-string 注入、模板准入、AST 依赖/危险调用扫描
- `_sec_out\misc.txt` — 零依赖核验、LICENSE/体积统计、引用关系
- `_sec_out\integrity.txt` — 源文件 mtime 对照（证明只读）
- `_sec_out\evidence-pwned-traversal.wav` — F-02 越界写入物证副本（17684 B）
- `_sec_poc\` — 全部 PoC 源码（可重跑）：`drive.ps1`/`drive2.ps1`/`drive3.ps1`、`jsonparse-proto.mjs`、`gen-expr-packs.mjs`、`no-eval-guard.mjs`、`convert-dse-copy.mjs`、`evil-content-pack.js`、`make-scale-pack.mjs`、`py-poc.py`、`p1..p8*.json`、`expr/`、`scale/`

**只读性与副作用声明（如实披露）**：
- 14 个源文件 mtime 与审计开始时**逐项一致**，未修改任何源码（`integrity.txt`）。
- 为跑通 PoC 必须实际调用 `play`，而 `play` 会写 `saves/last.json`、`saves/endings.json` 并重生成 `cue-*.wav`。审计开始时实测：`last.json`=802 B、`endings.json`=81 B（4 键）。
- **一次操作失误已披露**：我的 `saves/` 备份是在首次 PoC `play` **之后**才执行的，因此该备份并非原始状态；随后一次「恢复」误将后置快照写回。发现后已用原始内容重写并校验：`last.json`=**802 B**、`endings.json`=**81 B**，与审计开始时字节数一致（`_sec_out\restore.txt`）。
- **并发干扰**：审计期间 QA 同学正在跑 e2e，二者同时写 `saves/`，该目录内容在数分钟内被交替覆写（`integrity.txt` 记录到 mtime 16:22 的再次变更）。项目总字节较初始 +876 B，**全部来自 `saves/`**，其余 120 文件未变。此现象本身即 F-11 的实证。
- 项目内未残留任何临时文件：`PWNED_EXPR` / `PWNED_BY_IMPORT.txt` / `_sec_probe` / `out` / `evil-pack.json` 命中均为 0 处（`integrity.txt`）。
- 项目外的探针目录 `G:\local\_sec_probe\` 已删除（物证副本保留在 `_sec_out\`）。

**未覆盖 / 未能证实的部分（诚实标注）**：
- 未找到可将原型污染升级为 **RCE** 的攻击链（本仓库无 `eval`/`vm`/`child_process`/网络模块、零依赖，缺少可用 gadget）；若 `runtime.js` 未来被嵌入长生命周期进程，需重新评估。
- F-10 的 OOM 未做实跑（会损伤环境），仅有代码层证据 + 复杂度实测，置信度 5。
- F-11 的并发丢失更新 **24 次并发实测未复现**，置信度 4，故只列 P3。
- 用户交互式 `readline` 路径（`runtime.js:365-399`）未做交互式用例，仅以 `--input` 覆盖；该分支另有 `parseInt` 容错（`:405-407`），未见注入面。
