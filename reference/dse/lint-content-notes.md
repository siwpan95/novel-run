# DSE lint-content 校验项摘录（移植依据）

> 来源：G:/local/run_and_run/dict-scene-engine/scripts/lint-content.mjs
> 用途：novel-run 的 run/runtime.js `lint` 子命令按此移植，提升集成验证保真度。

## 7 类检查（原版口径）

1. **悬空 goto** —— 跳转目标不存在（`@` 前缀走白名单 `@restart` / `@loop:<id>`）。
2. **不可达场景** —— 从 entry 出发 BFS 到不了的场景 → error。
3. **结局可达性** —— 每个 `ending.*` 至少一条可达路径 → 否则 error。
4. **变量一致性** —— 内容引用的 `flags`/`items` 须在叙事账本声明；账本声明但内容从不读取 → 死变量（warning）。
5. **内容厚度** —— 场景文本过短告警（warning）。
6. **疑似假选择** —— 无副作用且与其他选项同归宿的选项（warning）。
7. **ID 命名** —— 符合命名空间规范 `^[a-z][a-z0-9]*([-_][a-z0-9]+)*(\.[a-z0-9]+([-_][a-z0-9]+)*)*$`。

## 退出码约定
- 存在 error → 1；仅 warning → 0（warning 不阻塞，但应清零）。

## 移植到 novel-run 的范围
- P0 已含：悬空 goto（check 1）。
- 本次移植：2 不可达(BFS) / 3 结局可达 / 5 内容厚度 / 6 假选择 / 7 ID 命名。
- 4 变量一致性依赖「叙事账本」概念，JSON 包未内置 ledger，暂以 warning 形式做轻量检查（声明式 state 字段 vs 使用字段对比）。
