"""Live navigation, randomized area visits, real weapon retaliation and civilian flight."""
import json,time,traceback,math
from pathlib import Path
import unreal as u

ai_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
ai_spawns=[row for name in ['CrowdDistrict','FacilityCrowd'] if (ai_root/f'resources/{name}.json').exists() for row in json.loads((ai_root/f'resources/{name}.json').read_text())['spawns']]
ai_test=dict(phase='ready',next=0,busy=False,results=[],deadline=time.monotonic()+240)
def ai_vec(v):return [v.x,v.y,v.z]
def ai_input(p,name,value):
    paths={'Fire':'/Game/Input/Actions/IA_Weapon_Fire','FireAuto':'/Game/Input/Actions/IA_Weapon_Fire_Auto','Aim':'/Game/Input/IA_Aim'}
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==p.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(paths[name]),u.Vector(value,0,0),[],[])
def ai_finish(error=None):
    u.unregister_slate_post_tick_callback(ai_test['handle']);ai_test.update(finished=True,error=error)
    (ai_root/'Artifacts/Environment/crowd-ai.json').write_text(json.dumps(dict(passed=not error,error=error,results=ai_test['results']),indent=2))
    print('CROWD_AI_TEST_COMPLETE',error)
def ai_tick(dt):
    if ai_test['busy']:return
    ai_test['busy']=True
    try:
        assert time.monotonic()<ai_test['deadline'],'Crowd AI timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        w=worlds[0];p=u.GameplayStatics.get_player_pawn(w,0)
        if not p:return
        npcs=[a for a in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if a.crowd_agent.enabled]
        if len(npcs)!=len(ai_spawns) or not all(a.crowd_agent.initialized for a in npcs):return
        now=u.GameplayStatics.get_time_seconds(w);phase=ai_test['phase']
        if ai_test.pop('release',False):
            ai_input(p,'Fire',0);ai_input(p,'FireAuto',0)
        if phase in ['aim','shoot','react','fight']:
            guard=next(a for a in npcs if a.get_name()==ai_test['guard'])
            camera=u.GameplayStatics.get_player_camera_manager(w,0).get_camera_location()
            p.get_controller().set_control_rotation(u.MathLibrary.find_look_at_rotation(camera,guard.get_actor_location()+u.Vector(0,0,15)))
            ai_input(p,'Aim',1)
        if now<ai_test['next']:return
        if phase=='ready':
            roles=[]
            for a in npcs:
                data=a.crowd_agent;item=a.baseline_equipment.get_active_item();skin=a.selected_visual_override.child_actor.get_class().get_name()
                assert isinstance(a.get_controller(),u.CRCrowdController)
                assert bool(item)==data.guard,(a.get_name(),item)
                assert ('UrbanTrailblazer' in skin)==(not data.guard),(a.get_name(),skin)
                roles.append(dict(name=a.get_name(),guard=data.guard,skin=skin,weapon=a.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).effects_profile.get_name() if item else None))
            assert sum(r['guard'] for r in roles)==sum(r['role'].startswith('Guard') for r in ai_spawns)
            ai_test['results'].append(dict(case='spawn_roles_and_loadouts',npcs=roles))
            p.get_controller().set_ignore_move_input(True);p.get_controller().set_ignore_look_input(True)
            u.SystemLibrary.execute_console_command(w,'God',p.get_controller())
            ai_test['start']={a.get_name():ai_vec(a.get_actor_location()) for a in npcs}
            # Raise visit probability only in this PIE fixture to exercise the branch deterministically.
            for area in u.GameplayStatics.get_all_actors_of_class(w,u.CRCrowdArea):area.set_editor_property('wander_chance',1.0)
            ai_test.update(phase='patrol',next=now+32)
        elif phase=='patrol':
            distances={a.get_name():math.dist(ai_test['start'][a.get_name()],ai_vec(a.get_actor_location())) for a in npcs}
            assert sum(d>150 for d in distances.values())>=10,distances
            visits={a.get_name():a.crowd_agent.area_visits for a in npcs}
            assert any(v>1 for v in visits.values()),visits
            for a in npcs:assert a.crowd_agent.state in [u.CRCrowdState.IDLE,u.CRCrowdState.PATROL],(a.get_name(),a.crowd_agent.state)
            ai_test['results'].append(dict(case='patrol_navigation_and_linked_area_visits',distance=distances,visits=visits))
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.BaselineWeaponPickup) if a.item_definition.get_name()=='ID_Pistol_C')
            p.set_actor_location(pickup.get_actor_location()+u.Vector(-100,0,40),False,True)
            p.baseline_equipment.server_pickup(pickup)
            ai_test.update(phase='position',next=now+1)
        elif phase=='position':
            guard=next(a for a in npcs if 'GuardRifle' in a.get_name())
            civ=next(a for a in npcs if not a.crowd_agent.guard)
            guard.crowd_agent.set_editor_property('current_area',None);guard.crowd_agent.set_editor_property('threat',None)
            for a,loc in [(p,(9900,-1000,94)),(guard,(10900,-1000,94)),(civ,(10600,-1450,94))]:
                a.character_movement.stop_movement_immediately();a.set_actor_location(u.Vector(*loc),False,True)
            guard.get_controller().stop_movement();guard.get_controller().set_control_rotation(u.Rotator(yaw=180));guard.set_actor_rotation(u.Rotator(yaw=180),False)
            ai_test.update(guard=guard.get_name(),civ=civ.get_name(),before_health=guard.get_component_by_class(u.LyraHealthComponent).get_health(),before_shots=guard.weapon_effects.shots_played,phase='aim',next=now+1.8)
        elif phase=='aim':ai_test.update(phase='shoot',next=now+.3)
        elif phase=='shoot':
            for name in ['Fire','FireAuto']:ai_input(p,name,1)
            ai_test.update(phase='react',next=now+.8,release=True)
        elif phase=='react':
            guard=next(a for a in npcs if a.get_name()==ai_test['guard']);civ=next(a for a in npcs if a.get_name()==ai_test['civ'])
            assert guard.get_component_by_class(u.LyraHealthComponent).get_health()<ai_test['before_health'],'Shot did not damage guard'
            assert guard.crowd_agent.damage_reactions>0 and guard.crowd_agent.threat==p
            assert civ.crowd_agent.state==u.CRCrowdState.FLEE,(civ.crowd_agent.state,civ.crowd_agent.hearing_detections)
            ai_test['results'].append(dict(case='damage_pursuit_and_civilian_fear',guard_health=guard.get_component_by_class(u.LyraHealthComponent).get_health(),damage_reactions=guard.crowd_agent.damage_reactions,civilian_state=str(civ.crowd_agent.state)))
            ai_test.update(phase='fight',next=now+12,guard_start=ai_vec(guard.get_actor_location()),civ_distance=math.dist(ai_vec(civ.get_actor_location()),ai_vec(p.get_actor_location())))
        elif phase=='fight':
            guard=next(a for a in npcs if a.get_name()==ai_test['guard']);civ=next(a for a in npcs if a.get_name()==ai_test['civ'])
            shots=guard.weapon_effects.shots_played-ai_test['before_shots'];travel=math.dist(ai_test['guard_start'],ai_vec(guard.get_actor_location()))
            flee=math.dist(ai_vec(civ.get_actor_location()),ai_vec(p.get_actor_location()))
            assert shots>0,('Guard never fired',guard.crowd_agent.shots_requested,guard.crowd_agent.state)
            assert guard.crowd_agent.tactical_moves>=2 and travel>150,(guard.crowd_agent.tactical_moves,travel)
            assert flee>ai_test['civ_distance']+400,(flee,ai_test['civ_distance'])
            ai_test['results'].append(dict(case='return_fire_tactical_movement_and_fleeing',shots=shots,tactical_moves=guard.crowd_agent.tactical_moves,guard_displacement=travel,civilian_distance=flee,hearing=guard.crowd_agent.hearing_detections,sight=guard.crowd_agent.sight_detections))
            ai_input(p,'Aim',0);ai_finish()
    except Exception:ai_finish(traceback.format_exc())
    finally:ai_test['busy']=False
ai_test['handle']=u.register_slate_post_tick_callback(ai_tick)
print('Started crowd roles/navigation/combat checks')
