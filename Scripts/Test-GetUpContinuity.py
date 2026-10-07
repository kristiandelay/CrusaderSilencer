"""Measure the actual body pose across ragdoll/get-up, through mapped recovery input."""
import json
import math
import time
import traceback
from pathlib import Path
import unreal as u

getup_out = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent / 'Artifacts/PhysicalTests'
getup_out.mkdir(parents=True, exist_ok=True)
getup_test = {'phase': 'position', 'index': 0, 'next': 0, 'results': [], 'samples': [],
              'busy': False, 'deadline': time.monotonic() + 180}
getup_bones = ['pelvis', 'head', 'hand_l', 'hand_r', 'foot_l', 'foot_r']
getup_cases = [('forward', (200, 0, 0), 0), ('backward', (-200, 0, 0), 0),
               ('left', (0, -220, 0), 0), ('turned_right', (-220, 0, 0), 90)]


def getup_input(pawn, value):
    subsystem = next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
                     if isinstance(s.get_outer(), u.LocalPlayer)
                     and u.GameplayStatics.get_player_controller(s, 0) == pawn.get_controller())
    subsystem.inject_input_vector_for_action(u.load_asset('/Game/Baseline/Input/IA_Ragdoll'),
                                            u.Vector(value, 0, 0), [], [])


def getup_pose(mesh):
    return {b: [getattr(mesh.get_socket_location(b), axis) for axis in ['x', 'y', 'z']]
            for b in getup_bones}


def getup_finish(error=None):
    u.unregister_slate_post_tick_callback(getup_test['handle'])
    getup_test['finished'] = True
    (getup_out / 'getup-continuity.json').write_text(json.dumps({
        'passed': error is None, 'error': error, 'results': getup_test['results'],
        'samples': getup_test['samples']}, indent=2))
    print('GETUP_CONTINUITY_COMPLETE', error)


