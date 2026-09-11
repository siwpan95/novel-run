#!/usr/bin/env node
// 场景运行时（对应 DSE 的 scenes/state/engine 插件，但**只加载惰性 JSON 数据**）。
//
// P0：JSON 惰性加载器（用 fs 读 JSON，不走 import() —— 与 DSE 的 ESM 内容包不同，
//     机器生成内容作为 inert data，反而收敛了安全面）
// P1：状态插值 {var} + 进入场景触发 audio 音效标记
// P2：分支 choices 驱动 → 多结局抵达 → 存档 + 结局统计
//
// CLI（--pack 省略时默认 packs/scale-pack.json；路径以仓库根为基准）：
//   node runtime.js info                       # 只读查询
//   node runtime.js scenes
//   node runtime.js lint
//   node runtime.js play --input "1,1,1,1"
//   node runtime.js stats                      # N 路结局跨游玩统计

import { readFileSync, writeFileSync, mkdirSync, renameSync } from 'node:fs'
import { resolve, dirname, basename } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createInterface } from 'node:readline/promises'
import { sound } from './sound.js'

const __dirname = dirname(fileURLToPath(import.meta.url))

// 存档根目录：默认 <repo>/saves；可用 NOVEL_RUN_SAVES 覆盖（便于测试/CI 隔离）。
// 各 pack 的存档按 pack 名隔离到子目录（见 savesDir），音效 WAV 仍写在根目录。
const SAVES = process.env.NOVEL_RUN_SAVES
  ? resolve(process.env.NOVEL_RUN_SAVES)
  : resolve(__dirname, '..', 'saves')

// ── 存档隔离与原子写 ──
// 背景：此前所有 pack 共用一个 saves/endings.json，导致
//   ① 不同 pack 的结局计数互相污染（实测出现过 admin/gateA 等陌生键）；
//   ② 读-改-写无保护，并发/重入会丢更新；
//   ③ 解析失败时 `catch { tally = {} }` 会静默把历史清零后覆盖写回。
function packKey(packPath) {
  const base = basename(String(packPath)).replace(/\.json$/i, '')
  return base.replace(/[^A-Za-z0-9._-]/g, '_') || 'default'
}

function savesDir(key) {
  return resolve(SAVES, key)
}

function writeJsonAtomic(path, obj) {
  const tmp = `${path}.tmp`
  writeFileSync(tmp, JSON.stringify(obj, null, 2))
  renameSync(tmp, path)   // 同目录 rename 为原子操作，避免写一半被读到
}

// ── P0：惰性加载（非 import） ──
// packs/*.json 是不可信输入：结构非法的包此前会让 lint/play 以 TypeError 崩栈
// （choices 为字符串 → `.map is not a function`；choice 缺 goto → `g.startsWith is not a function`）。
// 这里在加载期做一次结构校验，把「运行时崩栈」提前成「带清单的可读错误」。
const isPlainObject = (v) => v != null && typeof v === 'object' && !Array.isArray(v)

function validatePack(pack) {
  const errs = []
  for (const [id, sc] of Object.entries(pack.scenes)) {
    if (!isPlainObject(sc)) { errs.push(`${id}: 场景必须是对象`); continue }
    if (sc.choices != null && !Array.isArray(sc.choices)) errs.push(`${id}: choices 必须是数组`)
    if (sc.text != null && typeof sc.text !== 'string') errs.push(`${id}: text 必须是字符串`)
    if (sc.audio != null && typeof sc.audio !== 'string') errs.push(`${id}: audio 必须是字符串`)
    if (sc.onEnter != null && !isPlainObject(sc.onEnter)) errs.push(`${id}: onEnter 必须是对象`)
    if (!Array.isArray(sc.choices)) continue
    sc.choices.forEach((ch, i) => {
      if (!isPlainObject(ch)) { errs.push(`${id}.choices[${i}]: 选项必须是对象`); return }
      if (typeof ch.goto !== 'string' || !ch.goto) errs.push(`${id}.choices[${i}]: 缺少 goto（必须是字符串）`)
      if (ch.if != null && typeof ch.if !== 'string') errs.push(`${id}.choices[${i}]: if 必须是字符串`)
      if (ch.do != null && !isPlainObject(ch.do)) errs.push(`${id}.choices[${i}]: do 必须是对象`)
    })
  }
  return errs
}

