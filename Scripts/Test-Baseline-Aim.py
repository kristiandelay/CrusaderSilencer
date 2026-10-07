"""PIE tests of rendered muzzle alignment and mapped aiming/firing during momentum slides."""
import math
import json
import time
import traceback
from pathlib import Path
import unreal as u
aim_out=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent/'Artifacts/AimTests'
aim_out.mkdir(parents=True,exist_ok=True)
aim_test={'phase':'pickup','next':0,'weapon_index':0,'results':[],'busy':False,'deadline':time.monotonic()+240}

def aim_context():
    world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
    pawn=u.GameplayStatics.get_player_pawn(world,0)
    pc=pawn.get_controller()
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem)
             if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==pc)
    equipment=pawn.get_component_by_class(u.BaselineEquipmentComponent)
    return world,pawn,pc,sub,equipment

def aim_input(sub,name,value):
    paths={'Fire':'/Game/Input/Actions/IA_Weapon_Fire_Auto','FireSemi':'/Game/Input/Actions/IA_Weapon_Fire',
           'Reload':'/Game/Input/Actions/IA_Weapon_Reload',
           'Interact':'/Game/Baseline/Input/IA_Interact'}
    sub.inject_input_vector_for_action(u.load_asset(paths.get(name,'/Game/Input/IA_'+name)),u.Vector(*value),[],[])

def aim_ammo(item):
    tag=u.GameplayTag();tag.import_text('(TagName="Lyra.ShooterGame.Weapon.MagazineAmmo")')
    return item.get_stat_tag_stack_count(tag)

def aim_weapon(pawn):
    return pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_spawned_actors()[0]

def aim_error(pawn):
    muzzle=aim_weapon(pawn).get_component_by_class(u.SkeletalMeshComponent).get_socket_rotation('Muzzle')
    target=pawn.get_control_rotation()
    def direction(rotation):
        pitch,yaw=math.radians(rotation.pitch),math.radians(rotation.yaw)
        return (math.cos(pitch)*math.cos(yaw),math.cos(pitch)*math.sin(yaw),math.sin(pitch))
    dot=sum(a*b for a,b in zip(direction(muzzle),direction(target)))
    return math.degrees(math.acos(max(-1,min(1,dot))))

def aim_finish(error=None):
    u.unregister_slate_post_tick_callback(aim_test['handle'])
    aim_test['finished']=True
    try:
        _,pawn,_,sub,_=aim_context()
        for name in ['Fire','FireSemi','Aim','Move','Sprint','Crouch','Interact']:aim_input(sub,name,(0,0,0))
        pawn.character_movement.set_slide_requested(False)
        pawn.un_crouch()
    except Exception:pass
    aim_test.pop('capture',None)
    report={'passed':error is None,'error':error,'results':aim_test['results']}
    (aim_out/'aim-and-slide.json').write_text(json.dumps(report,indent=2))
    u.log('BASELINE_AIM_RESULT '+json.dumps(report))

