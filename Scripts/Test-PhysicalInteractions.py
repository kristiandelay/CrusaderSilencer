"""Mapped-input PIE checks for paired matching, passive ragdoll and recovery."""
import math
physical_out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/PhysicalTests'
physical_out.mkdir(parents=True,exist_ok=True)
physical_test={'phase':'setup','next':0,'results':[],'samples':[],'deadline':time.monotonic()+180,'busy':False,'index':0}

def physical_input(pawn,name,value):
    pc=pawn.get_controller()
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pc)
    sub.inject_input_vector_for_action(u.load_asset('/Game/Baseline/Input/IA_'+name),u.Vector(value,0,0),[],[])

def physical_finish(error=None):
    u.unregister_slate_post_tick_callback(physical_test['handle'])
    physical_test['finished']=True
    (physical_out/'physical-interactions.json').write_text(json.dumps({'passed':error is None,'error':error,'results':physical_test['results'],'samples':physical_test['samples']},indent=2))
    print('PHYSICAL_TEST_COMPLETE',error)

def physical_tick(dt):
    if physical_test['busy']:return
    physical_test['busy']=True
    try:
        assert time.monotonic()<physical_test['deadline'],'Physical test timeout'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        world=worlds[0]
        pawn=u.GameplayStatics.get_player_pawn(world,0)
        if not pawn:return
        physical=pawn.get_component_by_class(u.BaselinePhysicalInteractionComponent)
        now=u.GameplayStatics.get_time_seconds(world)
        if physical_test.pop('release',None):
            for name in ['Shove','Tackle','Takedown','Ragdoll','Interact']:physical_input(pawn,name,0)
        if now<physical_test['next']:return
        partners=[a for a in u.GameplayStatics.get_all_actors_of_class(world,u.CRTraversalCharacter) if 'TrainingPartner' in a.get_name()]
        assert partners,'No training partners'
        target=partners[0]
        other=target.get_component_by_class(u.BaselinePhysicalInteractionComponent)
        phase=physical_test['phase']
        if phase=='setup':
            assert physical.controls_created and other.controls_created,'Physics Control setup failed'
            assert len(pawn.get_component_by_class(u.PhysicsControlComponent).get_all_control_names())>10
            equipment=pawn.get_component_by_class(u.BaselineEquipmentComponent)
            if not pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance):
                pawn.set_actor_location(u.Vector(2100,-1100,94),False,True)
                pawn.set_actor_rotation(u.Rotator(yaw=0),False)
                pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
                physical_input(pawn,'Interact',1)
                physical_test.update(next=now+1,release=True)
                return
            physical_test.update(phase='position',next=now+1)
        elif phase=='position':
            assert not physical.is_busy() and not other.is_busy(),'Previous action did not release participants'
            pawn.character_movement.stop_movement_immediately()
            target.character_movement.stop_movement_immediately()
            # Leave enough open floor for the tackle's root motion and get-up
            # capsule; the old lane could put a passive body under a parkour block.
            pawn.set_actor_location(u.Vector(1500,-3200,94),False,True)
            pawn.set_actor_rotation(u.Rotator(yaw=0),False)
            pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
            target.set_actor_location(u.Vector(1650,-3200,94),False,True)
            target.set_actor_rotation(u.Rotator(yaw=180),False)
            if target.get_controller():target.get_controller().set_control_rotation(u.Rotator(yaw=180))
            physical_test.update(phase='trigger',next=now+1)
        elif phase=='trigger':
            action=['Shove','Tackle','Takedown','Ragdoll'][physical_test['index']]
            if action!='Ragdoll':assert physical.find_interaction_target()==target,physical.last_result
            physical_input(pawn,action,1)
            physical_test.update(phase='observe',started=now,next=now+.15,release=True,action=action,saw_pair=False,saw_ragdoll=False,saw_recovery=False)
        elif phase=='verify_restored':
            assert not physical.is_busy() and not other.is_busy(),'Recovery did not stay complete'
            for restored in [pawn,target]:
                assert restored.get_actor_location().z>50,'Capsule fell through floor after recovery'
                assert restored.capsule_component.get_collision_response_to_channel(u.CollisionChannel.ECC_WORLD_STATIC)==u.CollisionResponseType.ECR_BLOCK,'Floor collision was not restored'
            weapon=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
            assert weapon and not weapon.get_spawned_actors()[0].get_editor_property('bHidden'),'Weapon was not restored'
            physical_test['results'].append({'case':'recovery_restores_collision_and_weapon','passed':True})
            physical_finish()
        elif phase=='observe':
            elapsed=now-physical_test['started']
            a,b=str(physical.get_phase()),str(other.get_phase())
            physical_test['samples'].append({'action':physical_test['action'],'t':elapsed,'owner_phase':a,'target_phase':b,'owner_position':str(pawn.get_actor_location()),'target_position':str(target.get_actor_location()),'owner_collision':str(pawn.capsule_component.get_collision_enabled()),'target_collision':str(target.capsule_component.get_collision_enabled()),'owner_floor_response':str(pawn.capsule_component.get_collision_response_to_channel(u.CollisionChannel.ECC_WORLD_STATIC)),'target_floor_response':str(target.capsule_component.get_collision_response_to_channel(u.CollisionChannel.ECC_WORLD_STATIC))})
            if 'INTERACTION' in a and 'INTERACTION' in b:
                physical_test['saw_pair']=True
                match=physical.get_interaction_result()
                assert match.selected_anim and match.role=='Attacker'
                assert other.get_interaction_result().selected_anim==match.selected_anim
            if 'RAGDOLL' in a or 'RAGDOLL' in b:
                physical_test['saw_ragdoll']=True
                ragdoll=pawn if 'RAGDOLL' in a else target
                assert ragdoll.mesh.is_simulating_physics('pelvis'),'Ragdoll has no simulated pelvis'
                control=ragdoll.get_component_by_class(u.PhysicsControlComponent)
                assert not any(control.get_control_enabled(name) for name in control.get_all_control_names()),'Animation motors are fighting the ragdoll'
                assert ragdoll.mesh.get_socket_location('pelvis').z>-100,'Ragdoll fell through floor'
                if 'RAGDOLL' in a and elapsed>4:
                    physical_input(pawn,'Ragdoll',1)
                    physical_test['release']=True
            if 'RECOVERY' in a or 'RECOVERY' in b:physical_test['saw_recovery']=True
            weapon=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
            if weapon and physical.is_busy():assert weapon.get_spawned_actors()[0].get_editor_property('bHidden'),'Weapon visible during physical action'
            if elapsed>.35 and not physical.is_busy() and not other.is_busy():
                if physical_test['action']!='Ragdoll':assert physical_test['saw_pair'],physical.last_result
                assert physical_test['saw_ragdoll'],'No ragdoll phase'
                assert physical_test['saw_recovery'],'No matched get-up phase'
                physical_test['results'].append({'action':physical_test['action'],'duration':elapsed,'paired':physical_test['saw_pair'],'ragdoll':True,'recovery':True,'match_cost':physical.last_search_cost})
                physical_test['index']+=1
                if physical_test['index']==4:physical_test.update(phase='verify_restored',next=now+1.2)
                else:physical_test.update(phase='position',next=now+.6)
            else:
                assert elapsed<22,physical.last_result+' / '+other.last_result+' phases '+a+' '+b
                physical_test['next']=now+.08
    except Exception:physical_finish(traceback.format_exc())
    finally:physical_test['busy']=False

physical_test['handle']=u.register_slate_post_tick_callback(physical_tick)
print('Started physical interaction checks')
