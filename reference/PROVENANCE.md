# reference/ 来源与许可说明（PROVENANCE）

本目录存放 novel-run 集成验证所需的**外部参考素材**。这些文件**不是本仓库原创内容**，
而是从下列上游仓库复制/摘录（并做必要裁剪）而来。本文件用于标注来源、许可与已知问题。

> 两个上游仓库均为本项目作者（全哥 / siwpan）本人所有，且均为 **MIT 许可**，与本仓库许可兼容。

---

## 1. 来源清单

| 本地路径 | 来源仓库 | 上游路径 | 许可 | 在本项目中的作用 |
|---|---|---|---|---|
| `novel/*.json` | https://gitee.com/siwpan/novel | `novel_generator/word_banks/**` 的 6 个文件（`wuxia_terms` / `cultivation_terms` / `infinite_flow_terms` / `lowmagic_medieval_terms` / `names` / `hook_templates`） | MIT | 五题材词库素材（由 `gen/banks.py` 加载并清洗） |
| `novel-full/word_banks/**` | https://gitee.com/siwpan/novel | `novel_generator/word_banks/**`（全量，73 个文件） | MIT | **运行期硬依赖**：`gen/prose.py` 直接消费，用于散文渲染 |
| `novel-full/engine/*.py` | https://gitee.com/siwpan/novel | `novel_generator/engine/*.py` | MIT | 仅作**留档参考**，本项目不导入（详见 §4-2） |
| `dse/*.js` | https://gitee.com/siwpan/dict-scene-engine | `content/wuxia.js`、`content/changan.js`、`content/river.js` | MIT | 真实 DSE 内容包样例，供 `scripts/convert-dse.mjs` 转为惰性 JSON |
| `dse/lint-content-notes.md` | https://gitee.com/siwpan/dict-scene-engine | `scripts/lint-content.mjs` 的摘录说明 | MIT | `run/runtime.js` 的 7 项 lint 移植依据 |

> ⚠️ **`dse/*.js` 是可执行 ESM 模块**：上游 README 对 `content/` 明确标注
> 「⚠️ 可执行 ESM 模块，只装可信来源」。本仓库 `scripts/convert-dse.mjs` 会
> `await import()` **真正加载执行**它们——因此**切勿**把这些文件替换为来源不明的版本。
> 该脚本应视为 dev-only 工具，不要在不可信输入下运行。

**不在本目录、但同属外部输入的内容**：

- `corpus/*.json`：由本项目**联网搜索后自行整理**的题材语料（武侠门派 / 唐长安坊市 / 修仙境界 /
  主神空间 / 骑士教会黑死病），**非**复制自上游仓库。
- `packs/*.json`：本项目生成器的**产出物**，不是复制内容（可由 `npm run gen` 复现，同 seed 字节一致）。

---

## 2. 版本核验

内容复制于 **2026-09-10**。上游未以 submodule / lockfile 固定版本，故记录核验时的 HEAD 作为参考：

| 上游仓库 | 核验日期 | HEAD commit（核验时） |
|---|---|---|
| `siwpan/novel` | 2026-09-11 | `d33c1aeb78e47ac976e76918b63fd8190a4f965e` |
| `siwpan/dict-scene-engine` | 2026-09-11 | `dfd2300f9fd3720518903adbc2278b1780f39a8f` |

**局限（如实标注）**：复制动作发生在 2026-09-10，上表为 2026-09-11 的核验值。若上游在此期间
有新提交，`reference/` 的实际内容与上表 commit 可能不完全对应。**如需精确复现，请以本仓库
对应提交的文件哈希为准。**

---

## 3. 许可

| 主体 | 许可 | 依据 |
|---|---|---|
| 上游 `siwpan/novel` | **MIT** | 仓库 `LICENSE`：`Copyright (c) 2025 novel-generator contributors` |
| 上游 `siwpan/dict-scene-engine` | **MIT** | `package.json` → `"license": "MIT"`，`"author": "全哥 (siwpan)"` |
| 本仓库 `novel-run` | **MIT** | 根目录 `LICENSE`：`Copyright (c) 2026 siwpan (全哥)` |

MIT 允许再分发与演绎，**前提是保留版权与许可声明**。本文件即承担该声明作用；如需进一步
分发 `reference/` 下的内容，请一并保留本文件以及上游各自的 `LICENSE`。

---

## 4. 已知内容问题（如实标注，未美化）

1. **词库中混有抓取网页残留**：上游词库由联网抓取扩充，部分条目含网页正文碎片、广告与版权文本。
   实测样例（分布于 `novel/*.json` 与 `novel-full/word_banks/narrative/hook_templates.json`）：

   - `广告投放：www.oceanengine.com`
   - `2006-2022www.17k.comAllRightsReserved…`
   - `本文版权属于…` / `未经许可…`

   本项目 `gen/banks.py` 会在**加载时清洗**（丢弃含功能字、超长、疑广告/URL 的条目），
   但**清洗不是 100%**——离线审计仍在上游 hook 池中检出 13 条残留。**若要对外分发词库本身，
   建议先在上游 `siwpan/novel` 清理，而不是在本仓库打补丁。**

2. **`novel-full/engine/*.py` 不可直接运行**：仅为留档；其中 `beat_orchestrator.py` 引用了
   上游存在、此处未复制的 `.voice_engine` 模块。本项目运行时**不导入**这些文件。

3. **`.backup_originals/*.bak_*`**（词库清洗前的原始副本，约 1.15 MB）**未纳入本仓库**，
   已由根目录 `.gitignore` 排除。

---

## 5. 如何重新同步（可选）

> 以下为类 Unix shell 示例，Windows 下请用等价命令（`xcopy` / `robocopy` 或 PowerShell `Copy-Item`）。

```bash
# —— 词库（novel 侧）——
git clone https://gitee.com/siwpan/novel.git /tmp/novel
cp -r /tmp/novel/novel_generator/word_banks/. reference/novel-full/word_banks/

# —— 内容包（DSE 侧）——
git clone https://gitee.com/siwpan/dict-scene-engine.git /tmp/dse
cp /tmp/dse/content/wuxia.js   reference/dse/
cp /tmp/dse/content/changan.js reference/dse/
cp /tmp/dse/content/river.js   reference/dse/

# —— 重新转换为惰性 JSON（会执行上面的 ESM，确保来源可信）——
node scripts/convert-dse.mjs
```

同步完成后，请更新 §2 的 commit 表与核验日期。

---

## 6. 变更记录

| 日期 | 变更 |
|---|---|
| 2026-09-11 | 首次创建本文件；补录两个上游仓库的来源、许可（均 MIT）与核验 commit；标注词库抓取残留与 engine 留档不可运行两项已知问题。 |

---

> 本文件随 `reference/` 目录一并分发，用于满足 MIT 的版权与许可保留要求。
