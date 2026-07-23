---
name: loop-short-story
description: 使用四角色独立盲审、HARD/SOFT/SUBJECTIVE 三层评分、双阶段自动质量爬坡、三审一裁一改通顺性终校、world_rules 世界规则校验和 mirror_character 镜像角色追踪，运行受控的选题、阅读承诺、场景因果、信息递进、人物情绪和外部审改 Loop，创作、审查并迭代1000–3000字全题材中文网络短篇。适用于从创意开发完整可发布故事、把已有设定或大纲扩写成短篇、诊断并修订现有短篇，以及执行可迁移的规格—架构—初稿—审稿—修订—终校流程。
---

# 多 Loop 网络短篇创作

通过多个有边界的 Loop 创作完整的中文网络短篇。提升发布前的点击、完读和情绪传播潜力，但不得承诺实际流量或收益。不得强制故事包含时间循环、结尾反转、平台专用公式、固定对话比例或固定钩子间隔。

## 选择进入路径

- 面对新创意：先初始化项目，再运行选题 Loop，并根据入选方案填写 `story_spec.yaml`。
- 面对已有设定或大纲：把已确定的创作决策规范化到 `story_spec.yaml`，再进入规格批准点。
- 面对已有正文：把原稿保存在项目受管 `drafts/` 目录之外，推断临时规格和架构，明确标注所有推断，并在修改正文前取得两次批准；批准后再用 `record-draft` 导入，禁止直接覆盖受管版本。
- 面对已有项目：先读取 `state.json`，从记录的阶段继续。不得静默重新生成已批准的产物。

使用作者指定的目录；未指定时，在当前工作区创建 `stories/<short-slug>/`。从本文件位置相对定位脚本，不得写死特定宿主的安装路径。使用环境中可用的 `python3` 或 `python`。

## 执行工作流

在开始创作前读取 [references/orchestration.md](references/orchestration.md)。宿主支持隔离子 Agent 时，默认使用 `multi_agent`；否则使用 `single_agent_fallback`，按相同角色顺序执行并生成完全相同的产物。协调器独占项目文件和状态写权限；子 Agent 只能返回自己的结构化 JSON，不得直接编辑项目。

### 1. 选择并批准故事规格

读取 [references/contracts.md](references/contracts.md)。先初始化项目：

```text
python <skill-dir>/scripts/loop_project.py init <project-dir>
```

面对新创意时，派发三个隔离的选题角色，每个角色只生成一张选题卡。协调器收齐三个方案后，比较钩子清晰度、差异性、情绪压力、画面具体性和短篇可完成性。由作者选择；除非作者要求，不得混合多个候选方案。把候选卡和选择记录写入 `concepts/`，然后运行：

```text
python <skill-dir>/scripts/loop_project.py validate concepts <project-dir>
```

填写 Schema v2 的 `story_spec.yaml`。只保留一条核心阅读承诺和一个中心冲突。根据故事选择反转、揭示、价值重估、情绪结算、直接解决或其他合适的结尾策略，不得把所有题材强行写成反转故事。

运行 `validate spec`，向作者简要展示题材、受众、钩子、核心阅读承诺、主角欲望与缺陷、中心冲突、目标情绪和结尾策略，然后等待明确批准：

```text
python <skill-dir>/scripts/loop_project.py approve spec <project-dir>
```

在当前创作周期内把已批准规格视为不可变边界。若选题根本无法成立，停止当前正文周期并返回选题 Loop，不得用语言润色掩盖选题失败。

### 2. 建立并批准故事架构

读取 [references/loop-craft.md](references/loop-craft.md)。生成 `loop_map.json` 和 `beat_sheet.json`。

