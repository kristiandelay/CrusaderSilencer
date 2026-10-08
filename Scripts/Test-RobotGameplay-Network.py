"""Two-player PIE: client provocation, server-only damage, replicated lasers/death."""
import json,time,traceback
from pathlib import Path
import unreal as u

rn_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
rn_test=dict(phase='ready',next=0,busy=False,results=[],deadline=time.monotonic()+150)

def rn_set(obj,name,value):assert u.CRBlueprintTools.set_property_text(obj,name,str(value))
def rn_health(p):return p.get_component_by_class(u.LyraHealthComponent).get_health()
def rn_input(p,name,value):
    path={'Aim':'/Game/Input/IA_Aim','Fire':'/Game/Input/Actions/IA_Weapon_Fire','FireAuto':'/Game/Input/Actions/IA_Weapon_Fire_Auto'}[name]
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==p.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(path),u.Vector(value,0,0),[],[])

def rn_finish(error=None):
    u.unregister_slate_post_tick_callback(rn_test['handle']);rn_test.update(finished=True,error=error)
    (rn_root/'Artifacts/RobotGameplay/network.json').write_text(json.dumps(dict(passed=not error,error=error,results=rn_test['results']),indent=2)+'\n')
    print('ROBOT_NETWORK_COMPLETE',error)

