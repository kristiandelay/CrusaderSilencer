"""Exercise the real merged pawn through its mapped Enhanced Input actions in PIE."""
import math
test_out = Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/GymTests'
test_out.mkdir(parents=True, exist_ok=True)
test_world = u.EditorLevelLibrary.get_pie_worlds(False)[0]
test_pawn = u.GameplayStatics.get_player_pawn(test_world, 0)
assert isinstance(test_pawn, u.LyraCharacter)
assert isinstance(test_pawn.character_movement, u.BaselineCharacterMovement)
test_subsystems = [s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
                   if isinstance(s.get_outer(), u.LocalPlayer) and u.GameplayStatics.get_player_controller(s, 0) == test_pawn.get_controller()]
assert len(test_subsystems) == 1
test_input = test_subsystems[0]
test_actions = {name: u.load_asset('/Game/Input/IA_' + name) for name in ['Move', 'Walk', 'Sprint', 'Crouch', 'Jump']}
assert all(test_input.query_keys_mapped_to_action(action) for action in test_actions.values())
test_traversal = next(c for c in test_pawn.get_components_by_class(u.ActorComponent) if c.get_name() == 'AC_TraversalLogic')
test_cases = [
    {'name': 'jog', 'kind': 'locomotion'},
    {'name': 'walk', 'kind': 'locomotion', 'action': 'Walk'},
    {'name': 'sprint', 'kind': 'locomotion', 'action': 'Sprint'},
    {'name': 'crouch', 'kind': 'crouch', 'action': 'Crouch'},
    {'name': 'jump', 'kind': 'jump', 'action': 'Jump'},
    {'name': 'hurdle', 'kind': 'traversal', 'start': [2730,-800,94], 'yaw': 0, 'axis': 0, 'edge': 2800},
    # The narrow side of block 11 is 50 cm, below GASP's authored 60 cm ledge minimum.
    {'name': 'mantle', 'kind': 'traversal', 'start': [4300,-970,94], 'yaw': 90, 'axis': 1, 'edge': -900},
    {'name': 'climb', 'kind': 'traversal', 'start': [2700,-1770,94], 'yaw': 90, 'axis': 1, 'edge': -1700},
    {'name': 'vault', 'kind': 'traversal', 'start': [4810,-800,444], 'yaw': 0, 'axis': 0, 'edge': 4880},
]
gym_test = {'index': 0, 'phase': 'place', 'next': 0, 'results': [], 'busy': False}

def gym_vec(v):
    return [v.x, v.y, v.z]

def gym_input(name, value):
    test_input.inject_input_vector_for_action(test_actions[name], u.Vector(*value), [], [])

def gym_finish(error=None):
    u.unregister_slate_post_tick_callback(gym_test['handle'])
    for action in test_actions:
        gym_input(action, (0, 0, 0))
    result = {'passed': error is None and len(gym_test['results']) == len(test_cases), 'error': error,
              'pawn': test_pawn.get_class().get_path_name(), 'results': gym_test['results'],
              'input_keys': {name: [key.export_text() for key in test_input.query_keys_mapped_to_action(action)] for name, action in test_actions.items()}}
    (test_out / 'result.json').write_text(json.dumps(result, indent=2))
    u.log('CR_GYM_TEST_RESULT ' + json.dumps(result))
    # Do not keep PIE actors alive after the user presses Escape.
    for name in ['test_world', 'test_pawn', 'test_input', 'test_subsystems', 'test_traversal']:
        globals().pop(name, None)
    gym_test.pop('capture_task', None)