function loadPack(path) {
  // 路径以「仓库根」为基准解析：此前的 resolve(path) 依赖 CWD，从别处调用 runtime.js
  // 时会找不到 packs/；绝对路径仍原样生效（path.resolve 遇到绝对段会重置）。
  const abs = resolve(__dirname, '..', path)
  let raw
  try {
    raw = readFileSync(abs, 'utf8')
  } catch (e) {
    if (e.code === 'ENOENT') throw new Error(`场景包不存在: ${abs}`)
    if (e.code === 'EISDIR') throw new Error(`--pack 指向的是目录而非文件: ${abs}`)
    throw new Error(`读取场景包失败: ${e.message}`)
  }
  let pack
  try {
    pack = JSON.parse(raw)
  } catch (e) {
    throw new Error(`场景包不是合法 JSON（${abs}）: ${e.message}`)
  }
  if (!isPlainObject(pack.scenes)) {
    throw new Error('场景包缺少 scenes 字段（或类型不是普通对象）')
  }
  const errs = validatePack(pack)
  if (errs.length) {
    throw new Error(`场景包结构校验失败（${errs.length} 项）:\n  - ${errs.join('\n  - ')}`)
  }
  return pack
}

// ── P0 + DSE 内容校验（移植自 dict-scene-engine/lint-content.mjs，并补齐可玩性检查）──
//   errors（阻断级，lint 退出码 1）：
//     · dangling_goto         悬空跳转（goto 指向不存在的场景）
//     · missing_entry         入口场景不存在（可达性分析无从进行）
//     · ending_reachability   结局不可达（场景走不到任何结局）
//     · undefined_var         插值变量未在 state 定义
//     · fake_choice           伪分支（所有选项指向同一目标）
//     · choice_shape          choice 缺 goto / if 语法错误 / 字段类型错（补：使「0 阻断」⇒「play 不崩」）
//     · unsafe_path           do / onEnter 的键含 __proto__ / constructor / prototype
//     · conditional_dead_end  初始状态下所有选项的 if 均不满足（补：条件死局检测）
//   warnings（规范级，不阻断）：
//     · unreachable           不可达场景（从 entry BFS 无法到达）
//     · id_naming             场景 ID 非小写 snake_case
//     · content_thickness     正文过薄
const ID_RE = /^[a-z][a-z0-9_]*$/
const MIN_TEXT_CHARS = 8
const VAR_RE = /\{([a-zA-Z_]\w*)\}/g