def rn_tick(dt):
    if rn_test['busy']:return
    rn_test['busy']=True
    try:
        assert time.monotonic()<rn_test['deadline'],'Network timed out: '+rn_test['phase']
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if len(worlds)!=2:return
        pawns=[p for w in worlds for p in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if isinstance(p.get_controller(),u.PlayerController)]
        try:
            host=next(p for p in pawns if p.has_authority() and p.is_locally_controlled())
            server_client=next(p for p in pawns if p.has_authority() and not p.is_locally_controlled())
            client=next(p for p in pawns if not p.has_authority() and p.is_locally_controlled())
        except StopIteration:return
        sw=host.get_world();cw=client.get_world();now=u.GameplayStatics.get_time_seconds(sw)
        robots=u.GameplayStatics.get_all_actors_of_class(sw,u.CRRobotCharacter)
        copies=u.GameplayStatics.get_all_actors_of_class(cw,u.CRRobotCharacter)
        if len(robots)!=6 or len(copies)!=6 or not all(r.crowd_agent.initialized for r in robots+copies):return
        phase=rn_test['phase'];r=rn_test.get('robot')
        if rn_test.pop('release',False):
            rn_input(client,'Fire',0);rn_input(client,'FireAuto',0)
        if r and rn_test.get('hold'):
            r.get_controller().stop_movement();r.character_movement.stop_movement_immediately()
        if phase in ['aim','hit']:
            eye=u.GameplayStatics.get_player_camera_manager(cw,0).get_camera_location()
            client.get_controller().set_control_rotation(u.MathLibrary.find_look_at_rotation(eye,r.get_actor_location()+u.Vector(0,0,20)))
            rn_input(client,'Aim',1)
        if phase=='fire' and now<rn_test['next']:
            if r.mounted_shots<3 or rn_test['copy'].mounted_shots!=r.mounted_shots:return
            if rn_test['copy'].weapon_effects.shots_played<3:return
            if rn_health(server_client)>=rn_test['player_health'] or rn_health(client)!=rn_health(server_client):return
            rn_test['next']=now
        if now<rn_test['next']:return
        if phase=='ready':
            # Crowd state can arrive before the player state's health attributes.
            if not all(rn_health(r)==r.armor_health for r in robots+copies):return
            assert {r.get_name():r.armor_health for r in robots}=={r.get_name():r.armor_health for r in copies}
            assert all(not r.crowd_agent.provoked and r.mounted_shots==0 and rn_health(r)==r.armor_health for r in robots+copies)
            rn_test.update(phase='patrol',next=now+15,plants={r.get_path_name():r.mesh.get_anim_instance().foot_plants for r in robots+copies})
        elif phase=='patrol':
            moving=[r for r in copies if r.mesh.get_anim_instance().foot_plants>rn_test['plants'][r.get_path_name()]+2]
            assert len(moving)>=4,[(r.get_name(),r.mesh.get_anim_instance().foot_plants) for r in copies]
            assert all(r.mounted_shots==0 and not r.crowd_agent.provoked for r in robots+copies)
            rn_test['results'].append(dict(case='six_replicated_peaceful_robots_and_remote_gait',moving_observers=len(moving)))
            r=robots[0];copy=next(a for a in copies if a.get_name()==r.get_name())
            rn_test.update(robot=r,copy=copy,hold=True)
            for actor in u.GameplayStatics.get_all_actors_of_class(sw,u.CRTraversalCharacter):
                if actor.crowd_agent.enabled and actor!=r:
                    actor.get_controller().stop_movement();actor.get_controller().set_actor_tick_enabled(False);actor.character_movement.stop_movement_immediately()
            for p in [host,client]:p.get_controller().set_ignore_move_input(True);p.get_controller().set_ignore_look_input(True)
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(sw,u.BaselineWeaponPickup) if a.item_definition.get_name()=='ID_Pistol_C')
            server_client.set_actor_location(pickup.get_actor_location()+u.Vector(-100,0,40),False,True);server_client.baseline_equipment.server_pickup(pickup)
            rn_test.update(phase='place',next=now+1.5)
        elif phase=='place':
            assert client.baseline_equipment.get_active_item()
            rn_set(r.crowd_agent,'CurrentArea','None')
            r.set_actor_location(u.Vector(12900,-1750,94),False,True);r.set_actor_rotation(u.Rotator(yaw=180),False)
            r.get_controller().set_control_rotation(u.Rotator(yaw=180))
            server_client.character_movement.stop_movement_immediately();server_client.set_actor_location(u.Vector(12150,-1750,94),False,True);server_client.force_net_update()
            host.set_actor_location(u.Vector(12150,-1150,94),False,True);host.force_net_update()
            rn_test.update(phase='ambient',next=now+1.5)
        elif phase=='ambient':
            u.AISense_Hearing.report_noise_event(sw,server_client.get_actor_location(),1,server_client,3000,'Gunfire')
            rn_test.update(phase='aim',next=now+2)
        elif phase=='aim':
            assert not r.crowd_agent.provoked and not rn_test['copy'].crowd_agent.provoked and r.mounted_shots==0
            rn_input(client,'Fire',1);rn_input(client,'FireAuto',1)
            rn_test.update(phase='hit',next=now+.8,release=True)
        elif phase=='hit':
            assert rn_health(r)<r.armor_health and rn_health(r)==rn_health(rn_test['copy'])
            assert r.crowd_agent.provoked and rn_test['copy'].crowd_agent.provoked
            assert r.crowd_agent.threat==server_client and rn_test['copy'].crowd_agent.threat==client
            assert all(not a.crowd_agent.provoked for a in robots if a!=r)
            rn_test['results'].append(dict(case='client_shot_provokes_only_attacked_robot',health=rn_health(r),replicated_attacker=True))
            rn_input(client,'Aim',0);rn_test.update(phase='fire',next=now+18,hold=False,player_health=rn_health(server_client))
        elif phase=='fire':
            copy=rn_test['copy']
            assert r.mounted_shots>=3 and copy.mounted_shots==r.mounted_shots
            # Cosmetics use the existing unreliable multicast: lost effects may
            # be skipped, while authoritative damage/state must replicate.
            assert 3<=copy.weapon_effects.shots_played<=r.weapon_effects.shots_played==r.mounted_shots
            assert copy.weapon_effects.trails_played>0 and copy.weapon_effects.last_profile==r.laser_effects
            assert rn_health(server_client)<rn_test['player_health'] and rn_health(client)==rn_health(server_client)
            rn_test['results'].append(dict(case='authoritative_damage_replicated_laser_and_sound',shots=r.mounted_shots,observer_shots=copy.weapon_effects.shots_played,client_health=rn_health(client),sound=r.laser_effects.fire_sound.get_path_name()))
            asc=u.AbilitySystemLibrary.get_ability_system_component(server_client)
            effect=u.load_asset('/Game/GameplayEffects/Damage/GE_Damage_Basic_SetByCaller').generated_class()
            spec=asc.make_outgoing_spec(effect,1,asc.make_effect_context());tag=u.GameplayTag();tag.import_text('(TagName="SetByCaller.Damage")')
            spec=u.AbilitySystemLibrary.assign_tag_set_by_caller_magnitude(spec,tag,1000)
            rn_test.update(old_name=r.get_name(),old_class=r.get_class())
            u.AbilitySystemLibrary.get_ability_system_component(r).apply_gameplay_effect_spec_to_self(spec)
            rn_test.update(phase='shutdown',next=now+1)
        elif phase=='shutdown':
            assert r.shutdown and rn_test['copy'].shutdown
            assert rn_test['copy'].mesh.get_anim_instance().shutdown_blend>.3
            rn_test['results'].append(dict(case='replicated_mechanical_shutdown',observer_blend=rn_test['copy'].mesh.get_anim_instance().shutdown_blend))
            rn_test.update(phase='respawn',next=now+10)
        elif phase=='respawn':
            replacements=[a for a in robots+copies if a.get_class()==rn_test['old_class'] and a.get_name()!=rn_test['old_name']]
            assert len(replacements)==2 and replacements[0].get_name()==replacements[1].get_name()
            assert all(not a.shutdown and not a.crowd_agent.provoked and rn_health(a)==a.armor_health for a in replacements)
            rn_test['results'].append(dict(case='replicated_neutral_respawn',health=rn_health(replacements[0])))
            rn_finish()
    except Exception:rn_finish(traceback.format_exc())
    finally:rn_test['busy']=False

rn_test['handle']=u.register_slate_post_tick_callback(rn_tick)
print('ROBOT_NETWORK_STARTED')
