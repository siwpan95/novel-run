// 把从 dict-scene-engine 复制来的真实内容包（ESM）转为运行时可加载的 JSON 惰性数据。
// 证明「复制自真实仓库的 DSE 内容包」能在 novel-run 运行时中加载并结构校验通过。
//
// 注意：仅对可信来源（本仓库 reference/dse/ 下、来自我们自己的仓库副本）执行 import()，
// 与 DSE 安全模型一致——内容即代码，只信可信源。转换产物是 inert data，运行时不再执行。

import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = resolve(__dirname, '..')

// DSE 内容包用 battle:{onWin,onLose,onFlee} 表达战斗分支，而 novel-run 运行时只认
// choice.goto。转换时把 battle 摊平为真实 goto 选项，使导出的 JSON 既能被静态图分析
// （lint 的可达性检查）也能被运行时直接 play。
function flattenBattle(scenes) {
  for (const sc of Object.values(scenes)) {
    if (sc && sc.battle && typeof sc.battle === 'object') {
      const b = sc.battle
      const derived = []
      if (b.onWin) derived.push({ text: '拔刀应战（胜）', goto: b.onWin })
      if (b.onLose) derived.push({ text: '拔刀应战（败）', goto: b.onLose })
      if (b.onFlee && b.onFlee !== b.onLose) derived.push({ text: '转身避让', goto: b.onFlee })
      // 战斗分支置前，保留原 choices（若有）在后
      sc.choices = [...derived, ...(sc.choices ?? [])]
    }
  }
  return scenes
}

async function convert(srcRel, outRel, meta) {
  const src = resolve(ROOT, srcRel)
  const mod = await import(pathToFileURL(src).href)
  const dict = mod.default ?? mod
  flattenBattle(dict)
  const pack = {
    meta,
    state: { hero_name: '刀客', world: '武侠', location: '风陵渡', mood: '平静', gold: 20, karma: 0 },
    scenes: dict,
  }
  const out = resolve(ROOT, outRel)
  mkdirSync(dirname(out), { recursive: true })
  writeFileSync(out, JSON.stringify(pack, null, 2), 'utf8')
  console.log(`转换 ${srcRel} → ${outRel}  场景数=${Object.keys(dict).length}`)
  return out
}

await convert(
  'reference/dse/wuxia.js',
  'packs/wuxia-dse.json',
  { title: 'DSE 真实武侠包（wuxia.js 转 JSON）', version: '0.2', seed: null, entry: 'wuxia.start', genre: 'wuxia-dse' }
)
