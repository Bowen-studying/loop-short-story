# 多 Agent 编排契约

把多 Agent 当作角色隔离机制，而不是绑定某个产品的 API。宿主支持独立子 Agent 时默认并行派发；不支持时，由同一 Agent 按完全相同的角色顺序执行，并生成相同格式的产物。

## 目录

- [权限边界](#权限边界)
- [执行模式](#执行模式)
- [调度顺序](#调度顺序)
- [正文单作者约束](#正文单作者约束)
- [选题编排](#选题编排)
- [审稿编排](#审稿编排)
- [过期与隔离规则](#过期与隔离规则)

## 权限边界

协调器独占以下权限：

- 创建和修改项目文件；
- 写入 `state.json`；
- 执行规格与架构批准；
- 保存子 Agent 返回的 JSON；
- 汇总评分、选择修订路由和执行定稿。

子 Agent 只能读取协调器提供的只读快照，并返回一个符合契约的 JSON 对象。不得让子 Agent 直接修改项目目录、批准指纹、当前稿件、其他角色报告或状态文件。

## 执行模式

在所有协调产物中记录以下模式之一：

- `multi_agent`：宿主能够启动隔离的子 Agent。选题 Agent 彼此不可见；四个审稿 Agent 也彼此不可见。
- `single_agent_fallback`：宿主不支持子 Agent。协调器依次清空角色上下文，按照固定角色顺序独立执行，并生成与多 Agent 模式相同的文件、字段和验证结果。

不得因为使用降级模式而减少候选方案、合并审稿角色、降低评分门槛或跳过产物。

## 调度顺序

协调器按以下顺序执行，不得让角色跨越人工批准点：

```text
初始化项目
  → 并行派发 C1/C2/C3（或降级模式依次执行）
  → 协调评分并等待作者选择
  → 建立并批准 StorySpec
  → 建立并批准 LoopMap + BeatSheet
  → 派发一个正文 Agent 完成整篇初稿
  → 并行派发四个审稿角色（或降级模式依次执行）
  → 协调器聚合并运行 validate review
  → 派发一个正文 Agent 执行唯一修订层级
  → 重新独立审稿，直至通过或停止
```

调用任何角色时，只提供完成该角色任务所需的只读输入和字段契约。选题与审稿角色必须只返回一个 JSON 对象，不得包含 Markdown 代码围栏或额外说明；正文 Agent 必须只返回一篇带一级标题的完整 Markdown 稿件。协调器先验证返回结构，再写入项目文件。

## 正文单作者约束

每个完整稿件版本必须由一个且仅一个正文 Agent 完成：

- 初稿 Agent 一次读取已批准的 StorySpec、LoopMap 和 BeatSheet，返回完整的 Markdown 故事。
- 不得把不同场景分配给不同 Agent，不得让协调器拼接多个正文候选，也不得用投票选择段落。
- 协调器只校验并保存完整稿，不得代写连接段、统一文风或静默修复内容。
- 修订时，每个新版本也只能由一个正文 Agent 在上一份完整稿上处理唯一指定层级，并返回新的完整稿。
- 正文 Agent 把候选完整稿返回给协调器，不得直接打开或覆盖 `drafts/draft-vN.md`。协调器只从受管目录之外导入候选稿。
- 修订 Agent 同时返回修订影响 JSON；来源和候选指纹必须匹配，受影响维度不得超出当前路由。发现跨层变化时拒绝记录并返回更早层级。
- 四个审稿 Agent 只能诊断和提出修改动作，不能直接改写正文。

协调器调用 `record-draft` 时必须用 `--author-id` 记录正文 Agent。脚本为每版生成 `draft-vN.manifest.json`，并在审稿前校验单 Agent 模式、正文指纹、来源版本和修订层级。

宿主可以让同一个正文 Agent 连续负责各版本，以保持声音；也可以在版本之间更换 Agent，但同一版本不得多人合写。无论哪种方式，都必须保留完整的上一版作为修订输入。

## 选题编排

### 独立生成

向三个隔离角色分别提供相同的作者需求，但不得提供其他角色的候选方案。三个角色只返回一张选题卡，分别保存为：

```text
concepts/C1.json
concepts/C2.json
concepts/C3.json
```

每张选题卡使用以下结构：

```json
{
  "schema_version": 2,
  "candidate_id": "C1",
  "genre": "题材",
  "theme": "主题命题",
  "premise": "一句话核心设定",
  "hook": "可直接进入正文的具体钩子",
  "protagonist_pressure": "主角面临的即时压力",
  "central_choice": "主角最终必须作出的中心选择",
  "expected_payoff": "故事承诺交付的决定性结果",
  "target_emotion": "目标情绪",
  "short_form_fit": "为什么能在1000–3000字内完整兑现"
}
```

### 协调评分与作者选择

协调器只在收到三张卡后进行比较，不得把一个角色的创意交给另一个角色补写。按以下五项各评0–5分：

- `hook_clarity`
- `distinctiveness`
- `emotional_pressure`
- `visual_specificity`
- `short_form_feasibility`

把结果保存为 `concepts/selection.json`：

```json
{
  "schema_version": 2,
  "execution_mode": "multi_agent",
  "candidate_files": {
    "C1": "C1.json",
    "C2": "C2.json",
    "C3": "C3.json"
  },
  "candidate_fingerprints": {
    "C1": "sha256",
    "C2": "sha256",
    "C3": "sha256"
  },
  "scores": {
    "C1": {
      "hook_clarity": 0,
      "distinctiveness": 0,
      "emotional_pressure": 0,
      "visual_specificity": 0,
      "short_form_feasibility": 0
    },
    "C2": {
      "hook_clarity": 0,
      "distinctiveness": 0,
      "emotional_pressure": 0,
      "visual_specificity": 0,
      "short_form_feasibility": 0
    },
    "C3": {
      "hook_clarity": 0,
      "distinctiveness": 0,
      "emotional_pressure": 0,
      "visual_specificity": 0,
      "short_form_feasibility": 0
    }
  },
  "recommended_id": "C1",
  "selected_id": "C1",
  "selection_rationale": "推荐理由及作者选择记录"
}
```

由协调器展示三张选题卡和评分。作者可以选择非最高分方案；不得把“推荐”冒充“批准”。作者选择后，协调器据此填写 `story_spec.yaml`，并在第一次人工批准时锁定 StorySpec。

在建立 StorySpec 前运行 `validate concepts`。校验器必须确认三个候选均存在且互不重复、五项评分完整、候选与选择记录指纹一致、推荐方案具有最高总分，并且 `selected_id` 已记录作者选择。

## 审稿编排

### 四个独立角色

四个角色读取职责受限的当前快照，并且不得读取其他角色的报告。协调器可以向报告预填批准指纹，但不得因此把未授权内容暴露给角色：

| 角色 | 允许读取 | 负责评分 | 负责读者测试 | 允许的问题层级 |
| --- | --- | --- | --- | --- |
| `causality` | 当前正文、连续性台账；不得读取预设结局、Loop resolution、主题答案 | `causal_logic`、`information_progression` | `actions_follow_causes`、`continuity_is_consistent`、`story_loops_close`、`closure_excludes_stronger_alternative`、`payoff_uses_prepared_elements` | `structure` |
| `conversion` | 当前正文、核心阅读承诺；不得读取预设解决方式 | `topic_differentiation`、`opening_conversion`、`promise_payoff` | `opening_makes_promise_clear`、`early_proof_supports_promise` | `premise`、`promise` |
| `character` | 当前正文、主角欲望、缺陷和目标情绪；不得读取预设人物结算 | `protagonist_agency`、`emotional_impact` | `protagonist_choice_drives_result`、`ending_delivers_target_emotion` | `character` |
| `prose` | 当前正文、风格约束和可信度约束 | `prose_naturalness`、`ending_resonance` | `domain_language_is_credible` | `prose` |

因果角色先完成盲读：只根据正文推断核心结果，提出最强替代解释，并指出正文是否有决定性支持排除它。开放结尾也必须区分已经成立的最小结论和仍然开放的部分。协调器不得在角色返回前透露 StorySpec.theme、ending_strategy、阅读承诺的兑现答案、故事 Loop resolution、closure_test 或人物 settlement。

每个角色只填写自己负责的字段，不得替其他角色评分。角色报告结构如下：

```json
{
  "schema_version": 2,
  "role": "causality",
  "draft": "drafts/draft-v0.md",
  "draft_fingerprint": "sha256",
  "spec_fingerprint": "sha256",
  "architecture_fingerprint": "sha256",
  "review_context": "draft_and_continuity_without_intended_resolution",
  "scores": {
    "causal_logic": 0,
    "information_progression": 0
  },
  "dimension_evidence": {
    "causal_logic": ["当前稿准确证据"],
    "information_progression": ["当前稿准确证据"]
  },
  "reader_tests": {
    "actions_follow_causes": false,
    "continuity_is_consistent": false,
    "story_loops_close": false,
    "closure_excludes_stronger_alternative": false,
    "payoff_uses_prepared_elements": false
  },
  "blind_assessment": {
    "inferred_core_outcome": "从正文实际推断到的核心结果",
    "strongest_competing_explanation": "同一正文仍支持的最强替代解释",
    "decisive_support": "排除替代解释的正文支持；缺失时明确写缺失",
    "outcome_is_entailed": false
  },
  "findings": [
    {
      "severity": "blocker",
      "dimension": "causal_logic",
      "layer": "structure",
      "evidence": "引用原文或准确定位问题",
      "fix": "边界明确的修改动作"
    }
  ],
  "summary": "本角色的独立结论"
}
```

`severity` 只能使用 `blocker`、`major`、`minor`。只有 `blocker` 会进入阻断项，但较低评分或失败测试仍可让稿件失败。每个评分维度都必须在 `dimension_evidence` 中重新引用当前稿，禁止写“与上一版一致”来代替复核。任一评分低于4或读者测试为 `false` 时，必须存在对应维度的问题。每条问题必须包含原文证据和具体动作，不得只写抽象评价。

### 协调器聚合

把同一版本的四份报告和聚合报告放在同一目录：

```text
reviews/review-vN/
├── causality.json
├── conversion.json
├── character.json
├── prose.json
└── aggregate.json
```

协调器不得修改角色分数或测试结果。聚合报告只记录来源、快照和综合说明：

```json
{
  "schema_version": 2,
  "draft": "drafts/draft-v0.md",
  "draft_fingerprint": "sha256",
  "execution_mode": "multi_agent",
  "reports": {
    "causality": "causality.json",
    "conversion": "conversion.json",
    "character": "character.json",
    "prose": "prose.json"
  },
  "report_fingerprints": {
    "causality": "sha256",
    "conversion": "sha256",
    "character": "sha256",
    "prose": "sha256"
  },
  "synthesis": "跨角色问题之间的关系及最小修改范围",
  "theme_sentence": "故事最终证明的主题句",
  "warnings": []
}
```

总分、六个 Loop 的 `loop_acceptance`、通过结论、阻断项和修订路由全部由脚本从四份报告确定性计算，聚合报告不得重复填写或覆盖。

## 过期与隔离规则

- 四份角色报告必须针对同一份当前初稿，并记录完全相同的初稿、规格和架构指纹。
- `aggregate.json` 必须记录四份角色报告的指纹；任一角色报告在聚合后被修改，整组审稿立即过期。
- 缺少任一角色报告、角色重复、越权评分、越权读者测试、跨层级问题或指纹不一致都必须使 `validate review` 失败。
- 新初稿产生后，上一版本的全部角色报告和聚合报告都不得复用。
- 每次校验都重新验证所有历史稿及清单；任一旧稿被覆盖、清单失配、版本断号或状态历史不一致时，整组审稿立即失效。
- 报告声明的 `review_context` 必须与角色权限一致。因果报告的盲读结论必须与 `closure_excludes_stronger_alternative` 一致。
- 多 Agent 与单 Agent 降级模式执行相同校验；正文内容可以不同，契约和质量门槛必须相同。
