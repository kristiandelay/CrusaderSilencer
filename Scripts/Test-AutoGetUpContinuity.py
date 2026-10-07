"""Check the post-physics automatic recovery path used by training partners."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal as u

auto_getup = {'busy': False, 'started': time.monotonic(), 'previous': None,
              'results': [], 'recovering': False}
auto_getup_bones = ['pelvis', 'head', 'hand_l', 'hand_r', 'foot_l', 'foot_r']


def auto_getup_pose(mesh):
    return {b: tuple(getattr(mesh.get_socket_location(b), axis) for axis in 'xyz')
            for b in auto_getup_bones}


def auto_getup_finish(error=None):
    u.unregister_slate_post_tick_callback(auto_getup['handle'])
    auto_getup['finished'] = True
    output = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent / 'Artifacts/PhysicalTests/auto-getup-continuity.json'
    output.write_text(json.dumps({'passed': error is None, 'error': error,
                                 'results': auto_getup['results']}, indent=2))
    print('AUTO_GETUP_CONTINUITY_COMPLETE', error)


def auto_getup_tick(dt):
    if auto_getup['busy']:
        return
    auto_getup['busy'] = True
    try:
        assert time.monotonic() - auto_getup['started'] < 25, 'Automatic get-up timed out'
        worlds = u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:
            return
        partners = [p for p in u.GameplayStatics.get_all_actors_of_class(worlds[0], u.Character)
                    if 'TrainingPartner' in p.get_class().get_name()]
        if not partners or not partners[0].physical_interaction.controls_created:
            return
        pawn = partners[0]
        physical = pawn.physical_interaction
        previous = auto_getup['previous']
        if previous is None:
            assert pawn.has_authority(), 'Run this check in standalone PIE'
            assert not physical.is_busy()
            pawn.character_movement.stop_movement_immediately()
            pawn.set_actor_location(u.Vector(1500, -3200, 94), False, True)
            physical.start_ragdoll(u.Vector(180, 0, 0))
        phase = physical.get_phase()
        pose = auto_getup_pose(pawn.mesh)
        visible = auto_getup_pose(pawn.baseline_equipment.get_presentation_mesh())
        if previous:
            source_jump = max(math.dist(pose[b], previous[1][b]) for b in auto_getup_bones)
            visible_jump = max(math.dist(visible[b], previous[2][b]) for b in auto_getup_bones)
            if previous[0] == u.BaselinePhysicalPhase.RAGDOLL and phase == u.BaselinePhysicalPhase.RECOVERY:
                auto_getup['results'].append({'case': 'automatic_training_partner_getup',
                    'first_source_jump_cm': source_jump, 'first_visible_jump_cm': visible_jump})
                assert source_jump < 25, 'Automatic recovery snapped source pose: ' + str(source_jump)
                assert visible_jump < 30, 'Automatic recovery snapped visible pose: ' + str(visible_jump)
                auto_getup['recovering'] = True
            if auto_getup['recovering'] and phase == u.BaselinePhysicalPhase.LOCOMOTION:
                auto_getup['results'][-1].update(return_to_locomotion_jump_cm=source_jump,
                    visible_return_to_locomotion_jump_cm=visible_jump)
                assert source_jump < 20 and visible_jump < 25, 'Automatic recovery snapped at completion'
                assert pose['pelvis'][2] > 65, 'Automatic recovery did not reach a standing pose'
                auto_getup_finish()
        auto_getup['previous'] = (phase, pose, visible)
    except Exception:
        auto_getup_finish(traceback.format_exc())
    finally:
        auto_getup['busy'] = False


auto_getup['handle'] = u.register_slate_post_tick_callback(auto_getup_tick)
print('Started automatic get-up continuity check')
