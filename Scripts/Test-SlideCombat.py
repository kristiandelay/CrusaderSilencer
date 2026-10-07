"""Check real weapon alignment and shots while sliding with the current rig."""
import json,math,time,traceback
from pathlib import Path
import unreal as u

ss_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
ss_test=dict(phase='pickup',index=0,next=0,busy=False,results=[],deadline=time.monotonic()+150)
ss_cases=[(weapon,left) for weapon in ['Rifle','Pistol','Shotgun'] for left in [False,True]]

def ss_input(sub,name,value):
    paths={'Interact':'/Game/Baseline/Input/IA_Interact','Fire':'/Game/Input/Actions/IA_Weapon_Fire_Auto','FireSemi':'/Game/Input/Actions/IA_Weapon_Fire'}
    sub.inject_input_vector_for_action(u.load_asset(paths.get(name,'/Game/Input/IA_'+name)),u.Vector(*value) if isinstance(value,tuple) else u.Vector(value,0,0),[],[])

def ss_ammo(p):
    tag=u.GameplayTag();tag.import_text('(TagName="Lyra.ShooterGame.Weapon.MagazineAmmo")')
    return p.baseline_equipment.get_active_item().get_stat_tag_stack_count(tag)

def ss_finish(error=None):
    u.unregister_slate_post_tick_callback(ss_test['handle']);ss_test.update(finished=True,error=error)
    p=u.GameplayStatics.get_player_pawn(u.EditorLevelLibrary.get_pie_worlds(False)[0],0)
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==p.get_controller())
    for n in ['Aim','Fire','FireSemi','Move','Sprint','Crouch','Interact']:ss_input(sub,n,0)
    p.character_movement.set_slide_requested(False);p.un_crouch()
    (ss_root/'Artifacts/SlideCadence/combat.json').write_text(json.dumps(dict(passed=error is None,error=error,results=ss_test['results']),indent=2)+'\n')
    print('SLIDE_COMBAT_COMPLETE',error)

def ss_tick(dt):
    if ss_test['busy']:return
    ss_test['busy']=True
    try:
        assert time.monotonic()<ss_test['deadline'],'Slide combat check timed out'
        w=u.EditorLevelLibrary.get_pie_worlds(False)[0];p=u.GameplayStatics.get_player_pawn(w,0)
        sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==p.get_controller())
        now=u.GameplayStatics.get_time_seconds(w);eq=p.baseline_equipment;move=p.character_movement
        if ss_test.pop('release',False):ss_input(sub,'Interact',0)
        if now<ss_test['next']:return
        phase=ss_test['phase'];kind,left=ss_cases[ss_test['index']]
        if phase=='pickup':
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.BaselineWeaponPickup) if kind in a.item_definition.get_name())
            p.set_actor_location(pickup.get_actor_location()+u.Vector(-100,0,40),False,True)
            p.get_controller().set_control_rotation(u.Rotator(yaw=0))
            ss_test.update(phase='interact',next=now+.5)
        elif phase=='interact':
            ss_input(sub,'Interact',1);ss_test.update(phase='place',next=now+1,release=True)
        elif phase=='place':
            assert kind in p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_class().get_name()
            for n in ['Aim','Fire','FireSemi','Move','Sprint','Crouch']:ss_input(sub,n,0)
            p.un_crouch();move.stop_movement_immediately()
            p.set_actor_location(u.Vector(-1400,-3200,94),False,True)
            p.set_actor_rotation(u.Rotator(yaw=0),False);p.get_controller().set_control_rotation(u.Rotator(yaw=0))
            if eq.is_left_shoulder()!=left:eq.toggle_shoulder()
            ss_test.update(phase='run',next=now+.7,started=now+.7)
        elif phase=='run':
            ss_input(sub,'Move',(0,1,0));ss_input(sub,'Sprint',1)
            assert now-ss_test['started']<5,'Could not reach slide speed'
            if p.get_velocity().length()>660:
                ss_input(sub,'Crouch',1)
                ss_test.update(phase='fire',started=now,before=ss_ammo(p),errors=[],hands=[])
        elif phase=='fire':
            for n in ['Move','Sprint','Crouch']:ss_input(sub,n,0)
            ss_input(sub,'Aim',1)
            p.get_controller().set_control_rotation(u.Rotator(pitch=25,yaw=45))
            elapsed=now-ss_test['started']
            # Measure aim before the weapon's recoil montage kicks the muzzle up.
            # Then fire while still sliding and verify ammunition and hand grips.
            for n in ['Fire','FireSemi']:ss_input(sub,n,1 if elapsed>1.0 else 0)
            if elapsed>.65:
                assert move.is_sliding() and not eq.are_hands_busy()
                weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_spawned_actors()[0]
                assert not weapon.get_editor_property('bHidden')
                r=weapon.get_component_by_class(u.SkeletalMeshComponent).get_socket_rotation('Muzzle')
                def direction(rot):
                    pitch,yaw=math.radians(rot.pitch),math.radians(rot.yaw)
                    return [math.cos(pitch)*math.cos(yaw),math.cos(pitch)*math.sin(yaw),math.sin(pitch)]
                if elapsed<.95:
                    ss_test['errors'].append(math.degrees(math.acos(max(-1,min(1,sum(a*b for a,b in zip(direction(r),direction(p.get_control_rotation()))))))))
                ss_test['hands'].append(max((eq.get_presentation_mesh().get_socket_location(n)-eq.get_weapon_animation_mesh().get_socket_location(n)).length() for n in ['hand_l','hand_r']))
            if elapsed>1.4:
                after=ss_ammo(p)
                assert after<ss_test['before'],'No rounds fired during slide'
                assert max(ss_test['errors'])<18,ss_test['errors']
                assert max(ss_test['hands'])<6,ss_test['hands']
                ss_test['results'].append(dict(weapon=kind,left_shoulder=left,rounds_fired=ss_test['before']-after,maximum_aim_error_before_recoil_degrees=max(ss_test['errors']),maximum_hand_error_cm=max(ss_test['hands'])))
                for n in ['Aim','Fire','FireSemi']:ss_input(sub,n,0)
                move.set_slide_requested(False);p.un_crouch()
                ss_test['index']+=1
                if ss_test['index']==len(ss_cases):ss_finish()
                else:ss_test.update(phase='pickup' if ss_cases[ss_test['index']][0]!=kind else 'place',next=now+1)
    except Exception:ss_finish(traceback.format_exc())
    finally:ss_test['busy']=False

ss_test['handle']=u.register_slate_post_tick_callback(ss_tick)