- 使用一条阅读承诺 Loop：开篇钩子 → 早期证明 → 决定性兑现 → 超额兑现。
- 使用2–4条故事 Loop：问题或期待 → 压力 → 行动 → 代价 → 回答、重估或兑现。
- 为核心兑现和每条故事 Loop 写出“必须成立的最小结论 → 最强替代解释 → 排除替代解释的决定性支持 → 允许保留的不确定性”。开放结尾也必须明确关闭什么、保留什么。
- 使用一条人物情绪 Loop：欲望与缺陷 → 惯性选择 → 代价升级 → 反缺陷选择 → 情绪结算。
- 使用4–8场，并依次覆盖 `hook`、`pressure`、`escalation`、`decisive_payoff`、`aftertaste`。
- 每场必须包含目标、阻碍、选择、后果、承诺动作、关联 Loop ID，以及知识、关系或风险中的至少一项具体变化。
- 在 `beat_sheet.json` 维护跨场景连续性台账，跟踪时间、次数、地点、身份、关系、物件、规则或知识状态；任何变化都必须绑定场景和原因。
- 可选 `loop_map.json` 顶层 `world_rules` 字段（可为 null）：当故事有超自然/科幻等特殊世界规则时填写 `mechanism`（机制名称）、`scope`（作用范围）、`limitations`（至少一条限制）、`invariants`（至少一条不可违背的恒定事实）。如无超自然现象，`mechanism` 填 `"nothing_supernatural"` 或整字段设为 null。
- 可选 `loop_map.json` 中 `character_loop.mirror_character` 字段（可为 null）：{`name`, `story_function`（trigger|obstacle|revealer|mirror）, `relationship_to_protagonist`}，用于标记与主角形成对照的镜像角色。

运行 `validate architecture`，向作者总结阅读承诺、故事 Loop 的闭合方式、人物关键选择、五阶段和高潮兑现，然后等待第二次明确批准：

```text
python <skill-dir>/scripts/loop_project.py approve architecture <project-dir>
```

两枚批准指纹均未记录前，不得起草正文。

### 3. 一次写完完整初稿

只派发一个正文 Agent，让它根据已批准的规格和架构一次返回完整故事，再由协调器原样写入 `drafts/draft-v0.md`。禁止按场景拆分给多个 Agent、拼接多个正文候选或由协调器补写连接段。第一行使用 Markdown 一级标题。正文不得暴露规划标签、Loop ID、评分名称或审稿术语。

让每场的后果制造下一场的压力。通过主角的决定性选择兑现开篇承诺。使用已经铺设的意义或情绪完成结尾；不得为了制造惊讶而临时添加未经铺垫的机制。

```text
python <skill-dir>/scripts/loop_project.py record-draft <project-dir> <draft-path> --author-id <manuscript-agent-id>
python <skill-dir>/scripts/loop_project.py validate draft <project-dir> <draft-path>
```

在语义审稿前修复所有确定性错误。把风格警告视为需要检查的证据，不得自动当成缺陷。

### 4. 只审稿，不改稿

读取 [references/review-rubric.md](references/review-rubric.md)。向因果、转化、人物、文字四个隔离角色提供职责受限的只读快照，不得把预设结局答案泄露给盲审角色。因果角色先仅从正文和连续性台账推断核心结果、最强替代解释及决定性支持；其他角色只读取完成职责所需的承诺、人物或风格约束。每个角色必须为自己负责的每个评分维度重新引用当前稿证据，禁止沿用“上一版未变化”的结论。协调器把四份报告和聚合报告保存到 `reviews/review-vN/`。审稿期间不得修改正文，也不得让角色读取彼此报告。

```text
python <skill-dir>/scripts/loop_project.py validate review <project-dir> <aggregate-path>
python <skill-dir>/scripts/loop_project.py record-review <project-dir> <aggregate-path>
```

### 5. 每版只修一个层级

严格服从校验器返回的路由：

- `structure`：修复因果、场景顺序、状态变化或故事 Loop 递进；改稿前重新校验并批准架构。
- `promise`：修复开篇承诺、早期证明、兑现、超额兑现或结尾铺垫。
- `character`：修复欲望、缺陷、能动性、关键选择、代价或情绪结算。
- `prose`：修复具体性、压缩度、转场、节奏、声音或局部可读性。

每个新版本只允许一个正文 Agent 在上一份完整稿上执行指定层级的修订并返回完整新稿；审稿 Agent 不得直接改写。尽量保留不受影响的段落。正文 Agent 同时返回修订影响 JSON，声明来源与候选指纹、受影响维度、是否改变结构以及保留的不变量。影响超出当前路由时不得记录新版本；应重新审稿并回到更早层级。每个新版本只能记录一个修订层级：

