# 项目产物契约（Schema v2）

使用以下可迁移的纯文本契约，使其他 Agent 无需读取对话历史即可继续项目。`story_spec.yaml` 使用 JSON 语法；它同时也是合法的 YAML 1.2，可由 Python 标准库解析。

## 目录

- [项目结构](#项目结构)
- [StorySpec](#storyspec)
- [LoopMap](#loopmap)
- [BeatSheet](#beatsheet)
- [初稿与定稿](#初稿与定稿)
- [ReviewReport](#reviewreport)
- [State](#state)
- [StoppedReport](#stoppedreport)

## 项目结构

```text
<project>/
├── story_spec.yaml
├── loop_map.json
├── beat_sheet.json
├── state.json
├── concepts/
│   ├── C1.json
│   ├── C2.json
│   ├── C3.json
│   └── selection.json
├── drafts/
│   ├── draft-vN.md
│   └── draft-vN.manifest.json
├── reviews/
│   └── review-vN/
│       ├── causality.json
│       ├── conversion.json
│       ├── character.json
│       ├── prose.json
│       └── aggregate.json
├── final.md
└── stopped_report.json
```

## StorySpec

在 `story_spec.yaml` 中保存经作者批准的创作边界：

```json
{
  "schema_version": 2,
  "language": "zh-CN",
  "target_length": {
    "min": 1000,
    "max": 3000,
    "unit": "non_whitespace_characters"
  },
  "genre": "主要题材或混合题材",
  "audience": "目标读者及阅读场景",
  "theme": "由结局证明且可以争辩的主题命题",
  "reader_promise": "故事承诺交付的单一体验或核心问题",
  "protagonist": {
    "identity": "具体身份与处境",
    "desire": "主角主动追求的结果",
    "flaw": "导致自我妨碍的信念或惯性反应"
  },
  "central_conflict": "让主角必须付出代价才能追求欲望的阻力",
  "target_emotion": "结尾希望留下的主导情绪",
  "ending_strategy": "揭示、选择、价值重估、反讽、释放或其他合适的兑现方式",
  "forbidden_tropes": ["本故事必须避免的捷径或发展方向"],
  "style_constraints": [],
  "credibility_constraints": ["需要保持可信的专业、事实或程序领域；没有时可为空"]
}
```

所有标量字符串必须非空。`forbidden_tropes` 至少包含一个非空字符串；`style_constraints` 与 `credibility_constraints` 可以为空。数组中的每一项都必须非空。不得强制使用反转、悬疑、重复事件、环形结尾或平台专用装置。已批准的规格控制所有下游工作。

## LoopMap

在 `loop_map.json` 中保存阅读承诺、信息递进和人物情绪 Loop：

```json
{
  "schema_version": 2,
  "reader_promise": {
    "hook": "开篇如何让核心承诺立即可感知",
    "proof": {"scene_id": "S2", "content": "证明故事确实会兑现开篇承诺的早期证据"},
    "payoff": {"scene_id": "S5", "content": "对核心承诺的决定性兑现"},
    "overdelivery": {"scene_id": "S6", "content": "在兑现之上增加的情绪、主题或解释价值"},
    "payoff_test": {
      "required_conclusion": "读者在结尾必须能够成立的最小结论",
      "strongest_competing_explanation": "不依赖作者意图时最有力的其他解释",
      "decisive_support": "正文中排除该替代解释的决定性行动、事实或后果",
      "support_scene": "S5",
      "remaining_uncertainty": "允许开放保留的部分；没有则写无"
    },
    "forbidden_drift": ["会抛弃或背叛核心承诺的发展方向"]
  },
  "story_loops": [
    {
      "id": "L1",
      "question_or_expectation": "读者等待了解、感受或看见解决的问题或期待",
      "pressure": "让问题升级的证据、对抗或风险",
      "action": "主角为此采取的行动",
      "cost": "行动带来的风险、损失或新增困难",
      "resolution": "用于闭合 Loop 的回答、重估或兑现",
      "setup_scene": "S1",
      "payoff_scene": "S5",
      "closure_test": {
        "required_conclusion": "本 Loop 必须成立的最小结论",
        "strongest_competing_explanation": "对同一证据最强的另一种解释",
        "decisive_support": "排除替代解释的具体支持",
        "support_scene": "S5",
        "remaining_uncertainty": "本 Loop 关闭后仍可保留的不确定性"
      }
    }
  ],
  "character_loop": {
    "desire": "必须与 StorySpec.protagonist.desire 完全一致",
    "flaw": "必须与 StorySpec.protagonist.flaw 完全一致",
    "habitual_choice": "由缺陷造成的早期惯性选择",
    "escalating_cost": "这一模式不断累积的代价",
    "break_choice": "抵抗或揭露缺陷的决定性选择",
    "settlement": "该选择造成的情绪结果"
  }
}
```

必须设置2–4条 `story_loops`，且 ID 互不相同。每条 Loop 必须先铺设、后兑现，两个场景引用都必须存在。核心兑现和每条 Loop 都必须完成替代解释测试；决定性支持不得晚于所声称的兑现场。开放结尾仍要写出必须成立的最小结论与允许保留的不确定性，不能用“开放”回避闭合中心冲突。`hook` 必须非空；`proof`、`payoff`、`overdelivery` 引用的场景顺序不得倒退。`forbidden_drift` 至少包含一个非空字符串。超额兑现可以深化、复杂化或从情绪上重构兑现，但不得撤销已经完成的兑现。

## BeatSheet

在 `beat_sheet.json` 中保存4–8场：

```json
{
  "schema_version": 2,
  "continuity_ledger": [
    {
      "id": "K1",
      "category": "time",
      "subject": "需要跨场保持一致的时间事实",
      "states": [
        {"scene_id": "S1", "value": "第一天", "change_reason": "故事起点"},
        {"scene_id": "S4", "value": "三天后", "change_reason": "明确经过三天"}
      ]
    }
  ],
  "scenes": [
    {
      "id": "S1",
      "phases": ["hook"],
      "target_share": 0.15,
      "goal": "主角在本场想得到什么",
      "obstacle": "什么阻止主角轻易得到结果",
      "choice": "主角采取的有后果的行动",
      "consequence": "本场不可逆的局部结果",
      "loop_ids": ["L1"],
      "continuity_refs": ["K1"],
      "promise_action": "本场如何承诺、施压、兑现或留下余味",
      "state_delta": {
        "knowledge": "新增了什么认知",
        "relationship": "人物关系发生了什么变化",
        "stakes": "什么变得更安全、更困难、被获得或受威胁"
      },
      "next_pull": "为什么下一场现在变得必要"
    }
  ]
}
```

每场的 `phases` 必须是非空数组，元素只能取自 `hook`、`pressure`、`escalation`、`decisive_payoff`、`aftertaste`。一场可以合并相邻阶段。把所有场景阶段展开后，阶段索引必须全局非递减，并且五个阶段都至少出现一次；相邻场景可以重复同一阶段，但架构不得倒退。这样既允许四场故事合并阶段，也允许六至八场故事延展某个阶段。

场景 ID 必须唯一。每场至少关联一个 `loop_id`，所有 ID 都必须指向 `LoopMap.story_loops`；每条故事 Loop 必须同时出现在自己的铺设场和兑现场。每场使用 `continuity_refs` 声明本场读取或改变的全局事实。`continuity_ledger` 保存1–12条最容易跨场冲突的事实，类别只使用 `time`、`count`、`location`、`identity`、`relationship`、`object`、`rule`、`knowledge`；每次状态变化必须按场景顺序记录新值和原因。每场必须包含非空的 `goal`、`obstacle`、`choice`、`consequence`、`promise_action`，并让 `state_delta` 至少一项非空。所有正数 `target_share` 的总和必须在1.0上下0.02误差内。除最后一场外，`next_pull` 必须非空；最后一场允许为空，因为完整短篇不必强行制造悬崖钩子。

## 初稿与定稿

把每个完整版本保存到 `drafts/draft-vN.md`：

```markdown
# 故事标题

这里只写故事正文，不得暴露 Schema 字段、场景 ID、审稿标签或规划笔记。
```

正文按去除空白后的字符数计数，排除 Markdown 标题，必须为1000–3000字。`draft-v0.md` 是第一版完整初稿。后续版本必须在 `state.json` 中只记录一个修订层级：`structure`、`promise`、`character` 或 `prose`。候选稿必须先保存在受管 `drafts/` 目录之外，再由协调器导入；禁止原地覆盖任何 `draft-vN.md`。

每个完整版本都必须配套 `draft-vN.manifest.json`，记录正文指纹、`authoring_mode: single_agent`、唯一的 `author_id`、来源版本和本轮唯一修订层级。缺少清单、指纹过期、作者标识为空或写作模式不是 `single_agent` 时，该稿不得进入审稿。清单只证明受控工作流的单作者责任边界；协调器仍必须禁止多人分场写作后冒充单作者稿。

```json
{
  "schema_version": 2,
  "draft": "draft-v1.md",
  "draft_fingerprint": "sha256",
  "authoring_mode": "single_agent",
  "author_id": "manuscript-agent",
  "source_draft": "drafts/draft-v0.md",
  "revision_layer": "structure",
  "revision_impact": {
    "schema_version": 2,
    "declared_layer": "structure",
    "source_fingerprint": "sha256",
    "candidate_fingerprint": "sha256",
    "affected_dimensions": ["causal_logic", "information_progression"],
    "structural_change": true,
    "change_summary": "本轮实际修改内容",
    "preserved_invariants": ["未改变的承诺、人物选择或声音"]
  }
}
```

`draft-v0.manifest.json` 的 `source_draft`、`revision_layer` 和 `revision_impact` 必须为 `null`。后续版本必须准确引用前一份完整稿，并记录本轮唯一修订层级和影响清单。影响维度超出当前路由、非结构修订声称改变结构、来源或候选指纹失配时不得记录。每次校验都重新核对全部历史稿和清单；任一旧版本被覆盖、缺失或篡改时，审稿与定稿立即停止。

只有当前初稿同时通过确定性校验和语义审稿时，才可原样复制为 `final.md`。定稿过程中不得静默改写。`final.md` 使用与初稿相同的标题加正文格式。

## ReviewReport

把当前初稿的审稿结果保存为四份独立角色报告和一份聚合报告。完整字段与权限边界见 [orchestration.md](orchestration.md)。每份角色报告只填写该角色负责的评分、读者测试、问题证据和修改动作：

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
    "causal_logic": ["当前稿的准确引用或位置"],
    "information_progression": ["当前稿的准确引用或位置"]
  },
  "reader_tests": {
    "actions_follow_causes": false,
    "continuity_is_consistent": false,
    "story_loops_close": false,
    "closure_excludes_stronger_alternative": false,
    "payoff_uses_prepared_elements": false
  },
  "blind_assessment": {
    "inferred_core_outcome": "不读取预设答案时，从正文推断出的核心结果",
    "strongest_competing_explanation": "正文仍可能支持的最强替代解释",
    "decisive_support": "真正排除替代解释的正文证据；缺少时说明缺少",
    "outcome_is_entailed": false
  },
  "findings": [
    {
      "severity": "blocker",
      "layer": "structure",
      "dimension": "causal_logic",
      "evidence": "引用原文或准确定位问题证据",
      "fix": "边界清晰的修复动作"
    }
  ],
  "summary": "本角色的独立结论"
}
```

九个维度最终都必须获得0–5的整数评分，但每个角色只能填写自己负责的维度。每个维度都必须在 `dimension_evidence` 中重新引用当前稿，不能写“沿用上一版”。因果角色必须在不读取预设结局答案的上下文中完成 `blind_assessment`；其布尔结论必须与替代解释读者测试一致。任一评分低于4或读者测试为 `false` 时，报告必须包含对应维度的问题证据和修改动作。只有转化角色可以使用 `premise`；它会停止当前正文周期，而不是创建第五个修订层级。协调器不得修改角色报告中的分数或测试结果。校验器从四份报告确定性派生 `total_score`、`semantic_pass`、`verdict`、`loop_acceptance`、阻断项和唯一的下一步 `route`；聚合报告不得重复填写这些计算字段。

## State

`state.json` 只允许脚本写入，其逻辑结构如下：

```json
{
  "schema_version": 2,
  "skill": "loop-short-story",
  "stage": "initialized",
  "concept_selection_fingerprint": null,
  "spec_fingerprint": null,
  "architecture_fingerprint": null,
  "current_draft": null,
  "current_review": null,
  "next_layer": null,
  "revision_count": 0,
  "layers_attempted": [],
  "history": []
}
```

不得手工修改批准状态、指纹、修订次数、路由或历史。新创意路径存在选题产物时，第一次规格批准会同时记录 `concept_selection_fingerprint`；直接导入已有设定时该字段可以为空。脚本会在记录第一份审稿后添加 `last_review_at`。这些指纹用于防止后续 Agent 静默修改创作决策。

使用以下状态转换：

```text
initialized
  → spec_approved
  → architecture_approved
  → reviewing
  → review_passed
  → complete

reviewing → architecture_revision_required → architecture_approved
reviewing → revision_required → reviewing（最多三次）
reviewing → stopped
```

必须取得两次明确的人工批准：第一次批准 `story_spec.yaml`，第二次共同批准 `loop_map.json` 和 `beat_sheet.json`。`spec_fingerprint` 保存第一次批准的指纹；`architecture_fingerprint` 保存两份架构文件共同生成的确定性指纹。任何规格变更都会使两枚批准和所有下游审稿失效。任何架构变更都会使架构批准和下游审稿失效。`current_review` 指向当前版本的 `reviews/review-vN/aggregate.json`。结构修订必须返回架构批准点；其他修订层级可以在不改变已批准架构的情况下，从 `revision_required` 生成新稿。根本选题失败或三轮修订耗尽都会进入 `stopped`，并把原因写入历史和 `stopped_report.json`。

## StoppedReport

三轮修订耗尽或选题必须重启时，生成 `stopped_report.json`，记录最后一次确定性校验、语义评分、尚未解决的阻断项及证据、已经尝试的层级、最佳稿件，以及开始新周期所需的最小作者决策。不得为了避免停止而降低验收门槛。