function lint(pack) {
  const errors = []
  const warnings = []
  const ids = Object.keys(pack.scenes)
  const idSet = new Set(ids)
  const entry = pack.meta?.entry ?? 'start'
  const stateKeys = new Set(Object.keys(pack.state ?? {}))

  const realTargets = (sc) =>
    (sc.choices ?? []).map((c) => c.goto).filter((g) => g && !g.startsWith('@') && idSet.has(g))
  const isEnding = (id) => {
    const sc = pack.scenes[id]
    if (!sc || !sc.choices || sc.choices.length === 0) return true
    return sc.choices.every((c) => typeof c.goto === 'string' && c.goto.startsWith('@'))
  }

  // 1. 悬空跳转
  for (const [id, sc] of Object.entries(pack.scenes)) {
    for (const ch of sc.choices ?? []) {
      const g = ch.goto
      if (g && !g.startsWith('@') && !idSet.has(g)) {
        errors.push(`[悬空跳转] ${id} -> ${g} 不存在`)
      }
    }
  }

  // 2. 不可达场景（从 entry BFS）
  if (idSet.has(entry)) {
    const seen = new Set([entry])
    const q = [entry]
    while (q.length) {
      const cur = q.shift()
      for (const g of realTargets(pack.scenes[cur])) {
        if (!seen.has(g)) { seen.add(g); q.push(g) }
      }
    }
    for (const id of ids) if (!seen.has(id)) {
      warnings.push(`[不可达] 场景 ${id} 从 entry(${entry}) 无法到达`)
    }
  } else {
    // 入口不存在 → 可达性与结局可达性都无从判断：升为阻断（原为 warning，
    // 会让 meta.entry 悬空、结构损坏的包仍然报「0 阻断问题」）。
    errors.push(`[无入口] entry(${entry}) 不存在，无法进行可达性与结局可达性分析`)
  }

  // 3. 结局可达性（每个非结局场景都应能走到某个结局）
  const reachesEnding = (start) => {
    const seen = new Set([start])
    const q = [start]
    while (q.length) {
      const cur = q.shift()
      if (isEnding(cur)) return true
      for (const g of realTargets(pack.scenes[cur])) {
        if (!seen.has(g)) { seen.add(g); q.push(g) }
      }
    }
    return false
  }
  for (const id of ids) {
    if (!isEnding(id) && !reachesEnding(id)) {
      errors.push(`[结局不可达] 场景 ${id} 走不到任何结局`)
    }
  }

  // 4. 未定义插值变量
  for (const [id, sc] of Object.entries(pack.scenes)) {
    const texts = [sc.text ?? '']
    for (const ch of sc.choices ?? []) texts.push(ch.text ?? '')
    for (const t of texts) {
      let m
      while ((m = VAR_RE.exec(t))) {
        const k = m[1]
        if (!stateKeys.has(k)) errors.push(`[未定义变量] ${id}: {${k}} 不在 state 中`)
      }
    }
  }

  // 5. 伪分支（多选项但结局完全一致：goto + if + do 均相同）
  for (const [id, sc] of Object.entries(pack.scenes)) {
    const chs = sc.choices ?? []
    if (chs.length > 1) {
      const sig = (c) => `${c.goto ?? ''}|${c.if ?? ''}|${JSON.stringify(c.do ?? null)}`
      const g0 = sig(chs[0])
      if (chs.every((c) => sig(c) === g0)) {
        errors.push(`[伪分支] ${id}: 所有选项结局一致（${chs[0].goto}）`)
      }
    }
  }

  // 6. 命名规范（小写 snake_case）
  for (const id of ids) {
    if (!ID_RE.test(id)) warnings.push(`[命名规范] 场景 ID "${id}" 非小写 snake_case`)
  }

  // 7. 内容厚度（去掉占位符后字符数）
  for (const [id, sc] of Object.entries(pack.scenes)) {
    const t = (sc.text ?? '').replace(/\{\w+\}/g, '').trim()
    if (!t) warnings.push(`[内容过薄] ${id}: 正文为空`)
    else if ([...t].length < MIN_TEXT_CHARS) warnings.push(`[内容过薄] ${id}: 正文仅 ${[...t].length} 字`)
  }

  // 8. choice 形态 + if 语法 + 不安全路径
  //    目的：让 lint 的「0 阻断」真正等价于「play 不会崩」。此前这三类问题
  //    均为 lint 放行、直到 play 阶段才以 Error/TypeError 暴露。
  for (const [id, sc] of Object.entries(pack.scenes)) {
    const doKeys = new Set([
      ...Object.keys(sc.onEnter ?? {}),
      ...(sc.choices ?? []).flatMap((c) => Object.keys(c.do ?? {})),
    ])
    for (const k of doKeys) {
      if (String(k).split('.').some((s) => UNSAFE_PATH_SEGMENTS.has(s))) {
        errors.push(`[不安全路径] ${id}: 键 "${k}" 含保留段名（禁止原型链访问）`)
      }
    }
    ;(sc.choices ?? []).forEach((ch, i) => {
      if (ch.if != null) {
        try { parseExpr(tokenizeExpr(String(ch.if))) }
        catch (e) { errors.push(`[if语法] ${id}: choices[${i}] ${e.message}`) }
      }
    })
  }

  // 9. 条件死局：初始状态下所有选项的 if 均不满足 ⇒ 该场景永远走不下去。
  //    仅当 if 引用的「根路径」全部存在于初始 state 时才判定，否则跳过——
  //    以免误伤运行时才写入的标志（如 epilogue 依赖的 resolved，由 branch 的 do 写入）。
  for (const [id, sc] of Object.entries(pack.scenes)) {
    if (isEnding(id)) continue
    const chs = sc.choices ?? []
    if (chs.length === 0) continue
    let allHidden = true
    let decidable = true
    for (const ch of chs) {
      if (ch.if == null) { allHidden = false; break }
      const roots = [...String(ch.if).matchAll(/[A-Za-z_][\w.]*/g)].map((m) => m[0].split('.')[0])
      if (roots.some((r) => !stateKeys.has(r))) { decidable = false; break }
      let ok = false
      try { ok = evalCond(ch.if, pack.state ?? {}) } catch { decidable = false; break }
      if (ok) { allHidden = false; break }
    }
    if (decidable && allHidden) {
      errors.push(`[条件死局] ${id}: 初始状态下所有选项的 if 均不满足，无法继续`)
    }
  }

  return { errors, warnings }
}