```text
python <skill-dir>/scripts/loop_project.py record-draft <project-dir> <new-draft> --author-id <manuscript-agent-id> --layer <layer> --impact <impact-json>
```

每次修订后重新审稿。最多修订三轮。三轮后仍不合格时，保留最佳稿并生成 `stopped_report.json`；不得降低门槛冒充通过。

### 6. 定稿

仅当内容质量审稿达到≥44分（quality_ready）且语句通顺性终校（copyedit）通过（publication_ready）时定稿：

```text
python <skill-dir>/scripts/loop_project.py finalize <project-dir> <draft-path> <review-path>
```

返回定稿文件、正文字符数、修订次数、主题句和剩余的非阻断警告。

## 双阶段自动质量爬坡

### 内容质量 Loop（自动）

内容质量审稿通过后（semantic_pass=true），自动进入爬坡逻辑：

- **分数 ≥44**：直接进入 `quality_ready`，可启动 copyedit（语句通顺性终校）
- **分数 40-43**：进入优化区间。使用 `_compute_quality_auto_climb` 自动决定下一步：
  - 若 `optimization_budget` > 0：`auto_optimize` → 继续在 prose 层优化
  - 每次优化递减 `optimization_budget_remaining`（初始 2）
  - 跟踪 `quality_best_scores` 记录最高分对应的草稿
  - 若新稿得分降低：保留 best_draft，不更新 best_scores
  - 优化预算耗尽后仍未达 44：`quality_ready`（接受 best_draft）
- **分数 <40**（理论路径，semantic_pass 需要 ≥40）：
  - 若 `repair_budget` > 0：`auto_repair` → 继续修复
  - 修复预算耗尽：`stopped` → 生成 stopped_report.json

**状态跟踪字段**（state.json）：
- `quality_best_scores`：最佳审稿得分
- `best_draft_fingerprint`：最佳稿的 SHA256
- `quality_scores_history`：[{round, total_score, scores, route, draft_fingerprint}]
- `repair_budget_remaining`：初始 3
- `optimization_budget_remaining`：初始 2

最多 3 轮修复 + 2 轮优化。候选跌破40/目标维度未提高/关键维度下降/盲比不胜时自动恢复最佳稿。

### 语句通顺性终校 Loop（copyedit）

内容质量结束后锁定剧情 → 三个独立 Agent 阅读全文 → 裁决 Agent 确认合并问题 → 计算九项通顺性评分 → 单一校改 Agent 修改完整稿 → 三 Agent 复验 → 自动爬坡至 44/无安全机会/两轮预算耗尽。

**启动 copyedit：**
```text
python <skill-dir>/scripts/loop_project.py start-copyedit <project-dir>
```

生成 `copyedit/lock.json`，锁定人物身份、数字、时间、连续性事实、Loop 结论、决定性证据、人物关键选择、结尾含义、段落顺序。

**验证 copyedit 审稿：**
```text
python <skill-dir>/scripts/loop_project.py validate copyedit-review <project-dir> <aggregate>
```

**记录 copyedit 审稿：**
```text
python <skill-dir>/scripts/loop_project.py record-copyedit-review <project-dir> <aggregate>
```

**人工决策（仅在两轮自动爬坡后仍未通过时）：**
```text
python <skill-dir>/scripts/loop_project.py decide-copyedit <project-dir> approve-fallback|accept|reject
```

### 状态机

```
quality_ready → copyedit_reviewing → copyedit_revision_required
→ copyedit_reviewing（自动最多两轮）→ publication_ready → complete
```

两轮后仍未通过：copyedit_human_required。含义取舍：立即人工，不消耗自动预算。

### 九项 45 分通顺性评分

| 角色 | 维度 |
|---|---|
| syntax | grammar_integrity, collocation_word_order, precision_concision |
| coherence | referential_clarity, sentence_logic, local_transition |
| readaloud | rhythm_readability, repetition_naturalness, punctuation_dialogue_flow |

- 5 分：没有确认问题
- 4 分：存在可定位的提升机会（必须记录 gap_to_5、evidence、minimal_action、预期增益、信心、回归风险）
- 3 分及以下：存在影响首次理解的问题
- 5 分维度不得伪造提升机会
- blocker/major 问题必须使对应维度 ≤ 3

