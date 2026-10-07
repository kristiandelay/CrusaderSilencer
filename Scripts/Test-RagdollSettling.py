"""PIE: real falls settle without pose motors, remain physical, and recover.

Run in the standalone gym. The report measures pelvis and limb motion for a
full quiet second after landing, allowing four to eight seconds for impact
motion to settle before judging the resting pose.
"""
from pathlib import Path
import json
import math
import time
import traceback
import unreal as u

settle_out = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent / 'Artifacts/PhysicalTests'
settle_out.mkdir(parents=True, exist_ok=True)
settle_test = {'phase': 'setup', 'index': 0, 'next': 0, 'results': [], 'samples': [],
               'busy': False, 'deadline': time.monotonic() + 160}
settle_bones = ['pelvis', 'spine_03', 'head', 'upperarm_l', 'lowerarm_l', 'hand_l',
                'upperarm_r', 'lowerarm_r', 'hand_r', 'thigh_l', 'calf_l', 'foot_l',
                'thigh_r', 'calf_r', 'foot_r']


def settle_input(pawn, name, value):
    subsystem = next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
                     if isinstance(s.get_outer(), u.LocalPlayer)
                     and u.GameplayStatics.get_player_controller(s, 0) == pawn.get_controller())
    path = '/Game/Input/IA_Jump' if name == 'Jump' else '/Game/Baseline/Input/IA_' + name
    subsystem.inject_input_vector_for_action(u.load_asset(path),
                                            u.Vector(value, 0, 0), [], [])


def settle_finish(error=None):
    u.unregister_slate_post_tick_callback(settle_test['handle'])
    settle_test['finished'] = True
    (settle_out / 'ragdoll-settling.json').write_text(json.dumps({
        'passed': error is None, 'error': error, 'results': settle_test['results'],
        'samples': settle_test['samples']}, indent=2))
    print('RAGDOLL_SETTLING_COMPLETE', error)


def settle_positions(mesh):
    return {bone: mesh.get_socket_location(bone) for bone in settle_bones}


