"""Guard and civilian use the player's jump, slide and GASP traversal selection."""
import json,time,traceback,math
from pathlib import Path
import unreal as u
# Humanoid fixtures; mechanical pawns are covered by Test-RobotGameplay.py.

ct_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
ct_actions=[
 dict(name='Jump',start=[8000,-1850,94],goal=[8700,-1850,94],yaw=0),
 dict(name='Slide',start=[8000,-1850,94],goal=[9600,-1850,94],yaw=0),
 dict(name='Hurdle',action='Vault',start=[2730,-800,94],goal=[3020,-800,94],yaw=0,axis=0,edge=2820),
 dict(name='Mantle',action='Climb',start=[4300,-970,94],goal=[4300,-800,194],yaw=90,axis=1,edge=-880),
 dict(name='Climb',start=[2700,-1770,94],goal=[2700,-1590,344],yaw=90,axis=1,edge=-1680),
 dict(name='Vault',start=[4810,-800,444],goal=[5350,-800,94],yaw=0,axis=0,edge=4900)]
ct_cases=[dict(role=role,**case) for role in ['Guard','Civilian'] for case in ct_actions]
ct_test=dict(phase='place',index=0,next=0,busy=False,results=[],deadline=time.monotonic()+240)
def ct_vec(v):return [v.x,v.y,v.z]
def ct_finish(error=None):
    u.unregister_slate_post_tick_callback(ct_test['handle']);ct_test.update(finished=True,error=error)
    (ct_root/'Artifacts/Environment/crowd-traversal.json').write_text(json.dumps(dict(passed=not error,error=error,results=ct_test['results']),indent=2))
    print('CROWD_TRAVERSAL_COMPLETE',error)
def ct_tick(dt):
    if ct_test['busy']:return
    ct_test['busy']=True
    try:
        assert time.monotonic()<ct_test['deadline'],'NPC traversal timed out'
        ws=u.EditorLevelLibrary.get_pie_worlds(False)
        if not ws:return
        case=ct_cases[ct_test['index']];now=u.GameplayStatics.get_time_seconds(ws[0]);phase=ct_test['phase']
        matches=[a for a in u.GameplayStatics.get_all_actors_of_class(ws[0],u.CRTraversalCharacter) if a.crowd_agent.enabled and not isinstance(a,u.CRRobotCharacter) and a.crowd_agent.initialized and a.crowd_agent.guard==(case['role']=='Guard')]
        if not matches:return
        p=next((a for a in matches if a.get_name()==ct_test.get('pawn')),matches[0]);ctrl=p.get_controller()
        if phase=='warm' and case['name']=='Slide':p.add_movement_input(u.Vector(1,0,0),1,True)
        if phase=='check':
            ct_test['heights'].append(p.get_actor_location().z);ct_test['capsules'].append(p.capsule_component.get_scaled_capsule_half_height())
            ct_test['sliding']|=p.character_movement.is_sliding()
            montage=p.mesh.get_anim_instance().get_current_active_montage()
            if montage:ct_test['montage']=montage.get_path_name()
            weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
            if weapon and weapon.get_spawned_actors():ct_test['stowed']|=weapon.get_spawned_actors()[0].get_editor_property('bHidden')
        if now<ct_test['next']:return
        if phase=='place':
            ctrl.stop_movement();p.character_movement.stop_movement_immediately();p.un_crouch()
            # Avoid PostEditChange reconstructing the pawn and losing GASP tick bindings.
            for key,value in [('CurrentArea','None'),('Threat','None'),('DesiredSpeed','700')]:
                assert u.CRBlueprintTools.set_property_text(p.crowd_agent,key,value)
            p.set_actor_location(u.Vector(*case['start']),False,True);p.set_actor_rotation(u.Rotator(yaw=case['yaw']),False);ctrl.set_control_rotation(u.Rotator(yaw=case['yaw']))
            ct_test.update(pawn=p.get_name(),phase='warm',next=now+1,heights=[],capsules=[],sliding=False,montage=None,stowed=False)
        elif phase=='warm':
            assert ctrl.request_movement_action(case.get('action',case['name']),u.Vector(*case['goal'])),('Action rejected',case,p.get_velocity(),p.character_movement.movement_mode)
            ct_test.update(phase='check',next=now+4,started=now,start=ct_vec(p.get_actor_location()))
        elif phase=='check':
            montage=p.mesh.get_anim_instance().get_current_active_montage()
            if montage or p.character_movement.movement_mode!=u.MovementMode.MOVE_WALKING:
                assert now-ct_test['started']<12,('Action failed to finish',case,montage)
                ct_test['next']=now+.3;return
            end=ct_vec(p.get_actor_location())
            result=dict(role=case['role'],action=case['name'],start=ct_test['start'],end=end,max_z=max(ct_test['heights']),minimum_capsule=min(ct_test['capsules']),sliding=ct_test['sliding'],montage=ct_test['montage'],weapon_stowed=ct_test['stowed'])
            ct_test['results'].append(result)
            if case['name']=='Jump':assert result['max_z']>ct_test['start'][2]+65,result
            elif case['name']=='Slide':assert result['sliding'] and result['minimum_capsule']<70,result
            else:
                assert result['montage'] and end[case['axis']]>case['edge'],result
                if case['role']=='Guard':assert result['weapon_stowed'],result
            weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
            if weapon:assert not weapon.get_spawned_actors()[0].get_editor_property('bHidden'),'Weapon did not return after action'
            ct_test['index']+=1
            if ct_test['index']==len(ct_cases):ct_finish()
            else:ct_test.update(phase='place',next=now+.5)
    except Exception:ct_finish(traceback.format_exc())
    finally:ct_test['busy']=False
ct_test['handle']=u.register_slate_post_tick_callback(ct_tick)
print('Started',len(ct_cases),'NPC movement parity cases')