### 40 分合格硬门

- 九项总分 ≥ 40，每项 ≥ 4
- 无 blocker/major/high-confidence confirmed_must_fix
- 三份报告覆盖正文 100%
- 所有引用、位置、指纹有效
- 指代/对白归属/句间逻辑首次阅读即可理解
- 内容锁定检查全部通过
- 剩余问题最多两项（只能是不影响理解的风格建议）

## 始终遵守的约束

- 只保留一条核心阅读承诺，并在高潮中真正兑现。
- 让主角的选择和后果改变每场的知识、关系或风险。
- 让每条故事 Loop 先铺设、后兑现，并闭合所有已记录 Loop。
- 让主角的关键选择造成决定性结果。
- 严格区分阻断项和分数；高总分不能抵消断裂的因果或未兑现的承诺。
- 不得把作者预设答案当作正文已经证明的结论；最强替代解释未被排除时必须返回结构修订。
- 把所有受管初稿视为不可变版本；任一历史正文、清单或来源指纹失配时停止审稿和定稿。
- 保留规格和架构两个作者批准点；只有结构回退才要求重新批准架构。
- 脚本必须保持确定性且只使用 Python 标准库，不得调用外部模型 API。
- 所有项目产物必须使用可迁移的纯文本、JSON 或兼容 JSON 的 YAML。

## Pitfalls

### 已有设定导入时跳过选题阶段

当用户带着已有故事概念（无论是新想的还是从 v1 项目迁移的）进入时，直接从"填写 story_spec.yaml"开始，不要运行选题 Loop（三张候选卡 + 评分 + 选择）。选题 Loop 仅用于"用户有一个模糊主题但没有具体设定"的场景。

### 重跑必须完全重新开始

当用户说"重跑一遍""重新开始""不要省略任何步骤"时，必须：
1. 创建全新的项目目录（如 `记忆异常-v6`，不要覆写旧项目）
2. 每一步都真正派发独立子 Agent（正文、四角色盲审、copyedit 三审），不得用协调器伪造分数或复用旧稿
3. 不跳过流程中的任何阶段（spec→architecture→draft→review→climb→copyedit→finalize）
4. 即使知道故事概念相同，也必须让子 Agent 重新生成正文和审稿报告
5. 如果子 Agent 失败（超时/无返回），重试而非用旧版本替代

### continuity_ledger 校验

`validate architecture` 对连续性台账有三条硬约束：(1) states 内 scene_id 不能重复——同场景多事件合并为一条；(2) 每个 state.scene_id 必须被对应场景的 continuity_refs 引用；(3) states 按场景时间顺序排列。详见 `references/continuity-ledger-pitfalls.md`。

### canonical_hash 用于 report_fingerprints

aggregate.json 的 `report_fingerprints` 必须使用 **canonical_hash**（JSON 解析→排序键→json.dumps(separators=(",",":"))→SHA256），不是原始文件字节的 SHA256。正确流程：先写入四份角色报告到磁盘 → 用脚本的 `canonical_hash(value)` 函数（从 JSON 解析再序列化）计算每个文件的指纹 → 用这些值写入 aggregate.json。不要用 `hashlib.sha256(file_bytes).hexdigest()` 计算文件级哈希——会全员不匹配。

### aggregate report_fingerprints 键顺序

validator 检查 `report_fingerprints` 键必须恰好为 `['causality', 'character', 'conversion', 'prose']`（字母序）。Python dict 的插入顺序会被检查，如果键序不对会失败。最简单的方法是在写入 aggregate 前确保 dict 按这个顺序构建。

### findings severity 只允许三个值

`severity` 字段只允许：`"blocker"`、`"major"`、`"minor"`。不能用 `"info"`、`"positive"`、`"check"`、`"strength"`、`"observation"`。任何其他值都会导致 `validate review` 失败。正面的 finding 不需要写进 findings 数组——放在 summary 里即可。

### closure_excludes_stronger_alternative 与开放式结尾

当故事有**有意的开放式结尾**（两种解释都被正文充分支持），`closure_excludes_stronger_alternative` 测试会失败，导致 semantic_pass=false 和 route=structure。这不是故事缺陷而是设计选择。

