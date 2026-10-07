"""Real weapon kills plus Lyra damage/death/respawn and dropped inventory checks."""
import json
import time
import traceback
from pathlib import Path
import unreal as u

death_out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/CombatTests'
death_out.mkdir(parents=True,exist_ok=True)
death_test={'phase':'pickup','next':0,'results':[],'busy':False,'deadline':time.monotonic()+150,'cycle':0,'pickup_index':0}


def death_input(pawn,name,value):
    paths={'Fire':'/Game/Input/Actions/IA_Weapon_Fire_Auto','Aim':'/Game/Input/IA_Aim'}
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
             if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pawn.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(paths.get(name,'/Game/Baseline/Input/IA_'+name)),u.Vector(value,0,0),[],[])


def death_damage(source,target,amount):
    source_asc=u.AbilitySystemLibrary.get_ability_system_component(source)
    target_asc=u.AbilitySystemLibrary.get_ability_system_component(target)
    effect=u.load_asset('/Game/GameplayEffects/Damage/GE_Damage_Basic_SetByCaller').generated_class()
    spec=source_asc.make_outgoing_spec(effect,1,source_asc.make_effect_context())
    tag=u.GameplayTag();tag.import_text('(TagName="SetByCaller.Damage")')
    spec=u.AbilitySystemLibrary.assign_tag_set_by_caller_magnitude(spec,tag,amount)
    target_asc.apply_gameplay_effect_spec_to_self(spec)


def death_finish(error=None):
    u.unregister_slate_post_tick_callback(death_test['handle'])
    death_test['finished']=True
    (death_out/'combat-death.json').write_text(json.dumps({'passed':error is None,'error':error,'results':death_test['results']},indent=2))
    print('COMBAT_DEATH_COMPLETE',error)


