// e2e_scale.js —— novel-run 「千场景 / 多 POV / 多结局」端到端断言（Task #20）
//
// 复用 run/runtime.js 的真实 lint（7 项检查），并在图层面做可达性断言：
//   · 两个结局 ending_a / ending_b 均可达
//   · 6 条 POV 线（林朔/唐川/白夜/叶琳/墟核/玩家群体）均出现在可达场景
//   · 关键拍的 Rashomon「复眼」场景可达
//   · hub 章的 POV 切换「线」场景可达
//
// 用法：node run/e2e_scale.js [pack ...]
//   不传参则默认测 packs/scale-pack.json 与 packs/scale-stress.json

import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { lint, loadPack } from './runtime.js'

const __dirname = dirname(fileURLToPath(import.meta.url))
const POV_THREADS = ['林朔', '唐川', '白夜', '叶琳', '墟核', '玩家群体']

let failures = 0
function check(name, cond, detail = '') {
  if (cond) {
    console.log(`  ✓ ${name}`)
  } else {
    failures++
    console.log(`  ✗ ${name}  ${detail}`)
  }
}

// 从入口 BFS，收集可达场景 id 与其 pov
function reach(pack) {
  const entry = pack.meta?.entry ?? 'start'
  const seen = new Set()
  const queue = [entry]
  const povs = new Set()
  const titles = []
  while (queue.length) {
    const id = queue.shift()
    if (seen.has(id)) continue
    seen.add(id)
    const sc = pack.scenes[id]
    if (!sc) continue
    const pov = sc.pov ?? sc.onEnter?.pov
    if (pov) povs.add(pov)
    titles.push(sc.title ?? id)
    for (const c of sc.choices ?? []) {
      const g = c.goto
      if (typeof g === 'string' && g.startsWith('@')) continue // 特殊跳转=终止
      if (pack.scenes[g]) queue.push(g)
    }
  }
  return { seen, povs, titles }
}

function testPack(relPath) {
  const path = resolve(__dirname, '..', relPath)
  console.log(`\n=== ${relPath} ===`)
  let pack
  try {
    pack = loadPack(path)
  } catch (e) {
    check(`加载 ${relPath}`, false, e.message)
    return
  }
  check(`加载 ${relPath}`, true, `场景数=${Object.keys(pack.scenes).length}`)

  const { errors, warnings } = lint(pack)
  check('7 项 lint 0 阻断', errors.length === 0, errors.join(' | '))
  if (warnings.length) console.log(`    (规范建议 ${warnings.length} 项，非阻断)`)

  const { seen, povs, titles } = reach(pack)
  // N 路结局：从 pack.meta.n_endings 派生需断言的结局 id（ending_0..ending_{n-1}）
  const nEnd = pack.meta?.n_endings ?? 2
  for (let i = 0; i < nEnd; i++) {
    check(`结局 ending_${i} 可达`, seen.has(`ending_${i}`))
  }
  // 真/暗线后续分支：resolved 标志经 epilogue 的 if 门控分流到两路终局
  const ep = pack.meta?.epilogue_lines
  const trueLine = ep?.resolved_line ?? 'epilogue_true'
  const falseLine = ep?.unresolved_line ?? 'epilogue_false'
  check(`真线终局 ${trueLine} 可达`, seen.has(trueLine))
  check(`暗线终局 ${falseLine} 可达`, seen.has(falseLine))
  for (const p of POV_THREADS) {
    check(`POV 线可达: ${p}`, povs.has(p))
  }
  check('Rashomon 复眼场景可达', titles.some((t) => t.includes('复眼')))
  check('POV 切换「线」场景可达', titles.some((t) => t.includes('线')))
  // 真/暗线后续分支结构校验：epilogue 以 if 门控 resolved==1/0 分流到两路终局
  const epi = pack.scenes['epilogue']
  const conds = (epi?.choices ?? []).map((c) => c.if).sort()
  check('epilogue 以 if 门控 resolved 分流', conds.includes('resolved == 1') && conds.includes('resolved == 0'))
  check(`真线终局 ${trueLine} 可达`, seen.has(trueLine))
  check(`暗线终局 ${falseLine} 可达`, seen.has(falseLine))
}

const args = process.argv.slice(2)
const packs = args.length
  ? args
  : ['packs/scale-pack.json', 'packs/scale-stress.json']

for (const p of packs) testPack(p)

console.log(`\n==== e2e 结果: ${failures === 0 ? 'ALL PASS' : failures + ' 项失败'} ====`)
process.exit(failures === 0 ? 0 : 1)
