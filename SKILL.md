---
name: write-loop-short-story
description: Create, review, and iteratively revise 1000–2000-character Chinese short fiction built around time loops, repeated-event variation, recursive endings, or circular narratives. Use when an author wants to develop a loop-story idea, turn an outline into a complete short story, audit an existing loop narrative, or run a controlled specification–outline–draft–review–revision workflow with human approval gates and deterministic validation.
---

# Write Loop Short Story

Build a Chinese loop-narrative short story through two nested loops: three escalating repetitions inside the story and a bounded review/revision cycle outside it. Preserve author control over the premise and architecture; use scripts only for deterministic checks.

## Select an entry route

- For a new idea, initialize a project and build `story_spec.yaml`.
- For an existing outline, import its decisions into `story_spec.yaml`, then continue at the specification gate.
- For an existing story, place it at `drafts/draft-v0.md`, infer a provisional specification and outline, clearly label all inference, and obtain both approvals before changing prose.
- For an existing skill project, read `state.json` first and resume from its recorded stage. Never silently regenerate approved artifacts.

Use the author's requested directory. If none is given, create `stories/<short-slug>/` under the current workspace. Locate scripts relative to this `SKILL.md`; do not hardcode a Codex-specific installation path. Use `python3` or `python`, whichever is available.

## Run the workflow

### 1. Establish the specification

Read [references/contracts.md](references/contracts.md). Initialize the project:

```text
python <skill-dir>/scripts/loop_project.py init <project-dir>
```

Complete `story_spec.yaml` from the author's intent. Ask only for decisions that materially affect theme, protagonist, loop rule, escape, or final reinterpretation. Do not write an outline or prose yet.

Run `validate spec`, show the author a compact summary of the theme, loop rule, exception, three clues, apparent escape, and final twist, then wait for explicit approval. Record it only after approval:

```text
python <skill-dir>/scripts/loop_project.py approve spec <project-dir>
```

Treat the approved specification as immutable. If it changes, invalidate all later approval and return here.

### 2. Establish the architecture

Read [references/loop-craft.md](references/loop-craft.md). Generate `beat_sheet.json` and `clue_ledger.json`; use no more than seven scenes and exactly three clues. Give every scene non-empty knowledge, action, and cost deltas.

Run `validate outline`, summarize the five phases and clue payoffs, then wait for the author's second explicit approval:

```text
python <skill-dir>/scripts/loop_project.py approve outline <project-dir>
```

Do not draft before both fingerprints are recorded.

### 3. Draft the complete story

Write the whole story once into `drafts/draft-v0.md`. Keep the title as the first Markdown heading; do not expose planning labels, deltas, clue IDs, or review language in the prose. Compress recurring scenes to their recognition anchor plus the changed choice and consequence.

Run:

```text
python <skill-dir>/scripts/loop_project.py record-draft <project-dir> <draft-path>
python <skill-dir>/scripts/loop_project.py validate draft <project-dir> <draft-path>
```

Fix objective failures before semantic review. Treat stylistic warnings as evidence to inspect, not automatic defects.

### 4. Review without rewriting

Read [references/review-rubric.md](references/review-rubric.md). Review the current draft as a skeptical first-time reader. Write only a structured report to `reviews/review-vN.json`; cite specific textual evidence for every blocker. Do not edit prose during review.

Validate the report without changing state, then record it to apply the routing decision:

```text
python <skill-dir>/scripts/loop_project.py validate review <project-dir> <review-path>
python <skill-dir>/scripts/loop_project.py record-review <project-dir> <review-path>
```

### 5. Revise one layer at a time

Follow the routing returned by `validate review`:

- `structure`: stop prose editing, revise the outline, validate it, and obtain renewed outline approval.
- `clue`: change only clue planting, misreading, payoff, and twist preparation.
- `character`: change only desire, flaw, choice, and emotional consequence.
- `prose`: change only opening delivery, compression, specificity, rhythm, and naturalness.

Preserve all unaffected passages where practical. Record each new version and its single layer:

```text
python <skill-dir>/scripts/loop_project.py record-draft <project-dir> <new-draft> --layer <layer>
```

Review again after each revision. Stop after three revisions. If the story still fails, leave the best draft intact and emit `stopped_report.json` with unresolved evidence and the next recommended author decision; do not lower thresholds or continue polishing indefinitely.

### 6. Finalize

When the objective draft checks and semantic review both pass, finalize without another rewrite:

```text
python <skill-dir>/scripts/loop_project.py finalize <project-dir> <draft-path> <review-path>
```

Return the final file, its character count, revision count, theme sentence, and any non-blocking warnings.

## Preserve these invariants

- Keep one main loop rule and one explicit exception.
- Make each repetition change knowledge, action, and cost.
- Plant every final explanation before its payoff; introduce no rescuer, technology, or world rule in the final twist.
- Separate blockers from scores. A high total never excuses a structural contradiction or unfair clue.
- Keep author approval at the specification and outline gates. Require renewed outline approval only after a structural rollback.
- Do not use external model APIs from the skill. Let the host agent write and reason; keep scripts deterministic and standard-library only.
- Keep all project artifacts portable plain text, JSON, or JSON-compatible YAML.
