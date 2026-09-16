"""Versioned submission checks shared by the production controller.

These checks verify actual bindings, measured reuse and completed review evidence.
They cannot certify that prose is persuasive or that a reviewer really watched.
No approval or production file is written by this module.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def json_digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def enabled(authority):
    return authority.get('delivery_spec', {}).get('production_contract_version') == 2


def checked_ref(root, ref):
    if not isinstance(ref, dict) or not ref.get('path') or not ref.get('sha256'):
        raise ValueError('a file path and SHA-256 binding are required')
    path = (Path(root) / ref['path']).resolve()
    if not path.is_file() or digest(path) != ref['sha256']:
        raise ValueError(f'missing or changed bound file: {path}')
    return path


def read_ref(root, ref):
    return json.loads(checked_ref(root, ref).read_text())


def bind_item(root, ref, item, label):
    path = checked_ref(root, ref)
    if not item or ref['sha256'] != item.get('sha256') or path != (Path(root)/item['path']).resolve():
        raise ValueError(f'{label} does not bind the current artifact')


def review(root, value, label, proof=True):
    if not isinstance(value, dict) or str(value.get('status', '')).lower() != 'pass':
        raise ValueError(f'{label}: actual review is incomplete')
    if not str(value.get('reviewer', '')).strip() or not str(value.get('notes', '')).strip():
        raise ValueError(f'{label}: reviewer and substantive review notes are required')
    if proof:
        refs = value.get('evidence', [])
        if not isinstance(refs, list) or not refs:
            raise ValueError(f'{label}: bound review evidence is required')
        for ref in refs:
            checked_ref(root, ref)


def check_submission(root, role, item, authority, items):
    """Return actionable errors; v1 projects keep their frozen contract."""
    if not enabled(authority):
        return []
    report_role = {
        'script_qa': ('editorial_submission_v2', ['script']),
        'voice_release': ('voice_submission_v2', ['script', 'narration']),
        'source_freeze': ('source_capacity_v2', ['subtitle']),
        'a_review': ('a_submission_v2', ['track_plan', 'narration', 'subtitle', 'timing_contract']),
    }.get(role)
    if not report_role:
        return []
    try:
        report = read_ref(root, item.get('meta', {}).get('submission_review'))
        if report.get('schema') != report_role[0] or report.get('status') != 'PASS':
            raise ValueError(f'{role}: a PASS {report_role[0]} report is required')
        bindings = report.get('bindings', {})
        for key in report_role[1]:
            target = items.get(key) or authority.get(key)
            bind_item(root, bindings.get(key), target, key)
        if role == 'script_qa':
            for key in ('thesis_and_evidence', 'character_motivation', 'counterexplanation_and_falsifier',
                        'full_referent_and_readaloud_review', 'opening_promise', 'ending_payoff'):
                review(root, report.get(key), key)
            canonical = checked_ref(root, bindings.get('canonical_text')).read_text()
            ending = authority['delivery_spec'].get('fixed_signoff')
            if ending and not canonical.rstrip().endswith(ending):
                raise ValueError('canonical text does not end with the fixed Foxjiu signoff')
        elif role == 'voice_release':
            for key in ('fixed_reference_preflight', 'opening_prosody', 'pronunciation_hotspots', 'joins_and_tail'):
                review(root, report.get(key), key)
            preflight = read_ref(root, report.get('reference_preflight'))
            if preflight.get('passed') is not True or preflight.get('phase') != 'bulk':
                raise ValueError('bulk voice-reference and opening-smoke preflight must pass')
            for key in ('source_manifest_binding', 'rule_binding', 'smoke_review_binding'):
                checked_ref(root, preflight.get(key))
            if preflight.get('reference_sha256') != authority['delivery_spec'].get('voice_reference_sha256'):
                raise ValueError('voice preflight does not use the frozen series reference')
            verifier_path = Path(__file__).resolve().parents[2]/'voxcpm-batch-dubbing/scripts/verify_voice_reference.py'
            loader = importlib.util.spec_from_file_location('voice_contract_preflight', verifier_path)
            verifier = importlib.util.module_from_spec(loader)
            loader.loader.exec_module(verifier)
            fresh = verifier.verify(checked_ref(root, preflight['source_manifest_binding']),
                                    checked_ref(root, preflight['rule_binding']), 'bulk',
                                    checked_ref(root, preflight['smoke_review_binding']))
            if not fresh['passed']:
                raise ValueError('voice inputs or actual opening sample changed: ' + '; '.join(fresh['failures']))
        elif role == 'source_freeze':
            bind_item(root, bindings.get('source_freeze'), item, 'source_freeze')
            rows = report.get('capacities', [])
            if not rows or report.get('unresolved_capacity_gaps') != 0:
                raise ValueError('source capacity assessment is missing or has unresolved gaps')
            for row in rows:
                need = row.get('required_slots')
                groups = row.get('eligible_physical_groups', [])
                callbacks = row.get('planned_callbacks', 0)
                if not row.get('subject') or type(need) is not int or need < 1 or type(callbacks) is not int or callbacks < 0:
                    raise ValueError('capacity rows require a subject, positive demand and explicit callbacks')
                if len(set(groups)) != len(groups) or len(groups)+callbacks < need:
                    raise ValueError(f'not enough distinct physical shots for {row["subject"]}')
            if sum(x.get('planned_callbacks', 0) for x in rows) > authority['delivery_spec'].get('max_reuse_groups', 4):
                raise ValueError('capacity plan exceeds the episode callback allowance')
            review(root, report.get('capacity_review'), 'capacity_review')
        elif role == 'a_review':
            check_a_submission(root, report, authority, item)
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        return [f'{role} submission gate: {exc}']
    return []


def check_a_submission(root, report, authority, item):
    spec = authority['delivery_spec']
    bindings = report['bindings']
    selected = read_ref(root, bindings.get('selected_segments'))
    segments = selected.get('segments') if isinstance(selected, dict) else selected
    if not isinstance(segments, list) or not segments:
        raise ValueError('selected A segments are missing')
    origins = read_ref(root, report['source_origins']) if report.get('source_origins') else {}
    aliases = read_ref(root, report['family_aliases']) if report.get('family_aliases') else {}
    module_path = Path(__file__).resolve().parents[2]/'zhangyanfa-track-design/scripts/audit_global_reuse.py'
    loader = importlib.util.spec_from_file_location('physical_reuse_contract', module_path)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    result = module.audit(segments, origins, aliases, spec.get('max_reuse_groups', 4), spec.get('max_group_occurrences', 2))
    if result['status'] != 'pass':
        raise ValueError(f'global physical-shot audit failed: {result["repeated_group_count"]} groups, '
                         f'maximum {result["max_group_occurrences"]} occurrences; {len(result["adjacent_violations"])} boundary issues')
    if segments[0]['start_frame'] != 0 or segments[-1]['end_frame'] != spec['target_frame_count']:
        raise ValueError('A must cover the full frozen clock including the audio tail')
    allowed = set(spec.get('a_visual_types', ['gameplay', 'official_cg', 'official_pv', 'story_cutscene']))
    for segment in segments:
        if segment.get('visual_type') not in allowed:
            raise ValueError(f'A contains missing/forbidden visual type: {segment.get("segment_id")}')
        if not segment.get('source_sha256') and not origins.get(segment['source_id'], {}).get('parent_sha256'):
            raise ValueError('physical source identity must include an original-file SHA')
        if segment.get('production_caption_baked') is not False or segment.get('production_card_baked') is not False:
            raise ValueError('A segment must explicitly exclude added narration captions and text cards')
    hook_end = min(spec['target_frame_count'], spec.get('hook_seconds', 10)*spec['fps'])
    hook = [s for s in segments if s['start_frame'] < hook_end]
    if any(s['visual_type'] not in {'official_cg', 'official_pv', 'story_cutscene'} for s in hook):
        raise ValueError('the opening must use CG/PV/story cutscenes throughout')
    if hook_end >= spec['fps']*3 and len({s['visual_family_id'] for s in hook}) < 2:
        raise ValueError('the opening requires distinct physical shots, not a single standing shot')
    for key in ('near_visual_review', 'whole_episode_review', 'opening_review', 'auxiliary_overlay_review'):
        review(root, report.get(key), key)
    opening = report['opening_review']
    if opening.get('watched_with_frozen_narration') is not True:
        raise ValueError('the opening must be reviewed together with frozen narration')
    roles = opening.get('shot_purposes', [])
    if {x.get('segment_id') for x in roles} != {s['segment_id'] for s in hook}:
        raise ValueError('every actual opening shot needs a narrative purpose')
    if any(not str(x.get('purpose', '')).strip() or not str(x.get('new_information', '')).strip() for x in roles):
        raise ValueError('opening shot purposes must explain the information each cut adds')
    ui = report.get('review_ui', {})
    if ui.get('framework_id') != 'foxjiu-review-ui-v1' or not ui.get('version_namespace'):
        raise ValueError('the fixed review UI and a version namespace are required')
    if ui.get('previous_version_namespace') == ui['version_namespace']:
        raise ValueError('a revised plan cannot inherit the old review draft namespace')
    framework = read_ref(root, ui.get('framework_manifest'))
    expected_sha = spec.get('review_ui_manifest_sha256')
    if expected_sha and ui['framework_manifest']['sha256'] != expected_sha:
        raise ValueError('review UI manifest differs from the frozen framework')
    for name, sha in framework.get('sha256', {}).items():
        ref = ui.get('framework_files', {}).get(name)
        checked_ref(root, ref)
        if ref['sha256'] != sha:
            raise ValueError(f'review UI framework was changed: {name}')
    if item.get('meta', {}).get('selected_segments_sha256') != bindings['selected_segments']['sha256']:
        raise ValueError('registered A review must bind the actually reviewed selected segments')


def check_bgm_derivation(root, authority, items, approvals, approval_for):
    errors = []
    try:
        candidate = items.get('bgm_review')
        master = items.get('bgm_master')
        if not candidate or not approval_for(approvals, candidate, 'bgm_review'):
            raise ValueError('the exact BGM audition must be selected first')
        if not master:
            raise ValueError('full-length BGM master is missing')
        derivation = read_ref(root, master.get('meta', {}).get('derivation'))
        if derivation.get('schema') != 'bgm_derivation_v2' or derivation.get('status') != 'PASS':
            raise ValueError('a bound full-length BGM derivation report is required')
        for role in ('bgm_review', 'bgm_master', 'narration', 'subtitle', 'timing_contract'):
            bind_item(root, derivation.get('bindings', {}).get(role), items.get(role) or authority.get(role), role)
        if derivation.get('candidate_id') != candidate.get('meta', {}).get('candidate_id'):
            raise ValueError('full-length BGM was derived from a different candidate')
        if derivation.get('target_frame_count') != authority['delivery_spec']['target_frame_count']:
            raise ValueError('BGM derivation uses the wrong clock')
        if derivation.get('chapter_coverage_pass') is not True or derivation.get('narration_intelligibility_pass') is not True:
            raise ValueError('BGM chapters or narration intelligibility did not pass')
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        errors.append(f'BGM derivation: {exc}')
    return errors


def check_split_delivery(root, authority, items):
    try:
        bundle_item = items.get('split_delivery')
        qa_item = items.get('split_delivery_qa')
        if not bundle_item or not qa_item:
            raise ValueError('independent delivery manifest and QA are required')
        bundle = json.loads((Path(root)/bundle_item['path']).read_text())
        qa = json.loads((Path(root)/qa_item['path']).read_text())
        if bundle.get('schema') != 'independent_delivery_v2' or bundle.get('status') != 'ready' or qa.get('status') != 'PASS':
            raise ValueError('independent delivery is incomplete')
        bind_item(root, qa.get('delivery'), bundle_item, 'split_delivery')
        spec = authority['delivery_spec']
        required = ['narration','subtitle','timing_contract','bgm_master','render_qa']
        required += [t.lower()+'_master' for t in spec['active_tracks'] if t in 'ABC']
        for role in required:
            bind_item(root, bundle.get('assets', {}).get(role), items.get(role), role)
        for key in ('width','height','fps','target_frame_count'):
            if bundle.get(key) != spec.get(key):
                raise ValueError(f'independent delivery {key} differs from the frozen clock')
        if bundle.get('a_subtitle_baked') != spec.get('a_subtitle_baked', False):
            raise ValueError('A caption output disagrees with the delivery contract')
        if bundle.get('a_audio_baked') is not False or bundle.get('a_auxiliary_overlays_baked') is not False:
            raise ValueError('independent A must not bake narration, BGM, or B/C overlays')
        if not qa.get('audio_tail_pass') or not qa.get('asset_clock_pass'):
            raise ValueError('independent assets have not passed clock/tail QA')
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as exc:
        return [f'independent delivery: {exc}']
    return []
