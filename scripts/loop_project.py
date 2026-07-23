#!/usr/bin/env python3
"""Portable state and validation tool for write-loop-short-story.

Uses only the Python standard library. All commands emit JSON to stdout.
Validation failures return exit code 1; usage or unsafe state errors return 2.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any


PHASES = ["anchor", "anomaly", "rule", "truth", "false_escape_twist"]
SCORE_KEYS = [
    "opening_effectiveness",
    "causal_logic",
    "information_progression",
    "clue_fairness",
    "character_choice",
    "prose_naturalness",
    "ending_resonance",
]
TEST_KEYS = [
    "false_ending_stands_without_twist",
    "two_clues_gain_second_meaning",
    "actions_follow_knowledge",
    "truth_not_revealed_too_early",
    "twist_uses_existing_evidence",
]
LAYERS = ["structure", "clue", "character", "prose"]


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


def project_path(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def state_path(project: Path) -> Path:
    return project / "state.json"


def load_state(project: Path) -> dict[str, Any]:
    value = read_json(state_path(project))
    if not isinstance(value, dict):
        raise ProjectError("state.json must contain an object")
    return value


def save_state(project: Path, state: dict[str, Any]) -> None:
    write_json(state_path(project), state)


def add_event(state: dict[str, Any], event: str, **details: Any) -> None:
    item = {"event": event, "at": now()}
    item.update(details)
    state.setdefault("history", []).append(item)


def template_spec() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "language": "zh-CN",
        "target_length": {"min": 1000, "max": 2000, "unit": "non_whitespace_characters"},
        "theme": "",
        "protagonist": {"identity": "", "desire": "", "flaw": ""},
        "loop": {
            "trigger": "",
            "reset": "",
            "retained_memory": "",
            "rule": "",
            "exception": "",
            "true_cause": "",
        },
        "key_clues": ["", "", ""],
        "red_herring": "",
        "apparent_escape": "",
        "final_twist": "",
        "forbidden_tropes": [""],
        "style_constraints": [],
    }


def command_init(args: argparse.Namespace) -> int:
    project = project_path(args.project)
    if project.exists() and any(project.iterdir()):
        raise ProjectError(f"refusing to overwrite non-empty directory: {project}")
    project.mkdir(parents=True, exist_ok=True)
    (project / "drafts").mkdir(exist_ok=True)
    (project / "reviews").mkdir(exist_ok=True)
    write_json(project / "story_spec.yaml", template_spec())
    state = {
        "schema_version": 1,
        "stage": "initialized",
        "revision_count": 0,
        "current_draft": None,
        "current_review": None,
        "spec_fingerprint": None,
        "outline_fingerprint": None,
        "next_layer": None,
        "layers_attempted": [],
        "history": [],
    }
    add_event(state, "initialized")
    save_state(project, state)
    return emit({"ok": True, "project": str(project), "stage": "initialized"})


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_spec(project: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        spec = read_json(project / "story_spec.yaml")
    except ProjectError as exc:
        return result(False, [str(exc)], warnings)
    if not isinstance(spec, dict):
        return result(False, ["story_spec.yaml must contain an object"], warnings)
    if spec.get("schema_version") != 1:
        errors.append("schema_version must equal 1")
    if spec.get("language") != "zh-CN":
        warnings.append("language is not zh-CN")
    target = spec.get("target_length")
    if target != {"min": 1000, "max": 2000, "unit": "non_whitespace_characters"}:
        errors.append("target_length must be 1000–2000 non_whitespace_characters")
    for key in ("theme", "red_herring", "apparent_escape", "final_twist"):
        if not nonempty(spec.get(key)):
            errors.append(f"{key} must be a non-empty string")
    protagonist = spec.get("protagonist")
    if not isinstance(protagonist, dict):
        errors.append("protagonist must be an object")
    else:
        for key in ("identity", "desire", "flaw"):
            if not nonempty(protagonist.get(key)):
                errors.append(f"protagonist.{key} must be a non-empty string")
    loop = spec.get("loop")
    if not isinstance(loop, dict):
        errors.append("loop must be an object")
    else:
        for key in ("trigger", "reset", "retained_memory", "rule", "exception", "true_cause"):
            if not nonempty(loop.get(key)):
                errors.append(f"loop.{key} must be a non-empty string")
        if nonempty(loop.get("rule")) and loop.get("rule", "").strip() == loop.get("exception", "").strip():
            errors.append("loop.rule and loop.exception must differ")
    clues = spec.get("key_clues")
    if not isinstance(clues, list) or len(clues) != 3 or any(not nonempty(x) for x in clues):
        errors.append("key_clues must contain exactly three non-empty strings")
    elif len({x.strip() for x in clues}) != 3:
        errors.append("key_clues must be distinct")
    forbidden = spec.get("forbidden_tropes")
    if not isinstance(forbidden, list) or not forbidden or any(not nonempty(x) for x in forbidden):
        errors.append("forbidden_tropes must contain at least one non-empty string")
    styles = spec.get("style_constraints")
    if not isinstance(styles, list) or any(not nonempty(x) for x in styles):
        errors.append("style_constraints must be an array of non-empty strings")
    return result(not errors, errors, warnings, fingerprint=canonical_hash(spec) if not errors else None)


def validate_outline(project: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        beats = read_json(project / "beat_sheet.json")
        clues = read_json(project / "clue_ledger.json")
    except ProjectError as exc:
        return result(False, [str(exc)], warnings)
    if not isinstance(beats, list) or not 1 <= len(beats) <= 7:
        return result(False, ["beat_sheet.json must contain one to seven scenes"], warnings)
    scene_ids: list[str] = []
    seen_phases: list[str] = []
    clue_usage: set[str] = set()
    shares: list[float] = []
    for index, scene in enumerate(beats, start=1):
        prefix = f"scene {index}"
        if not isinstance(scene, dict):
            errors.append(f"{prefix} must be an object")
            continue
        sid = scene.get("id")
        if not nonempty(sid):
            errors.append(f"{prefix}.id must be non-empty")
        else:
            scene_ids.append(sid.strip())
        phase = scene.get("phase")
        if phase not in PHASES:
            errors.append(f"{prefix}.phase must be one of {PHASES}")
        else:
            seen_phases.append(phase)
        share = scene.get("target_share")
        if not isinstance(share, (int, float)) or isinstance(share, bool) or share <= 0:
            errors.append(f"{prefix}.target_share must be a positive number")
        else:
            shares.append(float(share))
        for key in ("goal", "conflict"):
            if not nonempty(scene.get(key)):
                errors.append(f"{prefix}.{key} must be non-empty")
        ids = scene.get("clue_ids")
        if not isinstance(ids, list) or any(x not in {"C1", "C2", "C3"} for x in ids):
            errors.append(f"{prefix}.clue_ids may contain C1, C2, and C3 only")
        else:
            clue_usage.update(ids)
        delta = scene.get("delta")
        if not isinstance(delta, dict):
            errors.append(f"{prefix}.delta must be an object")
        else:
            for key in ("knowledge", "action", "cost"):
                if not nonempty(delta.get(key)):
                    errors.append(f"{prefix}.delta.{key} must be non-empty")
    if len(scene_ids) != len(set(scene_ids)):
        errors.append("scene ids must be unique")
    phase_numbers = [PHASES.index(x) for x in seen_phases]
    if set(seen_phases) != set(PHASES) or phase_numbers != sorted(phase_numbers):
        errors.append("all five phases must appear once or contiguously in the required order")
    if shares and not 0.98 <= sum(shares) <= 1.02:
        errors.append(f"target_share values must sum to 1.0, got {sum(shares):.3f}")
    if clue_usage != {"C1", "C2", "C3"}:
        errors.append("all three clue ids must appear in the BeatSheet")

    if not isinstance(clues, list) or len(clues) != 3:
        errors.append("clue_ledger.json must contain exactly three entries")
    else:
        ledger_ids: list[str] = []
        scene_order = {sid: i for i, sid in enumerate(scene_ids)}
        for index, clue in enumerate(clues, start=1):
            prefix = f"clue {index}"
            if not isinstance(clue, dict):
                errors.append(f"{prefix} must be an object")
                continue
            cid = clue.get("id")
            if nonempty(cid):
                ledger_ids.append(cid.strip())
            else:
                errors.append(f"{prefix}.id must be non-empty")
            for key in ("surface", "misread_as", "true_meaning"):
                if not nonempty(clue.get(key)):
                    errors.append(f"{prefix}.{key} must be non-empty")
            plant = clue.get("plant_scene")
            payoff = clue.get("payoff_scene")
            if plant not in scene_order:
                errors.append(f"{prefix}.plant_scene must reference an existing scene")
            if payoff not in scene_order:
                errors.append(f"{prefix}.payoff_scene must reference an existing scene")
            if plant in scene_order and payoff in scene_order and scene_order[plant] > scene_order[payoff]:
                errors.append(f"{prefix} cannot be planted after its payoff")
        if set(ledger_ids) != {"C1", "C2", "C3"} or len(ledger_ids) != 3:
            errors.append("clue ledger ids must be exactly C1, C2, and C3")
    fingerprint = canonical_hash({"beat_sheet": beats, "clue_ledger": clues}) if not errors else None
    return result(not errors, errors, warnings, fingerprint=fingerprint)


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


def approval_errors(project: Path, state: dict[str, Any], outline: bool = True) -> list[str]:
    errors: list[str] = []
    try:
        current_spec = file_hash(project / "story_spec.yaml")
    except ProjectError as exc:
        return [str(exc)]
    if state.get("spec_fingerprint") != current_spec:
        errors.append("approved StorySpec fingerprint does not match the current file")
    if outline:
        check = validate_outline(project)
        if not check["ok"]:
            errors.extend(check["errors"])
        elif state.get("outline_fingerprint") != check.get("fingerprint"):
            errors.append("approved outline fingerprint does not match current files")
    return errors


def validate_draft(project: Path, draft_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        state = load_state(project)
        text = draft_path.read_text(encoding="utf-8")
    except (ProjectError, FileNotFoundError) as exc:
        return result(False, [str(exc)], warnings)
    errors.extend(approval_errors(project, state, outline=True))
    body, has_title = story_body(text)
    if not has_title:
        errors.append("draft must begin with one Markdown H1 title")
    length = len(re.sub(r"\s+", "", body))
    if not 1000 <= length <= 2000:
        errors.append(f"body length must be 1000–2000 non-whitespace characters, got {length}")
    ratio = duplicate_sentence_ratio(body)
    if ratio > 0.15:
        errors.append(f"exact repeated-sentence ratio exceeds 0.15: {ratio:.4f}")
    markers = ["Δ认知", "Δ行动", "Δ代价", "ClueLedger", "BeatSheet", "ReviewReport"]
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


def review_analysis(review: Any) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(review, dict):
        return result(False, ["review must be an object"], warnings)
    if review.get("schema_version") != 1:
        errors.append("review.schema_version must equal 1")
    if not nonempty(review.get("draft")):
        errors.append("review.draft must be non-empty")
    scores = review.get("scores")
    clean_scores: dict[str, int] = {}
    if not isinstance(scores, dict):
        errors.append("review.scores must be an object")
    else:
        for key in SCORE_KEYS:
            value = scores.get(key)
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 5:
                errors.append(f"score {key} must be an integer from 0 to 5")
            else:
                clean_scores[key] = value
    blockers = review.get("blockers")
    blocker_layers: list[str] = []
    if not isinstance(blockers, list):
        errors.append("review.blockers must be an array")
    else:
        for index, blocker in enumerate(blockers, start=1):
            if not isinstance(blocker, dict):
                errors.append(f"blocker {index} must be an object")
                continue
            layer = blocker.get("layer")
            if layer not in LAYERS:
                errors.append(f"blocker {index}.layer must be one of {LAYERS}")
            else:
                blocker_layers.append(layer)
            for key in ("evidence", "fix"):
                if not nonempty(blocker.get(key)):
                    errors.append(f"blocker {index}.{key} must be non-empty")
    tests = review.get("reader_tests")
    clean_tests: dict[str, bool] = {}
    if not isinstance(tests, dict):
        errors.append("review.reader_tests must be an object")
    else:
        for key in TEST_KEYS:
            value = tests.get(key)
            if not isinstance(value, bool):
                errors.append(f"reader test {key} must be boolean")
            else:
                clean_tests[key] = value
    if not nonempty(review.get("theme_sentence")):
        errors.append("review.theme_sentence must be non-empty")
    if not isinstance(review.get("warnings", []), list):
        errors.append("review.warnings must be an array")
    if errors:
        return result(False, errors, warnings, semantic_pass=False, route=None)

    total = sum(clean_scores.values())
    semantic_pass = (
        total >= 29
        and clean_scores["causal_logic"] >= 4
        and clean_scores["clue_fairness"] >= 4
        and all(clean_scores[key] >= 3 for key in SCORE_KEYS if key not in {"causal_logic", "clue_fairness"})
        and all(clean_tests.values())
        and not blockers
    )
    route: str | None = None
    if not semantic_pass:
        route = route_review(clean_scores, clean_tests, blocker_layers, total)
    return result(
        True,
        [],
        warnings,
        semantic_pass=semantic_pass,
        total_score=total,
        route=route,
    )


def route_review(scores: dict[str, int], tests: dict[str, bool], blockers: list[str], total: int) -> str:
    if (
        "structure" in blockers
        or scores["causal_logic"] < 4
        or scores["information_progression"] < 3
        or not tests["actions_follow_knowledge"]
    ):
        return "structure"
    if (
        "clue" in blockers
        or scores["clue_fairness"] < 4
        or not tests["false_ending_stands_without_twist"]
        or not tests["two_clues_gain_second_meaning"]
        or not tests["truth_not_revealed_too_early"]
        or not tests["twist_uses_existing_evidence"]
    ):
        return "clue"
    if "character" in blockers or scores["character_choice"] < 3:
        return "character"
    if (
        "prose" in blockers
        or scores["opening_effectiveness"] < 3
        or scores["prose_naturalness"] < 3
        or scores["ending_resonance"] < 3
        or total < 29
    ):
        return "prose"
    return "prose"


def command_validate(args: argparse.Namespace) -> int:
    project = project_path(args.project)
    if args.kind == "spec":
        check = validate_spec(project)
    elif args.kind == "outline":
        check = validate_outline(project)
    elif args.kind == "draft":
        draft = resolve_artifact(project, args.artifact, "draft")
        check = validate_draft(project, draft)
    else:
        review_path = resolve_artifact(project, args.artifact, "review")
        try:
            review = read_json(review_path)
            check = review_analysis(review)
        except ProjectError as exc:
            check = result(False, [str(exc)], [])
        check["review"] = str(review_path)
    emit(check)
    return 0 if check["ok"] else 1


def command_approve(args: argparse.Namespace) -> int:
    project = project_path(args.project)
    state = load_state(project)
    if args.kind == "spec":
        check = validate_spec(project)
        if not check["ok"]:
            emit(check)
            return 1
        current = check["fingerprint"]
        if state.get("current_draft") and state.get("spec_fingerprint") != current:
            raise ProjectError("cannot change StorySpec after drafting; start a new project to preserve provenance")
        state["spec_fingerprint"] = current
        state["outline_fingerprint"] = None
        state["stage"] = "spec_approved"
        state["next_layer"] = None
        add_event(state, "spec_approved", fingerprint=current)
    else:
        spec_errors = approval_errors(project, state, outline=False)
        if spec_errors:
            emit(result(False, spec_errors, []))
            return 1
        check = validate_outline(project)
        if not check["ok"]:
            emit(check)
            return 1
        state["outline_fingerprint"] = check["fingerprint"]
        state["stage"] = "outline_approved"
        state["next_layer"] = None
        add_event(state, "outline_approved", fingerprint=check["fingerprint"])
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
    if state.get("stage") in {"complete", "stopped"}:
        raise ProjectError(f"cannot record a draft after project stage {state.get('stage')}")
    errors = approval_errors(project, state, outline=True)
    if errors:
        emit(result(False, errors, []))
        return 1
    source = Path(args.draft).expanduser().resolve()
    if not source.is_file():
        raise ProjectError(f"draft not found: {source}")
    check = validate_draft(project, source)
    if not check["ok"]:
        emit(check)
        return 1
    current = state.get("current_draft")
    if current is None:
        if args.layer:
            raise ProjectError("the initial draft must not specify a revision layer")
        version = 0
    else:
        if args.layer not in LAYERS:
            raise ProjectError(f"a revision must specify one layer from {LAYERS}")
        if state.get("revision_count", 0) >= 3:
            raise ProjectError("revision budget exhausted")
        if args.layer == "structure" and not any(
            item.get("event") == "outline_approved" and item.get("at", "") > state.get("last_review_at", "")
            for item in state.get("history", [])
        ):
            raise ProjectError("a structure revision requires renewed outline approval after the last review")
        state["revision_count"] = int(state.get("revision_count", 0)) + 1
        version = state["revision_count"]
        state.setdefault("layers_attempted", []).append(args.layer)
    destination = project / "drafts" / f"draft-v{version}.md"
    safely_copy(source, destination)
    check["draft"] = str(destination.resolve())
    state["current_draft"] = str(destination.relative_to(project)).replace("\\", "/")
    state["current_review"] = None
    state["stage"] = "reviewing"
    state["next_layer"] = None
    add_event(state, "draft_recorded", version=version, layer=args.layer)
    save_state(project, state)
    check.update({"stage": "reviewing", "version": version})
    return emit(check)


def command_record_review(args: argparse.Namespace) -> int:
    project = project_path(args.project)
    state = load_state(project)
    draft = resolve_artifact(project, None, "draft")
    draft_check = validate_draft(project, draft)
    if not draft_check["ok"]:
        emit(draft_check)
        return 1
    source = Path(args.review).expanduser().resolve()
    review = read_json(source)
    check = review_analysis(review)
    if not check["ok"]:
        emit(check)
        return 1
    if Path(review["draft"]).name != draft.name:
        raise ProjectError(f"review targets {review['draft']}, current draft is {draft.name}")
    version = int(state.get("revision_count", 0))
    destination = project / "reviews" / f"review-v{version}.json"
    safely_copy(source, destination)
    state["current_review"] = str(destination.relative_to(project)).replace("\\", "/")
    state["last_review_at"] = now()
    if check["semantic_pass"]:
        state["stage"] = "review_passed"
        state["next_layer"] = None
    elif version >= 3:
        state["stage"] = "stopped"
        state["next_layer"] = None
        write_json(project / "stopped_report.json", {
            "stage": "stopped",
            "reason": "revision_budget_exhausted",
            "draft": draft.name,
            "deterministic": draft_check,
            "semantic": check,
            "unresolved_blockers": review.get("blockers", []),
            "layers_attempted": state.get("layers_attempted", []),
            "next_author_decision": "Revise the premise or architecture in a new author-approved cycle.",
        })
    elif check["route"] == "structure":
        state["stage"] = "outline_revision_required"
        state["next_layer"] = "structure"
        state["outline_fingerprint"] = None
    else:
        state["stage"] = "revision_required"
        state["next_layer"] = check["route"]
    add_event(state, "review_recorded", version=version, semantic_pass=check["semantic_pass"], route=check["route"])
    save_state(project, state)
    check.update({"stage": state["stage"], "review": str(destination)})
    return emit(check)


def command_finalize(args: argparse.Namespace) -> int:
    project = project_path(args.project)
    state = load_state(project)
    draft = Path(args.draft).expanduser().resolve()
    review_path = Path(args.review).expanduser().resolve()
    current_draft = resolve_artifact(project, None, "draft")
    current_review = resolve_artifact(project, None, "review")
    if draft != current_draft or review_path != current_review:
        raise ProjectError("finalize must use the current recorded draft and review")
    draft_check = validate_draft(project, draft)
    review_check = review_analysis(read_json(review_path))
    if not draft_check["ok"] or not review_check["ok"] or not review_check["semantic_pass"]:
        emit({"ok": False, "draft": draft_check, "review": review_check})
        return 1
    if state.get("stage") != "review_passed":
        raise ProjectError(f"project stage must be review_passed, got {state.get('stage')}")
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
    if (project / "beat_sheet.json").exists() or (project / "clue_ledger.json").exists():
        checks["outline"] = validate_outline(project)
    if state.get("current_draft"):
        checks["draft"] = validate_draft(project, resolve_artifact(project, None, "draft"))
    return emit({"ok": True, "project": str(project), "state": state, "checks": checks})


def command_self_test(_: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory() as temp:
        project = Path(temp) / "story"
        command_init(argparse.Namespace(project=str(project)))
        spec = template_spec()
        spec.update({
            "theme": "逃避选择会使出口变成另一层牢笼",
            "protagonist": {"identity": "维修员", "desire": "离开车站", "flaw": "拒绝承担责任"},
            "loop": {
                "trigger": "签字", "reset": "钟声", "retained_memory": "灼痛",
                "rule": "每次签字都会重置", "exception": "记忆保留", "true_cause": "责任测试",
            },
            "key_clues": ["停钟", "旧录音", "破损花盆"],
            "red_herring": "未来的自己在求救",
            "apparent_escape": "删除自己的权限",
            "final_twist": "出口只是下一层测试",
            "forbidden_tropes": ["梦醒后一切没发生"],
        })
        write_json(project / "story_spec.yaml", spec)
        assert command_approve(argparse.Namespace(project=str(project), kind="spec")) == 0
        beats = []
        for i, phase in enumerate(PHASES, start=1):
            beats.append({
                "id": f"S{i}", "phase": phase, "target_share": [0.1, 0.2, 0.25, 0.3, 0.15][i - 1],
                "goal": "目标", "conflict": "冲突", "clue_ids": [f"C{min(i, 3)}"],
                "delta": {"knowledge": "新认知", "action": "新行动", "cost": "新代价"},
            })
        ledger = [
            {"id": f"C{i}", "surface": "表象", "plant_scene": f"S{i}", "misread_as": "误读", "true_meaning": "真义", "payoff_scene": "S5"}
            for i in range(1, 4)
        ]
        write_json(project / "beat_sheet.json", beats)
        write_json(project / "clue_ledger.json", ledger)
        assert command_approve(argparse.Namespace(project=str(project), kind="outline")) == 0
        draft = project / "incoming.md"
        draft.write_text("# 测试\n\n" + "月" * 1100 + "。\n\n结束。\n", encoding="utf-8")
        assert command_record_draft(argparse.Namespace(project=str(project), draft=str(draft), layer=None)) == 0
        review = {
            "schema_version": 1,
            "draft": "draft-v0.md",
            "scores": {key: 5 for key in SCORE_KEYS},
            "blockers": [],
            "reader_tests": {key: True for key in TEST_KEYS},
            "theme_sentence": "选择需要承担代价。",
            "warnings": [],
        }
        review_path = project / "incoming-review.json"
        write_json(review_path, review)
        assert command_record_review(argparse.Namespace(project=str(project), review=str(review_path))) == 0
        current_draft = project / "drafts" / "draft-v0.md"
        current_review = project / "reviews" / "review-v0.json"
        assert command_finalize(argparse.Namespace(project=str(project), draft=str(current_draft), review=str(current_review))) == 0
        assert load_state(project)["stage"] == "complete"
        failing_review = dict(review)
        failing_review["scores"] = dict(review["scores"])
        failing_review["scores"]["causal_logic"] = 2
        failing_review["reader_tests"] = dict(review["reader_tests"])
        failing_review["reader_tests"]["actions_follow_knowledge"] = False
        analysis = review_analysis(failing_review)
        assert analysis["ok"] and not analysis["semantic_pass"] and analysis["route"] == "structure"
        repeated = "同一句足够长的测试文本。"
        assert duplicate_sentence_ratio(repeated + repeated) > 0.45
    return emit({"ok": True, "self_test": "passed"})


def result(ok: bool, errors: list[str], warnings: list[str], **extra: Any) -> dict[str, Any]:
    value: dict[str, Any] = {"ok": ok, "errors": errors, "warnings": warnings}
    value.update(extra)
    return value


def emit(value: Any) -> int:
    print(json.dumps(value, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and track a loop short-story project")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("project")
    init.set_defaults(func=command_init)
    validate = sub.add_parser("validate")
    validate.add_argument("kind", choices=["spec", "outline", "draft", "review"])
    validate.add_argument("project")
    validate.add_argument("artifact", nargs="?")
    validate.set_defaults(func=command_validate)
    approve = sub.add_parser("approve")
    approve.add_argument("kind", choices=["spec", "outline"])
    approve.add_argument("project")
    approve.set_defaults(func=command_approve)
    record_draft = sub.add_parser("record-draft")
    record_draft.add_argument("project")
    record_draft.add_argument("draft")
    record_draft.add_argument("--layer", choices=LAYERS)
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
