"""Occluded hearing, visual reacquisition, GAS death, drops and role respawn."""
import json,time,traceback
from pathlib import Path
import unreal as u
sd_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
sd_expected=sum(len(json.loads((sd_root/f'resources/{name}.json').read_text())['spawns']) for name in ['CrowdDistrict','FacilityCrowd'] if (sd_root/f'resources/{name}.json').exists())
sd_test=dict(phase='place',next=0,busy=False,results=[],deadline=time.monotonic()+180)
def sd_damage(source,target):
    asc=u.AbilitySystemLibrary.get_ability_system_component(source)
    effect=u.load_asset('/Game/GameplayEffects/Damage/GE_Damage_Basic_SetByCaller').generated_class()
    spec=asc.make_outgoing_spec(effect,1,asc.make_effect_context())
    tag=u.GameplayTag();tag.import_text('(TagName="SetByCaller.Damage")')
    spec=u.AbilitySystemLibrary.assign_tag_set_by_caller_magnitude(spec,tag,500)
    u.AbilitySystemLibrary.get_ability_system_component(target).apply_gameplay_effect_spec_to_self(spec)
def sd_finish(error=None):
    u.unregister_slate_post_tick_callback(sd_test['handle']);sd_test.update(finished=True,error=error)
    (sd_root/'Artifacts/Environment/crowd-senses-death.json').write_text(json.dumps(dict(passed=not error,error=error,results=sd_test['results']),indent=2))
def sd_tick(dt):
    if sd_test['busy']:return
    sd_test['busy']=True
    try:
        assert time.monotonic()<sd_test['deadline'],'Senses/death timed out'
        ws=u.EditorLevelLibrary.get_pie_worlds(False)
        if not ws:return
        w=ws[0];p=u.GameplayStatics.get_player_pawn(w,0)
        npcs=[a for a in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if a.crowd_agent.enabled]
        if not p or len(npcs)!=sd_expected or not all(a.crowd_agent.initialized for a in npcs):return
        now=u.GameplayStatics.get_time_seconds(w)
        if now<sd_test['next']:return
        phase=sd_test['phase']
        if phase=='place':
            guard=next(a for a in npcs if 'GuardRifle' in a.get_name());civ=next(a for a in npcs if not a.crowd_agent.guard)
            guard.get_controller().stop_movement();guard.character_movement.stop_movement_immediately();guard.crowd_agent.set_editor_property('current_area',None)
            guard.set_actor_location(u.Vector(15000,4000,94),False,True);guard.set_actor_rotation(u.Rotator(yaw=180),False);guard.get_controller().set_control_rotation(u.Rotator(yaw=180))
            p.set_actor_location(u.Vector(14000,4000,94),False,True);p.get_controller().set_ignore_move_input(True)
            u.SystemLibrary.execute_console_command(w,'God',p.get_controller())
            wall=u.CRBlueprintTools.spawn_pie_test_actor(w,u.StaticMeshActor,u.Transform(location=u.Vector(14500,4000,200)))
            wall.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE);wall.static_mesh_component.set_static_mesh(u.load_asset('/Engine/BasicShapes/Cube'));wall.set_actor_scale3d(u.Vector(1.5,5,4));wall.static_mesh_component.set_collision_profile_name('BlockAll')
            sd_test.update(guard=guard,civ=civ,wall=wall,phase='footstep',next=now+1,before_hearing=guard.crowd_agent.hearing_detections,before_shots=guard.weapon_effects.shots_played)
        elif phase=='footstep':
            u.AISense_Hearing.report_noise_event(w,p.get_actor_location(),1,p,1200,'Footstep');sd_test.update(phase='heard',next=now+.6)
        elif phase=='heard':
            g=sd_test['guard'];assert not g.get_controller().line_of_sight_to(p)
            assert g.crowd_agent.hearing_detections>sd_test['before_hearing'] and g.crowd_agent.state==u.CRCrowdState.INVESTIGATE
            assert g.weapon_effects.shots_played==sd_test['before_shots']
            sd_test['results'].append(dict(case='occluded_footstep_investigation',heard=True,no_blind_fire=True))
            u.AISense_Hearing.report_noise_event(w,p.get_actor_location(),1,p,1200,'Gunfire');sd_test.update(phase='gunfire',next=now+.6)
        elif phase=='gunfire':
            g=sd_test['guard'];assert not g.get_controller().line_of_sight_to(p)
            assert g.weapon_effects.shots_played==sd_test['before_shots']
            sd_test['results'].append(dict(case='occluded_gunfire_investigation',no_blind_fire=True))
            sd_test['wall'].destroy_actor();sd_test.update(phase='visible',next=now+4)
        elif phase=='visible':
            g=sd_test['guard'];assert g.weapon_effects.shots_played>sd_test['before_shots']
            assert g.crowd_agent.sight_detections>0 and g.crowd_agent.threat==p
            sd_test['results'].append(dict(case='sight_reacquisition_after_gunfire',shots=g.weapon_effects.shots_played-sd_test['before_shots']))
            sd_test['old_names']={a.get_name() for a in npcs};sd_test['before_pickups']=len(u.GameplayStatics.get_all_actors_of_class(w,u.BaselineWeaponPickup))
            for target in [g,sd_test['civ']]:sd_damage(p,target)
            sd_test.update(phase='death',next=now+.25)
        elif phase=='death':
            for target in [sd_test['guard'],sd_test['civ']]:
                assert target.get_component_by_class(u.LyraHealthComponent).is_dead_or_dying()
                assert 'DEAD' in str(target.physical_interaction.get_phase()) and target.mesh.is_simulating_physics('pelvis')
            assert len(u.GameplayStatics.get_all_actors_of_class(w,u.BaselineWeaponPickup))==sd_test['before_pickups']+1
            sd_test['results'].append(dict(case='guard_and_civilian_death',ragdolls=2,weapon_drops=1));sd_test.update(phase='respawn',next=now+5)
        else:
            replacements=[a for a in npcs if a.get_name() not in sd_test['old_names']]
            assert len(replacements)==2
            assert sorted(a.crowd_agent.guard for a in replacements)==[False,True]
            for a in replacements:
                assert a.get_component_by_class(u.LyraHealthComponent).get_health()==100 and a.can_use_movement_actions()
                assert bool(a.baseline_equipment.get_active_item())==a.crowd_agent.guard
            sd_test['results'].append(dict(case='role_preserving_respawn',replacements=2));sd_finish()
    except Exception:sd_finish(traceback.format_exc())
    finally:sd_test['busy']=False
sd_test['handle']=u.register_slate_post_tick_callback(sd_tick)
