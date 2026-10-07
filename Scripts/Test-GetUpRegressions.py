"""Run recovery, ragdoll, interaction and parkour checks sequentially in standalone PIE."""
from pathlib import Path
import json
import time
import traceback
import unreal as u

recovery_root = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
recovery_steps = [
    ('Test-GetUpContinuity.py', 'getup_test', 'PhysicalTests/getup-continuity.json'),
    ('Test-RagdollSettling.py', 'settle_test', 'PhysicalTests/ragdoll-settling.json'),
    ('Test-PhysicalInteractions.py', 'physical_test', 'PhysicalTests/physical-interactions.json'),
    ('Test-PhysicalBoundaries.py', 'boundary_physical', 'PhysicalTests/physical-boundaries.json'),
    ('Test-TraversalGym.py', 'gym_test', 'GymTests/result.json'),
    ('Test-AutoGetUpContinuity.py', 'auto_getup', 'PhysicalTests/auto-getup-continuity.json'),
]
recovery_pipeline = {'index': 0, 'busy': False, 'results': [], 'started': time.time()}


def recovery_pipeline_finish(error=None):
    u.unregister_slate_post_tick_callback(recovery_pipeline['handle'])
    recovery_pipeline.update(finished=True, error=error)
    (recovery_root / 'Artifacts/PhysicalTests/getup-regressions.json').write_text(json.dumps({
        'passed': error is None, 'error': error, 'results': recovery_pipeline['results']}, indent=2))
    print('GETUP_REGRESSIONS_COMPLETE', error)


def recovery_pipeline_tick(dt):
    if recovery_pipeline['busy']:
        return
    recovery_pipeline['busy'] = True
    try:
        script, state, report = recovery_steps[recovery_pipeline['index']]
        path = recovery_root / 'Artifacts' / report
        if state != 'gym_test' and not globals().get(state, {}).get('finished'):
            return
        if not path.exists() or path.stat().st_mtime < recovery_pipeline['started']:
            return
        result = json.loads(path.read_text())
        assert result['passed'], result.get('error')
        recovery_pipeline['results'].append({'script': script, 'report': report,
                                             'cases': len(result.get('results', [])), 'passed': True})
        recovery_pipeline['index'] += 1
        if recovery_pipeline['index'] == len(recovery_steps):
            recovery_pipeline_finish()
        else:
            recovery_pipeline['started'] = time.time()
            exec((recovery_root / 'Scripts' / recovery_steps[recovery_pipeline['index']][0]).read_text(), globals())
    except Exception:
        recovery_pipeline_finish(traceback.format_exc())
    finally:
        recovery_pipeline['busy'] = False


exec((recovery_root / 'Scripts' / recovery_steps[0][0]).read_text(), globals())
recovery_pipeline['handle'] = u.register_slate_post_tick_callback(recovery_pipeline_tick)
print('Sequential get-up regressions queued')
