"""Exercise Black Iron Rifle aim and fire during a slide on both shoulders."""
import math
import json
import time
import traceback
import unreal as u

cs_slide={'phase':'place','side':0,'next':0,'results':[],'busy':False,'deadline':time.monotonic()+90}
def css_finish(error=None):
    u.unregister_slate_post_tick_callback(cs_slide['handle'])
    cs_slide.update(finished=True,error=error)
    world=u.EditorLevelLibrary.get_pie_worlds(False)[0];pawn=u.GameplayStatics.get_player_pawn(world,0)
    for n in ['Aim','Fire','Move','Sprint','Crouch']:cs_input(pawn,n,0)
    pawn.character_movement.set_slide_requested(False);pawn.un_crouch()
    (cs_out/'slide-validation.json').write_text(json.dumps({'passed':error is None,'error':error,'results':cs_slide['results']},indent=2))
    print('CRIMSON_SLIDE_COMPLETE',error)

def css_tick(dt):
    if cs_slide['busy']:return
    cs_slide['busy']=True
    try:
        assert time.monotonic()<cs_slide['deadline']
        world=u.EditorLevelLibrary.get_pie_worlds(False)[0];pawn=u.GameplayStatics.get_player_pawn(world,0)
        now=u.GameplayStatics.get_time_seconds(world);eq=pawn.baseline_equipment;move=pawn.character_movement
        if now<cs_slide['next']:return
        phase=cs_slide['phase']
        if phase=='place':
            for n in ['Aim','Fire','Move','Sprint','Crouch']:cs_input(pawn,n,0)
            pawn.un_crouch();move.stop_movement_immediately()
            pawn.set_actor_location(u.Vector(-1400,-3200,94),False,True)
            pawn.set_actor_rotation(u.Rotator(yaw=0),False);pawn.get_controller().set_control_rotation(u.Rotator(yaw=0))
            if eq.is_left_shoulder()!=(cs_slide['side']==1):eq.toggle_shoulder()
            cs_slide.update(phase='run',next=now+.7,started=now+.7)
        elif phase=='run':
            cs_input(pawn,'Move',(0,1,0));cs_input(pawn,'Sprint',1)
            assert now-cs_slide['started']<5,'Could not reach slide speed'
            if pawn.get_velocity().length()>660:
                cs_input(pawn,'Crouch',1)
                cs_slide.update(phase='fire',started=now,before=cs_ammo(pawn),errors=[],hand_errors=[])
        elif phase=='fire':
            for n in ['Move','Sprint','Crouch']:cs_input(pawn,n,0)
            cs_input(pawn,'Aim',1)
            pawn.get_controller().set_control_rotation(u.Rotator(pitch=25,yaw=45))
            elapsed=now-cs_slide['started']
            # Acquire the sideways aim before firing; retain the normal carry
            # transition instead of requiring an instantaneous 45-degree snap.
            cs_input(pawn,'Fire',1 if elapsed>.4 else 0)
            if elapsed>.5:
                assert move.is_sliding() and not eq.are_hands_busy()
                weapon=pawn.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).get_spawned_actors()[0]
                assert not weapon.get_editor_property('bHidden')
                r=weapon.get_component_by_class(u.SkeletalMeshComponent).get_socket_rotation('Muzzle')
                def direction(rot):
                    p,y=math.radians(rot.pitch),math.radians(rot.yaw)
                    return [math.cos(p)*math.cos(y),math.cos(p)*math.sin(y),math.sin(p)]
                error=math.degrees(math.acos(max(-1,min(1,sum(a*b for a,b in zip(direction(r),direction(pawn.get_control_rotation())))))))
                cs_slide['errors'].append(error)
                cs_slide['hand_errors'].append(max((eq.get_presentation_mesh().get_socket_location(n)-eq.get_weapon_animation_mesh().get_socket_location(n)).length() for n in ['hand_l','hand_r']))
            if elapsed>.95:
                after=cs_ammo(pawn)
                assert after<cs_slide['before'],'No rounds fired while sliding'
                assert max(cs_slide['errors'])<18,cs_slide['errors']
                assert max(cs_slide['hand_errors'])<6,cs_slide['hand_errors']
                cs_slide['results'].append({'left':cs_slide['side']==1,'rounds_fired':cs_slide['before']-after,'maximum_muzzle_error_degrees':max(cs_slide['errors']),'maximum_hand_error_cm':max(cs_slide['hand_errors'])})
                for n in ['Aim','Fire']:cs_input(pawn,n,0)
                move.set_slide_requested(False);pawn.un_crouch()
                cs_slide['side']+=1
                if cs_slide['side']==2:css_finish()
                else:cs_slide.update(phase='place',next=now+1)
    except Exception:css_finish(traceback.format_exc())
    finally:cs_slide['busy']=False
cs_slide['handle']=u.register_slate_post_tick_callback(css_tick)