**v3 自动覆盖机制**：`validate_review_bundle` 在 closure_excludes=false 时会检查 `loop_map.json`——如果 **所有** story_loop 的 `closure_test.remaining_uncertainty` 和 reader_promise 的 `payoff_test.remaining_uncertainty` 均为非空，系统自动将 closure_excludes 覆盖为 true，并在 warnings 中记录"intentional ambiguity acknowledged"。这样开放结尾在架构层面被声明后，自动流程不会被阻断。

**v4 最小闭合检查**：覆盖生效后，系统会进一步验证：从 `loop_map.json` 中提取所有 `required_conclusion`，用简单关键词匹配在正文中搜索。如果至少一条 `required_conclusion` 的核心词能在正文中找到 → 最小闭合通过。如果全部找不到 → 撤销覆盖（恢复 false），记录到 warnings："closure_excludes override reverted: no required_conclusion found in draft body"。

因此，在编写 loop_map 时务必为每条故事 Loop 和阅读承诺的 payoff_test 填写 `remaining_uncertainty` 字段——即使写"无"也比空着好。空着的 `remaining_uncertainty` 会导致覆盖不生效。

### 审稿必须真正派发独立子 Agent

四角色盲审（causality/conversion/character/prose）**必须**通过 `delegate_task` 派发独立子 Agent。协调器不得自己填写评分伪造审稿结果。关键要求：
- 每个子 Agent 只收到职责范围内的上下文（盲审：causality 不看预设结局，conversion 只看阅读承诺，character 只看主角信息，prose 只看风格和可信度约束）
- 子 Agent 返回后**立即检查**其 `draft_fingerprint` 是否与当前初稿的 SHA256 匹配——不匹配则丢弃，协调器降级重做
- 严禁用"分数应该和上次一样"为由跳过重新派发

### review_context 精确值

四份角色报告的 `review_context` 字段必须精确匹配脚本 `REVIEW_CONTEXTS` 中定义的值，否则 `validate review` 失败。实际值如下：

```
causality:   "draft_and_continuity_without_intended_resolution"
conversion:  "draft_and_reader_promise_without_resolution"
character:   "draft_and_character_contract_without_resolution"
prose:       "draft_style_and_credibility_constraints"
```

注意 causality 是 `without_intended_resolution`（含 intended），其他三个是 `without_resolution`（不含 intended）。这些字符串定义在 `scripts/loop_project.py` 的 `REVIEW_CONTEXTS` 常量中，是唯一权威来源。

### 新增 reader_tests（v4）

v4 在原有 10 个 reader_tests 基础上新增 3 个：

- **world_rules_consistent**（causality 角色，维度 causal_logic）：检查正文是否违反 `loop_map.world_rules` 中声明的世界规则。若 `world_rules` 为 null 或 `mechanism` 为 `"nothing_supernatural"` → 自动 true。否则需验证正文未违反 scope/limitations/invariants。
- **protagonist_behavior_is_credible**（character 角色，维度 protagonist_agency）：若 `StorySpec.protagonist.identity` 含专业元素，检查主角行为是否与该身份存在不可解释的矛盾。若矛盾已在 `character_loop.flaw` 中声明 → 视为有意设计，测试通过。无专业身份时自动 true。
- **mirror_character_fulfills_function**（character 角色，维度 protagonist_agency）：若 `loop_map.character_loop.mirror_character` 非 null，检查该镜像角色是否在故事中履行了其声明的 `story_function`。null 时自动 true。

所有新增测试向后兼容——空/null 时等同于旧行为。

### record-draft 修订时必须带 --impact

从 v2.1 起，第一次以后的 `record-draft`（即 `--layer` 非空时）**必须**附带 `--impact <json-file>`。impact JSON 需要以下字段（全部必填）：

```json
{"schema_version":2,"declared_layer":"prose","source_fingerprint":"<sha256>","candidate_fingerprint":"<sha256>","affected_dimensions":["prose_naturalness"],"structural_change":false,"change_summary":"描述修改了什么","preserved_invariants":["至少一项保持不变的内容"]}
```

缺少任意字段会拒绝导入。v0 初稿不需要 `--impact`（第一次导入）。

### record-draft 拒绝受管目录内的文件

