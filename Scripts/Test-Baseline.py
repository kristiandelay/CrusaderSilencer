"""PIE integration checks driven through the baseline's actual Enhanced Input actions."""
import math
baseline_out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/BaselineTests'
baseline_out.mkdir(parents=True,exist_ok=True)
baseline_test={'phase':'pickup','next':0,'results':[],'busy':False,'wall_deadline':time.monotonic()+300}

def baseline_context():
    world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
    pawn=u.GameplayStatics.get_player_pawn(world,0)
    controller=pawn.get_controller()
    subs=[s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
          if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==controller]
    assert len(subs)==1
    return world,pawn,controller,subs[0]

def baseline_input(sub,name,value):
    paths={'Interact':'/Game/Baseline/Input/IA_Interact','Drop':'/Game/Baseline/Input/IA_Drop',
           'Cycle':'/Game/Baseline/Input/IA_Cycle','Fire':'/Game/Input/Actions/IA_Weapon_Fire_Auto',
           'FireSemi':'/Game/Input/Actions/IA_Weapon_Fire',
           'Reload':'/Game/Input/Actions/IA_Weapon_Reload'}
    action=u.load_asset(paths.get(name,'/Game/Input/IA_'+name))
    sub.inject_input_vector_for_action(action,u.Vector(*value),[],[])

def baseline_stats(item):
    result={}
    for name in ['MagazineAmmo','SpareAmmo','MagazineSize']:
        tag=u.GameplayTag()
        assert tag.import_text('(TagName="Lyra.ShooterGame.Weapon.'+name+'")')
        result[name]=item.get_stat_tag_stack_count(tag)
    return result

def baseline_result(name,**data):
    baseline_test['results'].append({'name':name,**data})
    u.log('BASELINE_CASE '+json.dumps(baseline_test['results'][-1]))

def baseline_finish(error=None):
    u.unregister_slate_post_tick_callback(baseline_test['handle'])
    baseline_test['finished']=True
    try:
        _,_,_,sub=baseline_context()
        for name in ['Interact','Drop','Cycle','Fire','FireSemi','Reload','Move','Sprint','Crouch','Jump']:
            baseline_input(sub,name,(0,0,0))
    except Exception:
        pass
    baseline_test.pop('capture',None)
    report={'passed':error is None,'error':error,'results':baseline_test['results']}
    (baseline_out/'result.json').write_text(json.dumps(report,indent=2))
    u.log('BASELINE_RESULT '+json.dumps(report))

