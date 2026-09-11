// 极简程序化 PCM 合成器（对应 DSE 的 sound.js：事件订阅 → 程序化合成 PCM → 播放）。
// 零三方依赖：用 Node 标准库 Buffer 直接写 16-bit PCM WAV。
//
// 验证路线 P1：场景带 audio 标记 → 运行时在场景进入时触发对应音效，
// 证明「生成侧产出音效标记、运行时程序化合成」这条链路可行。

import { writeFileSync, mkdirSync } from 'node:fs'
import { resolve, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))

// cue id → 合成参数（无三方依赖，纯数学生成）
const CUES = {
  ambient:  { freq: 220, dur: 0.25, type: 'sine' },
  tension:  { freq: 330, dur: 0.20, type: 'sawtooth' },
  suspense: { freq: 277, dur: 0.30, type: 'triangle' },
  choice:   { freq: 440, dur: 0.15, type: 'square' },
  resolve:  { freq: 523, dur: 0.40, type: 'sine' },
  fade:     { freq: 165, dur: 0.50, type: 'sine' },
}

function sample(type, phase) {
  switch (type) {
    case 'square':   return Math.sign(Math.sin(phase))
    case 'sawtooth': return 2 * (phase / (2 * Math.PI) - Math.floor(0.5 + phase / (2 * Math.PI)))
    case 'triangle': return Math.sin(phase) * Math.sin(phase * 0.5)
    default:         return Math.sin(phase) // sine
  }
}

export function render(cue, dir) {
  // 白名单校验：cue 来自不可信 pack，若直接拼入文件名可经 `..` 逃逸到项目外
  // （实测 audio="../../../../_x/pwned" 会在项目外写出 .wav）；未知 cue 一律跳过合成。
  const key = String(cue ?? '')
  if (!Object.hasOwn(CUES, key)) {
    console.log(`  [音效] ${key} (未知 cue，跳过合成)`)
    return
  }
  const cfg = CUES[key]
  const sr = 44100
  const n = Math.floor(sr * cfg.dur)
  const data = Buffer.alloc(n * 2)
  for (let i = 0; i < n; i++) {
    const t = i / sr
    const s = sample(cfg.type, 2 * Math.PI * cfg.freq * t) * 0.25
    data.writeInt16LE(Math.round(s * 32767), i * 2)
  }
  const header = Buffer.alloc(44)
  header.write('RIFF', 0)
  header.writeUInt32LE(36 + data.length, 4)
  header.write('WAVE', 8)
  header.write('fmt ', 12)
  header.writeUInt32LE(16, 16)
  header.writeUInt16LE(1, 20)        // PCM
  header.writeUInt16LE(1, 22)        // mono
  header.writeUInt32LE(sr, 24)
  header.writeUInt32LE(sr * 2, 28)   // byte rate
  header.writeUInt16LE(2, 32)        // block align
  header.writeUInt16LE(16, 34)       // bits/sample
  header.write('data', 36)
  header.writeUInt32LE(data.length, 40)
  try {
    mkdirSync(dir, { recursive: true })
    const out = resolve(dir, `cue-${key}.wav`)
    writeFileSync(out, Buffer.concat([header, data]))
    console.log(`  [音效] ${key} → ${out}`)
  } catch (e) {
    console.log(`  [音效] ${key} (合成跳过: ${e.message})`)
  }
}

export const sound = {
  play(cue, dir) {
    render(cue, dir ?? resolve(__dirname, '..', 'saves'))
  },
}