`record-draft` 要求初稿文件位于项目 `drafts/` 目录**之外**。先从子 Agent 收到正文后保存到 `/tmp/` 或桌面等外部路径，再调用 `record-draft`。脚本会拒绝 `drafts/` 内的文件路径。

### dimension_evidence 必须非空

每份角色报告的 `dimension_evidence` 中，**每个被该角色评分的维度**都必须有至少一条证据字符串。空数组 `[]` 会导致 `validate review` 失败。即使分数不变的修订轮次，也必须写至少一条引用当前稿的证据（如 "v1: unchanged from v0 baseline"）。

### aggregate 禁止多余字段

`aggregate.json` 只能是文档列出的字段（schema_version, draft, draft_fingerprint, execution_mode, reports, report_fingerprints, synthesis, theme_sentence, warnings）。**严禁**在其中出现 `spec_fingerprint`、`architecture_fingerprint`、`total_score`、`scores` 等——这些由 validator 从角色报告中确定性计算。多一个字段都会导致 `validate review` 失败。

### copyedit 报告格式约束

copyedit 三份角色报告（syntax/coherence/readaloud）有独立于内容审稿的格式要求：
- 必须有 `agent_id`（非空字符串，三份报告的 agent_id 必须互不相同）
- 必须有 `spec_fingerprint` 字段
- 必须有 `issues`（数组，即使为空也要用 `[]`）
- 必须有 `coverage_percent`（0-100 的整数）
- 不能有 `findings`、`summary`、`architecture_fingerprint` 等字段

copyedit 的 aggregate 不能有 `adjudication_fingerprint` 字段。

### topic_differentiation 路由（v4 已修正）

`topic_differentiation < 4` 时 `route_review` 将其路由到 `premise` 层（v4 修正：此前错误路由到 promise）。premise 层不进行文本修订——系统设 stage 为 `premise_revision_required`，生成 `premise_revision_brief.json` 告知作者需修改 StorySpec 的 concept 字段。作者可通过 `reapprove-premise <project>` 重新验证规格后继续，或使用 `decide-quality <project> accept` 强制通过。

### 主观维度不阻断 semantic_pass（v4）

维度分为三类：

| 类型 | 维度 | semantic_pass |
|---|---|---|
| 硬阻断 | causal_logic, information_progression, promise_payoff | <4 → false |
| 软阻断 | prose_naturalness, ending_resonance, opening_conversion | <4 → false |
| 主观 | topic_differentiation, protagonist_agency, emotional_impact | <4 → warning，不阻断 |

主观维度低于 4 时仅记录 `subjective_dim_warning`，不影响 loop_acceptance 或 semantic_pass。topic loop 和 character_emotion loop 不再因主观维度分数过低而失败。

### premise_revision_required 轻量恢复（v4）

当 route=premise 时，系统不再直接 stopped，而是进入 `premise_revision_required` 状态，生成 `premise_revision_brief.json`。作者可：
- `reapprove-premise <project>`：修改 StorySpec concept 字段后重新验证规格，继续使用已有 draft
- `decide-quality <project> accept`：直接提升至 quality_ready（保留当前稿）

### decide-quality 对 premise 开放（v4）

`decide-quality accept` 现接受 `premise_revision_required` 和 `stopped`（含 premise_failure）两种状态。前提是 stopped_report 或 premise_revision_brief 存在。禁止在 premise_failure 来源的 stopped 上 accept 的限制已放宽——作者可以接受当前稿直接进入 copyedit。

### semantic_pass=false 时的爬坡预算（v4 已修正）

`semantic_pass=false` 时系统也会跟踪 `repair_budget_remaining` 和 `quality_scores_history`。每轮记录审稿分数到底历史，递减 repair_budget。预算耗尽或 version >= 3 时 stopped。structure 路由单独处理（走架构修订），不消耗 repair budget。

此前 v3 及更早版本只在 `semantic_pass=true` 时激活爬坡，导致 semantic_pass=false 时无限路由直到版本=3停止。v4 统一了两条路径的预算管理。

### 独立审稿分数波动是正常行为（v4 已分类处理）

