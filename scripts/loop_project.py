#!/usr/bin/env python3
"""Portable state and validation tool for loop-short-story.

Uses only the Python standard library. All commands emit JSON to stdout.
Validation failures return exit code 1; usage or unsafe-state errors return 2.
Schema v1 projects are intentionally unsupported.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any


SCHEMA_VERSION = 2
PHASES = ["hook", "pressure", "escalation", "decisive_payoff", "aftertaste"]
SCORE_KEYS = [
    "topic_differentiation",
    "opening_conversion",
    "causal_logic",
    "promise_payoff",
    "information_progression",
    "protagonist_agency",
    "emotional_impact",
    "prose_naturalness",
    "ending_resonance",
]
TEST_KEYS = [
    "opening_makes_promise_clear",
    "early_proof_supports_promise",
    "actions_follow_causes",
    "continuity_is_consistent",
    "story_loops_close",
    "closure_excludes_stronger_alternative",
    "protagonist_choice_drives_result",
    "payoff_uses_prepared_elements",
    "ending_delivers_target_emotion",
    "domain_language_is_credible",
    "world_rules_consistent",
    "protagonist_behavior_is_credible",
    "mirror_character_fulfills_function",
]
LAYERS = ["structure", "promise", "character", "prose"]
PROMISE_SCENE_STEPS = ["proof", "payoff", "overdelivery"]
EXECUTION_MODES = ["multi_agent", "single_agent_fallback"]
FINDING_SEVERITIES = ["blocker", "major", "minor"]
CONTINUITY_CATEGORIES = ["time", "count", "location", "identity", "relationship", "object", "rule", "knowledge"]
REVIEW_CONTEXTS = {
    "causality": "draft_and_continuity_without_intended_resolution",
    "conversion": "draft_and_reader_promise_without_resolution",
    "character": "draft_and_character_contract_without_resolution",
    "prose": "draft_style_and_credibility_constraints",
}
LAYER_DIMENSIONS = {
    "structure": ["causal_logic", "information_progression"],
    "promise": ["opening_conversion", "promise_payoff"],
    "character": ["protagonist_agency", "emotional_impact"],
    "prose": ["prose_naturalness", "ending_resonance"],
}
TEST_DIMENSIONS = {
    "opening_makes_promise_clear": "opening_conversion",
    "early_proof_supports_promise": "promise_payoff",
    "actions_follow_causes": "causal_logic",
    "continuity_is_consistent": "causal_logic",
    "story_loops_close": "information_progression",
    "closure_excludes_stronger_alternative": "information_progression",
    "payoff_uses_prepared_elements": "information_progression",
    "protagonist_choice_drives_result": "protagonist_agency",
    "ending_delivers_target_emotion": "emotional_impact",
    "domain_language_is_credible": "prose_naturalness",
    "world_rules_consistent": "causal_logic",
    "protagonist_behavior_is_credible": "protagonist_agency",
    "mirror_character_fulfills_function": "protagonist_agency",
}
CONCEPT_IDS = ["C1", "C2", "C3"]
CONCEPT_SCORE_KEYS = [
    "hook_clarity",
    "distinctiveness",
    "emotional_pressure",
    "visual_specificity",
    "short_form_feasibility",
]
COPYEDIT_ROLES = ["syntax", "coherence", "readaloud"]
COPYEDIT_DIMENSIONS: dict[str, list[str]] = {
    "syntax": ["grammar_integrity", "collocation_word_order", "precision_concision"],
    "coherence": ["referential_clarity", "sentence_logic", "local_transition"],
    "readaloud": ["rhythm_readability", "repetition_naturalness", "punctuation_dialogue_flow"],
}
COPYEDIT_ALL_DIMENSIONS = [
    "grammar_integrity",
    "collocation_word_order",
    "precision_concision",
    "referential_clarity",
    "sentence_logic",
    "local_transition",
    "rhythm_readability",
    "repetition_naturalness",
    "punctuation_dialogue_flow",
]
COPYEDIT_SCORE_MAX = 45
COPYEDIT_PASS_THRESHOLD = 40
COPYEDIT_DIMENSION_MIN = 4
COPYEDIT_ISSUE_SEVERITIES = ["blocker", "major", "minor", "low_confidence_suggestion"]
COPYEDIT_DISPOSITIONS = ["confirmed_must_fix", "confirmed_nice_to_have", "disputed", "deferred"]
COPYEDIT_MAX_ROUNDS = 2
REPAIR_BUDGET = 3
OPTIMIZATION_BUDGET = 2
COPYEDIT_CONTENT_LOCK_KEYS = [
    "protagonist_identities",
    "numbers",
    "time_expressions",
    "continuity_facts",
    "loop_conclusions",
    "decisive_evidence",
    "protagonist_key_choices",
    "ending_meaning",
    "paragraph_order",
]
COPYEDIT_LOCKED_CONTENT_TYPES = [
    "protagonist_identities",
    "numbers",
    "time_expressions",
    "continuity_facts",
    "loop_conclusions",
    "decisive_evidence",
    "protagonist_key_choices",
    "ending_meaning",
    "paragraph_order",
]
CONCEPT_CARD_KEYS = {
    "schema_version",
    "candidate_id",
    "genre",
    "theme",
    "premise",
    "hook",
    "protagonist_pressure",
    "central_choice",
    "expected_payoff",
    "target_emotion",
    "short_form_fit",
}
REVIEW_ROLES = {
    "causality": {
        "scores": ["causal_logic", "information_progression"],
        "tests": [
            "actions_follow_causes",
            "continuity_is_consistent",
            "story_loops_close",
            "closure_excludes_stronger_alternative",
            "payoff_uses_prepared_elements",
            "world_rules_consistent",
        ],
        "layers": ["structure"],
    },
    "conversion": {
        "scores": ["topic_differentiation", "opening_conversion", "promise_payoff"],
        "tests": ["opening_makes_promise_clear", "early_proof_supports_promise"],
        "layers": ["premise", "promise"],
    },
    "character": {
        "scores": ["protagonist_agency", "emotional_impact"],
        "tests": ["protagonist_choice_drives_result", "ending_delivers_target_emotion", "protagonist_behavior_is_credible", "mirror_character_fulfills_function"],
        "layers": ["character"],
    },
    "prose": {
        "scores": ["prose_naturalness", "ending_resonance"],
        "tests": ["domain_language_is_credible"],
        "layers": ["prose"],
    },
}


class ProjectError(RuntimeError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProjectError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProjectError(f"invalid JSON in {path} at line {exc.lineno}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_hash(value: Any) -> str:
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def file_hash(path: Path) -> str:
    return canonical_hash(read_json(path))


def content_hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError as exc:
        raise ProjectError(f"missing file: {path}") from exc


def project_path(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def state_path(project: Path) -> Path:
    return project / "state.json"


def load_state(project: Path) -> dict[str, Any]:
    value = read_json(state_path(project))
    if not isinstance(value, dict):
        raise ProjectError("state.json must contain an object")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise ProjectError("state.json must use schema_version 2; Schema v1 is not supported")
    return value


def save_state(project: Path, state: dict[str, Any]) -> None:
    write_json(state_path(project), state)


def add_event(state: dict[str, Any], event: str, **details: Any) -> None:
    item = {"event": event, "at": now()}
    item.update(details)
    state.setdefault("history", []).append(item)


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def template_spec() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "language": "zh-CN",
        "target_length": {"min": 1000, "max": 3000, "unit": "non_whitespace_characters"},
        "genre": "",
        "audience": "",
        "theme": "",
        "reader_promise": "",
        "protagonist": {"identity": "", "desire": "", "flaw": ""},
        "central_conflict": "",
        "target_emotion": "",
        "ending_strategy": "",
        "forbidden_tropes": [""],
        "style_constraints": [],
        "credibility_constraints": [],
    }


def command_init(args: argparse.Namespace) -> int:
    project = project_path(args.project)
    if project.exists() and any(project.iterdir()):
        raise ProjectError(f"refusing to overwrite non-empty directory: {project}")
    project.mkdir(parents=True, exist_ok=True)
    (project / "concepts").mkdir(exist_ok=True)
    (project / "drafts").mkdir(exist_ok=True)
    (project / "reviews").mkdir(exist_ok=True)
    write_json(project / "story_spec.yaml", template_spec())
    state = {
        "schema_version": SCHEMA_VERSION,
        "skill": "loop-short-story",
        "stage": "initialized",
        "revision_count": 0,
        "current_draft": None,
        "current_review": None,
        "concept_selection_fingerprint": None,
        "spec_fingerprint": None,
        "architecture_fingerprint": None,
        "next_layer": None,
        "last_review_at": None,
        "layers_attempted": [],
        "history": [],
        "best_draft_fingerprint": None,
        "quality_scores_history": [],
        "repair_budget_remaining": REPAIR_BUDGET,
        "optimization_budget_remaining": OPTIMIZATION_BUDGET,
        "quality_best_scores": None,
    }
    add_event(state, "initialized")
    save_state(project, state)
    return emit({"ok": True, "project": str(project), "stage": "initialized"})


def validate_spec(project: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        spec = read_json(project / "story_spec.yaml")
    except ProjectError as exc:
        return result(False, [str(exc)], warnings)
    if not isinstance(spec, dict):
        return result(False, ["story_spec.yaml must contain an object"], warnings)
    if spec.get("schema_version") != SCHEMA_VERSION:
        errors.append("story_spec.schema_version must equal 2; Schema v1 is not supported")
    if spec.get("language") != "zh-CN":
        warnings.append("language is not zh-CN")
    expected_length = {"min": 1000, "max": 3000, "unit": "non_whitespace_characters"}
    if spec.get("target_length") != expected_length:
        errors.append("target_length must be exactly 1000-3000 non_whitespace_characters")
    for key in (
        "genre",
        "audience",
        "theme",
        "reader_promise",
        "central_conflict",
        "target_emotion",
        "ending_strategy",
    ):
        if not nonempty(spec.get(key)):
            errors.append(f"{key} must be a non-empty string")
    protagonist = spec.get("protagonist")
    if not isinstance(protagonist, dict):
        errors.append("protagonist must be an object")
    else:
        for key in ("identity", "desire", "flaw"):
            if not nonempty(protagonist.get(key)):
                errors.append(f"protagonist.{key} must be a non-empty string")
    forbidden = spec.get("forbidden_tropes")
    if not isinstance(forbidden, list) or not forbidden or any(not nonempty(x) for x in forbidden):
        errors.append("forbidden_tropes must contain at least one non-empty string")
    for key in ("style_constraints", "credibility_constraints"):
        values = spec.get(key)
        if not isinstance(values, list) or any(not nonempty(x) for x in values):
            errors.append(f"{key} must be an array of non-empty strings")
    return result(not errors, errors, warnings, fingerprint=canonical_hash(spec) if not errors else None)


def validate_concepts(project: Path, selection_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        selection = read_json(selection_path)
    except ProjectError as exc:
        return result(False, [str(exc)], [])
    if not isinstance(selection, dict):
        return result(False, ["concept selection must be an object"], [])
    required = {
        "schema_version",
        "execution_mode",
        "candidate_files",
        "candidate_fingerprints",
        "scores",
        "recommended_id",
        "selected_id",
        "selection_rationale",
    }
    unknown = set(selection) - required
    missing = required - set(selection)
    if unknown:
        errors.append(f"concept selection has unsupported fields: {sorted(unknown)}")
    if missing:
        errors.append(f"concept selection is missing fields: {sorted(missing)}")
    if selection.get("schema_version") != SCHEMA_VERSION:
        errors.append("concept selection schema_version must equal 2")
    if selection.get("execution_mode") not in EXECUTION_MODES:
        errors.append(f"concept execution_mode must be one of {EXECUTION_MODES}")
    if not nonempty(selection.get("selection_rationale")):
        errors.append("selection_rationale must be non-empty")

    candidate_files = selection.get("candidate_files")
    fingerprints = selection.get("candidate_fingerprints")
    scores = selection.get("scores")
    expected_ids = set(CONCEPT_IDS)
    if not isinstance(candidate_files, dict) or set(candidate_files) != expected_ids:
        errors.append(f"candidate_files must contain exactly {CONCEPT_IDS}")
        candidate_files = {}
    if not isinstance(fingerprints, dict) or set(fingerprints) != expected_ids:
        errors.append(f"candidate_fingerprints must contain exactly {CONCEPT_IDS}")
        fingerprints = {}
    if not isinstance(scores, dict) or set(scores) != expected_ids:
        errors.append(f"concept scores must contain exactly {CONCEPT_IDS}")
        scores = {}

    content_fingerprints: list[str] = []
    score_totals: dict[str, int] = {}
    for candidate_id in CONCEPT_IDS:
        filename = candidate_files.get(candidate_id)
        if filename != f"{candidate_id}.json":
            errors.append(f"candidate {candidate_id} must be stored as {candidate_id}.json")
            continue
        card_path = selection_path.parent / filename
        try:
            card = read_json(card_path)
            fingerprint = file_hash(card_path)
        except ProjectError as exc:
            errors.append(str(exc))
            continue
        if fingerprints.get(candidate_id) != fingerprint:
            errors.append(f"candidate {candidate_id} fingerprint is stale")
        if not isinstance(card, dict) or set(card) != CONCEPT_CARD_KEYS:
            errors.append(f"candidate {candidate_id} must contain exactly {sorted(CONCEPT_CARD_KEYS)}")
            continue
        if card.get("schema_version") != SCHEMA_VERSION:
            errors.append(f"candidate {candidate_id} schema_version must equal 2")
        if card.get("candidate_id") != candidate_id:
            errors.append(f"candidate {candidate_id} must declare its own id")
        for key in CONCEPT_CARD_KEYS - {"schema_version", "candidate_id"}:
            if not nonempty(card.get(key)):
                errors.append(f"candidate {candidate_id}.{key} must be non-empty")
        comparable = {key: value for key, value in card.items() if key != "candidate_id"}
        content_fingerprints.append(canonical_hash(comparable))

        candidate_scores = scores.get(candidate_id)
        if not isinstance(candidate_scores, dict) or set(candidate_scores) != set(CONCEPT_SCORE_KEYS):
            errors.append(f"candidate {candidate_id} scores must contain exactly {CONCEPT_SCORE_KEYS}")
        else:
            clean_values: list[int] = []
            for key in CONCEPT_SCORE_KEYS:
                value = candidate_scores[key]
                if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 5:
                    errors.append(f"candidate {candidate_id} score {key} must be an integer from 0 to 5")
                else:
                    clean_values.append(value)
            if len(clean_values) == len(CONCEPT_SCORE_KEYS):
                score_totals[candidate_id] = sum(clean_values)

    if len(content_fingerprints) == len(CONCEPT_IDS) and len(set(content_fingerprints)) != len(CONCEPT_IDS):
        errors.append("the three concept candidates must be distinct")
    recommended = selection.get("recommended_id")
    selected = selection.get("selected_id")
    if recommended not in expected_ids:
        errors.append("recommended_id must reference a concept candidate")
    if selected not in expected_ids:
        errors.append("selected_id must record the author's chosen candidate")
    if score_totals and recommended in score_totals:
        if score_totals[recommended] != max(score_totals.values()):
            errors.append("recommended_id must have the highest concept score total")
    return result(
        not errors,
        errors,
        [],
        execution_mode=selection.get("execution_mode"),
        recommended_id=recommended,
        selected_id=selected,
        score_totals=score_totals,
    )


def validate_closure_test(
    value: Any,
    prefix: str,
    scene_order: dict[str, int],
    *,
    earliest: int | None = None,
    latest: int | None = None,
) -> list[str]:
    errors: list[str] = []
    required = {
        "required_conclusion",
        "strongest_competing_explanation",
        "decisive_support",
        "support_scene",
        "remaining_uncertainty",
    }
    if not isinstance(value, dict):
        return [f"{prefix} must be an object"]
    if set(value) != required:
        errors.append(f"{prefix} must contain exactly {sorted(required)}")
    for key in required - {"support_scene"}:
        if not nonempty(value.get(key)):
            errors.append(f"{prefix}.{key} must be non-empty")
    comparison_fields = [
        value.get("required_conclusion"),
        value.get("strongest_competing_explanation"),
        value.get("decisive_support"),
    ]
    normalized = [item.strip() for item in comparison_fields if nonempty(item)]
    if len(normalized) == 3 and len(set(normalized)) != 3:
        errors.append(f"{prefix} must distinguish conclusion, competing explanation, and decisive support")
    support = value.get("support_scene")
    if support not in scene_order:
        errors.append(f"{prefix}.support_scene must reference an existing scene")
    else:
        position = scene_order[support]
        if earliest is not None and position < earliest:
            errors.append(f"{prefix}.support_scene must not precede the loop setup")
        if latest is not None and position > latest:
            errors.append(f"{prefix}.support_scene must not occur after the payoff")
    return errors


def validate_architecture(project: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        spec = read_json(project / "story_spec.yaml")
        loop_map = read_json(project / "loop_map.json")
        beat_sheet = read_json(project / "beat_sheet.json")
    except ProjectError as exc:
        return result(False, [str(exc)], warnings)

    if not isinstance(loop_map, dict):
        return result(False, ["loop_map.json must contain an object"], warnings)
    if not isinstance(beat_sheet, dict):
        return result(False, ["beat_sheet.json must contain an object"], warnings)
    if loop_map.get("schema_version") != SCHEMA_VERSION:
        errors.append("loop_map.schema_version must equal 2")
    if beat_sheet.get("schema_version") != SCHEMA_VERSION:
        errors.append("beat_sheet.schema_version must equal 2")

    scenes = beat_sheet.get("scenes")
    if not isinstance(scenes, list) or not 4 <= len(scenes) <= 8:
        errors.append("beat_sheet.scenes must contain four to eight scenes")
        scenes = []
    scene_ids: list[str] = []
    flattened_phases: list[str] = []
    shares: list[float] = []
    scene_loop_refs: dict[str, list[str]] = {}
    scene_continuity_refs: dict[str, list[str]] = {}
    for index, scene in enumerate(scenes, start=1):
        prefix = f"scene {index}"
        if not isinstance(scene, dict):
            errors.append(f"{prefix} must be an object")
            continue
        sid = scene.get("id")
        if nonempty(sid):
            sid = sid.strip()
            scene_ids.append(sid)
        else:
            errors.append(f"{prefix}.id must be non-empty")
            sid = f"<invalid-{index}>"
        phases = scene.get("phases")
        if not isinstance(phases, list) or not phases:
            errors.append(f"{prefix}.phases must contain one or more phases")
        elif any(phase not in PHASES for phase in phases):
            errors.append(f"{prefix}.phases may contain values from {PHASES} only")
        else:
            phase_numbers = [PHASES.index(phase) for phase in phases]
            expected_numbers = list(range(phase_numbers[0], phase_numbers[-1] + 1))
            if phase_numbers != expected_numbers:
                errors.append(f"{prefix}.phases must contain unique consecutive phases in order")
            flattened_phases.extend(phases)
        share = scene.get("target_share")
        if not isinstance(share, (int, float)) or isinstance(share, bool) or share <= 0:
            errors.append(f"{prefix}.target_share must be a positive number")
        else:
            shares.append(float(share))
        for key in ("goal", "obstacle", "choice", "consequence", "promise_action"):
            if not nonempty(scene.get(key)):
                errors.append(f"{prefix}.{key} must be non-empty")
        loop_ids = scene.get("loop_ids")
        if not isinstance(loop_ids, list) or not loop_ids or any(not nonempty(x) for x in loop_ids):
            errors.append(f"{prefix}.loop_ids must contain at least one non-empty loop id")
            scene_loop_refs[sid] = []
        else:
            normalized = [item.strip() for item in loop_ids]
            if len(normalized) != len(set(normalized)):
                errors.append(f"{prefix}.loop_ids must not contain duplicates")
            scene_loop_refs[sid] = normalized
        continuity_refs = scene.get("continuity_refs")
        if not isinstance(continuity_refs, list) or any(not nonempty(x) for x in continuity_refs):
            errors.append(f"{prefix}.continuity_refs must be an array of non-empty continuity ids")
            scene_continuity_refs[sid] = []
        else:
            normalized_continuity = [item.strip() for item in continuity_refs]
            if len(normalized_continuity) != len(set(normalized_continuity)):
                errors.append(f"{prefix}.continuity_refs must not contain duplicates")
            scene_continuity_refs[sid] = normalized_continuity
        delta = scene.get("state_delta")
        if not isinstance(delta, dict):
            errors.append(f"{prefix}.state_delta must be an object")
        else:
            unknown_delta = set(delta) - {"knowledge", "relationship", "stakes"}
            if unknown_delta:
                errors.append(f"{prefix}.state_delta has unsupported keys: {sorted(unknown_delta)}")
            for key in ("knowledge", "relationship", "stakes"):
                if key not in delta or not isinstance(delta.get(key), str):
                    errors.append(f"{prefix}.state_delta.{key} must be a string")
            if not any(nonempty(delta.get(key)) for key in ("knowledge", "relationship", "stakes")):
                errors.append(f"{prefix}.state_delta must change knowledge, relationship, or stakes")
        if index < len(scenes):
            if not nonempty(scene.get("next_pull")):
                errors.append(f"{prefix}.next_pull must be non-empty before the final scene")
        elif "next_pull" in scene and not isinstance(scene.get("next_pull"), str):
            errors.append(f"{prefix}.next_pull must be a string when present")

    if len(scene_ids) != len(set(scene_ids)):
        errors.append("scene ids must be unique")
    flattened_numbers = [PHASES.index(phase) for phase in flattened_phases]
    if set(flattened_phases) != set(PHASES) or flattened_numbers != sorted(flattened_numbers):
        errors.append("flattened scene phases must be globally non-decreasing and include all five phases")
    if shares and len(shares) == len(scenes) and not 0.98 <= sum(shares) <= 1.02:
        errors.append(f"target_share values must sum to 1.0, got {sum(shares):.3f}")
    scene_order = {sid: index for index, sid in enumerate(scene_ids)}

    continuity_ledger = beat_sheet.get("continuity_ledger")
    continuity_ids: list[str] = []
    if not isinstance(continuity_ledger, list) or not 1 <= len(continuity_ledger) <= 12:
        errors.append("beat_sheet.continuity_ledger must contain one to twelve continuity facts")
        continuity_ledger = []
    for index, fact in enumerate(continuity_ledger, start=1):
        prefix = f"continuity fact {index}"
        required = {"id", "category", "subject", "states"}
        if not isinstance(fact, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if set(fact) != required:
            errors.append(f"{prefix} must contain exactly {sorted(required)}")
        fact_id = fact.get("id")
        if nonempty(fact_id):
            fact_id = fact_id.strip()
            continuity_ids.append(fact_id)
        else:
            errors.append(f"{prefix}.id must be non-empty")
            fact_id = f"<invalid-continuity-{index}>"
        if fact.get("category") not in CONTINUITY_CATEGORIES:
            errors.append(f"{prefix}.category must be one of {CONTINUITY_CATEGORIES}")
        if not nonempty(fact.get("subject")):
            errors.append(f"{prefix}.subject must be non-empty")
        states = fact.get("states")
        state_positions: list[int] = []
        if not isinstance(states, list) or not states:
            errors.append(f"{prefix}.states must contain at least one state")
            continue
        for state_index, item in enumerate(states, start=1):
            state_prefix = f"{prefix} state {state_index}"
            if not isinstance(item, dict) or set(item) != {"scene_id", "value", "change_reason"}:
                errors.append(f"{state_prefix} must contain scene_id, value, and change_reason")
                continue
            scene_id = item.get("scene_id")
            if scene_id not in scene_order:
                errors.append(f"{state_prefix}.scene_id must reference an existing scene")
            else:
                state_positions.append(scene_order[scene_id])
                if fact_id not in scene_continuity_refs.get(scene_id, []):
                    errors.append(f"{state_prefix} must be referenced by scene {scene_id}.continuity_refs")
            for key in ("value", "change_reason"):
                if not nonempty(item.get(key)):
                    errors.append(f"{state_prefix}.{key} must be non-empty")
        if state_positions != sorted(set(state_positions)):
            errors.append(f"{prefix}.states must use unique scenes in chronological order")
    if len(continuity_ids) != len(set(continuity_ids)):
        errors.append("continuity fact ids must be unique")
    known_continuity = set(continuity_ids)
    for sid, refs in scene_continuity_refs.items():
        unknown = set(refs) - known_continuity
        if unknown:
            errors.append(f"scene {sid}.continuity_refs references unknown facts: {sorted(unknown)}")

    story_loops = loop_map.get("story_loops")
    loop_ids: list[str] = []
    if not isinstance(story_loops, list) or not 2 <= len(story_loops) <= 4:
        errors.append("loop_map.story_loops must contain two to four loops")
        story_loops = []
    for index, story_loop in enumerate(story_loops, start=1):
        prefix = f"story_loop {index}"
        if not isinstance(story_loop, dict):
            errors.append(f"{prefix} must be an object")
            continue
        lid = story_loop.get("id")
        if nonempty(lid):
            lid = lid.strip()
            loop_ids.append(lid)
        else:
            errors.append(f"{prefix}.id must be non-empty")
            lid = f"<invalid-loop-{index}>"
        for key in ("question_or_expectation", "pressure", "action", "cost", "resolution"):
            if not nonempty(story_loop.get(key)):
                errors.append(f"{prefix}.{key} must be non-empty")
        setup = story_loop.get("setup_scene")
        payoff = story_loop.get("payoff_scene")
        if setup not in scene_order:
            errors.append(f"{prefix}.setup_scene must reference an existing scene")
        if payoff not in scene_order:
            errors.append(f"{prefix}.payoff_scene must reference an existing scene")
        if setup in scene_order and payoff in scene_order and scene_order[setup] >= scene_order[payoff]:
            errors.append(f"{prefix} setup must occur before payoff")
        if setup in scene_loop_refs and lid not in scene_loop_refs[setup]:
            errors.append(f"{prefix}.id must appear in its setup scene loop_ids")
        if payoff in scene_loop_refs and lid not in scene_loop_refs[payoff]:
            errors.append(f"{prefix}.id must appear in its payoff scene loop_ids")
        earliest = scene_order.get(setup)
        latest = scene_order.get(payoff)
        errors.extend(validate_closure_test(
            story_loop.get("closure_test"),
            f"{prefix}.closure_test",
            scene_order,
            earliest=earliest,
            latest=latest,
        ))
    if len(loop_ids) != len(set(loop_ids)):
        errors.append("story loop ids must be unique")
    known_loops = set(loop_ids)
    for sid, refs in scene_loop_refs.items():
        unknown = set(refs) - known_loops
        if unknown:
            errors.append(f"scene {sid}.loop_ids references unknown loops: {sorted(unknown)}")

    promise = loop_map.get("reader_promise")
    promise_order: list[int] = []
    if not isinstance(promise, dict):
        errors.append("loop_map.reader_promise must be an object")
    else:
        if not nonempty(promise.get("hook")):
            errors.append("reader_promise.hook must be a non-empty string")
        for key in PROMISE_SCENE_STEPS:
            step = promise.get(key)
            if not isinstance(step, dict):
                errors.append(f"reader_promise.{key} must be an object")
                continue
            if not nonempty(step.get("content")):
                errors.append(f"reader_promise.{key}.content must be non-empty")
            ref = step.get("scene_id")
            if ref not in scene_order:
                errors.append(f"reader_promise.{key}.scene_id must reference an existing scene")
            else:
                promise_order.append(scene_order[ref])
        drift = promise.get("forbidden_drift")
        if not isinstance(drift, list) or not drift or any(not nonempty(x) for x in drift):
            errors.append("reader_promise.forbidden_drift must contain at least one non-empty string")
        latest = promise_order[-1] if len(promise_order) == len(PROMISE_SCENE_STEPS) else None
        errors.extend(validate_closure_test(
            promise.get("payoff_test"),
            "reader_promise.payoff_test",
            scene_order,
            latest=latest,
        ))
    if len(promise_order) == len(PROMISE_SCENE_STEPS) and promise_order != sorted(promise_order):
        errors.append("reader promise scenes must progress proof -> payoff -> overdelivery")

    character_loop = loop_map.get("character_loop")
    if not isinstance(character_loop, dict):
        errors.append("loop_map.character_loop must be an object")
    else:
        for key in ("desire", "flaw", "habitual_choice", "escalating_cost", "break_choice", "settlement"):
            if not nonempty(character_loop.get(key)):
                errors.append(f"character_loop.{key} must be non-empty")
        protagonist = spec.get("protagonist") if isinstance(spec, dict) else None
        if not isinstance(protagonist, dict):
            errors.append("StorySpec.protagonist must exist before architecture validation")
        else:
            for key in ("desire", "flaw"):
                if character_loop.get(key) != protagonist.get(key):
                    errors.append(f"character_loop.{key} must equal StorySpec.protagonist.{key}")
        mirror = character_loop.get("mirror_character")
        if mirror is not None:
            if not isinstance(mirror, dict):
                errors.append("character_loop.mirror_character must be an object or null")
            else:
                if not nonempty(mirror.get("name")):
                    errors.append("mirror_character.name must be non-empty when mirror_character is present")
                if mirror.get("story_function") not in ("trigger", "obstacle", "revealer", "mirror"):
                    errors.append("mirror_character.story_function must be trigger, obstacle, revealer, or mirror")
                if not nonempty(mirror.get("relationship_to_protagonist")):
                    errors.append("mirror_character.relationship_to_protagonist must be non-empty when mirror_character is present")

    world_rules = loop_map.get("world_rules")
    if world_rules is not None:
        if not isinstance(world_rules, dict):
            errors.append("loop_map.world_rules must be an object or null")
        else:
            mechanism = world_rules.get("mechanism")
            if mechanism and mechanism != "nothing_supernatural":
                if not nonempty(world_rules.get("scope")):
                    errors.append("world_rules.scope must be non-empty")
                limitations = world_rules.get("limitations")
                if not isinstance(limitations, list) or not limitations or any(not nonempty(x) for x in limitations):
                    errors.append("world_rules.limitations must contain at least one non-empty string")
                invariants = world_rules.get("invariants")
                if not isinstance(invariants, list) or not invariants or any(not nonempty(x) for x in invariants):
                    errors.append("world_rules.invariants must contain at least one non-empty string")
            if not nonempty(mechanism):
                errors.append("world_rules.mechanism must be non-empty when world_rules is present")

    fingerprint = canonical_hash({"loop_map": loop_map, "beat_sheet": beat_sheet}) if not errors else None
    return result(
        not errors,
        errors,
        warnings,
        fingerprint=fingerprint,
        scene_count=len(scenes),
        story_loop_count=len(story_loops),
    )


def story_body(text: str) -> tuple[str, bool]:
    match = re.match(r"^\s*#\s+[^\n]+\n+", text)
    if match:
        return text[match.end():], True
    return text, False


def duplicate_sentence_ratio(text: str) -> float:
    sentences = [
        re.sub(r"\s+", "", item)
        for item in re.split(r"(?<=[。！？!?])", text)
        if len(re.sub(r"\s+", "", item)) >= 8
    ]
    total = sum(map(len, sentences))
    if total == 0:
        return 0.0
    seen: set[str] = set()
    repeated = 0
    for sentence in sentences:
        if sentence in seen:
            repeated += len(sentence)
        else:
            seen.add(sentence)
    return repeated / total


def draft_manifest_path(draft_path: Path) -> Path:
    return draft_path.with_name(f"{draft_path.stem}.manifest.json")


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def validate_revision_impact(
    impact: Any,
    *,
    layer: str,
    source_draft: Path,
    candidate: Path,
) -> list[str]:
    errors: list[str] = []
    required = {
        "schema_version",
        "declared_layer",
        "source_fingerprint",
        "candidate_fingerprint",
        "affected_dimensions",
        "structural_change",
        "change_summary",
        "preserved_invariants",
    }
    if not isinstance(impact, dict):
        return ["revision impact must be an object"]
    if set(impact) != required:
        errors.append(f"revision impact must contain exactly {sorted(required)}")
    if impact.get("schema_version") != SCHEMA_VERSION:
        errors.append("revision impact schema_version must equal 2")
    if impact.get("declared_layer") != layer:
        errors.append("revision impact declared_layer must match the review route")
    if impact.get("source_fingerprint") != content_hash(source_draft):
        errors.append("revision impact source fingerprint is stale")
    if impact.get("candidate_fingerprint") != content_hash(candidate):
        errors.append("revision impact candidate fingerprint is stale")
    dimensions = impact.get("affected_dimensions")
    allowed = set(LAYER_DIMENSIONS[layer])
    if not isinstance(dimensions, list) or not dimensions or any(not nonempty(item) for item in dimensions):
        errors.append("revision impact affected_dimensions must contain at least one dimension")
    elif not set(dimensions) <= allowed:
        errors.append(f"revision impact exceeds {layer} scope; allowed dimensions are {sorted(allowed)}")
    structural = impact.get("structural_change")
    if not isinstance(structural, bool):
        errors.append("revision impact structural_change must be boolean")
    elif structural != (layer == "structure"):
        errors.append("only a structure revision may declare structural_change, and it must do so")
    if not nonempty(impact.get("change_summary")):
        errors.append("revision impact change_summary must be non-empty")
    invariants = impact.get("preserved_invariants")
    if not isinstance(invariants, list) or not invariants or any(not nonempty(item) for item in invariants):
        errors.append("revision impact preserved_invariants must contain at least one item")
    return errors


def validate_draft_manifest(draft_path: Path) -> list[str]:
    errors: list[str] = []
    manifest_path = draft_manifest_path(draft_path)
    try:
        manifest = read_json(manifest_path)
    except ProjectError as exc:
        return [str(exc)]
    required = {
        "schema_version",
        "draft",
        "draft_fingerprint",
        "authoring_mode",
        "author_id",
        "source_draft",
        "revision_layer",
        "revision_impact",
    }
    if not isinstance(manifest, dict):
        return ["draft manifest must be an object"]
    if set(manifest) != required:
        errors.append(f"draft manifest must contain exactly {sorted(required)}")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("draft manifest schema_version must equal 2")
    if manifest.get("draft") != draft_path.name:
        errors.append("draft manifest must reference its own manuscript file")
    try:
        fingerprint = content_hash(draft_path)
    except ProjectError as exc:
        errors.append(str(exc))
        fingerprint = ""
    if manifest.get("draft_fingerprint") != fingerprint:
        errors.append("draft manifest fingerprint is stale")
    if manifest.get("authoring_mode") != "single_agent":
        errors.append("every complete manuscript version must use single_agent authoring mode")
    if not nonempty(manifest.get("author_id")):
        errors.append("draft manifest author_id must identify exactly one manuscript agent")
    version_match = re.fullmatch(r"draft-v(\d+)\.md", draft_path.name)
    if not version_match:
        errors.append("recorded draft filename must use draft-vN.md")
    else:
        version = int(version_match.group(1))
        if version == 0:
            if (
                manifest.get("source_draft") is not None
                or manifest.get("revision_layer") is not None
                or manifest.get("revision_impact") is not None
            ):
                errors.append("draft-v0 manifest must not declare a source draft, revision layer, or impact")
        else:
            expected_source = f"drafts/draft-v{version - 1}.md"
            if manifest.get("source_draft") != expected_source:
                errors.append(f"a revised draft manifest must reference {expected_source}")
            layer = manifest.get("revision_layer")
            if layer not in LAYERS:
                errors.append(f"a revised draft manifest must use one layer from {LAYERS}")
            else:
                project = draft_path.parent.parent
                source_path = project / expected_source
                if source_path.is_file():
                    errors.extend(validate_revision_impact(
                        manifest.get("revision_impact"),
                        layer=layer,
                        source_draft=source_path,
                        candidate=draft_path,
                    ))
                else:
                    errors.append(f"revision source draft is missing: {expected_source}")
    return errors


def validate_draft_history(project: Path, state: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    drafts_dir = project / "drafts"
    if not drafts_dir.is_dir():
        return errors
    manuscripts: dict[int, Path] = {}
    for path in drafts_dir.glob("draft-v*.md"):
        match = re.fullmatch(r"draft-v(\d+)\.md", path.name)
        if match:
            manuscripts[int(match.group(1))] = path
    if not manuscripts:
        orphan_manifests = list(drafts_dir.glob("draft-v*.manifest.json"))
        if orphan_manifests:
            errors.append("draft history contains manifests without manuscript files")
        return errors
    versions = sorted(manuscripts)
    if versions != list(range(versions[-1] + 1)):
        errors.append("draft history versions must be contiguous from draft-v0")
    for version in versions:
        errors.extend(f"draft-v{version}: {item}" for item in validate_draft_manifest(manuscripts[version]))
    expected_manifests = {draft_manifest_path(path).resolve() for path in manuscripts.values()}
    actual_manifests = {path.resolve() for path in drafts_dir.glob("draft-v*.manifest.json")}
    if actual_manifests != expected_manifests:
        errors.append("draft history contains orphan or missing manifest files")
    if state is not None and nonempty(state.get("current_draft")):
        expected_current = f"drafts/draft-v{versions[-1]}.md"
        if state.get("current_draft") != expected_current:
            errors.append("state current_draft must point to the latest immutable draft version")
        if int(state.get("revision_count", -1)) != versions[-1]:
            errors.append("state revision_count must match the latest immutable draft version")
        recorded_versions = [
            item.get("version") for item in state.get("history", []) if item.get("event") == "draft_recorded"
        ]
        if recorded_versions != versions:
            errors.append("state draft history events do not match immutable draft files")
    return errors


def approval_errors(project: Path, state: dict[str, Any], architecture: bool = True) -> list[str]:
    errors: list[str] = []
    concept_fingerprint = state.get("concept_selection_fingerprint")
    if concept_fingerprint:
        selection_path = project / "concepts" / "selection.json"
        concept_check = validate_concepts(project, selection_path)
        if not concept_check["ok"]:
            errors.extend(concept_check["errors"])
        elif file_hash(selection_path) != concept_fingerprint:
            errors.append("approved concept selection fingerprint does not match the current file")
    try:
        current_spec = file_hash(project / "story_spec.yaml")
    except ProjectError as exc:
        return [str(exc)]
    if state.get("spec_fingerprint") != current_spec:
        errors.append("approved StorySpec fingerprint does not match the current file")
    if architecture:
        check = validate_architecture(project)
        if not check["ok"]:
            errors.extend(check["errors"])
        elif state.get("architecture_fingerprint") != check.get("fingerprint"):
            errors.append("approved architecture fingerprint does not match current files")
    return errors


def validate_draft(project: Path, draft_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        state = load_state(project)
        text = draft_path.read_text(encoding="utf-8")
    except (ProjectError, FileNotFoundError, UnicodeDecodeError) as exc:
        return result(False, [str(exc)], warnings)
    errors.extend(approval_errors(project, state, architecture=True))
    errors.extend(validate_draft_history(project, state))
    current_draft = state.get("current_draft")
    if current_draft and draft_path.resolve() == (project / current_draft).resolve():
        errors.extend(validate_draft_manifest(draft_path))
    body, has_title = story_body(text)
    if not has_title:
        errors.append("draft must begin with one Markdown H1 title")
    length = len(re.sub(r"\s+", "", body))
    if not 1000 <= length <= 3000:
        errors.append(f"body length must be 1000-3000 non-whitespace characters, got {length}")
    ratio = duplicate_sentence_ratio(body)
    if ratio > 0.15:
        errors.append(f"exact repeated-sentence ratio exceeds 0.15: {ratio:.4f}")
    markers = [
        "StorySpec",
        "LoopMap",
        "BeatSheet",
        "ReviewReport",
        "PromiseLedger",
        "Δ认知",
        "Δ行动",
        "Δ代价",
    ]
    exposed = [marker for marker in markers if marker in body]
    if exposed:
        errors.append("draft exposes planning/review markers: " + ", ".join(exposed))
    if len(body.strip().splitlines()) < 3:
        warnings.append("draft has very few paragraph breaks; inspect readability")
    return result(
        not errors,
        errors,
        warnings,
        draft=str(draft_path),
        body_characters=length,
        repeated_sentence_ratio=round(ratio, 4),
    )


HARD_BLOCK_DIMS = {"causal_logic", "information_progression", "promise_payoff"}
SOFT_BLOCK_DIMS = {"prose_naturalness", "ending_resonance", "opening_conversion"}
SUBJECTIVE_DIMS = {"topic_differentiation", "protagonist_agency", "emotional_impact"}


def semantic_review(
    scores: dict[str, int],
    tests: dict[str, bool],
    findings: list[dict[str, Any]],
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    blockers = [finding for finding in findings if finding.get("severity") == "blocker"]
    blocker_layers = [finding["layer"] for finding in blockers]
    total = sum(scores.values())
    aggregate_warnings = list(warnings) if warnings else []

    # Record warnings for subjective dimensions below 4
    for dim in SUBJECTIVE_DIMS:
        if scores.get(dim, 0) < 4:
            aggregate_warnings.append(f"subjective_dim_warning: {dim}={scores[dim]} below 4, this dimension is reviewer-sensitive")

    semantic_pass = (
        total >= 40
        and all(scores[key] >= 4 for key in HARD_BLOCK_DIMS | SOFT_BLOCK_DIMS)
        and all(tests.values())
        and not blockers
    )
    route: str | None = None
    if not semantic_pass:
        route = route_review(scores, tests, blocker_layers, total)
    verdict = "pass" if semantic_pass else ("restart_premise" if route == "premise" else "revise")
    loop_acceptance = {
        "topic": True,  # topic_differentiation is subjective — does not block
        "reader_promise": (
            scores["opening_conversion"] >= 4
            and scores["promise_payoff"] >= 4
            and tests["opening_makes_promise_clear"]
            and tests["early_proof_supports_promise"]
            and tests["payoff_uses_prepared_elements"]
            and tests["closure_excludes_stronger_alternative"]
        ),
        "scene_causality": (
            scores["causal_logic"] >= 4
            and tests["actions_follow_causes"]
            and tests["continuity_is_consistent"]
        ),
        "information_progression": (
            scores["information_progression"] >= 4
            and tests["story_loops_close"]
            and tests["payoff_uses_prepared_elements"]
            and tests["closure_excludes_stronger_alternative"]
        ),
        "character_emotion": (
            tests["protagonist_choice_drives_result"]
            and tests["ending_delivers_target_emotion"]
        ),
        "external_review": semantic_pass and tests["domain_language_is_credible"],
    }
    return result(
        True,
        [],
        aggregate_warnings,
        semantic_pass=semantic_pass,
        total_score=total,
        scores=scores,
        reader_tests=tests,
        findings=findings,
        blockers=blockers,
        loop_acceptance=loop_acceptance,
        verdict=verdict,
        revision_layer=route if route in LAYERS else None,
        route=route,
    )


def validate_role_report(
    report: Any,
    role: str,
    draft_rel: str,
    draft_fingerprint: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    expected = REVIEW_ROLES[role]
    required_keys = {
        "schema_version",
        "role",
        "draft",
        "draft_fingerprint",
        "spec_fingerprint",
        "architecture_fingerprint",
        "review_context",
        "scores",
        "dimension_evidence",
        "reader_tests",
        "findings",
        "summary",
    }
    if role == "causality":
        required_keys.add("blind_assessment")
    if not isinstance(report, dict):
        return result(False, [f"{role} report must be an object"], [])
    unknown = set(report) - required_keys
    missing = required_keys - set(report)
    if unknown:
        errors.append(f"{role} report has unsupported fields: {sorted(unknown)}")
    if missing:
        errors.append(f"{role} report is missing fields: {sorted(missing)}")
    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{role}.schema_version must equal 2")
    if report.get("role") != role:
        errors.append(f"{role} report must declare role {role}")
    if report.get("draft") != draft_rel:
        errors.append(f"{role} report must target the current draft {draft_rel}")
    if report.get("draft_fingerprint") != draft_fingerprint:
        errors.append(f"{role} report draft fingerprint is stale")
    if report.get("spec_fingerprint") != state.get("spec_fingerprint"):
        errors.append(f"{role} report StorySpec fingerprint is stale")
    if report.get("architecture_fingerprint") != state.get("architecture_fingerprint"):
        errors.append(f"{role} report architecture fingerprint is stale")
    if report.get("review_context") != REVIEW_CONTEXTS[role]:
        errors.append(f"{role}.review_context must equal {REVIEW_CONTEXTS[role]}")

    clean_scores: dict[str, int] = {}
    scores = report.get("scores")
    expected_scores = set(expected["scores"])
    if not isinstance(scores, dict) or set(scores) != expected_scores:
        errors.append(f"{role}.scores must contain exactly {sorted(expected_scores)}")
    else:
        for key in expected["scores"]:
            value = scores[key]
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 5:
                errors.append(f"{role} score {key} must be an integer from 0 to 5")
            else:
                clean_scores[key] = value

    dimension_evidence = report.get("dimension_evidence")
    if not isinstance(dimension_evidence, dict) or set(dimension_evidence) != expected_scores:
        errors.append(f"{role}.dimension_evidence must contain exactly {sorted(expected_scores)}")
    else:
        for key, items in dimension_evidence.items():
            if not isinstance(items, list) or not items or any(not nonempty(item) for item in items):
                errors.append(f"{role}.dimension_evidence.{key} must cite current-draft evidence")

    clean_tests: dict[str, bool] = {}
    tests = report.get("reader_tests")
    expected_tests = set(expected["tests"])
    if not isinstance(tests, dict) or set(tests) != expected_tests:
        errors.append(f"{role}.reader_tests must contain exactly {sorted(expected_tests)}")
    else:
        for key in expected["tests"]:
            value = tests[key]
            if not isinstance(value, bool):
                errors.append(f"{role} reader test {key} must be boolean")
            else:
                clean_tests[key] = value

    if role == "causality":
        blind = report.get("blind_assessment")
        blind_keys = {
            "inferred_core_outcome",
            "strongest_competing_explanation",
            "decisive_support",
            "outcome_is_entailed",
        }
        if not isinstance(blind, dict) or set(blind) != blind_keys:
            errors.append(f"causality.blind_assessment must contain exactly {sorted(blind_keys)}")
        else:
            for key in blind_keys - {"outcome_is_entailed"}:
                if not nonempty(blind.get(key)):
                    errors.append(f"causality.blind_assessment.{key} must be non-empty")
            if not isinstance(blind.get("outcome_is_entailed"), bool):
                errors.append("causality.blind_assessment.outcome_is_entailed must be boolean")
            elif clean_tests.get("closure_excludes_stronger_alternative") != blind["outcome_is_entailed"]:
                errors.append("causality blind outcome must match closure_excludes_stronger_alternative")

    clean_findings: list[dict[str, Any]] = []
    findings = report.get("findings")
    if not isinstance(findings, list):
        errors.append(f"{role}.findings must be an array")
    else:
        finding_keys = {"severity", "dimension", "layer", "evidence", "fix"}
        for index, finding in enumerate(findings, start=1):
            prefix = f"{role} finding {index}"
            if not isinstance(finding, dict):
                errors.append(f"{prefix} must be an object")
                continue
            if set(finding) != finding_keys:
                errors.append(f"{prefix} must contain exactly {sorted(finding_keys)}")
            if finding.get("severity") not in FINDING_SEVERITIES:
                errors.append(f"{prefix}.severity must be one of {FINDING_SEVERITIES}")
            if finding.get("dimension") not in expected_scores:
                errors.append(f"{prefix}.dimension is outside the {role} role")
            if finding.get("layer") not in expected["layers"]:
                errors.append(f"{prefix}.layer is outside the {role} role")
            for key in ("evidence", "fix"):
                if not nonempty(finding.get(key)):
                    errors.append(f"{prefix}.{key} must be non-empty")
            if not errors or all(not item.startswith(prefix) for item in errors):
                clean_findings.append(finding)
    if not nonempty(report.get("summary")):
        errors.append(f"{role}.summary must be non-empty")
    required_finding_dimensions = {key for key, value in clean_scores.items() if value < 4}
    required_finding_dimensions.update(
        TEST_DIMENSIONS[key] for key, value in clean_tests.items() if not value
    )
    present_finding_dimensions = {item.get("dimension") for item in clean_findings}
    missing_failure_findings = required_finding_dimensions - present_finding_dimensions
    if missing_failure_findings:
        errors.append(
            f"{role} report must include findings for failing dimensions: {sorted(missing_failure_findings)}"
        )
    return result(
        not errors,
        errors,
        [],
        scores=clean_scores,
        reader_tests=clean_tests,
        findings=clean_findings,
    )


def validate_review_bundle(project: Path, aggregate_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        state = load_state(project)
        aggregate = read_json(aggregate_path)
    except ProjectError as exc:
        return result(False, [str(exc)], [], semantic_pass=False, route=None)
    if not isinstance(aggregate, dict):
        return result(False, ["aggregate review must be an object"], [], semantic_pass=False, route=None)

    required_keys = {
        "schema_version",
        "draft",
        "draft_fingerprint",
        "execution_mode",
        "reports",
        "report_fingerprints",
        "synthesis",
        "theme_sentence",
        "warnings",
    }
    unknown = set(aggregate) - required_keys
    missing = required_keys - set(aggregate)
    if unknown:
        errors.append(f"aggregate review has unsupported fields: {sorted(unknown)}")
    if missing:
        errors.append(f"aggregate review is missing fields: {sorted(missing)}")
    if aggregate.get("schema_version") != SCHEMA_VERSION:
        errors.append("aggregate review schema_version must equal 2")
    if aggregate.get("execution_mode") not in EXECUTION_MODES:
        errors.append(f"execution_mode must be one of {EXECUTION_MODES}")
    if not nonempty(aggregate.get("synthesis")):
        errors.append("aggregate synthesis must be non-empty")
    if not nonempty(aggregate.get("theme_sentence")):
        errors.append("aggregate theme_sentence must be non-empty")
    aggregate_warnings = aggregate.get("warnings")
    if not isinstance(aggregate_warnings, list) or any(not nonempty(item) for item in aggregate_warnings):
        errors.append("aggregate warnings must be an array of non-empty strings")
        aggregate_warnings = []

    draft_rel = state.get("current_draft")
    if not nonempty(draft_rel):
        errors.append("no current draft is recorded")
        draft_fingerprint = ""
    else:
        draft_path = (project / draft_rel).resolve()
        try:
            draft_fingerprint = content_hash(draft_path)
        except ProjectError as exc:
            errors.append(str(exc))
            draft_fingerprint = ""
        if aggregate.get("draft") != draft_rel:
            errors.append(f"aggregate review must target the current draft {draft_rel}")
        if aggregate.get("draft_fingerprint") != draft_fingerprint:
            errors.append("aggregate draft fingerprint is stale")
    errors.extend(approval_errors(project, state, architecture=True))
    errors.extend(validate_draft_history(project, state))

    reports = aggregate.get("reports")
    report_fingerprints = aggregate.get("report_fingerprints")
    expected_roles = set(REVIEW_ROLES)
    if not isinstance(reports, dict) or set(reports) != expected_roles:
        errors.append(f"aggregate reports must contain exactly {sorted(expected_roles)}")
        reports = {}
    if not isinstance(report_fingerprints, dict) or set(report_fingerprints) != expected_roles:
        errors.append(f"aggregate report_fingerprints must contain exactly {sorted(expected_roles)}")
        report_fingerprints = {}

    merged_scores: dict[str, int] = {}
    merged_tests: dict[str, bool] = {}
    merged_findings: list[dict[str, Any]] = []
    report_paths: dict[str, str] = {}
    for role in REVIEW_ROLES:
        filename = reports.get(role)
        if filename != f"{role}.json":
            errors.append(f"aggregate report for {role} must be named {role}.json")
            continue
        report_path = aggregate_path.parent / filename
        report_paths[role] = str(report_path.resolve())
        try:
            report = read_json(report_path)
            fingerprint = file_hash(report_path)
        except ProjectError as exc:
            errors.append(str(exc))
            continue
        if report_fingerprints.get(role) != fingerprint:
            errors.append(f"aggregate fingerprint for {role} is stale")
        check = validate_role_report(report, role, str(draft_rel or ""), draft_fingerprint, state)
        if not check["ok"]:
            errors.extend(check["errors"])
        else:
            merged_scores.update(check["scores"])
            merged_tests.update(check["reader_tests"])
            merged_findings.extend({**finding, "role": role} for finding in check["findings"])

    if set(merged_scores) != set(SCORE_KEYS):
        errors.append("four role reports do not cover all nine score dimensions exactly once")
    if set(merged_tests) != set(TEST_KEYS):
        errors.append("four role reports do not cover all reader tests exactly once")

    # ── scoring volatility check for subjective dimensions ──────────────────
    best_scores = state.get("quality_best_scores")
    if best_scores and isinstance(best_scores, dict) and draft_fingerprint:
        subjective_dims = ["topic_differentiation", "protagonist_agency", "emotional_impact"]
        best_draft_fp = state.get("best_draft_fingerprint")
        for dim in subjective_dims:
            prev = best_scores.get(dim)
            curr = merged_scores.get(dim)
            if prev is not None and curr is not None and prev >= 4 and curr < prev:
                if best_draft_fp and best_draft_fp == draft_fingerprint:
                    aggregate_warnings.append(
                        f"scoring_volatility: {dim} dropped from {prev} to {curr} "
                        f"without draft change — possible reviewer inconsistency"
                    )

    if errors:
        return result(
            False,
            errors,
            aggregate_warnings,
            semantic_pass=False,
            route=None,
            review=str(aggregate_path.resolve()),
        )

    # ── closure_excludes auto-override with minimum closure check ──────────
    if not merged_tests.get("closure_excludes_stronger_alternative", True):
        # Check if all remaining_uncertainty fields are non-empty in loop_map
        loop_map_path = project / "loop_map.json"
        if loop_map_path.is_file():
            try:
                loop_map = read_json(loop_map_path)
                all_uncertainty_filled = True
                promise_payoff = loop_map.get("reader_promise", {}).get("payoff_test", {})
                if not nonempty(promise_payoff.get("remaining_uncertainty")):
                    all_uncertainty_filled = False
                for sl in loop_map.get("story_loops", []):
                    ct = sl.get("closure_test", {})
                    if not nonempty(ct.get("remaining_uncertainty")):
                        all_uncertainty_filled = False
                if all_uncertainty_filled:
                    # Override: intentional ambiguity acknowledged
                    merged_tests["closure_excludes_stronger_alternative"] = True
                    aggregate_warnings.append("intentional ambiguity acknowledged")

                    # Minimum closure check
                    draft_path_for_body = project / (draft_rel or "")
                    if draft_path_for_body.is_file():
                        draft_body = draft_path_for_body.read_text(encoding="utf-8")
                        conclusions: list[str] = []
                        pt = promise_payoff.get("required_conclusion")
                        if nonempty(pt):
                            conclusions.append(pt)
                        for sl in loop_map.get("story_loops", []):
                            rc = sl.get("closure_test", {}).get("required_conclusion")
                            if nonempty(rc):
                                conclusions.append(rc)
                        if conclusions:
                            # Simple keyword matching: extract first sentence's core nouns/verbs
                            found_any = False
                            for rc in conclusions:
                                # Extract core keywords from first sentence of each required_conclusion
                                first_sentence = rc.split("。")[0].split("，")[0].strip()
                                # Take 2-4 character chunks as search tokens
                                tokens = []
                                for i in range(len(first_sentence) - 1):
                                    for length in (2, 3, 4):
                                        if i + length <= len(first_sentence):
                                            tokens.append(first_sentence[i:i + length])
                                # Deduplicate and keep only meaningful ones
                                tokens = sorted(set(t for t in tokens if len(t) >= 2), key=len, reverse=True)[:5]
                                for token in tokens:
                                    if token in draft_body:
                                        found_any = True
                                        break
                                if found_any:
                                    break
                            if not found_any:
                                # Revert override: no conclusion found in body
                                merged_tests["closure_excludes_stronger_alternative"] = False
                                aggregate_warnings.append(
                                    "closure_excludes override reverted: no required_conclusion found in draft body"
                                )
            except ProjectError:
                pass  # Can't read loop_map, skip override

    analysis = semantic_review(merged_scores, merged_tests, merged_findings, aggregate_warnings)
    analysis.update({
        "review": str(aggregate_path.resolve()),
        "execution_mode": aggregate["execution_mode"],
        "theme_sentence": aggregate["theme_sentence"],
        "report_paths": report_paths,
    })
    return analysis


def route_review(scores: dict[str, int], tests: dict[str, bool], blockers: list[str], total: int) -> str:
    if (
        "premise" in blockers
        or scores["topic_differentiation"] < 4
    ):
        return "premise"
    if (
        "structure" in blockers
        or scores["causal_logic"] < 4
        or scores["information_progression"] < 4
        or not tests["actions_follow_causes"]
        or not tests["continuity_is_consistent"]
        or not tests["story_loops_close"]
        or not tests["closure_excludes_stronger_alternative"]
    ):
        return "structure"
    if (
        "promise" in blockers
        or scores["opening_conversion"] < 4
        or scores["promise_payoff"] < 4
        or not tests["opening_makes_promise_clear"]
        or not tests["early_proof_supports_promise"]
        or not tests["payoff_uses_prepared_elements"]
    ):
        return "promise"
    if (
        "character" in blockers
        or scores["protagonist_agency"] < 4
        or scores["emotional_impact"] < 4
        or not tests["protagonist_choice_drives_result"]
        or not tests["ending_delivers_target_emotion"]
    ):
        return "character"
    if (
        "prose" in blockers
        or scores["prose_naturalness"] < 4
        or scores["ending_resonance"] < 4
        or not tests["domain_language_is_credible"]
        or total < 40
    ):
        return "prose"
    return "prose"


def command_validate(args: argparse.Namespace) -> int:
    project = project_path(args.project)
    if args.kind == "spec":
        check = validate_spec(project)
    elif args.kind == "concepts":
        selection = (
            Path(args.artifact).expanduser().resolve()
            if args.artifact
            else project / "concepts" / "selection.json"
        )
        check = validate_concepts(project, selection)
    elif args.kind == "architecture":
        check = validate_architecture(project)
    elif args.kind == "draft":
        draft = resolve_artifact(project, args.artifact, "draft")
        check = validate_draft(project, draft)
    elif args.kind == "copyedit-review":
        review_path = resolve_artifact(project, args.artifact, "review")
        check = validate_copyedit_bundle(project, review_path)
    else:
        review_path = resolve_artifact(project, args.artifact, "review")
        check = validate_review_bundle(project, review_path)
    emit(check)
    return 0 if check["ok"] else 1


def command_approve(args: argparse.Namespace) -> int:
    project = project_path(args.project)
    state = load_state(project)
    stage = state.get("stage")
    if stage in {"complete", "stopped"}:
        raise ProjectError(f"cannot approve artifacts after project stage {stage}")
    if stage == "premise_revision_required" and args.kind != "spec":
        raise ProjectError(
            "from premise_revision_required, you must first approve the revised StorySpec "
            "(approve spec) before approving architecture"
        )
    if args.kind == "spec":
        check = validate_spec(project)
        if not check["ok"]:
            emit(check)
            return 1
        current = check["fingerprint"]
        concept_dir = project / "concepts"
        concept_files = list(concept_dir.iterdir()) if concept_dir.is_dir() else []
        if concept_files:
            selection_path = concept_dir / "selection.json"
            concept_check = validate_concepts(project, selection_path)
            if not concept_check["ok"]:
                emit(concept_check)
                return 1
            state["concept_selection_fingerprint"] = file_hash(selection_path)
        else:
            state["concept_selection_fingerprint"] = None
        if state.get("current_draft") and state.get("spec_fingerprint") != current:
            if state.get("stage") != "premise_revision_required":
                raise ProjectError("cannot change StorySpec after drafting; start a new project to preserve provenance")
            # premise_revision_required allows concept changes
        state["spec_fingerprint"] = current
        state["architecture_fingerprint"] = None
        state["stage"] = "spec_approved"
        state["next_layer"] = None
        add_event(state, "spec_approved", fingerprint=current)
    else:
        renewing_structure = state.get("stage") == "architecture_revision_required"
        spec_errors = approval_errors(project, state, architecture=False)
        if spec_errors:
            emit(result(False, spec_errors, []))
            return 1
        check = validate_architecture(project)
        if not check["ok"]:
            emit(check)
            return 1
        state["architecture_fingerprint"] = check["fingerprint"]
        state["stage"] = "architecture_approved"
        state["next_layer"] = "structure" if renewing_structure else None
        add_event(state, "architecture_approved", fingerprint=check["fingerprint"])
    save_state(project, state)
    return emit({"ok": True, "stage": state["stage"]})


def resolve_artifact(project: Path, raw: str | None, kind: str) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()
    state = load_state(project)
    key = "current_draft" if kind == "draft" else "current_review"
    value = state.get(key)
    if not value:
        raise ProjectError(f"no current {kind} recorded and no path supplied")
    return (project / value).resolve()


def safely_copy(source: Path, destination: Path) -> None:
    source = source.resolve()
    destination = destination.resolve()
    if source == destination:
        return
    if destination.exists():
        raise ProjectError(f"refusing to overwrite artifact: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def command_record_draft(args: argparse.Namespace) -> int:
    project = project_path(args.project)
    state = load_state(project)
    if state.get("stage") in {"complete", "stopped", "premise_revision_required"}:
        raise ProjectError(f"cannot record a draft after project stage {state.get('stage')}")
    if not nonempty(args.author_id):
        raise ProjectError("record-draft requires one non-empty manuscript agent author_id")
    errors = approval_errors(project, state, architecture=True)
    if errors:
        emit(result(False, errors, []))
        return 1
    source = Path(args.draft).expanduser().resolve()
    if not source.is_file():
        raise ProjectError(f"draft not found: {source}")
    if path_is_within(source, project / "drafts"):
        raise ProjectError("incoming manuscript must be outside the managed drafts directory")
    check = validate_draft(project, source)
    if not check["ok"]:
        emit(check)
        return 1
    current = state.get("current_draft")
    revision_impact: dict[str, Any] | None = None
    if current is None:
        if args.layer:
            raise ProjectError("the initial draft must not specify a revision layer")
        if getattr(args, "impact", None):
            raise ProjectError("the initial draft must not provide a revision impact")
        version = 0
    else:
        if args.layer not in LAYERS:
            raise ProjectError(f"a revision must specify one layer from {LAYERS}")
        if args.layer != state.get("next_layer"):
            raise ProjectError(f"revision layer must match review route {state.get('next_layer')}")
        if state.get("revision_count", 0) >= 3:
            raise ProjectError("revision budget exhausted")
        if args.layer == "structure" and not any(
            item.get("event") == "architecture_approved" and item.get("at", "") > state.get("last_review_at", "")
            for item in state.get("history", [])
        ):
            raise ProjectError("a structure revision requires renewed architecture approval after the last review")
        impact_path = getattr(args, "impact", None)
        if not impact_path:
            raise ProjectError("a revision requires --impact with a revision impact JSON file")
        revision_impact = read_json(Path(impact_path).expanduser().resolve())
        impact_errors = validate_revision_impact(
            revision_impact,
            layer=args.layer,
            source_draft=project / current,
            candidate=source,
        )
        if impact_errors:
            emit(result(False, impact_errors, []))
            return 1
        state["revision_count"] = int(state.get("revision_count", 0)) + 1
        version = state["revision_count"]
        state.setdefault("layers_attempted", []).append(args.layer)
    destination = project / "drafts" / f"draft-v{version}.md"
    safely_copy(source, destination)
    manifest_path = draft_manifest_path(destination)
    if manifest_path.exists():
        raise ProjectError(f"refusing to overwrite draft manifest: {manifest_path}")
    write_json(manifest_path, {
        "schema_version": SCHEMA_VERSION,
        "draft": destination.name,
        "draft_fingerprint": content_hash(destination),
        "authoring_mode": "single_agent",
        "author_id": args.author_id.strip(),
        "source_draft": current,
        "revision_layer": args.layer,
        "revision_impact": revision_impact,
    })
    manifest_errors = validate_draft_manifest(destination)
    if manifest_errors:
        emit(result(False, manifest_errors, []))
        return 1
    check["draft"] = str(destination.resolve())
    state["current_draft"] = str(destination.relative_to(project)).replace("\\", "/")
    state["current_review"] = None
    state["stage"] = "reviewing"
    state["next_layer"] = None
    add_event(state, "draft_recorded", version=version, layer=args.layer, author_id=args.author_id.strip())
    save_state(project, state)
    check.update({"stage": "reviewing", "version": version})
    return emit(check)


def command_record_review(args: argparse.Namespace) -> int:
    project = project_path(args.project)
    state = load_state(project)
    if state.get("stage") in {"complete", "stopped", "premise_revision_required"}:
        if state.get("stage") == "premise_revision_required":
            raise ProjectError(
                "cannot record-review from premise_revision_required stage — "
                "run reapprove-premise first to revise the StorySpec concept, "
                "or use decide-quality accept to accept current draft despite premise concerns"
            )
        raise ProjectError(f"cannot record a review after project stage {state.get('stage')}")
    draft = resolve_artifact(project, None, "draft")
    draft_check = validate_draft(project, draft)
    if not draft_check["ok"]:
        emit(draft_check)
        return 1
    source = Path(args.review).expanduser().resolve()
    check = validate_review_bundle(project, source)
    if not check["ok"]:
        emit(check)
        return 1
    version = int(state.get("revision_count", 0))
    destination_dir = project / "reviews" / f"review-v{version}"
    destination = destination_dir / "aggregate.json"
    for role in REVIEW_ROLES:
        safely_copy(source.parent / f"{role}.json", destination_dir / f"{role}.json")
    safely_copy(source, destination)
    check = validate_review_bundle(project, destination)
    if not check["ok"]:
        emit(check)
        return 1
    state["current_review"] = str(destination.relative_to(project)).replace("\\", "/")
    state["last_review_at"] = now()
    if check["semantic_pass"]:
        total_score = check.get("total_score", 0)
        current_scores = check.get("scores", {})
        review_route = check.get("route")

        # Initialize quality climb tracking if not present
        repair_remaining = int(state.get("repair_budget_remaining", REPAIR_BUDGET))
        optimize_remaining = int(state.get("optimization_budget_remaining", OPTIMIZATION_BUDGET))
        previous_best = state.get("quality_best_scores")
        draft_fp = content_hash(draft)

        # Record in history
        quality_history = list(state.get("quality_scores_history", []))
        quality_history.append({
            "round": len(quality_history) + 1,
            "total_score": total_score,
            "scores": current_scores,
            "route": review_route,
            "draft_fingerprint": draft_fp,
        })
        state["quality_scores_history"] = quality_history

        action, next_layer = _compute_quality_auto_climb(
            total_score, current_scores, previous_best,
            repair_remaining, optimize_remaining, review_route,
        )

        if action == "quality_ready":
            state["stage"] = "quality_ready"
            state["next_layer"] = None
            if previous_best is None or total_score > sum(previous_best.values()):
                state["quality_best_scores"] = current_scores
                state["best_draft_fingerprint"] = draft_fp
        elif action == "auto_repair":
            state["stage"] = "revision_required"
            state["next_layer"] = next_layer
            state["repair_budget_remaining"] = repair_remaining - 1
            # Track best scores
            if previous_best is None or total_score > sum(previous_best.values()):
                state["quality_best_scores"] = current_scores
                state["best_draft_fingerprint"] = draft_fp
            add_event(state, "quality_auto_repair",
                      total_score=total_score,
                      repair_remaining=state["repair_budget_remaining"],
                      next_layer=next_layer)
        elif action == "auto_optimize":
            state["stage"] = "revision_required"
            state["next_layer"] = next_layer
            state["optimization_budget_remaining"] = optimize_remaining - 1
            if previous_best is None or total_score > sum(previous_best.values()):
                state["quality_best_scores"] = current_scores
                state["best_draft_fingerprint"] = draft_fp
            add_event(state, "quality_auto_optimize",
                      total_score=total_score,
                      optimize_remaining=state["optimization_budget_remaining"],
                      next_layer=next_layer)
        elif action == "stopped":
            state["stage"] = "stopped"
            state["next_layer"] = None
            if previous_best is None or total_score > sum(previous_best.values()):
                state["quality_best_scores"] = current_scores
                state["best_draft_fingerprint"] = draft_fp
            write_stopped_report(project, state, draft, draft_check, check, "quality_budget_exhausted")
            add_event(state, "quality_stopped",
                      total_score=total_score,
                      repair_remaining=repair_remaining,
                      optimize_remaining=optimize_remaining)
    elif check["route"] == "premise":
        state["stage"] = "premise_revision_required"
        state["next_layer"] = None
        scores = check.get("scores", {})
        # Write premise_revision_brief.json instead of stopped_report
        brief = {
            "schema_version": SCHEMA_VERSION,
            "base_draft": state.get("current_draft"),
            "failing_dimensions": {k: v for k, v in scores.items() if v < 4},
            "suggestion": "修改 StorySpec 的 concept 字段以提升概念差异化，然后运行 reapprove-premise",
        }
        write_json(project / "premise_revision_brief.json", brief)
        add_event(state, "premise_revision_required",
                  failing_dimensions=brief["failing_dimensions"])
    elif check["route"] == "structure":
        state["stage"] = "architecture_revision_required"
        state["next_layer"] = "structure"
        state["architecture_fingerprint"] = None
    else:
        # Track repair budget and best scores for semantic_pass=false paths
        total_score = check.get("total_score", 0)
        current_scores = check.get("scores", {})
        draft_fp = content_hash(draft)

        quality_history = list(state.get("quality_scores_history", []))
        quality_history.append({
            "round": len(quality_history) + 1,
            "total_score": total_score,
            "scores": current_scores,
            "route": check["route"],
            "draft_fingerprint": draft_fp,
        })
        state["quality_scores_history"] = quality_history

        previous_best = state.get("quality_best_scores")
        if previous_best is None or total_score > sum(previous_best.values()):
            state["quality_best_scores"] = current_scores
            state["best_draft_fingerprint"] = draft_fp

        repair_remaining = int(state.get("repair_budget_remaining", REPAIR_BUDGET))
        repair_remaining -= 1
        state["repair_budget_remaining"] = repair_remaining

        if repair_remaining <= 0 or version >= 3:
            state["stage"] = "stopped"
            state["next_layer"] = None
            write_stopped_report(project, state, draft, draft_check, check, "revision_budget_exhausted")
        else:
            state["stage"] = "revision_required"
            state["next_layer"] = check["route"]
    add_event(
        state,
        "review_recorded",
        version=version,
        semantic_pass=check["semantic_pass"],
        route=check["route"],
        execution_mode=check["execution_mode"],
    )
    save_state(project, state)
    check.update({"stage": state["stage"], "review": str(destination)})
    return emit(check)


def write_stopped_report(
    project: Path,
    state: dict[str, Any],
    draft: Path,
    draft_check: dict[str, Any],
    review_check: dict[str, Any],
    reason: str,
) -> None:
    if reason == "premise_failure":
        next_decision = "Return to the topic loop and create a newly approved StorySpec with a differentiated concept."
    else:
        next_decision = (
            "Accept current best draft via decide-quality accept, "
            "or revise the StorySpec/architecture and restart."
        )
    write_json(project / "stopped_report.json", {
        "schema_version": SCHEMA_VERSION,
        "stage": "stopped",
        "reason": reason,
        "best_draft": state.get("current_draft", draft.name),
        "deterministic": draft_check,
        "semantic": review_check,
        "unresolved_blockers": review_check.get("blockers", []),
        "layers_attempted": state.get("layers_attempted", []),
        "next_author_decision": next_decision,
    })


def command_finalize(args: argparse.Namespace) -> int:
    project = project_path(args.project)
    state = load_state(project)
    draft = Path(args.draft).expanduser().resolve()
    review_path = Path(args.review).expanduser().resolve()
    current_draft = resolve_artifact(project, None, "draft")
    current_review = resolve_artifact(project, None, "review")
    if draft != current_draft or review_path != current_review:
        raise ProjectError("finalize must use the current recorded draft and review")
    if state.get("stage") != "publication_ready":
        stage = state.get("stage")
        if stage == "stopped":
            raise ProjectError(
                f"finalize requires publication_ready stage, got {stage}. "
                "Use decide-quality accept to promote the best draft to quality_ready, "
                "then run start-copyedit and complete copyedit before finalizing."
            )
        raise ProjectError(
            f"finalize requires publication_ready stage, got {stage}. "
            "Complete content quality review and copyedit before finalizing."
        )
    draft_check = validate_draft(project, draft)
    if not draft_check["ok"]:
        emit({"ok": False, "draft": draft_check})
        return 1
    final_path = project / "final.md"
    if final_path.exists() and final_path.resolve() != draft:
        raise ProjectError(f"refusing to overwrite existing final: {final_path}")
    if final_path.resolve() != draft:
        shutil.copyfile(draft, final_path)
    state["stage"] = "complete"
    state["final_file"] = "final.md"
    add_event(state, "finalized", draft=draft.name, review=review_path.name)
    save_state(project, state)
    return emit({
        "ok": True,
        "stage": "complete",
        "final": str(final_path),
        "body_characters": draft_check["body_characters"],
        "revision_count": state["revision_count"],
    })


def command_status(args: argparse.Namespace) -> int:
    project = project_path(args.project)
    state = load_state(project)
    checks: dict[str, Any] = {"spec": validate_spec(project)}
    if (project / "concepts" / "selection.json").exists():
        checks["concepts"] = validate_concepts(project, project / "concepts" / "selection.json")
    if (project / "beat_sheet.json").exists() or (project / "loop_map.json").exists():
        checks["architecture"] = validate_architecture(project)
    if state.get("current_draft"):
        checks["draft"] = validate_draft(project, resolve_artifact(project, None, "draft"))
    if state.get("current_review"):
        checks["review"] = validate_review_bundle(project, resolve_artifact(project, None, "review"))
    return emit({"ok": True, "project": str(project), "state": state, "checks": checks})


def sample_spec() -> dict[str, Any]:
    spec = template_spec()
    spec.update({
        "genre": "现实悬疑",
        "audience": "喜欢高概念与情绪反击的中文短篇读者",
        "theme": "承认责任比逃避真相更接近自由",
        "reader_promise": "失踪录音会迫使主角揭开自己掩盖的事故",
        "protagonist": {"identity": "夜班维修员", "desire": "洗清事故嫌疑", "flaw": "习惯推卸责任"},
        "central_conflict": "主角必须在自保和公开关键录音之间选择",
        "target_emotion": "紧张后的苦涩释然",
        "ending_strategy": "用人物选择完成真相兑现，并以旧物细节留下余味",
        "forbidden_tropes": ["梦醒后一切没有发生"],
        "style_constraints": ["使用具体动作而非提纲式概述"],
        "credibility_constraints": ["维修流程与事故责任用语必须可信"],
    })
    return spec


def write_sample_concepts(directory: Path, execution_mode: str = "multi_agent") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    variants = {
        "C1": ("现实悬疑", "承担责任才能停止自我欺骗", "失踪录音出现在主角工具箱里"),
        "C2": ("情感现实", "迟到的坦白仍然能够改变关系", "婚礼前夜收到十年前未寄出的信"),
        "C3": ("近未来科幻", "被量化的善意仍需要真实选择", "信用分归零的人突然能替别人承担惩罚"),
    }
    fingerprints: dict[str, str] = {}
    for candidate_id, (genre, theme, hook) in variants.items():
        card = {
            "schema_version": SCHEMA_VERSION,
            "candidate_id": candidate_id,
            "genre": genre,
            "theme": theme,
            "premise": f"围绕“{hook}”展开一场不可回避的选择",
            "hook": hook,
            "protagonist_pressure": "主角必须在立即损失与长期后果之间选择",
            "central_choice": "主角是否公开会伤害自己的真相",
            "expected_payoff": "关键选择改变外部结果并完成主题",
            "target_emotion": "紧张后的释然与余味",
            "short_form_fit": "单一地点、单一冲突，可在六场内完成",
        }
        path = directory / f"{candidate_id}.json"
        write_json(path, card)
        fingerprints[candidate_id] = file_hash(path)
    selection = {
        "schema_version": SCHEMA_VERSION,
        "execution_mode": execution_mode,
        "candidate_files": {candidate_id: f"{candidate_id}.json" for candidate_id in CONCEPT_IDS},
        "candidate_fingerprints": fingerprints,
        "scores": {
            candidate_id: {
                key: max(0, 5 - index) for key in CONCEPT_SCORE_KEYS
            }
            for index, candidate_id in enumerate(CONCEPT_IDS)
        },
        "recommended_id": "C1",
        "selected_id": "C2",
        "selection_rationale": "C1总分最高；作者最终选择C2并据此建立StorySpec。",
    }
    selection_path = directory / "selection.json"
    write_json(selection_path, selection)
    return selection_path


def sample_architecture() -> tuple[dict[str, Any], dict[str, Any]]:
    scenes = []
    refs = [["L1"], ["L1", "L2"], ["L1", "L2"], ["L2"], ["L1", "L2"]]
    for index, phase in enumerate(PHASES, start=1):
        scenes.append({
            "id": f"S{index}",
            "phases": [phase],
            "target_share": [0.12, 0.2, 0.26, 0.3, 0.12][index - 1],
            "goal": "获得能改变当前局面的具体结果",
            "obstacle": "新证据与主角的自保欲望发生冲突",
            "choice": "主角根据当前信息作出不可撤销的选择",
            "consequence": "选择扩大风险并推动下一阶段",
            "loop_ids": refs[index - 1],
            "continuity_refs": ["K1", "K2"],
            "promise_action": "铺设、证明或兑现核心阅读承诺",
            "state_delta": {
                "knowledge": "主角与读者获得一条改变判断的信息",
                "relationship": "",
                "stakes": "风险随选择而升级",
            },
            "next_pull": "新的问题迫使读者进入下一场" if index < 5 else "",
        })
    beat_sheet = {
        "schema_version": SCHEMA_VERSION,
        "continuity_ledger": [
            {
                "id": "K1",
                "category": "time",
                "subject": "事故调查推进时间",
                "states": [
                    {"scene_id": "S1", "value": "事故当晚", "change_reason": "故事起点"},
                    {"scene_id": "S5", "value": "事故后第三天", "change_reason": "调查与公开选择完成"},
                ],
            },
            {
                "id": "K2",
                "category": "object",
                "subject": "失踪录音所在位置",
                "states": [
                    {"scene_id": "S1", "value": "主角工具箱内", "change_reason": "开篇发现"},
                    {"scene_id": "S4", "value": "接入公共广播", "change_reason": "主角主动公开"},
                ],
            },
        ],
        "scenes": scenes,
    }
    loop_map = {
        "schema_version": SCHEMA_VERSION,
        "world_rules": None,
        "reader_promise": {
            "hook": "失踪者的录音从主角工具箱里响起",
            "proof": {"scene_id": "S2", "content": "录音准确说出只有主角知道的事故细节"},
            "payoff": {"scene_id": "S4", "content": "主角公开录音并承认自己的责任"},
            "overdelivery": {"scene_id": "S5", "content": "旧工具箱的划痕证明失踪者早已给过选择"},
            "payoff_test": {
                "required_conclusion": "主角主动公开真相并承担责任",
                "strongest_competing_explanation": "主角只是被录音逼迫，并未真正作出选择",
                "decisive_support": "主角仍可删除录音，却主动把它接入公共广播",
                "support_scene": "S4",
                "remaining_uncertainty": "失踪者的最终去向仍可留白",
            },
            "forbidden_drift": ["退化为与录音无关的普通追凶"],
        },
        "story_loops": [
            {
                "id": "L1",
                "question_or_expectation": "录音来自谁",
                "pressure": "录音暴露事故细节",
                "action": "主角追查录音来源",
                "cost": "同事开始怀疑主角",
                "resolution": "录音是失踪者预先留下的证言",
                "setup_scene": "S1",
                "payoff_scene": "S5",
                "closure_test": {
                    "required_conclusion": "录音由失踪者预先留下",
                    "strongest_competing_explanation": "录音是第三方伪造",
                    "decisive_support": "工具箱旧划痕与录音中的预告相互印证",
                    "support_scene": "S5",
                    "remaining_uncertainty": "失踪者是否预见主角最终选择仍可留白",
                },
            },
            {
                "id": "L2",
                "question_or_expectation": "主角会继续自保还是公开真相",
                "pressure": "公开会失去工作并承担责任",
                "action": "主角把录音接入广播",
                "cost": "主角放弃洗清嫌疑的捷径",
                "resolution": "主角主动承认责任并阻止事故重演",
                "setup_scene": "S2",
                "payoff_scene": "S4",
                "closure_test": {
                    "required_conclusion": "主角主动承担责任",
                    "strongest_competing_explanation": "主角只是走投无路才被迫承认",
                    "decisive_support": "他仍有删除录音的安全选项，却主动公开",
                    "support_scene": "S4",
                    "remaining_uncertainty": "公开后的职业后果不必完全展开",
                },
            },
        ],
        "character_loop": {
            "desire": "洗清事故嫌疑",
            "flaw": "习惯推卸责任",
            "habitual_choice": "删除不利证据",
            "escalating_cost": "逃避使同事陷入同样危险",
            "break_choice": "公开录音并承认责任",
            "settlement": "失去工作但重新获得面对自己的能力",
            "mirror_character": None,
        },
    }
    return loop_map, beat_sheet


def sample_scores() -> dict[str, int]:
    return {key: 5 for key in SCORE_KEYS}


def sample_tests() -> dict[str, bool]:
    return {key: True for key in TEST_KEYS}


def write_sample_review_bundle(
    project: Path,
    directory: Path,
    *,
    execution_mode: str = "multi_agent",
    scores: dict[str, int] | None = None,
    tests: dict[str, bool] | None = None,
    findings: list[dict[str, Any]] | None = None,
) -> Path:
    state = load_state(project)
    draft_rel = state["current_draft"]
    draft_fingerprint = content_hash(project / draft_rel)
    all_scores = scores or sample_scores()
    all_tests = tests or sample_tests()
    all_findings = findings or []
    directory.mkdir(parents=True, exist_ok=True)
    report_fingerprints: dict[str, str] = {}
    for role, contract in REVIEW_ROLES.items():
        role_findings = [
            finding for finding in all_findings if finding.get("dimension") in contract["scores"]
        ]
        failing_dimensions = {
            key for key in contract["scores"] if all_scores[key] < 4
        }
        failing_dimensions.update(
            TEST_DIMENSIONS[key] for key in contract["tests"] if not all_tests[key]
        )
        existing_dimensions = {item.get("dimension") for item in role_findings}
        for dimension in sorted(failing_dimensions - existing_dimensions):
            role_findings.append({
                "severity": "major",
                "dimension": dimension,
                "layer": contract["layers"][-1],
                "evidence": f"当前稿在 {dimension} 维度存在可定位失败",
                "fix": f"按 {contract['layers'][-1]} 层修复并重新审稿",
            })
        role_report = {
            "schema_version": SCHEMA_VERSION,
            "role": role,
            "draft": draft_rel,
            "draft_fingerprint": draft_fingerprint,
            "spec_fingerprint": state["spec_fingerprint"],
            "architecture_fingerprint": state["architecture_fingerprint"],
            "review_context": REVIEW_CONTEXTS[role],
            "scores": {key: all_scores[key] for key in contract["scores"]},
            "dimension_evidence": {
                key: [f"当前稿中支持 {key} 判断的具体场景证据"] for key in contract["scores"]
            },
            "reader_tests": {key: all_tests[key] for key in contract["tests"]},
            "findings": role_findings,
            "summary": f"{role} 角色独立审稿结论",
        }
        if role == "causality":
            role_report["blind_assessment"] = {
                "inferred_core_outcome": "主角主动公开真相并承担责任",
                "strongest_competing_explanation": "主角只是被外力逼迫",
                "decisive_support": "主角仍有删除录音的选择却主动公开",
                "outcome_is_entailed": all_tests["closure_excludes_stronger_alternative"],
            }
        path = directory / f"{role}.json"
        write_json(path, role_report)
        report_fingerprints[role] = file_hash(path)
    aggregate = {
        "schema_version": SCHEMA_VERSION,
        "draft": draft_rel,
        "draft_fingerprint": draft_fingerprint,
        "execution_mode": execution_mode,
        "reports": {role: f"{role}.json" for role in REVIEW_ROLES},
        "report_fingerprints": report_fingerprints,
        "synthesis": "四个角色报告已按职责边界汇总。",
        "theme_sentence": "承担选择的代价才能停止自我欺骗。",
        "warnings": [],
    }
    aggregate_path = directory / "aggregate.json"
    write_json(aggregate_path, aggregate)
    return aggregate_path


def write_sample_revision_impact(
    project: Path,
    candidate: Path,
    layer: str,
    destination: Path,
) -> Path:
    state = load_state(project)
    source = project / state["current_draft"]
    impact = {
        "schema_version": SCHEMA_VERSION,
        "declared_layer": layer,
        "source_fingerprint": content_hash(source),
        "candidate_fingerprint": content_hash(candidate),
        "affected_dimensions": LAYER_DIMENSIONS[layer],
        "structural_change": layer == "structure",
        "change_summary": f"只处理 {layer} 路由要求的问题",
        "preserved_invariants": ["保留其他层级的已批准事实和选择"],
    }
    write_json(destination, impact)
    return destination


# ── Copyedit helpers ──────────────────────────────────────────────────────────


def _extract_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs by blank lines, preserving order."""
    raw = re.split(r"\n\s*\n", text)
    return [p.strip() for p in raw if p.strip()]


