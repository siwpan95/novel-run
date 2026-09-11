// 端到端验证：生成侧 → 运行侧 双向打通，验证 P0→P2 路线 + 移植的 DSE 7 项 lint + if/do 条件引擎。
//
// 覆盖：
//   · 五个题材包（wuxia / historical / cultivation / infinite_flow / lowmagic）各自生成 → lint → info → play 双分支
//   · 从真实 DSE 仓库复制来的 wuxia-dse 内容包：转换 → lint（0 阻断问题）
//   · wuxia-dse 实玩，验证 DSE 复刻的 if 门控 + do 增量/嵌套路径语义
//
// 断言等级：
//   P0  lint    → 0 阻断问题
//   P0  info    → 场景数=6、结局数=2
//   P1  插值    → play 输出含插值后的 hero_name，且 mood 随 do/onEnter 改写
//   P1  音效    → play 输出含 [音效] 标记
//   P2  分支    → 两条输入路径分别抵达 ending_a / ending_b，并写入存档
//   P2  if/do   → wuxia-dse 双路径验证 if 门控与 do 增量/嵌套路径（gold/items/flags/karma）

import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..')

const PYTHON_CANDIDATES = [
  'C:/Users/13122/.workbuddy/binaries/python/versions/3.13.12/python.exe',
  'F:/Python314/python.exe',
  'python3',
  'python',
]
// Node 运行时：优先取环境变量 NODE_BIN，否则复用当前执行的 Node 可执行文件。
// （原实现硬编码了本机绝对路径 .../node/versions/22.22.2-2/node.exe，换机/换版本即 ENOENT，
//   导致 spawnSync 返回空 stdout、后续 JSON.parse 崩溃 → npm test 必失败。）
const NODE = process.env.NODE_BIN || process.execPath

function findPython() {
  for (const p of PYTHON_CANDIDATES) {
    const r = spawnSync(p, ['--version'], { encoding: 'utf8' })
    if (r.status === 0) return p
  }
  throw new Error('未找到可用的 Python 运行时')
}

function run(cmd, args, opts = {}) {
  const r = spawnSync(cmd, args, { encoding: 'utf8', cwd: ROOT, ...opts })
  return { code: r.status, out: (r.stdout ?? '') + (r.stderr ?? '') }
}

let failures = 0
function assert(cond, msg) {
  if (cond) console.log(`  [OK] ${msg}`)
  else { console.log(`  [X]  ${msg}`); failures++ }
}

const PY = findPython()
console.log(`使用 Python: ${PY}`)
console.log(`使用 Node:   ${NODE}\n`)

// ── 0. 准备：生成三题材包 + 转换真实 DSE 内容包 ──
console.log('[准备] 生成三题材包 + 转换 DSE 内容包')
run(PY, ['gen/generate.py', '--world', 'all', '--seed', '42'])
run(NODE, ['scripts/convert-dse.mjs'])
const WORLDS = ['wuxia', 'historical', 'cultivation', 'infinite_flow', 'lowmagic']
const MOOD_RE = /(凝重|沉吟|灼热|畅快|淡泊|炽烈|淡然|黯然|紧绷)/

for (const w of WORLDS) {
  const PACK = resolve(ROOT, 'packs', `${w}.json`)
  console.log(`\n========== [${w}] P0→P2 ==========`)

  // P0: lint（7 项检查，0 阻断问题）
  const lint = run(NODE, ['run/runtime.js', 'lint', '--pack', PACK])
  assert(lint.code === 0 && /0 阻断问题/.test(lint.out), `${w}: lint 0 阻断问题`)

  // P0: info
  const info = run(NODE, ['run/runtime.js', 'info', '--pack', PACK])
  const infoJson = JSON.parse(info.out)
  assert(infoJson.scenes === 6, `${w}: 场景数=6 (实际 ${infoJson.scenes})`)
  assert(infoJson.endings.length === 2, `${w}: 结局数=2 (实际 ${infoJson.endings.length})`)

  // 取出 hero_name 用于插值断言
  const packJson = JSON.parse(readFileSync(PACK, 'utf8'))
  const hero = packJson.state.hero_name

  // P1: play 路径一 → ending_a
  const playA = run(NODE, ['run/runtime.js', 'play', '--pack', PACK, '--input', '1,1,1,1'])
  assert(playA.code === 0, `${w}: play 退出码 0`)
  assert(playA.out.includes(hero), `${w}: 插值 hero_name(${hero}) 生效`)
  assert(/\[音效\]/.test(playA.out), `${w}: audio 标记触发程序化音效`)
  assert(MOOD_RE.test(playA.out), `${w}: mood 随 onEnter/do 改写（出现非初始心境）`)
  assert(/\[结局\] 抵达 ending_a/.test(playA.out), `${w}: 路径 1,1,1,1 抵达 ending_a`)

  // P2: play 路径二 → ending_b
  const playB = run(NODE, ['run/runtime.js', 'play', '--pack', PACK, '--input', '1,1,1,2'])
  assert(playB.code === 0, `${w}: play 退出码 0`)
  assert(/\[结局\] 抵达 ending_b/.test(playB.out), `${w}: 路径 1,1,1,2 抵达 ending_b`)
}