// P1：状态插值（仅读 state 自有属性，避免 `{constructor}` 之类命中原型链成员）
function interpolate(text, state) {
  return String(text ?? '').replace(/\{(\w+)\}/g, (_, k) => (Object.hasOwn(state, k) ? String(state[k]) : `{${k}}`))
}

// ── DSE if/do 条件引擎（复刻自 dict-scene-engine 的 flags/items 表达式求值）──
// 设计约束：禁用 eval/Function；用 tokenizer + 递归下降解析，仅从 state 读取数据。
//   · 路径支持点式嵌套：gold / flags.heardMonk / items.antidote
//   · 运算符：>= <= == != > < && || !，以及括号
//   · 比较左/右可为路径或数字字面量
//   · 裸路径（无比较）按 truthy 求值（用于 flags.monkDeep 之类）

// ── 原型链防护 ──
// packs/*.json 是不可信输入：`do`/`onEnter` 的点式键若含 `__proto__` 段，会命中全局
// Object.prototype（实测可污染全局并据此绕过 choice.if 门控）。这里在读写路径的入口
// 统一拒绝危险段名，把「污染全局」降级为「明确报错」。
const UNSAFE_PATH_SEGMENTS = new Set(['__proto__', 'constructor', 'prototype'])

function assertSafePath(path) {
  for (const seg of String(path).split('.')) {
    if (UNSAFE_PATH_SEGMENTS.has(seg)) {
      throw new Error(`非法路径段 "${seg}"（禁止原型链访问）: ${path}`)
    }
  }
}

function getPath(obj, path) {
  assertSafePath(path)
  let cur = obj
  for (const p of String(path).split('.')) {
    if (cur == null) return undefined
    cur = cur[p]
  }
  return cur
}

function setPath(obj, path, value) {
  assertSafePath(path)
  const parts = String(path).split('.')
  let cur = obj
  for (let i = 0; i < parts.length - 1; i++) {
    const p = parts[i]
    if (cur[p] == null || typeof cur[p] !== 'object') cur[p] = {}
    cur = cur[p]
  }
  cur[parts[parts.length - 1]] = value
}