def aim_tick(dt):
    state=aim_test
    if state['busy']:return
    state['busy']=True
    try:
        assert time.monotonic()<state['deadline'],'Aim tests timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds or not u.GameplayStatics.get_player_pawn(worlds[0],0):return
        world,pawn,pc,sub,equipment=aim_context()
        now=u.GameplayStatics.get_time_seconds(world)
        if state['phase'] in ['angle','measure']:
            aim_input(sub,'Aim',(1,0,0))
        if now<state['next']:return
        phase=state['phase'];kind=['Rifle','Pistol','Shotgun'][state['weapon_index']]
        movement=pawn.character_movement
        if phase=='pickup':
            movement.set_slide_requested(False);pawn.un_crouch();movement.stop_movement_immediately()
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(world,u.BaselineWeaponPickup) if kind in a.item_definition.get_name())
            location=pickup.get_actor_location()
            pawn.set_actor_location(u.Vector(location.x-110,location.y,94),False,True)
            pawn.set_actor_rotation(u.Rotator(pitch=0,yaw=0,roll=0),True)
            pc.set_control_rotation(u.Rotator(pitch=0,yaw=0,roll=0))
            state.update(phase='interact',next=now+.5)
        elif phase=='interact':
            aim_input(sub,'Interact',(1,0,0))
            state.update(phase='carry',next=now+2,angle_index=0)
        elif phase=='carry':
            anim=equipment.get_presentation_mesh().get_anim_instance()
            muzzle=aim_weapon(pawn).get_component_by_class(u.SkeletalMeshComponent).get_socket_rotation('Muzzle')
            assert not equipment.is_weapon_ready() and anim.weapon_ready_weight<.02
            assert anim.weapon_upper_body_weight<.02 and abs(anim.aim_pitch)<.1
            assert muzzle.pitch<-35,f'{kind} never lowered: {muzzle}'
            state['results'].append({'weapon':kind,'case':'lowered_carry','muzzle_pitch':muzzle.pitch})
            state.update(phase='angle',next=now+.1)
        elif phase=='angle':
            assert kind in pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_class().get_name()
            pitch,yaw=[(0,0),(50,0),(-50,0),(20,60),(-20,-60)][state['angle_index']]
            pawn.set_actor_rotation(u.Rotator(pitch=0,yaw=0,roll=0),True)
            pc.set_control_rotation(u.Rotator(pitch=pitch,yaw=yaw,roll=0))
            state.update(phase='measure',next=now+1.2,pitch=pitch,yaw=yaw)
        elif phase=='measure':
            error=aim_error(pawn)
            assert error<18, f'{kind} barrel differs from aim by {error:.1f} degrees'
            anim=equipment.get_presentation_mesh().get_anim_instance()
            assert abs(anim.aim_pitch-state['pitch'])<1
            state['results'].append({'weapon':kind,'case':'aim','pitch':state['pitch'],'yaw':state['yaw'],'muzzle_error_degrees':error})
            if state['angle_index']==1:
                state['capture']=u.AutomationLibrary.take_high_res_screenshot(1440,900,str(aim_out/(kind.lower()+'-aim-up.png')),delay=0.0)
            state['angle_index']+=1
            state.update(phase='angle' if state['angle_index']<5 else 'slide_place',next=now+.1)
        elif phase=='slide_place':
            aim_input(sub,'Aim',(0,0,0))
            pawn.un_crouch();movement.stop_movement_immediately()
            pawn.set_actor_location(u.Vector(-1400,-3200,94),False,True)
            pawn.set_actor_rotation(u.Rotator(pitch=0,yaw=0,roll=0),True)
            pc.set_control_rotation(u.Rotator(pitch=0,yaw=0,roll=0))
            state.update(phase='run',next=now+.5,started=now+.5)
        elif phase=='run':
            aim_input(sub,'Move',(0,1,0));aim_input(sub,'Sprint',(1,0,0))
            assert now-state['started']<4,'Could not reach slide entry speed'
            if pawn.get_velocity().length()>660:
                aim_input(sub,'Crouch',(1,0,0))
                state.update(phase='slide_fire',started=now,ammo_before=aim_ammo(equipment.get_active_item()),errors=[],aim_yaws=[],captured=False)
        elif phase=='slide_fire':
            elapsed=now-state['started']
            for name in ['Move','Sprint','Crouch']:aim_input(sub,name,(0,0,0))
            for name in ['Aim','Fire','FireSemi']:aim_input(sub,name,(1,0,0))
            pc.set_control_rotation(u.Rotator(pitch=25,yaw=45,roll=0))
            if elapsed>.2:
                assert movement.is_sliding(),'Slide ended while firing'
                assert not equipment.are_hands_busy(),'Slide incorrectly blocks weapon abilities'
                assert not aim_weapon(pawn).get_editor_property('bHidden'),'Weapon hidden during slide'
                state['errors'].append(aim_error(pawn))
                state['aim_yaws'].append(equipment.get_presentation_mesh().get_anim_instance().aim_yaw)
            if elapsed>.4 and not state['captured']:
                state['captured']=True
                state['capture']=u.AutomationLibrary.take_high_res_screenshot(1440,900,str(aim_out/(kind.lower()+'-slide-fire.png')),delay=0.0)
            if elapsed>.8:
                for name in ['Aim','Fire','FireSemi']:aim_input(sub,name,(0,0,0))
                after=aim_ammo(equipment.get_active_item())
                assert after<state['ammo_before'],'Firing while sliding consumed no ammo'
                assert state['errors'] and max(state['errors'])<18,str(state['errors'])
                assert max(abs(y) for y in state['aim_yaws'])>20,'No sideways aim offset during slide'
                state['results'].append({'weapon':kind,'case':'aim_and_fire_while_sliding','ammo_before':state['ammo_before'],'ammo_after':after,'maximum_muzzle_error_degrees':max(state['errors']),'aim_yaw':state['aim_yaws'][-1]})
                movement.set_slide_requested(False);pawn.un_crouch()
                state.update(phase='reload_start',next=now+1.5)
        elif phase=='reload_start':
            assert equipment.get_presentation_mesh().get_anim_instance().weapon_upper_body_weight<.02
            aim_input(sub,'Reload',(1,0,0))
            state.update(phase='reload_measure',started=now,maximum_reload_weight=0)
        elif phase=='reload_measure':
            anim=equipment.get_presentation_mesh().get_anim_instance()
            state['maximum_reload_weight']=max(state['maximum_reload_weight'],anim.weapon_upper_body_weight)
            if now-state['started']>4:
                assert aim_ammo(equipment.get_active_item())==state['ammo_before'],'Reload did not restore ammunition'
                assert state['maximum_reload_weight']>.8,'Reload never blended into the upper body'
                assert anim.weapon_upper_body_weight<.02,'Reload never returned to relaxed carry'
                state['results'].append({'weapon':kind,'case':'reload_from_carry','maximum_reload_weight':state['maximum_reload_weight']})
                state['weapon_index']+=1
                if state['weapon_index']==3:aim_finish()
                else:state.update(phase='pickup',next=now+.5)
    except Exception:aim_finish(traceback.format_exc())
    finally:state['busy']=False

aim_test['handle']=u.register_slate_post_tick_callback(aim_tick)
print('Started three-weapon muzzle alignment and slide-combat tests')