def gym_tick(dt):
    if gym_test['busy'] or u.GameplayStatics.get_time_seconds(test_world) < gym_test['next']:
        return
    gym_test['busy'] = True
    try:
        now = u.GameplayStatics.get_time_seconds(test_world)
        case = test_cases[gym_test['index']]
        phase = gym_test['phase']
        if phase == 'place':
            for action in test_actions:
                gym_input(action, (0, 0, 0))
            test_pawn.un_crouch()
            test_pawn.character_movement.stop_movement_immediately()
            test_pawn.set_actor_location(u.Vector(*case.get('start', [-1400,-3200,94])), False, True)
            rotation = u.Rotator(pitch=0, yaw=case.get('yaw', 0), roll=0)
            test_pawn.set_actor_rotation(rotation, True)
            test_pawn.get_controller().set_control_rotation(u.Rotator(pitch=-10, yaw=case.get('yaw', 0), roll=0))
            gym_test.update(phase='settle', next=now+0.7)
        elif phase == 'settle':
            assert test_pawn.character_movement.movement_mode == u.MovementMode.MOVE_WALKING, case['name']+' has no starting floor'
            gym_test.update(phase='act', started=now, start=gym_vec(test_pawn.get_actor_location()), speeds=[], heights=[], capsule_heights=[], montage=None, captured=False, contact_captured=False, weapon_stowed=False, recovery_started=None,input_sent=False)
        elif phase == 'act':
            elapsed = now-gym_test['started']
            kind = case['kind']
            if kind in ['locomotion', 'crouch']:
                gym_input('Move', (0, 1, 0))
            if case.get('action'):
                # A short wall-clock pulse can disappear entirely between slow editor frames.
                hold = elapsed < 1.4 if case['action'] in ['Walk', 'Sprint'] else not gym_test['input_sent']
                gym_input(case['action'], (1 if hold else 0, 0, 0))
            if kind == 'traversal':
                # CMC uses IA_Jump for contextual traversal. IA_Traverse is Mover-only.
                gym_input('Jump', (0 if gym_test['input_sent'] else 1, 0, 0))
            gym_test['input_sent'] = True
            location = test_pawn.get_actor_location()
            velocity = test_pawn.get_velocity()
            gym_test['speeds'].append(math.hypot(velocity.x, velocity.y))
            gym_test['heights'].append(location.z)
            gym_test['capsule_heights'].append(test_pawn.capsule_component.get_scaled_capsule_half_height())
            montage = test_pawn.mesh.get_anim_instance().get_current_active_montage()
            if montage:
                gym_test['montage'] = montage.get_path_name()
                equipped = test_pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
                if equipped and kind == 'traversal':
                    actors = equipped.get_spawned_actors()
                    if actors and actors[0].get_editor_property('bHidden'):
                        gym_test['weapon_stowed'] = True
                if kind == 'traversal' and not gym_test['captured'] and elapsed > .3:
                    gym_test['capture_task'] = u.AutomationLibrary.take_high_res_screenshot(1440,900,str(test_out/(case['name']+'.png')),delay=0.0)
                    gym_test['captured'] = True
                if case['name'] == 'climb' and not gym_test['contact_captured'] and elapsed > 1.2:
                    gym_test['capture_task'] = u.AutomationLibrary.take_high_res_screenshot(1440,900,str(test_out/'climb-contact.png'),delay=0.0)
                    gym_test['contact_captured'] = True
            if kind == 'traversal':
                assert elapsed < 12, case['name']+' timed out; montage='+str(gym_test['montage'])+' position='+str(gym_vec(location))
                finished = elapsed > 1 and gym_test['montage'] and not montage and not test_traversal.get_editor_property('DoingTraversalAction') and test_pawn.character_movement.movement_mode == u.MovementMode.MOVE_WALKING
                if finished:
                    equipped=test_pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
                    if equipped:
                        if gym_test['recovery_started'] is None:gym_test['recovery_started']=now
                        actors=equipped.get_spawned_actors()
                        assert actors,'Equipped actor was lost during traversal'
                        # Montage evaluation can finish after the equipment tick in
                        # this frame. Require restoration within a bounded interval.
                        if actors[0].get_editor_property('bHidden'):
                            assert now-gym_test['recovery_started']<.5,'Weapon stayed hidden after traversal'
                            return
            else:
                finished = elapsed > (2.5 if kind == 'jump' else 1.4)
            if finished:
                end = gym_vec(location)
                result = {'name': case['name'], 'start': gym_test['start'], 'end': end, 'max_speed': max(gym_test['speeds']), 'max_z': max(gym_test['heights']), 'min_capsule_half_height': min(gym_test['capsule_heights']), 'montage': gym_test['montage']}
                if kind == 'traversal':
                    assert end[case['axis']] > case['edge']+20, case['name']+' did not cross its ledge: '+str(result)
                    if test_pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance):
                        assert gym_test['weapon_stowed'], 'Equipped weapon was not hidden during traversal'
                        actors=test_pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_spawned_actors()
                        assert actors and not actors[0].get_editor_property('bHidden'), 'Weapon did not return after traversal'
                        result['weapon_hidden_during_action'] = True
                        result['weapon_restored_after_action'] = True
                elif kind == 'locomotion':
                    assert math.dist(end[:2], gym_test['start'][:2]) > 100, 'No movement: '+str(result)
                elif kind == 'crouch':
                    assert result['min_capsule_half_height'] < 70, 'Crouch capsule unchanged: '+str(result)
                elif kind == 'jump':
                    assert result['max_z'] > gym_test['start'][2]+75, 'No jump: '+str(result)
                    assert test_pawn.character_movement.movement_mode == u.MovementMode.MOVE_WALKING
                gym_test['results'].append(result)
                u.log('CR_GYM_CASE '+json.dumps(result))
                gym_test['index'] += 1
                if gym_test['index'] == len(test_cases):
                    speeds={r['name']:r['max_speed'] for r in gym_test['results']}
                    assert speeds['walk'] < speeds['jog'] < speeds['sprint'], str(speeds)
                    gym_finish()
                else:
                    gym_test.update(phase='place', next=now+0.2)
    except Exception:
        gym_finish(traceback.format_exc())
    finally:
        gym_test['busy'] = False

gym_test['handle'] = u.register_slate_post_tick_callback(gym_tick)
print('Started', len(test_cases), 'mapped-input cases')