function tokenizeExpr(src) {
  const toks = []
  let i = 0
  const isDigit = (c) => c >= '0' && c <= '9'
  const isIdent = (c) => (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c === '_' || c === '.'
  while (i < src.length) {
    const c = src[i]
    if (c === ' ' || c === '\t' || c === '\n' || c === '\r') { i++; continue }
    if (isDigit(c) || (c === '-' && isDigit(src[i + 1]))) {
      let j = i + 1
      while (j < src.length && (isDigit(src[j]) || src[j] === '.')) j++
      toks.push({ t: 'num', v: parseFloat(src.slice(i, j)) })
      i = j
      continue
    }
    if (isIdent(c)) {
      let j = i + 1
      while (j < src.length && isIdent(src[j])) j++
      toks.push({ t: 'path', v: src.slice(i, j) })
      i = j
      continue
    }
    const two = src.slice(i, i + 2)
    if (['>=', '<=', '==', '!=', '&&', '||'].includes(two)) {
      toks.push({ t: 'op', v: two }); i += 2; continue
    }
    if (c === '>' || c === '<' || c === '!' || c === '(' || c === ')') {
      toks.push({ t: 'op', v: c }); i++; continue
    }
    throw new Error(`条件表达式含无法解析的字符 "${c}" @ "${src}"`)
  }
  return toks
}

const CMP_OPS = ['>=', '<=', '==', '!=', '>', '<']

function parseExpr(toks) {
  let pos = 0
  const peek = () => toks[pos]
  const next = () => toks[pos++]

  function pOr() {
    let left = pAnd()
    while (peek() && peek().t === 'op' && peek().v === '||') { next(); left = { type: 'or', left, right: pAnd() } }
    return left
  }
  function pAnd() {
    let left = pCmp()
    while (peek() && peek().t === 'op' && peek().v === '&&') { next(); left = { type: 'and', left, right: pCmp() } }
    return left
  }
  function pCmp() {
    let left = pUnary()
    while (peek() && peek().t === 'op' && CMP_OPS.includes(peek().v)) {
      const op = next().v
      left = { type: 'cmp', op, left, right: pUnary() }
    }
    return left
  }
  function pUnary() {
    if (peek() && peek().t === 'op' && peek().v === '!') { next(); return { type: 'not', operand: pUnary() } }
    return pPrimary()
  }
  function pPrimary() {
    const tk = peek()
    if (!tk) throw new Error('条件表达式意外结束')
    if (tk.t === 'num') { next(); return { type: 'num', v: tk.v } }
    if (tk.t === 'path') { next(); return { type: 'path', v: tk.v } }
    if (tk.t === 'op' && tk.v === '(') {
      next()
      const e = pOr()
      if (!peek() || peek().v !== ')') throw new Error('条件表达式缺少右括号')
      next()
      return e
    }
    throw new Error(`条件表达式无法解析 token: ${JSON.stringify(tk)}`)
  }

  const ast = pOr()
  if (pos < toks.length) throw new Error(`条件表达式存在多余 token: ${JSON.stringify(toks.slice(pos))}`)
  return ast
}

function truthy(v) {
  if (typeof v === 'number') return v !== 0
  return !!v
}

function evalNode(node, state) {
  switch (node.type) {
    case 'num': return node.v
    case 'path': return getPath(state, node.v)
    case 'not': return !truthy(evalNode(node.operand, state))
    case 'and': return truthy(evalNode(node.left, state)) && truthy(evalNode(node.right, state))
    case 'or': return truthy(evalNode(node.left, state)) || truthy(evalNode(node.right, state))
    case 'cmp': {
      const l = evalNode(node.left, state)
      const r = evalNode(node.right, state)
      switch (node.op) {
        case '>=': return l >= r
        case '<=': return l <= r
        case '>': return l > r
        case '<': return l < r
        case '==': return l === r
        case '!=': return l !== r
      }
    }
  }
  throw new Error(`未知表达式节点: ${JSON.stringify(node)}`)
}

function evalCond(expr, state) {
  if (expr == null) return true
  try {
    return truthy(evalNode(parseExpr(tokenizeExpr(expr)), state))
  } catch (e) {
    throw new Error(`if 条件求值失败 "${expr}": ${e.message}`)
  }
}

function isEnding(scene) {
  if (!scene.choices || scene.choices.length === 0) return true
  // 仅含 @ 特殊跳转（如 @restart）也视为结局
  return scene.choices.every((c) => typeof c.goto === 'string' && c.goto.startsWith('@'))
}

// DSE do 语义：数字为增量(delta)，布尔/字符串/Null 为赋值；键支持点式嵌套路径
function applyDo(state, do_) {
  if (!do_) return
  for (const [k, v] of Object.entries(do_)) {
    if (typeof v === 'number') {
      setPath(state, k, (getPath(state, k) ?? 0) + v)
    } else {
      setPath(state, k, v)
    }
  }
}

function cmdInfo(pack) {
  const endings = Object.entries(pack.scenes).filter(([, s]) => isEnding(s)).map(([id]) => id)
  const info = {
    title: pack.meta?.title,
    scenes: Object.keys(pack.scenes).length,
    endings,
    entry: pack.meta?.entry ?? 'start',
  }
  if (pack.meta?.n_endings != null) info.n_endings = pack.meta.n_endings
  if (pack.meta?.worlds != null) info.worlds = pack.meta.worlds
  console.log(JSON.stringify(info, null, 2))
}

function cmdScenes(pack) {
  for (const [id, sc] of Object.entries(pack.scenes)) {
    const tag = isEnding(sc) ? '⚑' : '  '
    const pov = sc.pov ?? sc.onEnter?.pov ?? ''
    console.log(`${tag} ${id}  (${sc.choices?.length ?? 0} choices)  [${pov}]  ${sc.title ?? ''}`)
  }
}

function cmdLint(pack) {
  const { errors, warnings } = lint(pack)
  if (warnings.length) {
    console.log('规范建议:')
    for (const w of warnings) console.log('  - ' + w)
  }
  if (errors.length === 0) {
    console.log(`OK: 0 阻断问题（9 项检查通过，${warnings.length} 项规范建议）`)
    process.exit(0)
  }
  console.log('阻断问题:')
  for (const e of errors) console.log('  - ' + e)
  console.log(`\n共 ${errors.length} 项阻断问题，${warnings.length} 项规范建议`)
  process.exit(1)
}

async function cmdPlay(pack, inputArg, key) {
  const state = { ...(pack.state ?? {}) }
  let cur = pack.meta?.entry ?? 'start'
  const visited = []
  const inputs = inputArg ? inputArg.split(',').map((s) => s.trim()).filter(Boolean) : []
  let idx = 0

  const rl = (!inputArg && process.stdin.isTTY)
    ? createInterface({ input: process.stdin, output: process.stdout })
    : null

  try {
    while (true) {
      const scene = pack.scenes[cur]
      if (!scene) { console.log(`[错误] 场景不存在: ${cur}`); process.exit(2) }
      visited.push(cur)
      applyDo(state, scene.onEnter) // P1：进入场景时按 onEnter 改写状态（镜像 DSE onEnter）
      const pov = scene.pov ?? scene.onEnter?.pov
      console.log(`\n# ${scene.title ?? cur}${pov ? `  〔视角: ${pov}〕` : ''}`)
      console.log(interpolate(scene.text, state))
      if (scene.audio) sound.play(scene.audio, SAVES) // P1：音效标记触发

      if (isEnding(scene)) {
        console.log(`\n[结局] 抵达 ${cur}（共经历 ${visited.length} 个场景）`)
        persist(key, cur, state, visited)
        return 0
      }

      // DSE if 条件引擎：按 if 过滤可见分支并重新编号
      const choices = (scene.choices ?? []).filter((c) => c.if == null || evalCond(c.if, state))
      if (choices.length === 0) {
        // 死局：不再写入结局统计，并以非零码退出
        // （此前会 exit 0 且把当前场景当作结局计入 saves/endings.json）
        console.log('\n[死局] 当前状态下没有任何可选分支（所有 if 条件均不满足）')
        process.exitCode = 4
        return
      }
      let pick
      if (inputs.length > idx) {
        pick = parseInt(inputs[idx++], 10) - 1
      } else if (rl) {
        choices.forEach((c, i) => console.log(`  ${i + 1}. ${interpolate(c.text, state)}`))
        const ans = await rl.question('选择> ')
        pick = parseInt(ans, 10) - 1
      } else {
        console.log('[无输入] 需 --input "1,2,..." 或非 TTY 脚本')
        process.exit(3)
      }

      if (Number.isNaN(pick) || pick < 0 || pick >= choices.length) {
        console.log('[无效选择]'); process.exit(3)
      }
      const ch = choices[pick]
      applyDo(state, ch.do) // P1：do 改写状态（mood 等）
      if (ch.goto.startsWith('@')) {
        console.log(`\n[特殊跳转] ${ch.goto}`)
        return 0 // @restart/@end 等一律视为终止（避免空转）
      }
      cur = ch.goto
    }
  } finally {
    if (rl) rl.close()
  }
}

function persist(key, ending, state, visited) {
  const dir = savesDir(key)
  try {
    mkdirSync(dir, { recursive: true })
    writeJsonAtomic(resolve(dir, 'last.json'), { ending, state, visited })
    // N 路结局统计：按 pack 隔离 + 原子写 + 损坏保护
    const tallyPath = resolve(dir, 'endings.json')
    let tally
    try {
      tally = JSON.parse(readFileSync(tallyPath, 'utf8'))
    } catch (e) {
      if (e.code === 'ENOENT') tally = {}          // 该 pack 首次游玩
      else throw new Error(`计数文件损坏（${tallyPath}）：${e.message} —— 已跳过写入，避免清空历史`)
    }
    if (!isPlainObject(tally)) {
      throw new Error(`计数文件结构非法（${tallyPath}）—— 已跳过写入，避免清空历史`)
    }
    tally[ending] = (tally[ending] ?? 0) + 1
    writeJsonAtomic(tallyPath, tally)
    console.log(`[存档] saves/${key}/last.json  ·  结局计数 ${ending} = ${tally[ending]}`)
  } catch (e) {
    console.log(`[存档跳过] ${e.message}`)
  }
}

// N 路结局统计：读取 saves/<pack>/endings.json 的累计计数，对照包内结局场景
function cmdStats(pack, key) {
  const tallyPath = resolve(savesDir(key), 'endings.json')
  let tally = {}
  let corrupt = null
  try {
    const parsed = JSON.parse(readFileSync(tallyPath, 'utf8'))
    if (isPlainObject(parsed)) tally = parsed
    else corrupt = '结构非法（非对象）'
  } catch (e) {
    if (e.code !== 'ENOENT') corrupt = e.message
  }
  const endings = Object.entries(pack.scenes).filter(([, s]) => isEnding(s)).map(([id]) => id)
  console.log(`N 路结局统计（saves/${key}/endings.json 跨游玩累计）:`)
  if (corrupt) console.log(`  ⚠️ 计数文件无法解析（${corrupt}）—— 仅显示包内结局定义，不做写入`)
  if (!endings.length) { console.log('  该包无结局场景'); return }
  for (const id of endings) {
    const sc = pack.scenes[id]
    const title = sc?.title ?? id
    const pov = sc?.pov ?? sc?.onEnter?.pov ?? ''
    console.log(`  ${id}  [${pov}]  「${title}」  次数=${tally[id] ?? 0}`)
  }
  // 仅统计当前包内的终局行（忽略历史包遗留的计数键），使总数与展示一致
  const total = endings.reduce((a, id) => a + (tally[id] ?? 0), 0)
  console.log(`  总游玩次数 = ${total}`)
}

async function main() {
  const args = process.argv.slice(2)
  const cmd = args[0]
  let packPath = 'packs/scale-pack.json'   // 默认包（原为已删除的 packs/demo-pack.json）
  let inputArg = undefined
  for (let i = 1; i < args.length; i++) {
    if (args[i] === '--pack') packPath = args[++i]
    else if (args[i] === '--input') inputArg = args[++i]
  }
  const pack = loadPack(packPath)
  const key = packKey(packPath)   // 存档按 pack 名隔离到 saves/<key>/

  switch (cmd) {
    case 'info':   return cmdInfo(pack)
    case 'scenes': return cmdScenes(pack)
    case 'lint':   return cmdLint(pack)
    case 'play':   return await cmdPlay(pack, inputArg, key)
    case 'stats':  return cmdStats(pack, key)
    default:
      console.log('用法: node runtime.js <info|scenes|lint|play|stats> --pack P [--input "1,2"]')
      process.exit(1)
  }
}

// 既可作为 CLI 运行，也可被 e2e 等脚本 require/import 复用 lint / loadPack（不触发 CLI）
const _isMain = !!process.argv[1] && fileURLToPath(import.meta.url) === resolve(process.argv[1])
if (_isMain) {
  main().catch((e) => {
    // 只输出一行可读错误；完整堆栈需 NOVEL_RUN_DEBUG=1（此前一律裸露 Node 堆栈与本机绝对路径）
    if (process.env.NOVEL_RUN_DEBUG) console.error(e)
    else console.error(`[错误] ${e && e.message ? e.message : String(e)}`)
    process.exit(typeof e?.exitCode === 'number' ? e.exitCode : 1)
  })
}
export { lint, loadPack, isEnding }
