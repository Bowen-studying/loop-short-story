# continuity_ledger 校验规则（补充 pitfalls）

`validate architecture` 对 continuity_ledger 施加三条硬约束：

1. **同场景 state 必须合并**：每个 continuity fact 的 states 数组内，scene_id 不能重复。同一场景内发生的多个事件（如 S3 中「取出照片」后再「锁进抽屉」）应合并为一条 state，将变化过程写入 value 字段（如 `"从钱包取出，发现嘴型变化→锁进抽屉，不再查看"`）。

2. **state→scene 双向引用**：每个 state 的 scene_id 必须被对应场景的 `continuity_refs` 引用。如果 K2 在 S1 有一个 state，则 S1 的 continuity_refs 数组中必须包含 `"K2"`。反过来——如果某个场景引用了 K3，K3 必须有一个 state 以该场景为 scene_id。

3. **states 按场景时间顺序排列**：states 数组内的顺序必须与场景在 beat_sheet 中的出现顺序一致。

典型错误：
- K7 有两个 state 都写 `"scene_id": "S3"` → 合并为一条
- K3 在 S2 有 state，但 S2 的 continuity_refs 里没有 K3 → 补全引用
- K2 在 S4 的 state 排在 S1 的 state 前面 → 调序

修复流程：先合并同场景 state → 检查每个 state.scene_id 是否被对应场景引用 → 检查排序。