def baseline_tick(dt):
    state=baseline_test
    if state['busy']:return
    state['busy']=True
    try:
        assert time.monotonic()<state['wall_deadline'],'Baseline test exceeded its wall-clock deadline'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds or not u.GameplayStatics.get_player_pawn(worlds[0],0):return
        world,pawn,controller,sub=baseline_context()
        # Screenshots can stall the editor; action durations must follow game time.
        now=u.GameplayStatics.get_time_seconds(world)
        if now<state['next']:return
        equipment=pawn.get_component_by_class(u.BaselineEquipmentComponent)
        movement=pawn.character_movement
        assert isinstance(movement,u.BaselineCharacterMovement)
        phase=state['phase']
        if phase=='pickup':
            pawn.set_actor_location(u.Vector(2100,-1100,94),False,True)
            controller.set_control_rotation(u.Rotator(pitch=-10,yaw=0,roll=0))
            assert 'Rifle' in equipment.find_pickup().item_definition.get_name()
            baseline_input(sub,'Interact',(1,0,0))
            state.update(phase='verify_pickup',next=now+2)
        elif phase=='verify_pickup':
            item=equipment.get_active_item()
            assert item and len(controller.inventory.get_all_items())==1
            stats=baseline_stats(item)
            assert stats['MagazineAmmo']==30
            mesh=equipment.get_presentation_mesh()
            assert isinstance(mesh.get_anim_instance(),u.BaselineAnimInstance)
            assert mesh.get_anim_instance().get_editor_property('weapon_pose_weight')>.9
            instances=pawn.equipment_manager.get_equipment_instances_of_type(u.BaselineWeaponInstance)
            assert len(instances)==1
            actors=instances[0].get_spawned_actors()
            assert len(actors)==1 and actors[0].root_component.get_attach_parent()==mesh
            baseline_result('rifle_pickup_and_equip',ammo=stats,weapon=instances[0].get_class().get_path_name())
            state['capture']=u.AutomationLibrary.take_high_res_screenshot(1440,900,str(baseline_out/'rifle-equipped.png'),delay=0.0)
            state.update(phase='fire',started=now,next=now+.5)
        elif phase=='fire':
            if now-state['started']<1.5:
                baseline_input(sub,'Fire',(1,0,0))
            else:
                baseline_input(sub,'Fire',(0,0,0))
                state.update(phase='verify_fire',next=now+.5)
        elif phase=='verify_fire':
            stats=baseline_stats(equipment.get_active_item())
            assert 0<stats['MagazineAmmo']<30, 'Lyra fire ability did not consume ammo: '+str(stats)
            baseline_result('lyra_rifle_fire',ammo=stats)
            state['before_reload']=stats
            baseline_input(sub,'Reload',(1,0,0))
            state.update(phase='verify_reload',next=now+4)
        elif phase=='verify_reload':
            stats=baseline_stats(equipment.get_active_item())
            assert stats['MagazineAmmo']==30 and stats['SpareAmmo']<state['before_reload']['SpareAmmo'],str(stats)
            assert sum(stats[k] for k in ['MagazineAmmo','SpareAmmo'])==sum(state['before_reload'][k] for k in ['MagazineAmmo','SpareAmmo'])
            baseline_result('lyra_reload',ammo=stats)
            state['saved_stats']=stats
            baseline_input(sub,'Drop',(1,0,0))
            state.update(phase='verify_drop',next=now+2)
        elif phase=='verify_drop':
            assert equipment.get_active_item() is None
            assert len(controller.inventory.get_all_items())==0
            assert not pawn.equipment_manager.get_equipment_instances_of_type(u.LyraEquipmentInstance)
            drops=[a for a in u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup) if a.get_editor_property('bHasSavedStats')]
            assert len(drops)==1
            drop=drops[0]
            assert drop.get_actor_location().z<70 and drop.collision.is_simulating_physics()
            location=drop.get_actor_location()
            baseline_result('drop_creates_physical_world_item',location=[location.x,location.y,location.z])
            pawn.set_actor_location(u.Vector(location.x-100,location.y,94),False,True)
            controller.set_control_rotation(u.Rotator(pitch=-10,yaw=0,roll=0))
            state.update(phase='repick',next=now+.5)
        elif phase=='repick':
            assert equipment.find_pickup()
            baseline_input(sub,'Interact',(1,0,0))
            state.update(phase='verify_repick',next=now+1)
        elif phase=='verify_repick':
            assert baseline_stats(equipment.get_active_item())==state['saved_stats']
            baseline_result('repick_preserves_ammo',ammo=baseline_stats(equipment.get_active_item()))
            state.update(phase='slide_place',next=now+.5,slide_case=0)
        elif phase=='slide_place':
            movement.set_slide_requested(False)
            pawn.un_crouch()
            movement.stop_movement_immediately()
            case=['flat','downhill','uphill'][state['slide_case']]
            if case=='flat':
                location=u.Vector(-1400,-3200,94);yaw=0
            else:
                ramp=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.StaticMeshActor) if 'Baseline_SlideRamp' in a.get_actor_label())
                center=ramp.get_actor_location();normal=ramp.get_actor_up_vector()
                x=-1350 if case=='downhill' else 0
                z=center.z+20/normal.z-normal.x/normal.z*(x-center.x)
                location=u.Vector(x,-4600,z+94);yaw=0 if case=='downhill' else 180
            pawn.set_actor_location(location,False,True)
            pawn.set_actor_rotation(u.Rotator(pitch=0,yaw=yaw,roll=0),True)
            controller.set_control_rotation(u.Rotator(pitch=-10,yaw=yaw,roll=0))
            state.update(phase='slide_run',next=now+.6,started=now+.6,slide_name=case)
        elif phase=='slide_run':
            baseline_input(sub,'Move',(0,1,0))
            baseline_input(sub,'Sprint',(1,0,0))
            assert now-state['started']<4, 'Could not reach slide entry speed: '+str(pawn.get_velocity())
            if pawn.get_velocity().length()>660:
                baseline_input(sub,'Crouch',(1,0,0))
                state.update(phase='slide_measure',started=now,speeds=[],sliding=[],heights=[])
        elif phase=='slide_measure':
            baseline_input(sub,'Move',(0,0,0))
            baseline_input(sub,'Sprint',(0,0,0))
            baseline_input(sub,'Crouch',(0,0,0))
            elapsed=now-state['started']
            state['speeds'].append(pawn.get_velocity().length())
            state['sliding'].append(movement.is_sliding())
            state['heights'].append(pawn.capsule_component.get_scaled_capsule_half_height())
            if elapsed>.25 and not state.get('shot_'+state['slide_name']):
                state['shot_'+state['slide_name']]=True
                state['capture']=u.AutomationLibrary.take_high_res_screenshot(1440,900,str(baseline_out/('slide-'+state['slide_name']+'.png')),delay=0.0)
            if elapsed>(3.5 if state['slide_name']=='flat' else .7):
                assert any(state['sliding']),'No slide state'
                assert min(state['heights'])<=60.1,'Capsule never crouched'
                speeds=state['speeds']
                if state['slide_name']=='flat':
                    assert max(speeds)>700 and speeds[-1]<180 and not movement.is_sliding(),str(speeds[::10])
                elif state['slide_name']=='downhill':
                    assert speeds[-1]>speeds[0]+15,str(speeds[::10])
                else:
                    assert speeds[-1]<speeds[0]-100,str(speeds[::10])
                baseline_result('slide_'+state['slide_name'],initial_speed=speeds[0],maximum_speed=max(speeds),final_speed=speeds[-1],capsule_half_height=min(state['heights']))
                state['slide_case']+=1
                if state['slide_case']==3:state.update(phase='other_place',next=now+.5,other_index=0)
                else:state.update(phase='slide_place',next=now+.3)
        elif phase=='other_place':
            movement.set_slide_requested(False)
            pawn.un_crouch()
            movement.stop_movement_immediately()
            kind=['Pistol','Shotgun'][state['other_index']]
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup) if kind in a.item_definition.get_name())
            location=pickup.get_actor_location()
            pawn.set_actor_location(u.Vector(location.x-110,location.y,94),False,True)
            pawn.set_actor_rotation(u.Rotator(pitch=0,yaw=0,roll=0),True)
            controller.set_control_rotation(u.Rotator(pitch=-10,yaw=0,roll=0))
            state.update(phase='other_pick',next=now+1,weapon_kind=kind)
        elif phase=='other_pick':
            assert equipment.find_pickup()
            baseline_input(sub,'Interact',(1,0,0))
            state.update(phase='other_verify',next=now+2)
        elif phase=='other_verify':
            instance=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
            assert instance and state['weapon_kind'] in instance.get_class().get_name()
            state['other_ammo']=baseline_stats(equipment.get_active_item())
            state.update(phase='other_fire',started=now)
        elif phase=='other_fire':
            if now-state['started']<.4:
                baseline_input(sub,'Fire',(1,0,0))
                baseline_input(sub,'FireSemi',(1,0,0))
            else:
                baseline_input(sub,'Fire',(0,0,0))
                baseline_input(sub,'FireSemi',(0,0,0))
                state.update(phase='other_check_fire',next=now+.8)
        elif phase=='other_check_fire':
            stats=baseline_stats(equipment.get_active_item())
            assert stats['MagazineAmmo']<state['other_ammo']['MagazineAmmo'],str(stats)
            baseline_result('lyra_'+state['weapon_kind'].lower()+'_pickup_and_fire',ammo=stats)
            state['other_index']+=1
            if state['other_index']==2:
                assert len(controller.inventory.get_all_items())==3
                state['old_slot']=controller.quick_bar.get_active_slot_index()
                baseline_input(sub,'Cycle',(1,0,0))
                state.update(phase='check_cycle',next=now+1)
            else:state.update(phase='other_place',next=now+.3)
        elif phase=='check_cycle':
            assert controller.quick_bar.get_active_slot_index()!=state['old_slot']
            assert len(pawn.equipment_manager.get_equipment_instances_of_type(u.LyraEquipmentInstance))==1
            assert len(pawn.get_components_by_class(u.LyraEquipmentManagerComponent))==1
            baseline_result('three_slot_inventory_and_switch',slots=len(controller.inventory.get_all_items()))
            # Empty-state setup verifies that definition defaults never refill a dropped item.
            item=equipment.get_active_item()
            for name in ['SpareAmmo','MagazineAmmo']:
                tag=u.GameplayTag();tag.import_text('(TagName="Lyra.ShooterGame.Weapon.'+name+'")')
                item.remove_stat_tag_stack(tag,item.get_stat_tag_stack_count(tag))
            baseline_input(sub,'Drop',(1,0,0))
            state.update(phase='empty_drop',next=now+2)
        elif phase=='empty_drop':
            assert len(controller.inventory.get_all_items())==2
            drops=[a for a in u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup) if a.get_editor_property('bHasSavedStats')]
            assert len(drops)==1
            location=drops[0].get_actor_location()
            pawn.set_actor_location(u.Vector(location.x-100,location.y,94),False,True)
            controller.set_control_rotation(u.Rotator(pitch=-10,yaw=0,roll=0))
            state.update(phase='empty_pick',next=now+.5)
        elif phase=='empty_pick':
            assert equipment.find_pickup()
            baseline_input(sub,'Interact',(1,0,0))
            state.update(phase='empty_verify',next=now+1)
        elif phase=='empty_verify':
            stats=baseline_stats(equipment.get_active_item())
            assert stats['MagazineAmmo']==0 and stats['SpareAmmo']==0,str(stats)
            assert len(controller.inventory.get_all_items())==3
            baseline_result('empty_weapon_drop_and_recovery',ammo=stats)
            baseline_finish()
    except Exception:
        baseline_finish(traceback.format_exc())
    finally:
        state['busy']=False

baseline_test['handle']=u.register_slate_post_tick_callback(baseline_tick)
print('Started baseline pickup/drop, fire/reload and slide checks')
