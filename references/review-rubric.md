# Review and revision rubric

Review in two passes. Complete deterministic checks first; then judge semantic quality. Never let a score cancel a blocker.

## Deterministic gates

Require all of the following:

- 1000–2000 non-whitespace body characters, excluding the Markdown title.
- Approved specification and outline fingerprints still match current files.
- One to seven scenes using all five phases in order.
- Exactly three clue-ledger entries with valid plant and payoff scenes.
- Non-empty knowledge, action, and cost deltas for every scene.
- No more than 15% of sentence characters are exact repeated sentences after first occurrence.
- No more than three recorded revisions.

These checks establish shape, not literary quality. Treat phrase lists, sentence length, paragraph length, “AI-like” constructions, and dialogue ratios as warnings unless the author explicitly promotes them to constraints.

## Semantic dimensions

Score each dimension from 0 to 5:

| Dimension | A score of 4–5 means |
| --- | --- |
| Opening effectiveness | The opening gives character, pressure, and a loop-relevant anomaly without background dumping. |
| Causal logic | Each inference and choice follows available evidence; the loop rule and exception stay consistent. |
| Information progression | Each repetition changes knowledge, action, and cost rather than replaying content. |
| Clue fairness | The twist relies on visible evidence that allowed a plausible earlier misreading. |
| Character choice | Desire and flaw shape decisions; escape requires a meaningful cost or reversal. |
| Prose naturalness | Details are specific, transitions unobtrusive, repetitions compressed, and voice non-generic. |
| Ending resonance | The false ending works, the final change expands meaning, and the character choice still matters. |

Pass only when:

- total score is at least 29/35;
- causal logic and clue fairness are at least 4;
- every other dimension is at least 3;
- every reader test is `true`;
- `blockers` is empty; and
- deterministic gates pass.

## Reader tests

Perform these as falsification attempts:

1. Remove the final twist. Does the apparent escape still form a credible ending?
2. Restore the twist. Do at least two earlier clues gain a second, text-supported meaning?
3. Trace each changed action backward. Is it caused by knowledge acquired in an earlier repetition?
4. Read only the first 40%. Is the true cause still uncertain rather than explicitly disclosed?
5. List everything needed for the final explanation. Did every item appear before the payoff?

Record `false` whenever evidence is mixed; explain it in a blocker or warning.

## Route the next action

Choose the earliest failing layer in this order:

1. `structure`: opening architecture, causal contradiction, information sequence, loop rule, or action not caused by knowledge.
2. `clue`: clue visibility, misreading, payoff, final reinterpretation, or unfair late information.
3. `character`: desire, flaw, motivation, choice, cost, or emotional consequence.
4. `prose`: compression, specificity, rhythm, transition, voice, or local opening delivery.

If any structure blocker exists, do not patch the manuscript. Set the state to `outline_revision_required`, propose a revised BeatSheet, and obtain renewed outline approval.

For all other layers, revise only passages evidenced by that layer. Preserve unaffected plot facts, clue meanings, character decisions, and voice. One draft version must record exactly one revision layer.

## Stop responsibly

After three revisions, stop regardless of score. Preserve the best draft and write `stopped_report.json` containing:

- the last deterministic result;
- the last semantic scores;
- unresolved blockers with evidence;
- layers already attempted; and
- the smallest author decision that could unblock a new cycle.

Do not lower thresholds, merge several layers into one emergency rewrite, or claim completion because the revision budget ended.