不同子 Agent 实例对同一篇初稿可能给出不同分数。这是盲审的设计意图。v4 将维度分为硬阻断/软阻断/主观三类：主观维度（topic_differentiation, protagonist_agency, emotional_impact）的波动不阻断 semantic_pass，只生成 `subjective_dim_warning`。软阻断维度（prose_naturalness, ending_resonance, opening_conversion）的波动仍阻断，但 `scoring_volatility` 警告会标注前后轮次的分数变化。

协调器**不得**因为"上次给 5 今天给 3"就丢弃低分报告或用旧分数覆盖。如果作者不接受当前分数，正确的做法是重新派发审稿（新 Agent 实例），或对主观维度不满时使用 `decide-quality accept`。

### 调用了外部工具但连接失败时的降级

当用户明确要求"调用 claude 完成开发"但 `claude` CLI 二进制因 API 连接失败（ConnectionRefused / timeout）无法使用时，应立刻改用 `delegate_task` 派发编码子 Agent 完成相同任务，而非反复重试 CLI。理由是：(1) 用户的核心诉求是"用外部编码工具完成任务"，不是"必须用某个特定二进制"；(2) `delegate_task` 子 Agent 可以访问相同的文件系统和工具集，能够完成等价的代码修改；(3) 每轮重试的 180 秒超时让用户等待毫无价值。规则：CLI 工具失败一次后检查原因（API 不通、认证失效），若是环境性故障则立即切换 delegate_task。

### quality_auto_climb 有一轮延迟

`_compute_quality_auto_climb` 在 optimization_budget 从 1 递减到 0 的那一轮，返回的是 `auto_optimize`（因为函数调用时 budget 还是 1），state 记录为 `revision_required`。**下一轮**（budget 已为 0）函数才会返回 `quality_ready`。所以看到 `optimization_budget_remaining=0` + `stage=revision_required` 是正常的——需要再迭代一次。

### protagonist_agency 评分指导：调查异常 = 能动性

character Agent 可能将"核心异常事件超越主角控制"作为 `protagonist_agency` 的扣分点。这是一个常见的评分偏差——它混淆了"制造事件"和"响应事件"。**派发 character Agent 时，必须在上下文说明**：侦探不需要亲手杀人来证明能动性。主动发现线索、设计实验（△对照表、控制组、p值）、做出关键决策（终止治疗）、承担后果——这些都是充分的能动性证据。外部事件是否超越控制不扣分——**主角如何响应它们才是评分依据**。

不加入这条指导时，同一篇主角有完整调查链和心理抉择的稿子可能被判 3（"异常是外部强加的"）；加入后同稿可能升到 5（"每一环都是选择而非命运"）。

### 子Agent可能审错内容——收到报告后必须验证draft_fingerprint

在 v4 运行中实测发生：conversion 子 Agent 在其 4 次 API 调用中审阅了一篇**完全不同的故事**（末世循环题材），而非传入的《挂钟》初稿。它返回的 `draft_fingerprint` 与当前稿完全不匹配。协调器**必须在收到每个子Agent返回后立即检查**其 `draft_fingerprint` 是否与当前初稿的 SHA256 匹配。不匹配 → 丢弃该报告，协调器以 single_agent_fallback 模式自行生成该角色报告，并在 aggregate 的 warnings 中记录"<role>子Agent审错内容，已降级重做"。

### decide-quality 命令（v4 stopped→quality_ready 出口）

当系统在内容质量阶段 stopped（revision_budget_exhausted），但作者认为当前稿已足够好时，可以用新命令跳过剩余爬坡：

```text
python <skill-dir>/scripts/loop_project.py decide-quality <project> accept
```

这会将 stage 从 `stopped` 提升为 `quality_ready`，保留 best_draft，之后可以正常走 `start-copyedit` → copyedit → `finalize`。前提是 stopped 原因不是 `premise_failure`（概念性失败不能 accept）。

### scoring_volatility 警告（v4）

当同一篇稿子（draft_fingerprint 相同）的某个主观维度（topic_differentiation / protagonist_agency / emotional_impact）在前后两轮审稿中从 ≥4 降到 <4，`validate_review_bundle` 会自动添加 `scoring_volatility` warning。这不影响 semantic_pass——只是提醒协调器"这个维度的评分可能受 Agent 差异影响，而非稿子质量变化"。如果想消除波动，重新派发新的独立审稿 Agent，而不是手动调分。