// ── 真实 DSE 内容包：转换后应 lint 通过（仅命名规范建议）──
console.log('\n========== [wuxia-dse] 移植内容包校验 ==========')
const DSE = resolve(ROOT, 'packs', 'wuxia-dse.json')
const dl = run(NODE, ['run/runtime.js', 'lint', '--pack', DSE])
assert(dl.code === 0 && /0 阻断问题/.test(dl.out), 'wuxia-dse: lint 0 阻断问题（已把 battle 摊平为 goto）')
const dinfo = JSON.parse(run(NODE, ['run/runtime.js', 'info', '--pack', DSE]).out)
assert(dinfo.scenes === 16, `wuxia-dse: 场景数=16 (实际 ${dinfo.scenes})`)

// ── wuxia-dse if/do 条件引擎（复刻 DSE 的 flags/items 表达式求值）──
console.log('\n========== [wuxia-dse] if/do 条件引擎 ==========')
const dseState = () => JSON.parse(readFileSync(resolve(ROOT, 'saves', 'last.json'), 'utf8')).state

// 路径 A：买解药(gold-10) → 撒迷粉(flags.dirtyFight) → 胜 → end-mutual
const dA = run(NODE, ['run/runtime.js', 'play', '--pack', DSE, '--input', '2,1,1,1,2,1,1'])
assert(dA.code === 0, 'wuxia-dse: 路径A play 退出码 0')
assert(/\[结局\] 抵达 wuxia\.end-mutual/.test(dA.out), 'wuxia-dse: 路径A 抵达 end-mutual（买解药+撒迷粉分支）')
const sA = dseState()
assert(sA.gold === 10, `wuxia-dse: 路径A 买解药后 gold=10 (实际 ${sA.gold})`)
assert(sA.items && sA.items.antidote === 1, 'wuxia-dse: 路径A items.antidote=1（嵌套路径 do 增量生效）')
assert(sA.flags && sA.flags.dirtyFight === true, 'wuxia-dse: 路径A flags.dirtyFight=true（嵌套路径 do 赋值生效）')

// 路径 B：不买解药 → 干净对决 → end-vengeance（验证 if 门控：撒迷粉选项不可见）
const dB = run(NODE, ['run/runtime.js', 'play', '--pack', DSE, '--input', '1,2,1,1,1,1'])
assert(dB.code === 0, 'wuxia-dse: 路径B play 退出码 0')
assert(/\[结局\] 抵达 wuxia\.end-vengeance/.test(dB.out), 'wuxia-dse: 路径B 抵达 end-vengeance（无解药→干净对决分支）')
const sB = dseState()
assert(!(sB.items && sB.items.antidote), 'wuxia-dse: 路径B 未买解药，items.antidote 不存在')
assert(!(sB.flags && sB.flags.dirtyFight), 'wuxia-dse: 路径B flags.dirtyFight 未置位（if 门控生效）')
// if 门控直接校验：无解药时 "撒迷粉" 选项不应出现在渲染出的可选项里
assert(!dB.out.includes('撒出在药铺配的迷粉'), 'wuxia-dse: 路径B 迷粉选项被 if(items.antidote>=1) 过滤，未渲染')

console.log(`\n==== e2e 结果: ${failures === 0 ? '全部通过 ✅' : `${failures} 项失败 ❌`} ====`)
process.exit(failures === 0 ? 0 : 1)