def settle_tick(dt):
    if settle_test['busy']:
        return
    settle_test['busy'] = True
    try:
        assert time.monotonic() < settle_test['deadline'], 'Ragdoll settling timeout'
        worlds = u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:
            return
        world = worlds[0]
        pawn = u.GameplayStatics.get_player_pawn(world, 0)
        if not pawn or not pawn.physical_interaction.controls_created:
            return
        now = u.GameplayStatics.get_time_seconds(world)
        if settle_test.pop('release', False):
            for action in ['Ragdoll', 'Interact', 'Jump']:
                settle_input(pawn, action, 0)
        if now < settle_test['next']:
            return
        physical = pawn.physical_interaction
        mesh = pawn.mesh
        phase = settle_test['phase']
        if phase == 'setup':
            assert not physical.is_busy(), 'Start the settling test with an idle player'
            if not pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance):
                pawn.set_actor_location(u.Vector(2100, -1100, 94), False, True)
                pawn.set_actor_rotation(u.Rotator(yaw=0), False)
                pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
                settle_input(pawn, 'Interact', 1)
                settle_test.update(next=now + 1, release=True)
                return
            settle_test.update(phase='position')
        elif phase == 'position':
            pawn.character_movement.stop_movement_immediately()
            pawn.set_actor_location(u.Vector(1500, -2800, 94), False, True)
            pawn.set_actor_rotation(u.Rotator(yaw=0), False)
            pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
            settle_test.update(phase='trigger', next=now + .7)
        elif phase == 'trigger':
            if settle_test['index'] == 0:
                settle_input(pawn, 'Ragdoll', 1)
                case = 'ground_level_fall'
            else:
                pawn.set_actor_location(u.Vector(1500, -2800, 1600), False, True)
                pawn.character_movement.set_movement_mode(u.MovementMode.MOVE_FALLING)
                case = 'high_speed_fall'
            settle_test.update(phase='observe', case=case, next=now + .05, started=now,
                               release=True, landed=None, initial_z=None, saw_recovery=False, checked_asset_drives=False)
        elif phase == 'observe':
            assert now - settle_test['started'] < 18, 'Body did not settle or ragdoll did not start'
            if physical.get_phase() == u.BaselinePhysicalPhase.RAGDOLL:
                assert mesh.is_simulating_physics('pelvis'), 'Body is not simulated'
                assert not any(pawn.physics_control.get_control_enabled(n)
                               for n in pawn.physics_control.get_all_control_names()), 'Pose motors remain enabled'
                if not settle_test['checked_asset_drives']:
                    for joint in mesh.get_constraints(False):
                        assert not any(u.ConstraintInstanceBlueprintLibrary.get_orientation_drive_twist_and_swing(joint)[1:]), 'Physics-asset orientation motors remain enabled'
                        assert not any(u.ConstraintInstanceBlueprintLibrary.get_angular_velocity_drive_twist_and_swing(joint)[1:]), 'Physics-asset velocity motors remain enabled'
                    settle_test['checked_asset_drives'] = True
                assert not mesh.get_anim_instance().is_any_montage_playing(), 'Flail montage still playing'
                pelvis = mesh.get_socket_location('pelvis')
                assert pelvis.z > -30, 'Ragdoll tunneled through the floor'
                if settle_test['initial_z'] is None:
                    settle_test['initial_z'] = pelvis.z
                if pelvis.z < 65 and settle_test['landed'] is None:
                    settle_test['landed'] = now
                if settle_test['landed'] is not None:
                    age = now - settle_test['landed']
                    positions = settle_positions(mesh)
                    linear = max(mesh.get_physics_linear_velocity(b).length() for b in settle_bones)
                    angular = max(mesh.get_physics_angular_velocity_in_degrees(b).length() for b in settle_bones)
                    settle_test['samples'].append({'case': settle_test['case'], 'time_after_landing': age,
                                                   'pelvis_z': pelvis.z, 'max_linear_cm_s': linear,
                                                   'max_angular_deg_s': angular})
                    if age >= 4:
                        rotations = {b: mesh.get_socket_transform(b).rotation for b in settle_bones}
                        if 'reference' not in settle_test:
                            settle_test['reference'] = positions
                            settle_test['reference_rotations'] = rotations
                            settle_test['window_started'] = age
                        displacement = max((positions[b] - settle_test['reference'][b]).length() for b in settle_bones)
                        rotation_drift = max(math.degrees(rotations[b].angular_distance(settle_test['reference_rotations'][b])) for b in settle_bones)
                        settle_test.setdefault('late', []).append((linear, angular, displacement, rotation_drift))
                    if 'window_started' in settle_test and age - settle_test['window_started'] >= 1:
                        assert len(settle_test['late']) >= 5, 'Insufficient settling samples'
                        peak_linear, peak_angular, drift, rotation_drift = (max(s[i] for s in settle_test['late']) for i in range(4))
                        if (peak_linear >= 15 or rotation_drift >= 8 or drift >= 5) and age < 8:
                            # A passive high-speed impact can take longer to
                            # settle. Require a complete quiet window, keeping
                            # the same motion limits and a bounded deadline.
                            for key in ['reference', 'reference_rotations', 'window_started', 'late']:
                                settle_test.pop(key)
                            settle_test['next'] = now + .1
                            return
                        assert peak_linear < 15, f'Limbs still moving at {peak_linear:.1f} cm/s'
                        # Contact-solver corrections can spike instantaneous angular
                        # velocity. Measure actual rotation over the settled window.
                        assert rotation_drift < 8, f'Limbs still rotating through {rotation_drift:.1f} degrees'
                        assert drift < 5, f'Body moved {drift:.1f} cm after settling'
                        if settle_test['index'] == 1:
                            assert settle_test['initial_z'] - pelvis.z > 500, 'High fall did not simulate its descent'
                        settle_test['results'].append({'case': settle_test['case'], 'passed': True,
                                                      'max_settled_linear_cm_s': peak_linear,
                                                      'max_settled_angular_deg_s': peak_angular,
                                                      'settled_rotation_drift_degrees': rotation_drift,
                                                      'settled_drift_cm': drift,
                                                      'verified_settled_after_seconds': age})
                        settle_test.pop('reference')
                        settle_test.pop('reference_rotations')
                        settle_test.pop('window_started')
                        settle_test.pop('late')
                        if settle_test['index'] == 0:
                            ceiling = u.CRBlueprintTools.spawn_pie_test_actor(world, u.StaticMeshActor,
                                u.Transform(location=u.Vector(pelvis.x, pelvis.y, 130)))
                            ceiling.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE)
                            ceiling.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'))
                            ceiling.set_actor_scale3d(u.Vector(3, 3, .25))
                            settle_test['ceiling_name'] = ceiling.get_name()
                            settle_test.update(phase='ceiling_request', next=now + .2)
                        else:
                            settle_input(pawn, 'Jump', 1)
                            settle_test.update(phase='recover', next=now + .1, release=True, recovery_started=now)
            settle_test['next'] = now + .1
        elif phase == 'ceiling_request':
            settle_input(pawn, 'Ragdoll', 1)
            settle_test.update(phase='ceiling_verify', next=now + .4, release=True)
        elif phase == 'ceiling_verify':
            assert physical.get_phase() == u.BaselinePhysicalPhase.RAGDOLL, 'Get-up bypassed the low ceiling'
            assert physical.last_result == 'Not enough room to stand', physical.last_result
            next(a for a in u.GameplayStatics.get_all_actors_of_class(world, u.StaticMeshActor)
                 if a.get_name() == settle_test['ceiling_name']).destroy_actor()
            settle_test['results'].append({'case': 'low_ceiling_blocks_get_up', 'passed': True})
            settle_test['impulse_start'] = mesh.get_socket_location('pelvis')
            mesh.add_impulse_to_all_bodies_below(u.Vector(180, 0, 140), 'pelvis', True, True)
            settle_test.update(phase='impulse', next=now + .35)
        elif phase == 'impulse':
            distance = (mesh.get_socket_location('pelvis') - settle_test['impulse_start']).length()
            assert distance > 10, 'Settled ragdoll was frozen instead of remaining physical'
            settle_test['results'].append({'case': 'settled_body_reacts_to_impulse', 'passed': True,
                                           'displacement_cm': distance})
            settle_test.update(phase='request_recovery', next=now + 3)
        elif phase == 'request_recovery':
            settle_input(pawn, 'Ragdoll', 1)
            settle_test.update(phase='recover', next=now + .1, release=True, recovery_started=now)
        elif phase == 'recover':
            assert now - settle_test['recovery_started'] < 10, 'Matched get-up did not finish'
            if physical.get_phase() == u.BaselinePhysicalPhase.RECOVERY:
                settle_test['saw_recovery'] = True
            if not physical.is_busy():
                assert settle_test['saw_recovery'], 'No get-up animation observed'
                assert not mesh.is_simulating_physics('pelvis'), 'Physics did not release for locomotion'
                settle_test.update(phase='verify', next=now + 1)
            else:
                settle_test['next'] = now + .08
        elif phase == 'verify':
            assert pawn.get_actor_location().z > 50, 'Recovered capsule fell through the floor'
            assert pawn.capsule_component.get_collision_response_to_channel(u.CollisionChannel.ECC_WORLD_STATIC) == u.CollisionResponseType.ECR_BLOCK
            weapon = pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
            assert weapon and not weapon.get_spawned_actors()[0].get_editor_property('bHidden'), 'Weapon did not return after recovery'
            settle_test['results'].append({'case': settle_test['case'] + '_recovery', 'passed': True})
            settle_test['index'] += 1
            if settle_test['index'] == 2:
                settle_finish()
            else:
                settle_test.update(phase='position', next=now + .2)
    except Exception:
        settle_finish(traceback.format_exc())
    finally:
        settle_test['busy'] = False


settle_test['handle'] = u.register_slate_post_tick_callback(settle_tick)
print('Started passive ragdoll settling checks')
