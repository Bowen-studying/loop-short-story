# Project contracts

Use these file names and schemas so another agent can resume the project without conversation history.

## Project layout

```text
<project>/
├── story_spec.yaml
├── beat_sheet.json
├── clue_ledger.json
├── state.json
├── drafts/
│   └── draft-vN.md
├── reviews/
│   └── review-vN.json
├── final.md
└── stopped_report.json
```

`story_spec.yaml` contains JSON syntax, which is valid YAML 1.2 and can be parsed with the Python standard library.

## StorySpec

```json
{
  "schema_version": 1,
  "language": "zh-CN",
  "target_length": {"min": 1000, "max": 2000, "unit": "non_whitespace_characters"},
  "theme": "A contestable statement expressed through the protagonist's choice",
  "protagonist": {
    "identity": "Concrete role and situation",
    "desire": "What they actively want",
    "flaw": "The self-defeating belief or habit"
  },
  "loop": {
    "trigger": "Observable event that starts or commits the loop",
    "reset": "Observable return point",
    "retained_memory": "What crosses resets",
    "rule": "The one governing rule",
    "exception": "The one permitted exception",
    "true_cause": "Why the loop exists"
  },
  "key_clues": ["clue one", "clue two", "clue three"],
  "red_herring": "A plausible wrong interpretation",
  "apparent_escape": "The method that seems to end the loop",
  "final_twist": "Existing evidence reinterpreted as a larger loop",
  "forbidden_tropes": ["At least one forbidden shortcut"],
  "style_constraints": []
}
```

All scalar strings except `style_constraints` must be non-empty. Require exactly three distinct clues, one rule, and one exception.

## BeatSheet

Store an array of one to seven scene objects in `beat_sheet.json`:

```json
[
  {
    "id": "S1",
    "phase": "anchor",
    "target_share": 0.10,
    "goal": "Immediate character goal",
    "conflict": "Force preventing it",
    "clue_ids": ["C1"],
    "delta": {
      "knowledge": "What becomes newly knowable",
      "action": "What changes because of that knowledge",
      "cost": "What becomes harder, lost, or risked"
    }
  }
]
```

Use all five phases in this order: `anchor`, `anomaly`, `rule`, `truth`, `false_escape_twist`. Scenes sharing a phase must remain contiguous. The three internal repetitions are `anomaly`, `rule`, and `truth`; their deltas must be especially concrete.

## ClueLedger

Store exactly three entries in `clue_ledger.json`:

```json
[
  {
    "id": "C1",
    "surface": "The concrete clue as perceived",
    "plant_scene": "S1",
    "misread_as": "Plausible initial explanation",
    "true_meaning": "Meaning after the reveal",
    "payoff_scene": "S5"
  }
]
```

Reference existing scene IDs. Plant a clue no later than its payoff. Use each clue ID in at least one BeatSheet scene.

## ReviewReport

```json
{
  "schema_version": 1,
  "draft": "draft-v0.md",
  "scores": {
    "opening_effectiveness": 0,
    "causal_logic": 0,
    "information_progression": 0,
    "clue_fairness": 0,
    "character_choice": 0,
    "prose_naturalness": 0,
    "ending_resonance": 0
  },
  "blockers": [
    {"layer": "structure", "evidence": "Quoted or precisely located evidence", "fix": "Bounded repair action"}
  ],
  "reader_tests": {
    "false_ending_stands_without_twist": false,
    "two_clues_gain_second_meaning": false,
    "actions_follow_knowledge": false,
    "truth_not_revealed_too_early": false,
    "twist_uses_existing_evidence": false
  },
  "theme_sentence": "One sentence stating what the story demonstrates",
  "warnings": []
}
```

Score every dimension with an integer from 0 to 5. Use blocker layers `structure`, `clue`, `character`, or `prose` only.

## State transitions

```text
initialized
  → spec_approved
  → outline_approved
  → drafting
  → reviewing
  → revising → reviewing (at most three times)
  → complete

reviewing → outline_revision_required → outline_approved
reviewing → stopped
```

`state.json` is script-owned. Never hand-edit fingerprints, revision counts, approvals, or history. Approved fingerprints prevent a later agent from silently changing creative decisions.

