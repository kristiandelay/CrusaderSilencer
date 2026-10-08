"""Verify all six fitted barrel layouts with real player provocation in PIE."""
import json,time,traceback
from pathlib import Path
import unreal as u

mw_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
mw_test=dict(phase='ready',next=0,busy=False,index=0,results=[],deadline=time.monotonic()+150)
def mw_health(p):return p.get_component_by_class(u.LyraHealthComponent).get_health()
def mw_input(p,name,value):
    path={'Aim':'/Game/Input/IA_Aim','Fire':'/Game/Input/Actions/IA_Weapon_Fire','FireAuto':'/Game/Input/Actions/IA_Weapon_Fire_Auto'}[name]
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==p.get_controller())
    sub.inject_input_vector_for_action(u.load_asset(path),u.Vector(value,0,0),[],[])
def mw_finish(error=None):
    u.unregister_slate_post_tick_callback(mw_test['handle']);mw_test.update(finished=True,error=error)
    (mw_root/'Artifacts/RobotGameplay/mounted-weapons.json').write_text(json.dumps(dict(passed=not error,error=error,results=mw_test['results']),indent=2)+'\n')
    print('ROBOT_MOUNTED_WEAPONS_COMPLETE',error)

def mw_tick(dt):
    if mw_test['busy']:return
    mw_test['busy']=True
    try:
        assert time.monotonic()<mw_test['deadline'],'Mounted weapon check timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if len(worlds)!=1:return
        w=worlds[0];p=u.GameplayStatics.get_player_pawn(w,0)
        robots=u.GameplayStatics.get_all_actors_of_class(w,u.CRRobotCharacter)
        if not p or len(robots)!=6 or not all(r.crowd_agent.initialized for r in robots):return
        now=u.GameplayStatics.get_time_seconds(w);phase=mw_test['phase'];r=mw_test.get('robot')
        if mw_test.pop('release',False):mw_input(p,'Fire',0);mw_input(p,'FireAuto',0)
        if phase in ['aim','fire']:
            eye=u.GameplayStatics.get_player_camera_manager(w,0).get_camera_location()
            p.get_controller().set_control_rotation(u.MathLibrary.find_look_at_rotation(eye,r.get_actor_location()+u.Vector(0,0,20)))
            mw_input(p,'Aim',1)
        if phase=='fire' and r.mounted_shots>=max(3,len(r.muzzle_positions)):
            assert r.crowd_agent.provoked and r.crowd_agent.threat==p and mw_health(r)<r.armor_health
            assert r.weapon_effects.shots_played==r.mounted_shots and r.weapon_effects.trails_played>=r.mounted_shots
            point=u.MathLibrary.inverse_transform_location(r.mesh.get_world_transform(),r.last_muzzle_position)
            error=min((point-m).length() for m in r.muzzle_positions)
            assert error<8,(r.get_name(),'barrel did not follow chassis',error)
            mw_test['results'].append(dict(name=r.mesh.skeletal_mesh_asset.get_name(),barrels=len(r.muzzle_positions),shots=r.mounted_shots,health=mw_health(r),muzzle_pose_offset_cm=error))
            mw_input(p,'Aim',0);r.get_controller().set_actor_tick_enabled(False)
            r.set_actor_location(u.Vector(23000,12000+mw_test['index']*400,94),False,True)
            mw_test['index']+=1
            if mw_test['index']==6:mw_finish();return
            mw_test.update(phase='place',next=now+.7)
        elif phase=='fire' and now>=mw_test['next']:raise AssertionError((r.get_name(),'did not return fire',r.mounted_shots,r.crowd_agent.state))
        if now<mw_test['next']:return
        phase=mw_test['phase']
        if phase=='ready':
            u.SystemLibrary.execute_console_command(w,'God',p.get_controller())
            p.get_controller().set_ignore_move_input(True);p.get_controller().set_ignore_look_input(True)
            for index,actor in enumerate(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if a.crowd_agent.enabled):
                actor.get_controller().stop_movement();actor.get_controller().set_actor_tick_enabled(False);actor.character_movement.stop_movement_immediately()
                actor.set_actor_location(u.Vector(23000,12000+index*400,94),False,True)
            pickup=next(a for a in u.GameplayStatics.get_all_actors_of_class(w,u.BaselineWeaponPickup) if a.item_definition.get_name()=='ID_Pistol_C')
            p.set_actor_location(pickup.get_actor_location()+u.Vector(-100,0,40),False,True);p.baseline_equipment.server_pickup(pickup)
            mw_test.update(phase='place',next=now+1)
        elif phase=='place':
            r=robots[mw_test['index']];mw_test['robot']=r
            assert not r.crowd_agent.provoked and r.mounted_shots==0
            u.CRBlueprintTools.set_property_text(r.crowd_agent,'CurrentArea','None')
            r.set_actor_location(u.Vector(12900,-1750,94),False,True);r.set_actor_rotation(u.Rotator(yaw=180),False)
            r.character_movement.disable_movement();r.get_controller().set_control_rotation(u.Rotator(yaw=180));r.get_controller().set_actor_tick_enabled(True)
            p.character_movement.stop_movement_immediately();p.set_actor_location(u.Vector(12150,-1750,94),False,True)
            mw_test.update(phase='aim',next=now+1.5)
        elif phase=='aim':
            mw_input(p,'Fire',1);mw_input(p,'FireAuto',1)
            mw_test.update(phase='fire',next=now+8,release=True)
    except Exception:mw_finish(traceback.format_exc())
    finally:mw_test['busy']=False

mw_test['handle']=u.register_slate_post_tick_callback(mw_tick)
print('ROBOT_MOUNTED_WEAPONS_STARTED')