def death_tick(dt):
    if death_test['busy']:return
    death_test['busy']=True
    try:
        assert time.monotonic()<death_test['deadline'],'Death checks timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        world=worlds[0]
        now=u.GameplayStatics.get_time_seconds(world)
        pawn=u.GameplayStatics.get_player_pawn(world,0)
        if death_test['phase']=='player_respawn' and now>=death_test['next']:
            assert pawn, 'Automatic respawn did not replace the dead pawn'
        if not pawn or not pawn.physical_interaction.controls_created:return
        if death_test.pop('release',False):
            for name in ['Interact','Aim','Fire','Cycle']:death_input(pawn,name,0)
        if now<death_test['next']:return
        partners=[a for a in u.GameplayStatics.get_all_actors_of_class(world,u.CRTraversalCharacter) if 'TrainingPartner' in a.get_class().get_name()]
        health=pawn.get_component_by_class(u.LyraHealthComponent)
        phase=death_test['phase']
        if phase=='pickup':
            assert pawn.has_authority(), 'Run in standalone PIE'
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup) if ['Rifle','Pistol','Shotgun'][death_test['pickup_index']] in a.item_definition.get_name())
            loc=pickup.get_actor_location()
            pawn.set_actor_location(u.Vector(loc.x-110,loc.y,94),False,True)
            pawn.set_actor_rotation(u.Rotator(yaw=0),False)
            pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
            death_input(pawn,'Interact',1)
            death_test.update(phase='acquired',next=now+1.2,release=True)
        elif phase=='acquired':
            death_test['pickup_index']+=1
            assert len([i for i in pawn.get_controller().quick_bar.get_slots() if i])==death_test['pickup_index']
            if death_test['pickup_index']<3: death_test.update(phase='pickup',next=now+.1)
            else:
                death_input(pawn,'Cycle',1)
                death_test.update(phase='position',next=now+.8,release=True)
        elif phase=='position':
            assert pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance),'Pickup failed'
            target=partners[0]
            pawn.set_actor_location(u.Vector(1500,-3200,94),False,True)
            target.set_actor_location(u.Vector(2200,-3200,94),False,True)
            death_test.update(phase='shoot',next=now+.7,target=target.get_name(),started=now+.7,minimum_health=100)
        elif phase=='shoot':
            target=next((a for a in partners if a.get_name()==death_test['target']),None)
            assert target,'Target disappeared before death was observed'
            th=target.get_component_by_class(u.LyraHealthComponent)
            death_test['minimum_health']=min(death_test['minimum_health'],th.get_health())
            if th.is_dead_or_dying():
                for name in ['Fire','Aim']:death_input(pawn,name,0)
                assert str(target.physical_interaction.get_phase()).find('DEAD')>=0,'Killed target is not in fatal ragdoll'
                assert target.mesh.is_simulating_physics('pelvis')
                assert not any(target.physics_control.get_control_enabled(n) for n in target.physics_control.get_all_control_names())
                target.physical_interaction.request_recovery()
                assert str(target.physical_interaction.get_phase()).find('DEAD')>=0,'Dead target got up'
                death_test['results'].append({'case':'real_rifle_damage_and_fatal_ragdoll','health':th.get_health(),'time_to_kill':now-death_test['started']})
                death_test.update(phase='target_respawn',next=now+3.8)
            else:
                assert now-death_test['started']<8,'Rifle never killed target; minimum health '+str(death_test['minimum_health'])
                camera=pawn.get_controller().player_camera_manager.get_camera_location()
                pawn.get_controller().set_control_rotation(u.MathLibrary.find_look_at_rotation(camera,target.mesh.get_socket_location('spine_03')))
                for name in ['Aim','Fire']:death_input(pawn,name,1)
        elif phase=='target_respawn':
            assert len(partners)==2,'Training target was not replaced cleanly'
            assert not any(a.get_name()==death_test['target'] for a in partners)
            assert all(a.get_component_by_class(u.LyraHealthComponent).get_health()==100 for a in partners)
            death_test['results'].append({'case':'training_target_respawns_with_full_health','passed':True})
            death_test.update(phase='damage_player',next=now+.2)
        elif phase=='damage_player':
            if death_test['cycle']==2:
                pawn.physical_interaction.start_ragdoll(u.Vector(80,0,0))
                death_test.update(phase='recover_for_death',next=now+4)
            elif death_test['cycle']==3:
                partner=partners[0]
                pawn.set_actor_location(u.Vector(1500,-3200,94),False,True)
                pawn.set_actor_rotation(u.Rotator(yaw=0),False)
                pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
                partner.set_actor_location(u.Vector(1650,-3200,94),False,True)
                partner.set_actor_rotation(u.Rotator(yaw=180),False)
                death_test.update(phase='pair_for_death',next=now+.7)
            else: death_test.update(phase='damage_now')
        elif phase=='recover_for_death':
            pawn.physical_interaction.request_recovery()
            assert pawn.physical_interaction.get_phase()==u.BaselinePhysicalPhase.RECOVERY
            death_test.update(phase='damage_now',next=now+.15)
        elif phase=='pair_for_death':
            pawn.physical_interaction.shove()
            assert pawn.physical_interaction.get_phase()==u.BaselinePhysicalPhase.INTERACTION
            death_test.update(phase='damage_now',next=now+.15)
        elif phase=='damage_now':
            death_test['old_pawn']=pawn.get_name()
            death_test['player_state']=pawn.player_state.get_name()
            death_test['pickups_before']=len(u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup))
            death_test['items_before']=len([i for i in pawn.get_controller().quick_bar.get_slots() if i])
            if death_test['cycle']==1:
                pawn.physical_interaction.start_ragdoll(u.Vector(80,0,0))
            death_damage(partners[0],pawn,35)
            assert abs(health.get_health()-65)<.1,'Nonlethal damage was not applied once'
            assert not health.is_dead_or_dying()
            death_damage(partners[0],pawn,100)
            death_test.update(phase='dead_player',next=now+.35,started=now)
        elif phase=='dead_player':
            assert health.is_dead_or_dying() and health.get_health()==0
            assert 'DEAD' in str(pawn.physical_interaction.get_phase()) and pawn.mesh.is_simulating_physics('pelvis')
            assert pawn.baseline_equipment.are_hands_busy()
            assert not pawn.can_use_movement_actions()
            old_side=pawn.baseline_equipment.is_left_shoulder()
            pawn.baseline_equipment.toggle_shoulder()
            pawn.physical_interaction.request_recovery()
            assert pawn.baseline_equipment.is_left_shoulder()==old_side and 'DEAD' in str(pawn.physical_interaction.get_phase())
            assert not any(pawn.get_controller().quick_bar.get_slots()),'Inventory still equipped on corpse'
            drops=len(u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup))-death_test['pickups_before']
            assert drops==death_test['items_before'],'Death duplicated or lost world weapon drops'
            if death_test['cycle']==3:
                assert all(not a.physical_interaction.is_busy() for a in partners), 'Death left the surviving partner locked in interaction'
            death_test['results'].append({'case':['player_combat_death','player_death_while_ragdolled','player_death_during_getup','player_death_during_paired_action'][death_test['cycle']],'drops':drops})
            death_test.update(phase='player_respawn',next=now+3.8)
        elif phase=='player_respawn':
            assert pawn.get_name()!=death_test['old_pawn'],'Player did not respawn'
            assert pawn.player_state.get_name()==death_test['player_state'],'Respawn replaced PlayerState/ASC ownership'
            assert health.get_health()==100 and not health.is_dead_or_dying()
            assert pawn.can_use_movement_actions() and not pawn.baseline_equipment.are_hands_busy()
            tag=u.GameplayTag(); tag.import_text('(TagName="Baseline.State.HandsBusy")')
            assert not u.AbilitySystemLibrary.get_ability_system_component(pawn).has_matching_gameplay_tag(tag), 'Dead avatar left weapon abilities blocked'
            assert not pawn.get_controller().is_move_input_ignored(),'Respawn retained death movement lock'
            assert not any(pawn.get_controller().quick_bar.get_slots())
            death_test['results'].append({'case':'clean_player_respawn','cycle':death_test['cycle']+1,'health':health.get_health()})
            death_test['cycle']+=1
            if death_test['cycle']==4:death_finish()
            else:death_test.update(phase='damage_player',next=now+.5)
    except Exception:death_finish(traceback.format_exc())
    finally:death_test['busy']=False


death_test['handle']=u.register_slate_post_tick_callback(death_tick)
print('Started combat death and respawn checks')
