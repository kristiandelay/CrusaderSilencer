"""Each armed guard loadout returns fire using Laser Trace 5."""
import json,time,traceback
from pathlib import Path
import unreal as u

lg_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
lg_test=dict(phase='place',index=0,next=0,busy=False,results=[],deadline=time.monotonic()+100)
lg_kinds=['Rifle','Pistol','Shotgun']

def lg_finish(error=None):
    u.unregister_slate_post_tick_callback(lg_test['handle']);lg_test.update(finished=True,error=error)
    (lg_root/'Artifacts/LaserTracer/guards.json').write_text(json.dumps(dict(passed=not error,error=error,results=lg_test['results']),indent=2))
    print('LASER_GUARDS_COMPLETE',error)

def lg_tick(dt):
    if lg_test['busy']:return
    lg_test['busy']=True
    try:
        assert time.monotonic()<lg_test['deadline'],'Guard firing timed out'
        w=u.EditorLevelLibrary.get_pie_worlds(False)[0];p=u.GameplayStatics.get_player_pawn(w,0)
        now=u.GameplayStatics.get_time_seconds(w)
        if now<lg_test['next']:return
        kind=lg_kinds[lg_test['index']]
        if lg_test['phase']=='place':
            guards=[a for a in u.GameplayStatics.get_all_actors_of_class(w,u.CRTraversalCharacter) if a.crowd_agent.guard and a.crowd_agent.initialized]
            g=next(a for a in guards if a.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance).effects_profile.get_name()=='FX_'+kind)
            p.get_controller().set_ignore_move_input(True)
            if not lg_test.get('god'):
                u.SystemLibrary.execute_console_command(w,'God',p.get_controller());lg_test['god']=True
            g.get_controller().stop_movement();g.character_movement.stop_movement_immediately()
            assert u.CRBlueprintTools.set_property_text(g.crowd_agent,'CurrentArea','None')
            g.set_actor_location(u.Vector(15000,4000,94),False,True);g.set_actor_rotation(u.Rotator(yaw=180),False);g.get_controller().set_control_rotation(u.Rotator(yaw=180))
            p.set_actor_location(u.Vector(14000,4000,94),False,True)
            lg_test.update(guard=g,before=g.weapon_effects.shots_played,phase='provoke',next=now+.8)
        elif lg_test['phase']=='provoke':
            u.AISense_Hearing.report_noise_event(w,p.get_actor_location(),1,p,1600,'Gunfire')
            lg_test.update(phase='check',next=now+.2)
        else:
            g=lg_test['guard'];fx=g.weapon_effects
            if fx.shots_played==lg_test['before']:return
            assert fx.last_profile.bullet_trail.get_name()=='NS_Laser_Trace_Red_2'
            assert fx.last_profile.movement_driven_trail and fx.trails_played>0
            assert len(fx.last_impacts)>=(2 if kind=='Shotgun' else 1)
            lg_test['results'].append(dict(weapon=kind,shots=fx.shots_played-lg_test['before'],pellets=len(fx.last_impacts),effect=fx.last_profile.bullet_trail.get_path_name()))
            g.set_actor_location(u.Vector(20000+lg_test['index']*2000,-5000,94),False,True)
            lg_test['index']+=1
            if lg_test['index']==len(lg_kinds):lg_finish()
            else:lg_test.update(phase='place',next=now+1)
    except Exception:lg_finish(traceback.format_exc())
    finally:lg_test['busy']=False

lg_test['handle']=u.register_slate_post_tick_callback(lg_tick)