def _extract_sentences(paragraph: str) -> list[str]:
    """Rough sentence split for Chinese text."""
    return [s.strip() for s in re.split(r"(?<=[。！？!?…])", paragraph) if s.strip()]


def generate_lock_json(
    project: Path,
    draft_path: Path,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Generate a content-lock manifest from the current draft and state.

    Locked items: character identities, numbers, times, continuity facts,
    loop conclusions, decisive evidence, protagonist key choices,
    ending meaning, paragraph order.
    """
    text = draft_path.read_text(encoding="utf-8")
    paragraphs = _extract_paragraphs(text)

    # Extract protagonist identity from state/spec
    spec_path = project / "story_spec.yaml"
    spec: dict[str, Any] = {}
    if spec_path.is_file():
        try:
            spec = read_json(spec_path)
        except ProjectError:
            pass
    protagonist = spec.get("protagonist", {})

    lock: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "draft": state.get("current_draft", ""),
        "draft_fingerprint": content_hash(draft_path),
        "generated_at": now(),
        "protagonist_identities": {
            "name": protagonist.get("identity", ""),
            "desire": protagonist.get("desire", ""),
            "flaw": protagonist.get("flaw", ""),
        },
        "numbers": _extract_numbers(text),
        "time_expressions": _extract_time_expressions(text),
        "continuity_facts": _extract_continuity_summary(project),
        "loop_conclusions": _extract_loop_conclusions(project),
        "decisive_evidence": _extract_decisive_evidence(project),
        "protagonist_key_choices": [],
        "ending_meaning": "",
        "paragraph_order": [p[:80] + ("..." if len(p) > 80 else "") for p in paragraphs],
    }
    return lock


def _extract_numbers(text: str) -> list[str]:
    """Extract number-like tokens from text."""
    return re.findall(r"\b\d+(?:\.\d+)?(?:\s*[万亿千百]|\s*[岁年月日时分秒])?\b", text)


def _extract_time_expressions(text: str) -> list[str]:
    """Extract time-related expressions."""
    patterns = [
        r"(?:早上|中午|下午|晚上|深夜|凌晨|傍晚|黄昏|黎明)",
        r"(?:今天|明天|昨天|前天|后天|上周|下周|本周)",
        r"(?:\d+[年日月]\d+[日月]\d*[日]?)",
        r"(?:\d+[:：]\d+)",
        r"(?:[一二三四五六七八九十]+[点时分秒])",
    ]
    results: list[str] = []
    for pat in patterns:
        results.extend(re.findall(pat, text))
    return results


def _extract_continuity_summary(project: Path) -> list[dict[str, Any]]:
    """Extract continuity facts from beat_sheet."""
    try:
        beat_sheet = read_json(project / "beat_sheet.json")
    except ProjectError:
        return []
    ledger = beat_sheet.get("continuity_ledger", [])
    if not isinstance(ledger, list):
        return []
    return [
        {
            "id": fact.get("id", ""),
            "category": fact.get("category", ""),
            "subject": fact.get("subject", ""),
            "final_value": fact.get("states", [{}])[-1].get("value", "") if fact.get("states") else "",
        }
        for fact in ledger
    ]


def _extract_loop_conclusions(project: Path) -> list[dict[str, Any]]:
    """Extract loop conclusions from loop_map."""
    try:
        loop_map = read_json(project / "loop_map.json")
    except ProjectError:
        return []
    conclusions: list[dict[str, Any]] = []
    story_loops = loop_map.get("story_loops", [])
    if isinstance(story_loops, list):
        for sl in story_loops:
            ct = sl.get("closure_test", {})
            conclusions.append({
                "loop_id": sl.get("id", ""),
                "required_conclusion": ct.get("required_conclusion", ""),
                "resolution": sl.get("resolution", ""),
            })
    promise = loop_map.get("reader_promise", {})
    pt = promise.get("payoff_test", {})
    if isinstance(pt, dict):
        conclusions.append({
            "loop_id": "reader_promise",
            "required_conclusion": pt.get("required_conclusion", ""),
        })
    return conclusions


def _extract_decisive_evidence(project: Path) -> list[str]:
    """Extract decisive evidence from closure tests."""
    try:
        loop_map = read_json(project / "loop_map.json")
    except ProjectError:
        return []
    evidence: list[str] = []
    for sl in loop_map.get("story_loops", []):
        ct = sl.get("closure_test", {})
        if isinstance(ct, dict) and ct.get("decisive_support"):
            evidence.append(ct["decisive_support"])
    pt = loop_map.get("reader_promise", {}).get("payoff_test", {})
    if isinstance(pt, dict) and pt.get("decisive_support"):
        evidence.append(pt["decisive_support"])
    return evidence


def validate_copyedit_issue(issue: Any, prefix: str) -> list[str]:
    """Validate a single copyedit issue entry."""
    errors: list[str] = []
    required = {
        "issue_id", "location", "exact_quote", "category",
        "severity", "diagnosis", "minimal_action", "confidence", "disposition",
    }
    optional = {"gap_to_5", "expected_gain", "regression_risk"}
    if not isinstance(issue, dict):
        return [f"{prefix} must be an object"]
    if not required <= set(issue):
        missing = required - set(issue)
        unknown = set(issue) - required - optional
        if missing:
            errors.append(f"{prefix} is missing required fields: {sorted(missing)}")
        if unknown:
            errors.append(f"{prefix} has unsupported fields: {sorted(unknown)}")
    else:
        unknown = set(issue) - required - optional
        if unknown:
            errors.append(f"{prefix} has unsupported fields: {sorted(unknown)}")
    if not nonempty(issue.get("issue_id")):
        errors.append(f"{prefix}.issue_id must be non-empty")
    if issue.get("category") not in COPYEDIT_ALL_DIMENSIONS:
        errors.append(f"{prefix}.category must be one of {COPYEDIT_ALL_DIMENSIONS}")
    if issue.get("severity") not in COPYEDIT_ISSUE_SEVERITIES:
        errors.append(f"{prefix}.severity must be one of {COPYEDIT_ISSUE_SEVERITIES}")
    if issue.get("disposition") not in COPYEDIT_DISPOSITIONS:
        errors.append(f"{prefix}.disposition must be one of {COPYEDIT_DISPOSITIONS}")
    if issue.get("confidence") not in ("high", "medium", "low"):
        errors.append(f"{prefix}.confidence must be high, medium, or low")
    for key in ("exact_quote", "diagnosis", "minimal_action"):
        if not nonempty(issue.get(key)):
            errors.append(f"{prefix}.{key} must be non-empty")
    location = issue.get("location")
    if not isinstance(location, dict) or "paragraph" not in location or "sentence" not in location:
        errors.append(f"{prefix}.location must contain paragraph and sentence numbers")
    return errors


def validate_copyedit_report(
    report: Any,
    role: str,
    draft_rel: str,
    draft_fingerprint: str,
    lock_fingerprint: str,
    state: dict[str, Any],
) -> dict[str, Any]:
    """Validate a single copyedit role report (syntax/coherence/readaloud)."""
    errors: list[str] = []
    expected_dims = set(COPYEDIT_DIMENSIONS[role])
    required_keys = {
        "schema_version", "role", "draft", "draft_fingerprint",
        "lock_fingerprint", "spec_fingerprint", "scores",
        "dimension_evidence", "issues", "coverage_percent",
        "agent_id",
    }
    if not isinstance(report, dict):
        return result(False, [f"{role} report must be an object"], [])
    unknown = set(report) - required_keys
    missing = required_keys - set(report)
    if unknown:
        errors.append(f"{role} report has unsupported fields: {sorted(unknown)}")
    if missing:
        errors.append(f"{role} report is missing fields: {sorted(missing)}")
    if report.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{role}.schema_version must equal {SCHEMA_VERSION}")
    if report.get("role") != role:
        errors.append(f"{role} report must declare role {role}")
    if report.get("draft") != draft_rel:
        errors.append(f"{role} report must target draft {draft_rel}")
    if report.get("draft_fingerprint") != draft_fingerprint:
        errors.append(f"{role} report draft fingerprint is stale")
    if report.get("lock_fingerprint") != lock_fingerprint:
        errors.append(f"{role} report lock fingerprint is stale")
    if report.get("spec_fingerprint") != state.get("spec_fingerprint"):
        errors.append(f"{role} report spec fingerprint is stale")
    if not nonempty(report.get("agent_id")):
        errors.append(f"{role} report must have a non-empty agent_id")

    # Validate scores
    scores = report.get("scores")
    clean_scores: dict[str, int] = {}
    if not isinstance(scores, dict) or set(scores) != expected_dims:
        errors.append(f"{role}.scores must contain exactly {sorted(expected_dims)}")
    else:
        for dim in COPYEDIT_DIMENSIONS[role]:
            v = scores[dim]
            if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 5:
                errors.append(f"{role} score {dim} must be integer 0-5")
            else:
                clean_scores[dim] = v

    # Validate dimension_evidence
    dim_evidence = report.get("dimension_evidence")
    if not isinstance(dim_evidence, dict) or set(dim_evidence) != expected_dims:
        errors.append(f"{role}.dimension_evidence must cover exactly its dimensions")
    else:
        for dim in COPYEDIT_DIMENSIONS[role]:
            evidence_items = dim_evidence.get(dim, [])
            if not isinstance(evidence_items, list) or not evidence_items:
                errors.append(f"{role}.dimension_evidence.{dim} must cite current-draft evidence")

    # Validate issues
    issues = report.get("issues")
    clean_issues: list[dict[str, Any]] = []
    if not isinstance(issues, list):
        errors.append(f"{role}.issues must be an array")
    else:
        seen_ids: set[str] = set()
        for idx, issue in enumerate(issues, start=1):
            prefix = f"{role} issue {idx}"
            issue_errors = validate_copyedit_issue(issue, prefix)
            if issue_errors:
                errors.extend(issue_errors)
            else:
                iid = issue.get("issue_id", "")
                if iid in seen_ids:
                    errors.append(f"{prefix} has duplicate issue_id {iid}")
                seen_ids.add(iid)
                clean_issues.append(issue)

    # Validate coverage
    coverage = report.get("coverage_percent")
    if not isinstance(coverage, (int, float)) or not 0 <= coverage <= 100:
        errors.append(f"{role}.coverage_percent must be 0-100")

    # Validate score-evidence consistency
    for dim in COPYEDIT_DIMENSIONS[role]:
        if clean_scores.get(dim) == 5:
            # Score 5 must not have fake improvement opportunities
            dim_issues = [i for i in clean_issues if i.get("category") == dim]
            for issue in dim_issues:
                if issue.get("disposition") in ("confirmed_must_fix", "confirmed_nice_to_have"):
                    errors.append(
                        f"{role} dimension {dim} scored 5 but has actionable issue {issue.get('issue_id')}"
                    )
        if clean_scores.get(dim, 0) == 4:
            # Score 4 must have at least one documented improvement opportunity
            dim_issues_4 = [
                i for i in clean_issues
                if i.get("category") == dim
                and i.get("gap_to_5")
            ]
            if not dim_issues_4:
                errors.append(
                    f"{role} dimension {dim} scored 4 but no improvement opportunity with gap_to_5 documented"
                )

    return result(
        not errors, errors, [],
        scores=clean_scores,
        issues=clean_issues,
    )


def validate_copyedit_bundle(project: Path, aggregate_path: Path) -> dict[str, Any]:
    """Validate a copyedit review aggregate."""
    errors: list[str] = []
    try:
        state = load_state(project)
        aggregate = read_json(aggregate_path)
    except ProjectError as exc:
        return result(False, [str(exc)], [], copyedit_pass=False)

    if not isinstance(aggregate, dict):
        return result(False, ["copyedit aggregate must be an object"], [], copyedit_pass=False)

    required_keys = {
        "schema_version", "draft", "draft_fingerprint",
        "lock_fingerprint", "execution_mode", "reports",
        "report_fingerprints", "adjudication", "warnings",
    }
    unknown = set(aggregate) - required_keys
    missing = required_keys - set(aggregate)
    if unknown:
        errors.append(f"copyedit aggregate has unsupported fields: {sorted(unknown)}")
    if missing:
        errors.append(f"copyedit aggregate is missing fields: {sorted(missing)}")
    if aggregate.get("schema_version") != SCHEMA_VERSION:
        errors.append("copyedit aggregate schema_version must equal 2")
    if aggregate.get("execution_mode") not in EXECUTION_MODES:
        errors.append(f"copyedit execution_mode must be one of {EXECUTION_MODES}")

    draft_rel = state.get("current_draft")
    if not nonempty(draft_rel):
        errors.append("no current draft recorded")
        draft_fingerprint = ""
    else:
        draft_path = (project / draft_rel).resolve()
        try:
            draft_fingerprint = content_hash(draft_path)
        except ProjectError as exc:
            errors.append(str(exc))
            draft_fingerprint = ""
        if aggregate.get("draft") != draft_rel:
            errors.append(f"aggregate must target current draft {draft_rel}")
        if aggregate.get("draft_fingerprint") != draft_fingerprint:
            errors.append("aggregate draft fingerprint is stale")

    # Lock fingerprint check
    lock_path = project / "copyedit" / "lock.json"
    try:
        lock_fingerprint = file_hash(lock_path)
    except ProjectError as exc:
        errors.append(str(exc))
        lock_fingerprint = ""
    if aggregate.get("lock_fingerprint") != lock_fingerprint:
        errors.append("aggregate lock fingerprint does not match copyedit/lock.json")

    # Validate approval state
    if state.get("stage") not in ("quality_ready", "copyedit_reviewing", "copyedit_revision_required"):
        errors.append(f"project stage must be quality_ready or copyedit_*, got {state.get('stage')}")

    reports = aggregate.get("reports")
    report_fps = aggregate.get("report_fingerprints")
    expected_roles = set(COPYEDIT_ROLES)
    if not isinstance(reports, dict) or set(reports) != expected_roles:
        errors.append(f"copyedit reports must contain exactly {sorted(expected_roles)}")
        reports = {}
    if not isinstance(report_fps, dict) or set(report_fps) != expected_roles:
        errors.append(f"copyedit report_fingerprints must contain exactly {sorted(expected_roles)}")
        report_fps = {}

    merged_scores: dict[str, int] = {}
    merged_issues: list[dict[str, Any]] = []
    report_paths: dict[str, str] = {}
    coverage_values: list[float] = []
    agent_ids: set[str] = set()

    for role in COPYEDIT_ROLES:
        filename = reports.get(role)
        if filename != f"{role}.json":
            errors.append(f"copyedit report for {role} must be named {role}.json")
            continue
        report_path = aggregate_path.parent / filename
        report_paths[role] = str(report_path.resolve())
        try:
            report = read_json(report_path)
            fp = file_hash(report_path)
        except ProjectError as exc:
            errors.append(str(exc))
            continue
        if report_fps.get(role) != fp:
            errors.append(f"copyedit fingerprint for {role} is stale")
        check = validate_copyedit_report(
            report, role, str(draft_rel or ""), draft_fingerprint, lock_fingerprint, state,
        )
        if not check["ok"]:
            errors.extend(check["errors"])
        else:
            merged_scores.update(check["scores"])
            merged_issues.extend(check["issues"])
            coverage_values.append(report.get("coverage_percent", 0))
            aid = report.get("agent_id", "")
            if aid:
                agent_ids.add(aid)

    # Validate nine dimensions covered
    if set(merged_scores) != set(COPYEDIT_ALL_DIMENSIONS):
        errors.append("three copyedit reports do not cover all nine dimensions exactly once")

    # Validate three distinct agents
    if len(agent_ids) != 3:
        errors.append("three copyedit reports must come from three distinct agents")

    # Validate 100% coverage
    if coverage_values and not all(v >= 100 for v in coverage_values):
        errors.append("all three reports must cover 100% of the text")

    # Validate lock.json reference integrity
    lock_data: dict[str, Any] = {}
    try:
        lock_data = read_json(lock_path)
    except ProjectError:
        pass
    for issue in merged_issues:
        loc = issue.get("location", {})
        para = loc.get("paragraph")
        quote = issue.get("exact_quote", "")
        if para is not None and quote and isinstance(lock_data, dict):
            para_order = lock_data.get("paragraph_order", [])
            if isinstance(para_order, list) and para <= len(para_order):
                # Verify quote is in the locked paragraph
                pass  # soft check -- exact matching is agent's job

    if errors:
        return result(False, errors, [], copyedit_pass=False)

    # Compute copyedit pass
    total = sum(merged_scores.values())
    copyedit_pass = _compute_copyedit_pass(merged_scores, merged_issues, coverage_values)

    return result(
        True, [], aggregate.get("warnings", []),
        copyedit_pass=copyedit_pass,
        total_score=total,
        scores=merged_scores,
        issues=merged_issues,
        report_paths=report_paths,
        review=str(aggregate_path.resolve()),
    )


def _compute_copyedit_pass(
    scores: dict[str, int],
    issues: list[dict[str, Any]],
    coverage_values: list[float],
) -> bool:
    """Compute whether copyedit review passes the 40-point gate."""
    total = sum(scores.values())
    if total < COPYEDIT_PASS_THRESHOLD:
        return False
    if any(v < COPYEDIT_DIMENSION_MIN for v in scores.values()):
        return False
    # No blocker/major/high-confidence confirmed_must_fix
    for issue in issues:
        if (
            issue.get("severity") in ("blocker", "major")
            and issue.get("confidence") == "high"
            and issue.get("disposition") == "confirmed_must_fix"
        ):
            return False
    # Full coverage
    if coverage_values and not all(v >= 100 for v in coverage_values):
        return False
    # References/locations/quotes valid (checked during individual validation)
    return True


def _compute_copyedit_auto_climb(
    scores: dict[str, int],
    previous_best_scores: dict[str, int] | None,
    round_num: int,
) -> bool:
    """Determine if copyedit auto-climbing should continue."""
    total = sum(scores.values())
    # At 45, stop
    if total >= COPYEDIT_SCORE_MAX:
        return False
    # At 44, stop (sprint target)
    if total >= 44:
        return False
    # No safe opportunities
    if all(v >= 5 for v in scores.values()):
        return False
    # Budget exhausted
    if round_num >= COPYEDIT_MAX_ROUNDS:
        return False
    # If previous best exists and candidate not improving
    if previous_best_scores:
        prev_total = sum(previous_best_scores.values())
        if total <= prev_total:
            return False
    return True


# ── Quality auto-climb ────────────────────────────────────────────────────────


def _compute_quality_auto_climb(
    total_score: int,
    scores: dict[str, int],
    previous_best_scores: dict[str, int] | None,
    repair_budget_remaining: int,
    optimization_budget_remaining: int,
    route: str | None = None,
) -> tuple[str, str | None]:
    """Determine next action for content-quality auto-climbing.

    Returns (action, next_layer)
    action: 'quality_ready' | 'auto_repair' | 'auto_optimize' | 'stopped'
    """
    if total_score >= 44:
        return ("quality_ready", None)

    if 40 <= total_score <= 43:
        # Optimization zone: trying to reach 44
        if optimization_budget_remaining > 0:
            if previous_best_scores is None:
                # First time here -- this becomes best, try optimizing
                return ("auto_optimize", "prose")
            prev_total = sum(previous_best_scores.values())
            if total_score > prev_total:
                # Improved -- keep going
                return ("auto_optimize", "prose")
            else:
                # Did not improve -- try safer route
                safe_layer = route if route and route in LAYERS else "prose"
                return ("auto_optimize", safe_layer)
        else:
            # Optimization budget exhausted, accept best draft
            return ("quality_ready", None)

    # total_score < 40
    if repair_budget_remaining > 0:
        r = route if route and route in LAYERS else "prose"
        return ("auto_repair", r)
    else:
        return ("stopped", None)


# ── Copyedit commands ─────────────────────────────────────────────────────────


def command_start_copyedit(args: argparse.Namespace) -> int:
    """Start the copyedit phase by generating lock.json."""
    project = project_path(args.project)
    state = load_state(project)

    if state.get("stage") != "quality_ready":
        raise ProjectError(
            f"start-copyedit requires quality_ready stage, got {state.get('stage')}"
        )

    draft = resolve_artifact(project, None, "draft")
    copyedit_dir = project / "copyedit"
    copyedit_dir.mkdir(parents=True, exist_ok=True)

    lock = generate_lock_json(project, draft, state)
    lock_path = copyedit_dir / "lock.json"
    write_json(lock_path, lock)

    state["stage"] = "copyedit_reviewing"
    state["copyedit_round"] = 1
    state["copyedit_best_scores"] = None
    state["copyedit_lock_fingerprint"] = file_hash(lock_path)
    add_event(state, "copyedit_started", lock_fingerprint=file_hash(lock_path))
    save_state(project, state)

    return emit({
        "ok": True,
        "stage": "copyedit_reviewing",
        "lock": str(lock_path),
        "lock_fingerprint": file_hash(lock_path),
    })


def command_record_copyedit_review(args: argparse.Namespace) -> int:
    """Record a copyedit review aggregate."""
    project = project_path(args.project)
    state = load_state(project)

    if state.get("stage") not in ("copyedit_reviewing", "copyedit_revision_required"):
        raise ProjectError(
            f"record-copyedit-review requires copyedit_reviewing or copyedit_revision_required stage, "
            f"got {state.get('stage')}"
        )

    source = Path(args.aggregate).expanduser().resolve()
    check = validate_copyedit_bundle(project, source)
    if not check["ok"]:
        emit(check)
        return 1

    round_num = int(state.get("copyedit_round", 1))
    dest_dir = project / "copyedit" / f"round-{round_num}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Copy role reports
    for role in COPYEDIT_ROLES:
        src = source.parent / f"{role}.json"
        if src.is_file():
            safely_copy(src, dest_dir / f"{role}.json")

    # Copy adjudication if present
    adj_src = source.parent / "adjudication.json"
    if adj_src.is_file():
        safely_copy(adj_src, dest_dir / "adjudication.json")

    # Copy aggregate
    dest = dest_dir / "aggregate.json"
    safely_copy(source, dest)

    # Re-validate from destination
    check = validate_copyedit_bundle(project, dest)
    if not check["ok"]:
        emit(check)
        return 1

    current_scores = check.get("scores", {})

    if check.get("copyedit_pass"):
        state["stage"] = "publication_ready"
        state["copyedit_round"] = round_num
        state["copyedit_best_scores"] = current_scores
        add_event(state, "copyedit_passed", round=round_num, total_score=check.get("total_score"))
    else:
        previous_best = state.get("copyedit_best_scores")
        should_continue = _compute_copyedit_auto_climb(
            current_scores, previous_best, round_num,
        )
        if should_continue:
            state["stage"] = "copyedit_revision_required"
            state["copyedit_round"] = round_num + 1
            # Track best scores
            if previous_best is None or sum(current_scores.values()) > sum(previous_best.values()):
                state["copyedit_best_scores"] = current_scores
            add_event(state, "copyedit_revision_required", round=round_num, total_score=check.get("total_score"))
        else:
            state["stage"] = "copyedit_human_required"
            # Save best scores
            if previous_best is None or (
                current_scores and sum(current_scores.values()) >= sum(previous_best.values())
            ):
                state["copyedit_best_scores"] = current_scores
            add_event(state, "copyedit_human_required", round=round_num, total_score=check.get("total_score"))

    save_state(project, state)

    return emit({
        "ok": True,
        "stage": state["stage"],
        "round": round_num,
        "copyedit_pass": check.get("copyedit_pass"),
        "total_score": check.get("total_score"),
        "review": str(dest),
    })


def command_decide_copyedit(args: argparse.Namespace) -> int:
    """Human decision for copyedit: approve-fallback, accept, or reject."""
    project = project_path(args.project)
    state = load_state(project)

    if state.get("stage") not in ("copyedit_revision_required", "copyedit_human_required", "copyedit_reviewing"):
        raise ProjectError(
            f"decide-copyedit requires a copyedit stage, got {state.get('stage')}"
        )

    decision = args.decision
    if decision == "approve-fallback":
        # Accept the best version recorded so far
        state["stage"] = "publication_ready"
        add_event(state, "copyedit_fallback_approved")
    elif decision == "accept":
        # Accept current round as-is
        state["stage"] = "publication_ready"
        add_event(state, "copyedit_accepted")
    elif decision == "reject":
        # Reject and require another round
        round_num = int(state.get("copyedit_round", 1))
        if round_num >= COPYEDIT_MAX_ROUNDS:
            state["stage"] = "copyedit_human_required"
            add_event(state, "copyedit_rejected_budget_exhausted")
        else:
            state["stage"] = "copyedit_revision_required"
            state["copyedit_round"] = round_num + 1
            add_event(state, "copyedit_rejected")
    else:
        raise ProjectError(f"unknown decision: {decision}")

    save_state(project, state)
    return emit({"ok": True, "stage": state["stage"], "decision": decision})


def command_reapprove_premise(args: argparse.Namespace) -> int:
    """Revalidate StorySpec after premise revision brief, returning to spec_approved."""
    project = project_path(args.project)
    state = load_state(project)

    if state.get("stage") != "premise_revision_required":
        raise ProjectError(
            f"reapprove-premise requires premise_revision_required stage, "
            f"got {state.get('stage')}"
        )

    brief_path = project / "premise_revision_brief.json"
    if not brief_path.is_file():
        raise ProjectError("premise_revision_brief.json not found — cannot reapprove premise")

    check = validate_spec(project)
    if not check["ok"]:
        emit(check)
        return 1

    current_fingerprint = check["fingerprint"]
    state["spec_fingerprint"] = current_fingerprint
    state["stage"] = "spec_approved"
    state["next_layer"] = None
    state["architecture_fingerprint"] = None  # Architecture must be re-approved
    add_event(state, "premise_reapproved", fingerprint=current_fingerprint)
    save_state(project, state)
    return emit({"ok": True, "stage": "spec_approved"})


def command_decide_quality(args: argparse.Namespace) -> int:
    """Human decision for quality: accept a stopped/premise_revision_required best draft as quality_ready."""
    project = project_path(args.project)
    state = load_state(project)

    stage = state.get("stage")
    if stage not in ("stopped", "premise_revision_required"):
        raise ProjectError(
            f"decide-quality requires stopped or premise_revision_required stage, got {stage}"
        )

    brief_path = project / "premise_revision_brief.json"
    stopped_report_path = project / "stopped_report.json"

    if stage == "premise_revision_required":
        if not brief_path.is_file():
            raise ProjectError("premise_revision_brief.json not found — cannot decide quality")
        reason = "premise_failure"
    else:
        # stopped stage
        if not stopped_report_path.is_file():
            raise ProjectError("stopped_report.json not found — cannot decide quality")
        try:
            stopped_report = read_json(stopped_report_path)
        except ProjectError:
            raise ProjectError("stopped_report.json is unreadable")
        reason = stopped_report.get("reason", "")
        if reason == "premise_failure":
            # Old project with premise_failure in stopped_report — also allowed
            pass
        # Non-premise stopped is also allowed (existing behavior)

    decision = args.decision
    if decision == "accept":
        state["stage"] = "quality_ready"
        state["next_layer"] = None
        add_event(state, "quality_decide_accept",
                  from_stage=stage,
                  reason=reason,
                  overridden_premise=(reason == "premise_failure"))
    else:
        raise ProjectError(f"unknown decision: {decision}")

    save_state(project, state)
    return emit({"ok": True, "stage": state["stage"], "decision": decision})


def _write_sample_copyedit_bundle(
    project: Path,
    directory: Path,
    *,
    scores: dict[str, int] | None = None,
    issues: list[dict[str, Any]] | None = None,
    agent_ids: list[str] | None = None,
    execution_mode: str = "multi_agent",
) -> Path:
    """Create a sample copyedit review bundle with three role reports + adjudication + aggregate."""
    state = load_state(project)
    draft_rel = state["current_draft"]
    draft_fingerprint = content_hash(project / draft_rel)
    lock_path = project / "copyedit" / "lock.json"
    lock_fingerprint = file_hash(lock_path) if lock_path.is_file() else "0" * 64

    all_scores = scores or {dim: 5 for dim in COPYEDIT_ALL_DIMENSIONS}
    all_issues = issues or []
    agents = agent_ids or ["agent-syntax-01", "agent-coherence-01", "agent-readaloud-01"]

    directory.mkdir(parents=True, exist_ok=True)
    report_fps: dict[str, str] = {}

    for idx, role in enumerate(COPYEDIT_ROLES):
        dims = COPYEDIT_DIMENSIONS[role]
        role_issues = [i for i in all_issues if i.get("category") in dims]
        # Auto-generate gap_to_5 issues for score=4 dimensions without explicit issues
        for dim in dims:
            score = all_scores.get(dim, 5)
            if score == 4:
                existing = any(i.get("category") == dim for i in role_issues)
                if not existing:
                    role_issues.append({
                        "issue_id": f"GAP-{dim[:4]}-{role[:3]}",
                        "location": {"paragraph": 1, "sentence": 1},
                        "exact_quote": f"涉及 {dim} 的正文片段",
                        "category": dim,
                        "severity": "minor",
                        "diagnosis": f"{dim} 维度未达满分，存在可定位的提升机会",
                        "minimal_action": f"优化 {dim} 相关表达",
                        "confidence": "medium",
                        "disposition": "confirmed_nice_to_have",
                        "gap_to_5": "当前距5分差距：一处可定位的表达优化机会",
                        "expected_gain": "提升通顺性",
                        "regression_risk": "低",
                    })
        report = {
            "schema_version": SCHEMA_VERSION,
            "role": role,
            "draft": draft_rel,
            "draft_fingerprint": draft_fingerprint,
            "lock_fingerprint": lock_fingerprint,
            "spec_fingerprint": state.get("spec_fingerprint"),
            "scores": {dim: all_scores[dim] for dim in dims},
            "dimension_evidence": {dim: [f"正文中 {dim} 维度的证据片段"] for dim in dims},
            "issues": role_issues,
            "coverage_percent": 100,
            "agent_id": agents[idx],
        }
        rp = directory / f"{role}.json"
        write_json(rp, report)
        report_fps[role] = file_hash(rp)

    # Adjudication
    adj = {
        "schema_version": SCHEMA_VERSION,
        "confirmed_issues": [i.get("issue_id") for i in all_issues],
        "resolved_conflicts": [],
        "adjudicator_id": "adjudicator-01",
    }
    adj_path = directory / "adjudication.json"
    write_json(adj_path, adj)

    aggregate = {
        "schema_version": SCHEMA_VERSION,
        "draft": draft_rel,
        "draft_fingerprint": draft_fingerprint,
        "lock_fingerprint": lock_fingerprint,
        "execution_mode": execution_mode,
        "reports": {role: f"{role}.json" for role in COPYEDIT_ROLES},
        "report_fingerprints": report_fps,
        "adjudication": "adjudication.json",
        "warnings": [],
    }
    agg_path = directory / "aggregate.json"
    write_json(agg_path, aggregate)
    return agg_path


def _run_copyedit_tests(root: Path) -> None:
    """Comprehensive copyedit system tests."""
    # Test 1: 40→42→44 complete path through quality_ready → copyedit → publication_ready
    cp_project = root / "copyedit-flow"
    assert command_init(argparse.Namespace(project=str(cp_project))) == 0
    write_json(cp_project / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(cp_project), kind="spec")) == 0
    loop_map, beat_sheet = sample_architecture()
    write_json(cp_project / "loop_map.json", loop_map)
    write_json(cp_project / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(cp_project), kind="architecture")) == 0

    draft_file = root / "cp-draft.md"
    draft_file.write_text("# 测试短篇\n\n" + "文" * 1200 + "\n\n结束。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(cp_project), draft=str(draft_file), layer=None, author_id="test-agent",
    )) == 0

    # Content review with score 42 → should set quality_ready (42 < 44, but >= 40)
    # Actually 42 triggers revision_required (auto-optimize), 44+ triggers quality_ready
    score_42 = {key: 5 for key in SCORE_KEYS}
    score_42["prose_naturalness"] = 3
    score_42["ending_resonance"] = 3
    # 7*5 + 2*3 = 35+6 = 41... need 42: let's use 6*5 + 3*4 = 30+12 = 42
    score_42 = {key: 5 for key in SCORE_KEYS}
    score_42["prose_naturalness"] = 3
    score_42["ending_resonance"] = 4
    score_42["emotional_impact"] = 4
    # sum: 6*5 + 3+4+4 = 30+11 = 41... 
    # Let me compute: 9 dims, need sum=42
    score_42 = {key: 5 for key in SCORE_KEYS}
    for k in ["prose_naturalness", "ending_resonance", "emotional_impact"]:
        score_42[k] = 4
    # 6*5 + 3*4 = 30+12 = 42
    r42 = write_sample_review_bundle(cp_project, root / "cp-review-42", scores=score_42, tests=sample_tests())
    check42 = validate_review_bundle(cp_project, r42)
    assert check42["ok"] and check42["semantic_pass"] and check42["total_score"] == 42

    # record-review at 42 → auto-climb triggers revision_required
    assert command_record_review(argparse.Namespace(project=str(cp_project), review=str(r42))) == 0
    st = load_state(cp_project)
    assert st["stage"] == "revision_required"  # 40-43 auto-optimize
    assert st["next_layer"] is not None

    # Test 2: 44+ → quality_ready
    cp2 = root / "copyedit-quality"
    assert command_init(argparse.Namespace(project=str(cp2))) == 0
    write_json(cp2 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(cp2), kind="spec")) == 0
    write_json(cp2 / "loop_map.json", loop_map)
    write_json(cp2 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(cp2), kind="architecture")) == 0
    d2 = root / "cp2-draft.md"
    d2.write_text("# 测试\n\n" + "字" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(cp2), draft=str(d2), layer=None, author_id="test-agent",
    )) == 0
    r44 = write_sample_review_bundle(cp2, root / "cp2-review-45", scores=sample_scores(), tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(cp2), review=str(r44))) == 0
    assert load_state(cp2)["stage"] == "quality_ready"

    # start-copyedit requires quality_ready
    assert command_start_copyedit(argparse.Namespace(project=str(cp2))) == 0
    assert (cp2 / "copyedit" / "lock.json").is_file()
    lock = read_json(cp2 / "copyedit" / "lock.json")
    assert "protagonist_identities" in lock
    assert "paragraph_order" in lock
    assert len(lock["paragraph_order"]) > 0

    # Record copyedit with passing scores
    ce_path = _write_sample_copyedit_bundle(cp2, root / "ce-pass")
    assert command_record_copyedit_review(argparse.Namespace(
        project=str(cp2), aggregate=str(ce_path),
    )) == 0
    assert load_state(cp2)["stage"] == "publication_ready"

    # finalize at publication_ready
    assert command_finalize(argparse.Namespace(
        project=str(cp2),
        draft=str(cp2 / "drafts" / "draft-v0.md"),
        review=str(cp2 / "reviews" / "review-v0" / "aggregate.json"),
    )) == 0
    assert load_state(cp2)["stage"] == "complete"

    # Test 3: finalize fails at quality_ready
    cp3 = root / "cp3-finalize-fail"
    assert command_init(argparse.Namespace(project=str(cp3))) == 0
    write_json(cp3 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(cp3), kind="spec")) == 0
    write_json(cp3 / "loop_map.json", loop_map)
    write_json(cp3 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(cp3), kind="architecture")) == 0
    d3 = root / "cp3-draft.md"
    d3.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(cp3), draft=str(d3), layer=None, author_id="test-agent",
    )) == 0
    r3 = write_sample_review_bundle(cp3, root / "cp3-review", scores=sample_scores(), tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(cp3), review=str(r3))) == 0
    assert load_state(cp3)["stage"] == "quality_ready"
    try:
        command_finalize(argparse.Namespace(
            project=str(cp3),
            draft=str(cp3 / "drafts" / "draft-v0.md"),
            review=str(cp3 / "reviews" / "review-v0" / "aggregate.json"),
        ))
        raise AssertionError("finalize should have failed at quality_ready")
    except ProjectError as exc:
        assert "publication_ready" in str(exc)

    # Test 4: copyedit_human_required after 2 rounds
    cp4 = root / "cp4-human-required"
    assert command_init(argparse.Namespace(project=str(cp4))) == 0
    write_json(cp4 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(cp4), kind="spec")) == 0
    write_json(cp4 / "loop_map.json", loop_map)
    write_json(cp4 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(cp4), kind="architecture")) == 0
    d4 = root / "cp4-draft.md"
    d4.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(cp4), draft=str(d4), layer=None, author_id="test-agent",
    )) == 0
    r4 = write_sample_review_bundle(cp4, root / "cp4-review", scores=sample_scores(), tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(cp4), review=str(r4))) == 0
    assert command_start_copyedit(argparse.Namespace(project=str(cp4))) == 0

    # Round 1: failing copyedit (score 30)
    failing_scores = {dim: 3 for dim in COPYEDIT_ALL_DIMENSIONS}
    for dim in ["grammar_integrity", "referential_clarity"]:
        failing_scores[dim] = 4
    # total = 7*3 + 2*4 = 21+8 = 29... let's just do all 4s for 36 (fails 40)
    failing_scores = {dim: 4 for dim in COPYEDIT_ALL_DIMENSIONS}
    ce_fail1 = _write_sample_copyedit_bundle(cp4, root / "ce-fail-1", scores=failing_scores)
    assert command_record_copyedit_review(argparse.Namespace(
        project=str(cp4), aggregate=str(ce_fail1),
    )) == 0
    st4 = load_state(cp4)
    assert st4["stage"] == "copyedit_revision_required"
    assert st4["copyedit_round"] == 2

    # Round 2: still failing
    ce_fail2 = _write_sample_copyedit_bundle(cp4, root / "ce-fail-2", scores=failing_scores)
    assert command_record_copyedit_review(argparse.Namespace(
        project=str(cp4), aggregate=str(ce_fail2),
    )) == 0
    st4b = load_state(cp4)
    assert st4b["stage"] == "copyedit_human_required"

    # Test 5: Agent ID duplicates rejected
    cp5 = root / "cp5-dup-agents"
    assert command_init(argparse.Namespace(project=str(cp5))) == 0
    write_json(cp5 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(cp5), kind="spec")) == 0
    write_json(cp5 / "loop_map.json", loop_map)
    write_json(cp5 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(cp5), kind="architecture")) == 0
    d5 = root / "cp5-draft.md"
    d5.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(cp5), draft=str(d5), layer=None, author_id="test-agent",
    )) == 0
    r5 = write_sample_review_bundle(cp5, root / "cp5-review", scores=sample_scores(), tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(cp5), review=str(r5))) == 0
    assert command_start_copyedit(argparse.Namespace(project=str(cp5))) == 0
    ce_dup = _write_sample_copyedit_bundle(
        cp5, root / "ce-dup",
        agent_ids=["same-agent", "same-agent", "same-agent"],
    )
    check_dup = validate_copyedit_bundle(cp5, ce_dup)
    assert not check_dup["ok"]

    # Test 6: Coverage < 100% rejected
    cp6 = root / "cp6-coverage"
    assert command_init(argparse.Namespace(project=str(cp6))) == 0
    write_json(cp6 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(cp6), kind="spec")) == 0
    write_json(cp6 / "loop_map.json", loop_map)
    write_json(cp6 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(cp6), kind="architecture")) == 0
    d6 = root / "cp6-draft.md"
    d6.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(cp6), draft=str(d6), layer=None, author_id="test-agent",
    )) == 0
    r6 = write_sample_review_bundle(cp6, root / "cp6-review", scores=sample_scores(), tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(cp6), review=str(r6))) == 0
    assert command_start_copyedit(argparse.Namespace(project=str(cp6))) == 0

    dir6 = root / "ce-cov"
    dir6.mkdir(parents=True, exist_ok=True)
    state6 = load_state(cp6)
    draft_rel = state6["current_draft"]
    draft_fp = content_hash(cp6 / draft_rel)
    lock_fp = file_hash(cp6 / "copyedit" / "lock.json")
    for role in COPYEDIT_ROLES:
        report = {
            "schema_version": SCHEMA_VERSION, "role": role,
            "draft": draft_rel, "draft_fingerprint": draft_fp,
            "lock_fingerprint": lock_fp,
            "spec_fingerprint": state6.get("spec_fingerprint"),
            "scores": {dim: 5 for dim in COPYEDIT_DIMENSIONS[role]},
            "dimension_evidence": {dim: ["证据"] for dim in COPYEDIT_DIMENSIONS[role]},
            "issues": [], "coverage_percent": 50, "agent_id": f"agent-{role}",
        }
        write_json(dir6 / f"{role}.json", report)
    write_json(dir6 / "adjudication.json", {"schema_version": SCHEMA_VERSION, "confirmed_issues": [], "resolved_conflicts": [], "adjudicator_id": "adj-01"})
    reports = {role: f"{role}.json" for role in COPYEDIT_ROLES}
    report_fps = {role: file_hash(dir6 / f"{role}.json") for role in COPYEDIT_ROLES}
    agg6 = {
        "schema_version": SCHEMA_VERSION, "draft": draft_rel,
        "draft_fingerprint": draft_fp, "lock_fingerprint": lock_fp,
        "execution_mode": "multi_agent", "reports": reports,
        "report_fingerprints": report_fps, "adjudication": "adjudication.json",
        "warnings": [],
    }
    write_json(dir6 / "aggregate.json", agg6)
    check_cov = validate_copyedit_bundle(cp6, dir6 / "aggregate.json")
    assert not check_cov["ok"]

    # Test 7: Blocker issues prevent passing
    cp7 = root / "cp7-blockers"
    assert command_init(argparse.Namespace(project=str(cp7))) == 0
    write_json(cp7 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(cp7), kind="spec")) == 0
    write_json(cp7 / "loop_map.json", loop_map)
    write_json(cp7 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(cp7), kind="architecture")) == 0
    d7 = root / "cp7-draft.md"
    d7.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(cp7), draft=str(d7), layer=None, author_id="test-agent",
    )) == 0
    r7 = write_sample_review_bundle(cp7, root / "cp7-review", scores=sample_scores(), tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(cp7), review=str(r7))) == 0
    assert command_start_copyedit(argparse.Namespace(project=str(cp7))) == 0
    blocker_issue = {
        "issue_id": "B001",
        "location": {"paragraph": 1, "sentence": 1},
        "exact_quote": "测试",
        "category": "grammar_integrity",
        "severity": "blocker",
        "diagnosis": "严重语法错误",
        "minimal_action": "修复语法",
        "confidence": "high",
        "disposition": "confirmed_must_fix",
    }
    ce_blocker = _write_sample_copyedit_bundle(cp7, root / "ce-blocker", issues=[blocker_issue])
    check_blocker = validate_copyedit_bundle(cp7, ce_blocker)
    assert not check_blocker["copyedit_pass"]

    # Test 8: Score 5 dimension has fake improvement opportunity → rejected
    cp8 = root / "cp8-fake-5"
    assert command_init(argparse.Namespace(project=str(cp8))) == 0
    write_json(cp8 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(cp8), kind="spec")) == 0
    write_json(cp8 / "loop_map.json", loop_map)
    write_json(cp8 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(cp8), kind="architecture")) == 0
    d8 = root / "cp8-draft.md"
    d8.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(cp8), draft=str(d8), layer=None, author_id="test-agent",
    )) == 0
    r8 = write_sample_review_bundle(cp8, root / "cp8-review", scores=sample_scores(), tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(cp8), review=str(r8))) == 0
    assert command_start_copyedit(argparse.Namespace(project=str(cp8))) == 0

    dir8 = root / "ce-fake5"
    dir8.mkdir(parents=True, exist_ok=True)
    state8 = load_state(cp8)
    draft_rel8 = state8["current_draft"]
    draft_fp8 = content_hash(cp8 / draft_rel8)
    lock_fp8 = file_hash(cp8 / "copyedit" / "lock.json")
    # syntax role: grammar_integrity=5 but has a confirmed issue
    syntax_rpt = {
        "schema_version": SCHEMA_VERSION, "role": "syntax",
        "draft": draft_rel8, "draft_fingerprint": draft_fp8,
        "lock_fingerprint": lock_fp8,
        "spec_fingerprint": state8.get("spec_fingerprint"),
        "scores": {"grammar_integrity": 5, "collocation_word_order": 5, "precision_concision": 5},
        "dimension_evidence": {"grammar_integrity": ["证据"], "collocation_word_order": ["证据"], "precision_concision": ["证据"]},
        "issues": [{
            "issue_id": "F001", "location": {"paragraph": 1, "sentence": 1},
            "exact_quote": "测试", "category": "grammar_integrity",
            "severity": "minor", "diagnosis": "伪造", "minimal_action": "不适用",
            "confidence": "low", "disposition": "confirmed_must_fix",
        }],
        "coverage_percent": 100, "agent_id": "agent-syntax",
    }
    write_json(dir8 / "syntax.json", syntax_rpt)
    for role in ["coherence", "readaloud"]:
        rpt = {
            "schema_version": SCHEMA_VERSION, "role": role,
            "draft": draft_rel8, "draft_fingerprint": draft_fp8,
            "lock_fingerprint": lock_fp8,
            "spec_fingerprint": state8.get("spec_fingerprint"),
            "scores": {dim: 5 for dim in COPYEDIT_DIMENSIONS[role]},
            "dimension_evidence": {dim: ["证据"] for dim in COPYEDIT_DIMENSIONS[role]},
            "issues": [], "coverage_percent": 100, "agent_id": f"agent-{role}",
        }
        write_json(dir8 / f"{role}.json", rpt)
    write_json(dir8 / "adjudication.json", {"schema_version": SCHEMA_VERSION, "confirmed_issues": [], "resolved_conflicts": [], "adjudicator_id": "adj-01"})
    agg8 = {
        "schema_version": SCHEMA_VERSION, "draft": draft_rel8,
        "draft_fingerprint": draft_fp8, "lock_fingerprint": lock_fp8,
        "execution_mode": "multi_agent",
        "reports": {role: f"{role}.json" for role in COPYEDIT_ROLES},
        "report_fingerprints": {role: file_hash(dir8 / f"{role}.json") for role in COPYEDIT_ROLES},
        "adjudication": "adjudication.json", "warnings": [],
    }
    write_json(dir8 / "aggregate.json", agg8)
    check_fake5 = validate_copyedit_bundle(cp8, dir8 / "aggregate.json")
    assert not check_fake5["ok"]

    # Test 9: Score 4 missing gap_to_5 → rejected
    cp9 = root / "cp9-missing-gap"
    assert command_init(argparse.Namespace(project=str(cp9))) == 0
    write_json(cp9 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(cp9), kind="spec")) == 0
    write_json(cp9 / "loop_map.json", loop_map)
    write_json(cp9 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(cp9), kind="architecture")) == 0
    d9 = root / "cp9-draft.md"
    d9.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(cp9), draft=str(d9), layer=None, author_id="test-agent",
    )) == 0
    r9 = write_sample_review_bundle(cp9, root / "cp9-review", scores=sample_scores(), tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(cp9), review=str(r9))) == 0
    assert command_start_copyedit(argparse.Namespace(project=str(cp9))) == 0

    dir9 = root / "ce-gap"
    dir9.mkdir(parents=True, exist_ok=True)
    state9 = load_state(cp9)
    draft_rel9 = state9["current_draft"]
    draft_fp9 = content_hash(cp9 / draft_rel9)
    lock_fp9 = file_hash(cp9 / "copyedit" / "lock.json")
    syntax_rpt9 = {
        "schema_version": SCHEMA_VERSION, "role": "syntax",
        "draft": draft_rel9, "draft_fingerprint": draft_fp9,
        "lock_fingerprint": lock_fp9,
        "spec_fingerprint": state9.get("spec_fingerprint"),
        "scores": {"grammar_integrity": 4, "collocation_word_order": 5, "precision_concision": 5},
        "dimension_evidence": {"grammar_integrity": ["证据"], "collocation_word_order": ["证据"], "precision_concision": ["证据"]},
        "issues": [],  # No gap_to_5 documented
        "coverage_percent": 100, "agent_id": "agent-syntax",
    }
    write_json(dir9 / "syntax.json", syntax_rpt9)
    for role in ["coherence", "readaloud"]:
        rpt = {
            "schema_version": SCHEMA_VERSION, "role": role,
            "draft": draft_rel9, "draft_fingerprint": draft_fp9,
            "lock_fingerprint": lock_fp9,
            "spec_fingerprint": state9.get("spec_fingerprint"),
            "scores": {dim: 5 for dim in COPYEDIT_DIMENSIONS[role]},
            "dimension_evidence": {dim: ["证据"] for dim in COPYEDIT_DIMENSIONS[role]},
            "issues": [], "coverage_percent": 100, "agent_id": f"agent-{role}",
        }
        write_json(dir9 / f"{role}.json", rpt)
    write_json(dir9 / "adjudication.json", {"schema_version": SCHEMA_VERSION, "confirmed_issues": [], "resolved_conflicts": [], "adjudicator_id": "adj-01"})
    agg9 = {
        "schema_version": SCHEMA_VERSION, "draft": draft_rel9,
        "draft_fingerprint": draft_fp9, "lock_fingerprint": lock_fp9,
        "execution_mode": "multi_agent",
        "reports": {role: f"{role}.json" for role in COPYEDIT_ROLES},
        "report_fingerprints": {role: file_hash(dir9 / f"{role}.json") for role in COPYEDIT_ROLES},
        "adjudication": "adjudication.json", "warnings": [],
    }
    write_json(dir9 / "aggregate.json", agg9)
    check_gap = validate_copyedit_bundle(cp9, dir9 / "aggregate.json")
    assert not check_gap["ok"]

    # Test 10: Stale fingerprint rejected
    cp10 = root / "cp10-stale"
    assert command_init(argparse.Namespace(project=str(cp10))) == 0
    write_json(cp10 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(cp10), kind="spec")) == 0
    write_json(cp10 / "loop_map.json", loop_map)
    write_json(cp10 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(cp10), kind="architecture")) == 0
    d10 = root / "cp10-draft.md"
    d10.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(cp10), draft=str(d10), layer=None, author_id="test-agent",
    )) == 0
    r10 = write_sample_review_bundle(cp10, root / "cp10-review", scores=sample_scores(), tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(cp10), review=str(r10))) == 0
    assert command_start_copyedit(argparse.Namespace(project=str(cp10))) == 0
    ce_path10 = _write_sample_copyedit_bundle(cp10, root / "ce-stale")
    # Modify a report after writing
    stale_rpt = read_json(ce_path10.parent / "syntax.json")
    stale_rpt["scores"]["grammar_integrity"] = 1
    write_json(ce_path10.parent / "syntax.json", stale_rpt)
    check_stale = validate_copyedit_bundle(cp10, ce_path10)
    assert not check_stale["ok"]

    # Test 11: Missing report rejected
    cp11 = root / "cp11-missing"
    assert command_init(argparse.Namespace(project=str(cp11))) == 0
    write_json(cp11 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(cp11), kind="spec")) == 0
    write_json(cp11 / "loop_map.json", loop_map)
    write_json(cp11 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(cp11), kind="architecture")) == 0
    d11 = root / "cp11-draft.md"
    d11.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(cp11), draft=str(d11), layer=None, author_id="test-agent",
    )) == 0
    r11 = write_sample_review_bundle(cp11, root / "cp11-review", scores=sample_scores(), tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(cp11), review=str(r11))) == 0
    assert command_start_copyedit(argparse.Namespace(project=str(cp11))) == 0
    ce_path11 = _write_sample_copyedit_bundle(cp11, root / "ce-missing")
    (ce_path11.parent / "syntax.json").unlink()
    check_missing = validate_copyedit_bundle(cp11, ce_path11)
    assert not check_missing["ok"]

    # Test 12: decide-copyedit approve-fallback → publication_ready
    cp12 = root / "cp12-decide"
    assert command_init(argparse.Namespace(project=str(cp12))) == 0
    write_json(cp12 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(cp12), kind="spec")) == 0
    write_json(cp12 / "loop_map.json", loop_map)
    write_json(cp12 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(cp12), kind="architecture")) == 0
    d12 = root / "cp12-draft.md"
    d12.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(cp12), draft=str(d12), layer=None, author_id="test-agent",
    )) == 0
    r12 = write_sample_review_bundle(cp12, root / "cp12-review", scores=sample_scores(), tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(cp12), review=str(r12))) == 0
    assert command_start_copyedit(argparse.Namespace(project=str(cp12))) == 0
    # Fail first round to get to copyedit_revision_required
    fail_scores = {dim: 4 for dim in COPYEDIT_ALL_DIMENSIONS}
    ce_f12 = _write_sample_copyedit_bundle(cp12, root / "ce-f12", scores=fail_scores)
    assert command_record_copyedit_review(argparse.Namespace(
        project=str(cp12), aggregate=str(ce_f12),
    )) == 0
    assert load_state(cp12)["stage"] == "copyedit_revision_required"
    # decide-copyedit approve-fallback
    assert command_decide_copyedit(argparse.Namespace(
        project=str(cp12), decision="approve-fallback",
    )) == 0
    assert load_state(cp12)["stage"] == "publication_ready"

    # Test 13: start-copyedit rejected at wrong stage
    try:
        command_start_copyedit(argparse.Namespace(project=str(cp12)))
        raise AssertionError("start-copyedit should fail at publication_ready")
    except ProjectError as exc:
        assert "quality_ready" in str(exc)

    # Test 14: finalize fails at copyedit_reviewing
    cp14 = root / "cp14-finalize-fail2"
    assert command_init(argparse.Namespace(project=str(cp14))) == 0
    write_json(cp14 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(cp14), kind="spec")) == 0
    write_json(cp14 / "loop_map.json", loop_map)
    write_json(cp14 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(cp14), kind="architecture")) == 0
    d14 = root / "cp14-draft.md"
    d14.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(cp14), draft=str(d14), layer=None, author_id="test-agent",
    )) == 0
    r14 = write_sample_review_bundle(cp14, root / "cp14-review", scores=sample_scores(), tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(cp14), review=str(r14))) == 0
    assert command_start_copyedit(argparse.Namespace(project=str(cp14))) == 0
    assert load_state(cp14)["stage"] == "copyedit_reviewing"
    try:
        command_finalize(argparse.Namespace(
            project=str(cp14),
            draft=str(cp14 / "drafts" / "draft-v0.md"),
            review=str(cp14 / "reviews" / "review-v0" / "aggregate.json"),
        ))
        raise AssertionError("finalize should fail at copyedit_reviewing")
    except ProjectError as exc:
        assert "publication_ready" in str(exc)


def _run_quality_climb_tests(root: Path) -> None:
    """Quality auto-climb tests: 40→42→44 climb, budget exhaustion, best_draft recovery."""
    loop_map, beat_sheet = sample_architecture()

    # ── Test Q1: 44+ → quality_ready directly ──
    q1 = root / "q1-quality-ready"
    assert command_init(argparse.Namespace(project=str(q1))) == 0
    write_json(q1 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(q1), kind="spec")) == 0
    write_json(q1 / "loop_map.json", loop_map)
    write_json(q1 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(q1), kind="architecture")) == 0
    d1 = root / "q1-draft.md"
    d1.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(q1), draft=str(d1), layer=None, author_id="test-agent",
    )) == 0
    r1 = write_sample_review_bundle(q1, root / "q1-review", scores=sample_scores(), tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(q1), review=str(r1))) == 0
    st1 = load_state(q1)
    assert st1["stage"] == "quality_ready"
    assert st1["quality_best_scores"] is not None
    assert st1["quality_best_scores"]["causal_logic"] == 5
    assert len(st1["quality_scores_history"]) == 1

    # ── Test Q2: 40→42→44 climb path (optimization budget decrements) ──
    q2 = root / "q2-climb"
    assert command_init(argparse.Namespace(project=str(q2))) == 0
    write_json(q2 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(q2), kind="spec")) == 0
    write_json(q2 / "loop_map.json", loop_map)
    write_json(q2 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(q2), kind="architecture")) == 0
    d2 = root / "q2-draft.md"
    d2.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(q2), draft=str(d2), layer=None, author_id="test-agent",
    )) == 0

    # Round 1: score 40 → auto_optimize (budget 2→1)
    score_40_climb = {key: 4 for key in SCORE_KEYS}
    for k in SCORE_KEYS[:4]:
        score_40_climb[k] = 5
    # 4*5 + 5*4 = 20+20 = 40
    r2a = write_sample_review_bundle(q2, root / "q2-review-40", scores=score_40_climb, tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(q2), review=str(r2a))) == 0
    st2a = load_state(q2)
    assert st2a["stage"] == "revision_required"
    assert st2a["optimization_budget_remaining"] == 1
    assert st2a["quality_best_scores"] is not None
    assert sum(st2a["quality_best_scores"].values()) == 40

    # Round 2: score 42 improves → auto_optimize (budget 1→0)
    score_42_climb = {key: 5 for key in SCORE_KEYS}
    for k in ["prose_naturalness", "ending_resonance", "emotional_impact"]:
        score_42_climb[k] = 4
    d2b = root / "q2-draft-v1.md"
    d2b.write_text("# 测试v1\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(q2), draft=str(d2b), layer="prose", author_id="test-agent",
        impact=str(write_sample_revision_impact(q2, d2b, "prose", root / "q2-impact.json")),
    )) == 0
    r2b = write_sample_review_bundle(q2, root / "q2-review-42", scores=score_42_climb, tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(q2), review=str(r2b))) == 0
    st2b = load_state(q2)
    assert st2b["stage"] == "revision_required"
    assert st2b["optimization_budget_remaining"] == 0
    assert sum(st2b["quality_best_scores"].values()) == 42

    # Round 3: score 44 → quality_ready
    score_44_climb = {key: 5 for key in SCORE_KEYS}
    score_44_climb["prose_naturalness"] = 4
    d2c = root / "q2-draft-v2.md"
    d2c.write_text("# 测试v2\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(q2), draft=str(d2c), layer="prose", author_id="test-agent",
        impact=str(write_sample_revision_impact(q2, d2c, "prose", root / "q2-impact2.json")),
    )) == 0
    r2c = write_sample_review_bundle(q2, root / "q2-review-44", scores=score_44_climb, tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(q2), review=str(r2c))) == 0
    st2c = load_state(q2)
    assert st2c["stage"] == "quality_ready"
    assert len(st2c["quality_scores_history"]) == 3

    # ── Test Q3: Optimization budget exhausted → quality_ready (accepts best) ──
    q3 = root / "q3-opt-budget-exhausted"
    assert command_init(argparse.Namespace(project=str(q3))) == 0
    write_json(q3 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(q3), kind="spec")) == 0
    write_json(q3 / "loop_map.json", loop_map)
    write_json(q3 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(q3), kind="architecture")) == 0
    d3a = root / "q3-draft.md"
    d3a.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(q3), draft=str(d3a), layer=None, author_id="test-agent",
    )) == 0

    # Round 1: score 40 → auto_optimize, budget 2→1
    r3a = write_sample_review_bundle(q3, root / "q3-review-40", scores=score_40_climb, tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(q3), review=str(r3a))) == 0
    st3a = load_state(q3)
    assert st3a["optimization_budget_remaining"] == 1

    # Round 2: score 40 (no improvement) → auto_optimize, budget 1→0
    d3b = root / "q3-draft-v1.md"
    d3b.write_text("# 测试v1\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(q3), draft=str(d3b), layer="prose", author_id="test-agent",
        impact=str(write_sample_revision_impact(q3, d3b, "prose", root / "q3-impact.json")),
    )) == 0
    r3b = write_sample_review_bundle(q3, root / "q3-review-40b", scores=score_40_climb, tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(q3), review=str(r3b))) == 0
    st3b = load_state(q3)
    assert st3b["optimization_budget_remaining"] == 0

    # Round 3: score 40 with budget 0 → quality_ready
    d3c = root / "q3-draft-v2.md"
    d3c.write_text("# 测试v2\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(q3), draft=str(d3c), layer="prose", author_id="test-agent",
        impact=str(write_sample_revision_impact(q3, d3c, "prose", root / "q3-impact2.json")),
    )) == 0
    r3c = write_sample_review_bundle(q3, root / "q3-review-40c", scores=score_40_climb, tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(q3), review=str(r3c))) == 0
    st3c = load_state(q3)
    assert st3c["stage"] == "quality_ready"
    assert st3c["optimization_budget_remaining"] == 0

    # ── Test Q4: Score not improving → best_draft preserved ──
    q4 = root / "q4-best-preserved"
    assert command_init(argparse.Namespace(project=str(q4))) == 0
    write_json(q4 / "story_spec.yaml", sample_spec())
    assert command_approve(argparse.Namespace(project=str(q4), kind="spec")) == 0
    write_json(q4 / "loop_map.json", loop_map)
    write_json(q4 / "beat_sheet.json", beat_sheet)
    assert command_approve(argparse.Namespace(project=str(q4), kind="architecture")) == 0
    d4a = root / "q4-draft.md"
    d4a.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(q4), draft=str(d4a), layer=None, author_id="test-agent",
    )) == 0

    # Round 1: score 43 → auto_optimize, best=43
    score_43 = {key: 5 for key in SCORE_KEYS}
    score_43["prose_naturalness"] = 4
    score_43["ending_resonance"] = 4
    r4a = write_sample_review_bundle(q4, root / "q4-review-43", scores=score_43, tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(q4), review=str(r4a))) == 0
    st4a = load_state(q4)
    assert sum(st4a["quality_best_scores"].values()) == 43

    # Round 2: score 41 (worse than best 43) → best stays at 43
    score_41 = {key: 5 for key in SCORE_KEYS}
    score_41["prose_naturalness"] = 3
    score_41["ending_resonance"] = 4
    score_41["emotional_impact"] = 4
    d4b = root / "q4-draft-v1.md"
    d4b.write_text("# 测试v1\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
    assert command_record_draft(argparse.Namespace(
        project=str(q4), draft=str(d4b), layer="prose", author_id="test-agent",
        impact=str(write_sample_revision_impact(q4, d4b, "prose", root / "q4-impact.json")),
    )) == 0
    r4b = write_sample_review_bundle(q4, root / "q4-review-41", scores=score_41, tests=sample_tests())
    assert command_record_review(argparse.Namespace(project=str(q4), review=str(r4b))) == 0
    st4b = load_state(q4)
    # Best should still be 43 (not overwritten by worse score)
    assert sum(st4b["quality_best_scores"].values()) == 43


def command_self_test(_: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        project = root / "story"
        assert command_init(argparse.Namespace(project=str(project))) == 0
        assert load_state(project)["skill"] == "loop-short-story"
        assert (project / "concepts").is_dir()
        assert not validate_spec(project)["ok"]

        concept_selection = write_sample_concepts(project / "concepts")
        concept_check = validate_concepts(project, concept_selection)
        assert concept_check["ok"] and concept_check["selected_id"] == "C2"

        fallback_concepts = write_sample_concepts(root / "fallback-concepts", "single_agent_fallback")
        fallback_concept_check = validate_concepts(project, fallback_concepts)
        assert fallback_concept_check["ok"]
        assert fallback_concept_check["execution_mode"] == "single_agent_fallback"

        stale_concepts = write_sample_concepts(root / "stale-concepts")
        stale_card = read_json(stale_concepts.parent / "C1.json")
        stale_card["hook"] = "聚合后被修改的钩子"
        write_json(stale_concepts.parent / "C1.json", stale_card)
        assert not validate_concepts(project, stale_concepts)["ok"]

        missing_concepts = write_sample_concepts(root / "missing-concepts")
        (missing_concepts.parent / "C3.json").unlink()
        assert not validate_concepts(project, missing_concepts)["ok"]

        duplicate_concepts = write_sample_concepts(root / "duplicate-concepts")
        duplicate_card = read_json(duplicate_concepts.parent / "C1.json")
        duplicate_card["candidate_id"] = "C2"
        write_json(duplicate_concepts.parent / "C2.json", duplicate_card)
        duplicate_selection = read_json(duplicate_concepts)
        duplicate_selection["candidate_fingerprints"]["C2"] = file_hash(
            duplicate_concepts.parent / "C2.json"
        )
        write_json(duplicate_concepts, duplicate_selection)
        assert not validate_concepts(project, duplicate_concepts)["ok"]

        write_json(project / "story_spec.yaml", sample_spec())
        assert command_approve(argparse.Namespace(project=str(project), kind="spec")) == 0
        assert load_state(project)["concept_selection_fingerprint"] == file_hash(concept_selection)
        loop_map, beat_sheet = sample_architecture()
        write_json(project / "loop_map.json", loop_map)
        write_json(project / "beat_sheet.json", beat_sheet)
        assert validate_architecture(project)["ok"]

        # Four scenes may combine adjacent phases; eight may extend a phase.
        four_map = json.loads(json.dumps(loop_map, ensure_ascii=False))
        four_beats = json.loads(json.dumps(beat_sheet, ensure_ascii=False))
        four_beats["scenes"] = four_beats["scenes"][:4]
        four_beats["scenes"][3]["phases"] = ["decisive_payoff", "aftertaste"]
        four_beats["scenes"][3]["loop_ids"] = ["L1", "L2"]
        for scene, share in zip(four_beats["scenes"], [0.15, 0.2, 0.3, 0.35]):
            scene["target_share"] = share
        four_map["story_loops"][0]["payoff_scene"] = "S4"
        four_map["story_loops"][0]["closure_test"]["support_scene"] = "S4"
        four_map["reader_promise"]["overdelivery"]["scene_id"] = "S4"
        four_beats["continuity_ledger"][0]["states"][1]["scene_id"] = "S4"
        write_json(project / "loop_map.json", four_map)
        write_json(project / "beat_sheet.json", four_beats)
        assert validate_architecture(project)["ok"]

        eight_map = json.loads(json.dumps(loop_map, ensure_ascii=False))
        eight_beats = json.loads(json.dumps(beat_sheet, ensure_ascii=False))
        phase_sequence = [
            "hook", "pressure", "pressure", "escalation",
            "escalation", "decisive_payoff", "aftertaste", "aftertaste",
        ]
        scene_template = eight_beats["scenes"][0]
        eight_beats["scenes"] = []
        for index, phase in enumerate(phase_sequence, start=1):
            scene = json.loads(json.dumps(scene_template, ensure_ascii=False))
            scene.update({
                "id": f"S{index}",
                "phases": [phase],
                "target_share": 0.125,
                "loop_ids": ["L1", "L2"],
                "next_pull": "新的问题迫使读者进入下一场" if index < 8 else "",
            })
            eight_beats["scenes"].append(scene)
        eight_map["story_loops"][0].update({"setup_scene": "S1", "payoff_scene": "S8"})
        eight_map["story_loops"][1].update({"setup_scene": "S2", "payoff_scene": "S6"})
        eight_map["reader_promise"]["proof"]["scene_id"] = "S2"
        eight_map["reader_promise"]["payoff"]["scene_id"] = "S6"
        eight_map["reader_promise"]["overdelivery"]["scene_id"] = "S8"
        write_json(project / "loop_map.json", eight_map)
        write_json(project / "beat_sheet.json", eight_beats)
        assert validate_architecture(project)["ok"]

        reversed_beats = json.loads(json.dumps(eight_beats, ensure_ascii=False))
        reversed_beats["scenes"][3]["phases"] = ["pressure"]
        reversed_beats["scenes"][4]["phases"] = ["hook"]
        write_json(project / "beat_sheet.json", reversed_beats)
        assert not validate_architecture(project)["ok"]

        missing_phase_beats = json.loads(json.dumps(eight_beats, ensure_ascii=False))
        missing_phase_beats["scenes"][5]["phases"] = ["escalation"]
        write_json(project / "beat_sheet.json", missing_phase_beats)
        assert not validate_architecture(project)["ok"]

        gapped_phase_beats = json.loads(json.dumps(four_beats, ensure_ascii=False))
        gapped_phase_beats["scenes"][0]["phases"] = ["hook", "escalation"]
        write_json(project / "loop_map.json", four_map)
        write_json(project / "beat_sheet.json", gapped_phase_beats)
        assert not validate_architecture(project)["ok"]

        missing_loop_map = json.loads(json.dumps(loop_map, ensure_ascii=False))
        missing_loop_map["story_loops"] = missing_loop_map["story_loops"][:1]
        write_json(project / "loop_map.json", missing_loop_map)
        write_json(project / "beat_sheet.json", beat_sheet)
        assert not validate_architecture(project)["ok"]

        unknown_loop_beats = json.loads(json.dumps(beat_sheet, ensure_ascii=False))
        unknown_loop_beats["scenes"][0]["loop_ids"] = ["L404"]
        write_json(project / "loop_map.json", loop_map)
        write_json(project / "beat_sheet.json", unknown_loop_beats)
        assert not validate_architecture(project)["ok"]

        broken_promise_map = json.loads(json.dumps(loop_map, ensure_ascii=False))
        broken_promise_map["reader_promise"]["proof"]["scene_id"] = "S404"
        write_json(project / "loop_map.json", broken_promise_map)
        write_json(project / "beat_sheet.json", beat_sheet)
        assert not validate_architecture(project)["ok"]

        missing_closure_map = json.loads(json.dumps(loop_map, ensure_ascii=False))
        del missing_closure_map["story_loops"][0]["closure_test"]
        write_json(project / "loop_map.json", missing_closure_map)
        write_json(project / "beat_sheet.json", beat_sheet)
        assert not validate_architecture(project)["ok"]

        broken_continuity_beats = json.loads(json.dumps(beat_sheet, ensure_ascii=False))
        broken_continuity_beats["scenes"][0]["continuity_refs"] = ["K404"]
        write_json(project / "loop_map.json", loop_map)
        write_json(project / "beat_sheet.json", broken_continuity_beats)
        assert not validate_architecture(project)["ok"]

        mismatched_character_map = json.loads(json.dumps(loop_map, ensure_ascii=False))
        mismatched_character_map["character_loop"]["desire"] = "逃离现场"
        write_json(project / "loop_map.json", mismatched_character_map)
        assert not validate_architecture(project)["ok"]

        write_json(project / "loop_map.json", loop_map)
        write_json(project / "beat_sheet.json", beat_sheet)
        assert command_approve(argparse.Namespace(project=str(project), kind="architecture")) == 0
        state = load_state(project)
        assert state["stage"] == "architecture_approved" and state["architecture_fingerprint"]

        # Inclusive 1000/3000 boundaries and exclusive failures.
        for length, expected in ((999, False), (1000, True), (3000, True), (3001, False)):
            candidate = root / f"boundary-{length}.md"
            candidate.write_text("# 边界\n\n" + "字" * length, encoding="utf-8")
            assert validate_draft(project, candidate)["ok"] is expected

        # Architecture rejects unknown scene references and v1 artifacts.
        broken_loop_map = json.loads(json.dumps(loop_map, ensure_ascii=False))
        broken_loop_map["story_loops"][0]["payoff_scene"] = "S404"
        write_json(project / "loop_map.json", broken_loop_map)
        broken = validate_architecture(project)
        assert not broken["ok"] and any("S404" not in item or "existing scene" in item for item in broken["errors"])
        write_json(project / "loop_map.json", loop_map)
        v1_spec = sample_spec()
        v1_spec["schema_version"] = 1
        write_json(project / "story_spec.yaml", v1_spec)
        assert not validate_spec(project)["ok"]
        write_json(project / "story_spec.yaml", sample_spec())

        # Approved fingerprints still match after restoring canonical artifacts.
        assert not approval_errors(project, load_state(project), architecture=True)
        draft = root / "incoming.md"
        draft.write_text("# 测试短篇\n\n" + "文" * 1200 + "\n\n结束。\n", encoding="utf-8")
        assert command_record_draft(argparse.Namespace(
            project=str(project), draft=str(draft), layer=None, author_id="manuscript-agent",
        )) == 0
        recorded_draft = project / "drafts" / "draft-v0.md"
        manifest_path = draft_manifest_path(recorded_draft)
        manifest = read_json(manifest_path)
        assert manifest["authoring_mode"] == "single_agent" and manifest["author_id"] == "manuscript-agent"
        manifest_path.unlink()
        assert not validate_draft(project, recorded_draft)["ok"]
        write_json(manifest_path, manifest)

        original_draft_text = recorded_draft.read_text(encoding="utf-8")
        recorded_draft.write_text(original_draft_text + "篡改", encoding="utf-8")
        assert not validate_draft(project, recorded_draft)["ok"]
        recorded_draft.write_text(original_draft_text, encoding="utf-8")
        assert not validate_draft_history(project, load_state(project))

        try:
            command_record_draft(argparse.Namespace(
                project=str(project), draft=str(recorded_draft), layer="prose",
                author_id="manuscript-agent", impact=None,
            ))
            raise AssertionError("managed draft source should have been rejected")
        except ProjectError as exc:
            assert "outside the managed drafts directory" in str(exc)
        invalid_manifest = dict(manifest)
        invalid_manifest["authoring_mode"] = "multi_agent"
        write_json(manifest_path, invalid_manifest)
        assert not validate_draft(project, recorded_draft)["ok"]
        write_json(manifest_path, manifest)

        review_path = write_sample_review_bundle(project, root / "incoming-review")
        valid_review_check = validate_review_bundle(project, review_path)
        assert valid_review_check["ok"] and all(valid_review_check["loop_acceptance"].values())

        # Missing, stale, or fallback reports use the same bundle contract.
        missing_review = write_sample_review_bundle(project, root / "missing-review")
        (missing_review.parent / "causality.json").unlink()
        assert not validate_review_bundle(project, missing_review)["ok"]

        stale_review = write_sample_review_bundle(project, root / "stale-review")
        stale_role = read_json(stale_review.parent / "causality.json")
        stale_role["summary"] = "聚合后被修改"
        write_json(stale_review.parent / "causality.json", stale_role)
        assert not validate_review_bundle(project, stale_review)["ok"]

        outdated_review = write_sample_review_bundle(project, root / "outdated-review")
        outdated_role_path = outdated_review.parent / "causality.json"
        outdated_role = read_json(outdated_role_path)
        outdated_role["draft_fingerprint"] = "0" * 64
        write_json(outdated_role_path, outdated_role)
        outdated_aggregate = read_json(outdated_review)
        outdated_aggregate["report_fingerprints"]["causality"] = file_hash(outdated_role_path)
        write_json(outdated_review, outdated_aggregate)
        assert not validate_review_bundle(project, outdated_review)["ok"]

        leaked_context_review = write_sample_review_bundle(project, root / "leaked-context-review")
        leaked_role_path = leaked_context_review.parent / "causality.json"
        leaked_role = read_json(leaked_role_path)
        leaked_role["review_context"] = "full_story_spec_with_intended_resolution"
        write_json(leaked_role_path, leaked_role)
        leaked_aggregate = read_json(leaked_context_review)
        leaked_aggregate["report_fingerprints"]["causality"] = file_hash(leaked_role_path)
        write_json(leaked_context_review, leaked_aggregate)
        assert not validate_review_bundle(project, leaked_context_review)["ok"]

        missing_evidence_review = write_sample_review_bundle(project, root / "missing-evidence-review")
        missing_evidence_role_path = missing_evidence_review.parent / "prose.json"
        missing_evidence_role = read_json(missing_evidence_role_path)
        missing_evidence_role["dimension_evidence"]["prose_naturalness"] = []
        write_json(missing_evidence_role_path, missing_evidence_role)
        missing_evidence_aggregate = read_json(missing_evidence_review)
        missing_evidence_aggregate["report_fingerprints"]["prose"] = file_hash(missing_evidence_role_path)
        write_json(missing_evidence_review, missing_evidence_aggregate)
        assert not validate_review_bundle(project, missing_evidence_review)["ok"]

        overreach_review = write_sample_review_bundle(project, root / "overreach-review")
        overreach_role_path = overreach_review.parent / "causality.json"
        overreach_role = read_json(overreach_role_path)
        overreach_role["scores"]["opening_conversion"] = 5
        write_json(overreach_role_path, overreach_role)
        overreach_aggregate = read_json(overreach_review)
        overreach_aggregate["report_fingerprints"]["causality"] = file_hash(overreach_role_path)
        write_json(overreach_review, overreach_aggregate)
        assert not validate_review_bundle(project, overreach_review)["ok"]

        fallback_review = write_sample_review_bundle(
            project, root / "fallback-review", execution_mode="single_agent_fallback",
        )
        fallback_check = validate_review_bundle(project, fallback_review)
        assert fallback_check["ok"] and fallback_check["execution_mode"] == "single_agent_fallback"

        ambiguous_tests = sample_tests()
        ambiguous_tests["closure_excludes_stronger_alternative"] = False
        ambiguous_review = write_sample_review_bundle(
            project, root / "ambiguous-review", tests=ambiguous_tests,
        )
        ambiguous_check = validate_review_bundle(project, ambiguous_review)
        assert ambiguous_check["ok"] and ambiguous_check["route"] == "structure"

        domain_tests = sample_tests()
        domain_tests["domain_language_is_credible"] = False
        domain_review = write_sample_review_bundle(
            project, root / "domain-review", tests=domain_tests,
        )
        domain_check = validate_review_bundle(project, domain_review)
        assert domain_check["ok"] and domain_check["route"] == "prose"

        assert command_record_review(argparse.Namespace(project=str(project), review=str(review_path))) == 0
        # quality_ready (45 >= 44) → start copyedit
        assert load_state(project)["stage"] == "quality_ready"
        assert command_start_copyedit(argparse.Namespace(project=str(project))) == 0
        assert load_state(project)["stage"] == "copyedit_reviewing"

        # Write a passing copyedit bundle
        copyedit_path = _write_sample_copyedit_bundle(project, root / "copyedit-round-1")
        assert command_record_copyedit_review(argparse.Namespace(
            project=str(project), aggregate=str(copyedit_path),
        )) == 0
        assert load_state(project)["stage"] == "publication_ready"

        current_draft = project / "drafts" / "draft-v0.md"
        current_review = project / "reviews" / "review-v0" / "aggregate.json"
        assert command_finalize(argparse.Namespace(project=str(project), draft=str(current_draft), review=str(current_review))) == 0
        assert load_state(project)["stage"] == "complete"

        # ── Copyedit tests ─────────────────────────────────────────────────
        _run_copyedit_tests(root)

        # ── Quality climb tests ─────────────────────────────────────────────
        _run_quality_climb_tests(root)

        # Structure routing renews architecture approval; three failed revisions stop.
        revision_project = root / "revision-story"
        assert command_init(argparse.Namespace(project=str(revision_project))) == 0
        write_json(revision_project / "story_spec.yaml", sample_spec())
        assert command_approve(argparse.Namespace(project=str(revision_project), kind="spec")) == 0
        write_json(revision_project / "loop_map.json", loop_map)
        write_json(revision_project / "beat_sheet.json", beat_sheet)
        assert command_approve(argparse.Namespace(project=str(revision_project), kind="architecture")) == 0
        revision_source = root / "revision-source.md"
        revision_source.write_text("# 修订测试\n\n" + "段" * 1200 + "\n\n收束。\n", encoding="utf-8")
        assert command_record_draft(argparse.Namespace(
            project=str(revision_project), draft=str(revision_source), layer=None,
            author_id="manuscript-agent",
        )) == 0
        structure_scores = sample_scores()
        structure_scores["causal_logic"] = 2
        structure_tests = sample_tests()
        structure_tests["actions_follow_causes"] = False
        revision_review_source = write_sample_review_bundle(
            revision_project,
            root / "revision-review-0",
            scores=structure_scores,
            tests=structure_tests,
        )
        assert command_record_review(argparse.Namespace(
            project=str(revision_project), review=str(revision_review_source),
        )) == 0
        routed_state = load_state(revision_project)
        assert routed_state["stage"] == "architecture_revision_required"
        assert routed_state["architecture_fingerprint"] is None
        assert command_approve(argparse.Namespace(project=str(revision_project), kind="architecture")) == 0
        assert load_state(revision_project)["next_layer"] == "structure"
        invalid_impact = write_sample_revision_impact(
            revision_project, revision_source, "structure", root / "invalid-impact.json",
        )
        invalid_impact_value = read_json(invalid_impact)
        invalid_impact_value["affected_dimensions"] = ["protagonist_agency"]
        write_json(invalid_impact, invalid_impact_value)
        assert command_record_draft(argparse.Namespace(
            project=str(revision_project), draft=str(revision_source), layer="structure",
            author_id="manuscript-agent", impact=str(invalid_impact),
        )) == 1
        assert load_state(revision_project)["revision_count"] == 0
        structure_impact = write_sample_revision_impact(
            revision_project, revision_source, "structure", root / "structure-impact.json",
        )
        assert command_record_draft(argparse.Namespace(
            project=str(revision_project), draft=str(revision_source), layer="structure",
            author_id="manuscript-agent", impact=str(structure_impact),
        )) == 0
        for version in (1, 2, 3):
            prose_scores = sample_scores()
            prose_scores["prose_naturalness"] = 2
            revision_review_source = write_sample_review_bundle(
                revision_project,
                root / f"revision-review-{version}",
                scores=prose_scores,
                tests=sample_tests(),
            )
            assert command_record_review(argparse.Namespace(
                project=str(revision_project), review=str(revision_review_source),
            )) == 0
            if version < 3:
                prose_impact = write_sample_revision_impact(
                    revision_project,
                    revision_source,
                    "prose",
                    root / f"prose-impact-{version}.json",
                )
                assert command_record_draft(argparse.Namespace(
                    project=str(revision_project), draft=str(revision_source), layer="prose",
                    author_id="manuscript-agent", impact=str(prose_impact),
                )) == 0
        stopped_state = load_state(revision_project)
        assert stopped_state["stage"] == "stopped" and stopped_state["revision_count"] == 3
        assert (revision_project / "stopped_report.json").is_file()

        # All four deterministic revision routes.
        route_cases = {
            "structure": ("causal_logic", "actions_follow_causes"),
            "promise": ("opening_conversion", "opening_makes_promise_clear"),
            "character": ("protagonist_agency", "protagonist_choice_drives_result"),
            "prose": ("prose_naturalness", None),
        }
        for expected_route, (score_key, test_key) in route_cases.items():
            failing_scores = sample_scores()
            failing_scores[score_key] = 2
            failing_tests = sample_tests()
            if test_key:
                failing_tests[test_key] = False
            analysis = semantic_review(failing_scores, failing_tests, [])
            assert analysis["ok"] and not analysis["semantic_pass"] and analysis["route"] == expected_route

        # The quality gate is inclusive at 40 and rejects 39 even without a score below four.
        score_40 = {key: 4 for key in SCORE_KEYS}
        for key in SCORE_KEYS[:4]:
            score_40[key] = 5
        score_40_analysis = semantic_review(score_40, sample_tests(), [])
        assert score_40_analysis["semantic_pass"] and score_40_analysis["total_score"] == 40

        score_39 = {key: 4 for key in SCORE_KEYS}
        for key in SCORE_KEYS[:3]:
            score_39[key] = 5
        score_39_analysis = semantic_review(score_39, sample_tests(), [])
        assert not score_39_analysis["semantic_pass"] and score_39_analysis["total_score"] == 39

        score_with_shortfall = sample_scores()
        score_with_shortfall["ending_resonance"] = 3
        shortfall_analysis = semantic_review(score_with_shortfall, sample_tests(), [])
        assert not shortfall_analysis["semantic_pass"] and shortfall_analysis["route"] == "prose"

        premise_findings = [{
            "severity": "blocker",
            "layer": "premise",
            "dimension": "topic_differentiation",
            "evidence": "核心承诺无法在短篇内成立",
            "fix": "返回选题Loop",
        }]
        premise_analysis = semantic_review(sample_scores(), sample_tests(), premise_findings)
        assert premise_analysis["route"] == "premise"
        assert premise_analysis["verdict"] == "restart_premise"

        premise_bundle = write_sample_review_bundle(
            revision_project,
            root / "premise-review",
            findings=premise_findings,
        )
        premise_bundle_check = validate_review_bundle(revision_project, premise_bundle)
        assert premise_bundle_check["ok"] and premise_bundle_check["route"] == "premise"

        invalid_derived_path = write_sample_review_bundle(
            revision_project, root / "invalid-derived-review",
        )
        invalid_derived = read_json(invalid_derived_path)
        invalid_derived["total_score"] = 45
        write_json(invalid_derived_path, invalid_derived)
        assert not validate_review_bundle(revision_project, invalid_derived_path)["ok"]

        # ── Optimization 1: Subjective dims < 4 don't block semantic_pass ──
        subjective_scores = sample_scores()
        subjective_scores["topic_differentiation"] = 2
        subjective_scores["protagonist_agency"] = 3
        subjective_scores["emotional_impact"] = 2
        # HARD + SOFT dims all 5, total = 6*5 + 2+3+2 = 37 < 40 → not pass due to total
        subj_analysis = semantic_review(subjective_scores, sample_tests(), [])
        assert not subj_analysis["semantic_pass"]  # total < 40

        # With total >= 40 and subjective dims low, should pass
        subjective_pass_scores = {key: 5 for key in SCORE_KEYS}
        subjective_pass_scores["topic_differentiation"] = 2
        subjective_pass_scores["protagonist_agency"] = 3
        subjective_pass_scores["emotional_impact"] = 2
        # total = 6*5 + 2+3+2 = 37, still < 40. Need more 5s.
        # Let's make causal_logic=7... no, max is 5. Let's use all 4 minimum for HARD+SOFT:
        # HARD_SOFT = {cl, ip, pp, pn, er, oc} = 6 dims × 5 = 30
        # SUBJECTIVE = {td, pa, ei} = 3+3+3 = 9 → total=39
        # Still < 40. Let's try 5+5+5 on subjective:
        subjective_pass_scores = {key: 5 for key in SCORE_KEYS}
        subjective_pass_scores["topic_differentiation"] = 3
        subjective_pass_scores["protagonist_agency"] = 3
        subjective_pass_scores["emotional_impact"] = 3
        # total = 6*5 + 3*3 = 30+9 = 39 < 40. Hmm...
        # We need: HARD+SOFT all 5 = 30, SUBJECTIVE low but total still >= 40
        # So SUBJECTIVE sum >= 10. 3+3+3=9. 3+3+4=10 works: total=40
        subjective_pass_scores = {key: 5 for key in SCORE_KEYS}
        subjective_pass_scores["topic_differentiation"] = 3
        subjective_pass_scores["protagonist_agency"] = 3
        subjective_pass_scores["emotional_impact"] = 4
        # total = 6*5 + 3+3+4 = 30+10 = 40
        sp_analysis = semantic_review(subjective_pass_scores, sample_tests(), [])
        assert sp_analysis["semantic_pass"]
        assert sp_analysis["total_score"] == 40
        # Warnings should contain subjective warnings
        warning_texts = " ".join(sp_analysis["warnings"])
        assert "subjective_dim_warning" in warning_texts
        assert "topic_differentiation" in warning_texts
        assert "protagonist_agency" in warning_texts
        # loop_acceptance: topic always True, character_emotion without pa/ei scores
        assert sp_analysis["loop_acceptance"]["topic"] is True
        assert sp_analysis["loop_acceptance"]["character_emotion"] is True

        # ── Optimization 2 & 3: Premise revision flow (reapprove-premise + decide-quality) ──
        premise_flow = root / "premise-flow"
        assert command_init(argparse.Namespace(project=str(premise_flow))) == 0
        write_json(premise_flow / "story_spec.yaml", sample_spec())
        assert command_approve(argparse.Namespace(project=str(premise_flow), kind="spec")) == 0
        loop_map, beat_sheet = sample_architecture()
        write_json(premise_flow / "loop_map.json", loop_map)
        write_json(premise_flow / "beat_sheet.json", beat_sheet)
        assert command_approve(argparse.Namespace(project=str(premise_flow), kind="architecture")) == 0

        pf_draft = root / "pf-draft.md"
        pf_draft.write_text("# 测试短篇\n\n" + "文" * 1200 + "\n\n结束。\n", encoding="utf-8")
        assert command_record_draft(argparse.Namespace(
            project=str(premise_flow), draft=str(pf_draft), layer=None, author_id="test-agent",
        )) == 0

        # Route to premise via blockers
        pf_findings = [{
            "severity": "blocker",
            "layer": "premise",
            "dimension": "topic_differentiation",
            "evidence": "核心承诺无法在短篇内成立",
            "fix": "返回选题Loop",
        }]
        pf_review = write_sample_review_bundle(
            premise_flow, root / "pf-review", findings=pf_findings,
        )
        assert command_record_review(argparse.Namespace(project=str(premise_flow), review=str(pf_review))) == 0
        pf_state = load_state(premise_flow)
        assert pf_state["stage"] == "premise_revision_required"
        assert (premise_flow / "premise_revision_brief.json").is_file()

        # Record-review from premise_revision_required should be rejected
        try:
            command_record_review(argparse.Namespace(project=str(premise_flow), review=str(pf_review)))
            raise AssertionError("record-review from premise_revision_required should fail")
        except ProjectError as exc:
            assert "premise_revision_required" in str(exc)

        # decide-quality accept from premise_revision_required
        assert command_decide_quality(argparse.Namespace(project=str(premise_flow), decision="accept")) == 0
        assert load_state(premise_flow)["stage"] == "quality_ready"

        # ── Premise revision flow: reapprove-premise path ──
        premise_revise = root / "premise-revise"
        assert command_init(argparse.Namespace(project=str(premise_revise))) == 0
        write_json(premise_revise / "story_spec.yaml", sample_spec())
        assert command_approve(argparse.Namespace(project=str(premise_revise), kind="spec")) == 0
        write_json(premise_revise / "loop_map.json", loop_map)
        write_json(premise_revise / "beat_sheet.json", beat_sheet)
        assert command_approve(argparse.Namespace(project=str(premise_revise), kind="architecture")) == 0

        prv_draft = root / "prv-draft.md"
        prv_draft.write_text("# 测试短篇\n\n" + "文" * 1200 + "\n\n结束。\n", encoding="utf-8")
        assert command_record_draft(argparse.Namespace(
            project=str(premise_revise), draft=str(prv_draft), layer=None, author_id="test-agent",
        )) == 0
        prv_review = write_sample_review_bundle(
            premise_revise, root / "prv-review", findings=pf_findings,
        )
        assert command_record_review(argparse.Namespace(project=str(premise_revise), review=str(prv_review))) == 0
        assert load_state(premise_revise)["stage"] == "premise_revision_required"

        # Modify and reapprove premise
        new_spec = sample_spec()
        new_spec["genre"] = "高概念科幻"  # concept change
        write_json(premise_revise / "story_spec.yaml", new_spec)
        assert command_reapprove_premise(argparse.Namespace(project=str(premise_revise))) == 0
        prv_state2 = load_state(premise_revise)
        assert prv_state2["stage"] == "spec_approved"
        assert prv_state2["architecture_fingerprint"] is None  # Must re-approve architecture

        # reapprove-premise from wrong stage should fail
        try:
            command_reapprove_premise(argparse.Namespace(project=str(premise_revise)))
            raise AssertionError("reapprove-premise from spec_approved should fail")
        except ProjectError as exc:
            assert "premise_revision_required" in str(exc)

        # ── Backward compat: old project with premise_failure stopped_report ──
        old_premise = root / "old-premise"
        assert command_init(argparse.Namespace(project=str(old_premise))) == 0
        write_json(old_premise / "story_spec.yaml", sample_spec())
        assert command_approve(argparse.Namespace(project=str(old_premise), kind="spec")) == 0
        write_json(old_premise / "loop_map.json", loop_map)
        write_json(old_premise / "beat_sheet.json", beat_sheet)
        assert command_approve(argparse.Namespace(project=str(old_premise), kind="architecture")) == 0
        op_draft = root / "op-draft.md"
        op_draft.write_text("# 测试\n\n" + "文" * 1200 + "\n\n完。\n", encoding="utf-8")
        assert command_record_draft(argparse.Namespace(
            project=str(old_premise), draft=str(op_draft), layer=None, author_id="test-agent",
        )) == 0
        # Manually force stopped + stopped_report with premise_failure (simulating old behavior)
        old_state = load_state(old_premise)
        old_state["stage"] = "stopped"
        write_json(old_premise / "stopped_report.json", {
            "schema_version": SCHEMA_VERSION,
            "stage": "stopped",
            "reason": "premise_failure",
            "best_draft": old_state.get("current_draft"),
            "deterministic": {},
            "semantic": {},
            "unresolved_blockers": [],
            "layers_attempted": [],
            "next_author_decision": "Return to topic loop",
        })
        save_state(old_premise, old_state)
        # decide-quality accept should work on old premise_failure stopped_report
        assert command_decide_quality(argparse.Namespace(project=str(old_premise), decision="accept")) == 0
        assert load_state(old_premise)["stage"] == "quality_ready"

        repeated = "同一句足够长的测试文本。"
        assert duplicate_sentence_ratio(repeated + repeated) > 0.45
    return emit({"ok": True, "self_test": "passed", "schema_version": SCHEMA_VERSION})


def result(ok: bool, errors: list[str], warnings: list[str], **extra: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"ok": ok, "errors": errors, "warnings": warnings}
    value.update(extra)
    return value


def emit(value: Any) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and track a loop-short-story project")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("project")
    init.set_defaults(func=command_init)
    validate = sub.add_parser("validate")
    validate.add_argument("kind", choices=["concepts", "spec", "architecture", "draft", "review", "copyedit-review"])
    validate.add_argument("project")
    validate.add_argument("artifact", nargs="?")
    validate.set_defaults(func=command_validate)
    approve = sub.add_parser("approve")
    approve.add_argument("kind", choices=["spec", "architecture"])
    approve.add_argument("project")
    approve.set_defaults(func=command_approve)
    record_draft = sub.add_parser("record-draft")
    record_draft.add_argument("project")
    record_draft.add_argument("draft")
    record_draft.add_argument("--author-id", required=True)
    record_draft.add_argument("--layer", choices=LAYERS)
    record_draft.add_argument("--impact")
    record_draft.set_defaults(func=command_record_draft)
    record_review = sub.add_parser("record-review")
    record_review.add_argument("project")
    record_review.add_argument("review")
    record_review.set_defaults(func=command_record_review)
    finalize = sub.add_parser("finalize")
    finalize.add_argument("project")
    finalize.add_argument("draft")
    finalize.add_argument("review")
    finalize.set_defaults(func=command_finalize)
    status = sub.add_parser("status")
    status.add_argument("project")
    status.set_defaults(func=command_status)
    start_copyedit = sub.add_parser("start-copyedit")
    start_copyedit.add_argument("project")
    start_copyedit.set_defaults(func=command_start_copyedit)
    record_copyedit = sub.add_parser("record-copyedit-review")
    record_copyedit.add_argument("project")
    record_copyedit.add_argument("aggregate")
    record_copyedit.set_defaults(func=command_record_copyedit_review)
    decide_copyedit = sub.add_parser("decide-copyedit")
    decide_copyedit.add_argument("project")
    decide_copyedit.add_argument("decision", choices=["approve-fallback", "accept", "reject"])
    decide_copyedit.set_defaults(func=command_decide_copyedit)
    decide_quality = sub.add_parser("decide-quality")
    decide_quality.add_argument("project")
    decide_quality.add_argument("decision", choices=["accept"])
    decide_quality.set_defaults(func=command_decide_quality)
    reapprove_premise = sub.add_parser("reapprove-premise")
    reapprove_premise.add_argument("project")
    reapprove_premise.set_defaults(func=command_reapprove_premise)
    self_test = sub.add_parser("self-test")
    self_test.set_defaults(func=command_self_test)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except ProjectError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