def getup_tick(dt):
    if getup_test['busy']:
        return
    getup_test['busy'] = True
    try:
        assert time.monotonic() < getup_test['deadline'], 'Get-up continuity timeout'
        worlds = u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:
            return
        pawn = u.GameplayStatics.get_player_pawn(worlds[0], 0)
        if not pawn or not pawn.physical_interaction.controls_created:
            return
        now = u.GameplayStatics.get_time_seconds(worlds[0])
        if getup_test.pop('release', False):
            getup_input(pawn, 0)
        if now < getup_test['next']:
            return
        physical = pawn.physical_interaction
        anim = pawn.mesh.get_anim_instance()
        case, velocity, yaw = getup_cases[getup_test['index']]
        phase = getup_test['phase']
        if phase == 'position':
            assert not physical.is_busy(), 'Previous get-up did not finish'
            pawn.character_movement.stop_movement_immediately()
            pawn.set_actor_location(u.Vector(1500, -3200, 94), False, True)
            pawn.set_actor_rotation(u.Rotator(yaw=yaw), False)
            pawn.get_controller().set_control_rotation(u.Rotator(pitch=-15, yaw=yaw))
            getup_test.update(phase='fall', next=now + .7)
        elif phase == 'fall':
            assert pawn.has_authority(), 'Run this suite in standalone PIE'
            physical.start_ragdoll(u.Vector(*velocity))
            getup_test.update(phase='request', next=now + 4)
        elif phase == 'request':
            assert physical.get_phase() == u.BaselinePhysicalPhase.RAGDOLL
            getup_test['last_pose'] = getup_pose(pawn.mesh)
            getup_test['last_visible'] = getup_pose(pawn.baseline_equipment.get_presentation_mesh())
            getup_test['previous_time'] = now
            getup_test['ground_pelvis'] = getup_test['last_pose']['pelvis']
            getup_input(pawn, 1)
            getup_test.update(phase='observe', started=now, release=True, saw_recovery=False,
                             first_jump=None, first_visible_jump=None, max_early_pelvis_step=0,
                             max_pelvis_speed=0, minimum_head_z=1e6)
        elif phase == 'observe':
            elapsed = now - getup_test['started']
            pose = getup_pose(pawn.mesh)
            visible = getup_pose(pawn.baseline_equipment.get_presentation_mesh())
            frame_jump = max(math.dist(pose[b], getup_test['last_pose'][b]) for b in getup_bones)
            visible_frame_jump = max(math.dist(visible[b], getup_test['last_visible'][b]) for b in getup_bones)
            state = physical.get_phase()
            montage = anim.get_current_active_montage()
            if state == u.BaselinePhysicalPhase.RECOVERY:
                getup_test['saw_recovery'] = True
                if getup_test['first_jump'] is None:
                    getup_test['first_jump'] = max(math.dist(pose[b], getup_test['last_pose'][b]) for b in getup_bones)
                    getup_test['first_visible_jump'] = max(math.dist(visible[b], getup_test['last_visible'][b]) for b in getup_bones)
                    getup_test['montage'] = montage.get_name() if montage else None
                    getup_test['start_time'] = anim.montage_get_position(montage) if montage else None
                pelvis_step = math.dist(pose['pelvis'], getup_test['last_pose']['pelvis'])
                if elapsed < .5:
                    getup_test['max_early_pelvis_step'] = max(getup_test['max_early_pelvis_step'], pelvis_step)
                if now > getup_test['previous_time']:
                    getup_test['max_pelvis_speed'] = max(getup_test['max_pelvis_speed'], pelvis_step / (now - getup_test['previous_time']))
                getup_test['minimum_head_z'] = min(getup_test['minimum_head_z'], visible['head'][2])
            getup_test['samples'].append({'case': case, 't': elapsed, 'phase': str(state),
                                          'source': pose, 'visible': visible,
                                          'snapshot_weight': anim.get_editor_property('recovery_pose_weight'),
                                          'montage_time': anim.montage_get_position(montage) if montage else None})
            getup_test['last_pose'] = pose
            getup_test['last_visible'] = visible
            getup_test['previous_time'] = now
            if elapsed > .5 and not physical.is_busy():
                assert getup_test['saw_recovery'], 'Get-up never started: ' + physical.last_result
                result = {'case': case, 'montage': getup_test['montage'], 'start_time': getup_test['start_time'],
                          'first_source_jump_cm': getup_test['first_jump'],
                          'first_visible_jump_cm': getup_test['first_visible_jump'],
                          'max_early_pelvis_step_cm': getup_test['max_early_pelvis_step'],
                          'max_pelvis_speed_cm_s': getup_test['max_pelvis_speed'],
                          'minimum_visible_head_z_cm': getup_test['minimum_head_z'],
                          'return_to_locomotion_jump_cm': frame_jump,
                          'visible_return_to_locomotion_jump_cm': visible_frame_jump, 'duration': elapsed}
                getup_test['results'].append(result)
                assert result['first_source_jump_cm'] < 25, 'Source body popped at get-up: ' + str(result)
                assert result['first_visible_jump_cm'] < 30, 'Visible body popped at get-up: ' + str(result)
                assert result['max_early_pelvis_step_cm'] < 20, 'Pelvis snapped during the initial blend: ' + str(result)
                assert result['minimum_visible_head_z_cm'] > 0, 'Head passed through the floor: ' + str(result)
                assert frame_jump < 20 and visible_frame_jump < 25, 'Body popped on return to locomotion: ' + str(result)
                assert pose['pelvis'][2] > 65, 'Get-up did not return to a standing pose'
                getup_test['index'] += 1
                if getup_test['index'] == len(getup_cases):
                    getup_finish()
                else:
                    getup_test.update(phase='position', next=now + .5)
            else:
                assert elapsed < 8, 'Get-up did not finish: ' + physical.last_result
    except Exception:
        getup_finish(traceback.format_exc())
    finally:
        getup_test['busy'] = False


getup_test['handle'] = u.register_slate_post_tick_callback(getup_tick)
print('Started get-up continuity checks')
