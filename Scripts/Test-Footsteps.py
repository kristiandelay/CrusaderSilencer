"""Real animation contact notifies while traversing each physical material."""
import json,time,traceback
from pathlib import Path
import unreal as u

fs_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
fs_pads=json.loads((fs_root/'resources/EnvironmentTestAreas.json').read_text())['footstep_surfaces']
fs_cases=[dict(pad=p,gait='walk') for p in fs_pads]+[dict(pad=next(p for p in fs_pads if p['name']=='Metal'),gait=g) for g in ['run','sprint','sneak','jump','idle','air','ragdoll']]
fs_test=dict(phase='place',index=0,next=0,busy=False,results=[],deadline=time.monotonic()+360)
def fs_input(p,name,value):
    sub=next(s for s in u.ObjectIterator(u.EnhancedInputLocalPlayerSubsystem) if isinstance(s.get_outer(),u.LocalPlayer) and u.GameplayStatics.get_player_controller(s,0)==p.get_controller())
    sub.inject_input_vector_for_action(u.load_asset('/Game/Input/IA_'+name),u.Vector(value,0,0),[],[])
def fs_finish(error=None):
    u.unregister_slate_post_tick_callback(fs_test['handle']);fs_test.update(finished=True,error=error)
    (fs_root/'Artifacts/Environment/footsteps.json').write_text(json.dumps(dict(passed=not error,error=error,results=fs_test['results']),indent=2))
    print('FOOTSTEPS_TEST_COMPLETE',error)
def fs_tick(dt):
    if fs_test['busy']:return
    fs_test['busy']=True
    try:
        assert time.monotonic()<fs_test['deadline'],'Footsteps test timed out'
        worlds=u.EditorLevelLibrary.get_pie_worlds(False)
        if not worlds:return
        p=u.GameplayStatics.get_player_pawn(worlds[0],0)
        if not p or not p.physical_interaction.controls_created:return
        now=u.GameplayStatics.get_time_seconds(p);case=fs_cases[fs_test['index']];phase=fs_test['phase'];foot=p.footsteps
        p.get_controller().set_control_rotation(u.Rotator(yaw=-90));p.get_controller().set_ignore_look_input(True);p.get_controller().set_ignore_move_input(True)
        if phase=='act' and case['gait'] in ['walk','run','sprint','sneak']:
            p.add_movement_input(u.Vector(0,-1,0),1,True)
            fs_input(p,'Walk',0)
            if case['gait']=='sprint':fs_input(p,'Sprint',1)
            if case['gait']=='sneak':p.crouch()
            fs_test['speeds'].append(p.get_velocity().length())
            if foot.sounds_played>fs_test['last_count']:
                fs_test['seen'].append(dict(surface=foot.last_surface,gait=str(foot.last_gait),foot=str(foot.last_foot),sound=foot.last_sound.get_path_name()))
                fs_test['last_count']=foot.sounds_played
        if now<fs_test['next']:return
        if phase=='place':
            for n in ['Walk','Sprint','Jump','Crouch']:fs_input(p,n,0)
            p.un_crouch();p.character_movement.stop_movement_immediately()
            p.character_movement.set_movement_mode(u.MovementMode.MOVE_WALKING)
            p.set_actor_location(u.Vector(*case['pad']['start']),False,True);p.set_actor_rotation(u.Rotator(yaw=-90),False)
            fs_test.update(phase='settle',next=now+.7)
        elif phase=='settle':
            walking='WantsToWalk_3_78963B154975E3BDE244A3BE438473E3=True' in p.get_editor_property('CharacterInputState').export_text()
            if walking != (case['gait']=='walk'):fs_input(p,'Walk',1)
            if case['gait']=='sneak':p.crouch()
            if case['gait']=='jump':p.jump()
            if case['gait']=='air':
                pos=p.get_actor_location();p.set_actor_location(pos+u.Vector(0,0,1200),False,True);p.character_movement.set_movement_mode(u.MovementMode.MOVE_FLYING)
            if case['gait']=='ragdoll':p.physical_interaction.start_ragdoll(u.Vector())
            fs_test.update(phase='act',next=now+(2.3 if case['gait']=='jump' else 1.1 if case['gait']=='sprint' else 1.6 if case['gait']=='run' else 2.4),before=foot.sounds_played,last_count=foot.sounds_played,before_jump=foot.jumps_played,before_land=foot.landings_played,seen=[],speeds=[])
        elif phase=='act':
            delta=foot.sounds_played-fs_test['before']
            result=dict(surface=case['pad']['name'],gait=case['gait'],sounds=delta,steps=fs_test['seen'],max_speed=max(fs_test['speeds'] or [0]),jump=foot.jumps_played-fs_test['before_jump'],land=foot.landings_played-fs_test['before_land'])
            fs_test['results'].append(result)
            if case['gait'] in ['idle','air','ragdoll']:assert delta==0,result
            elif case['gait']=='jump':assert result['land']>=1,result
            else:
                assert delta>=2,result
                assert all(x['surface']==case['pad']['surface'] for x in result['steps']),result
                assert any(case['gait'].upper() in x['gait'] for x in result['steps']),result
            for n in ['Walk','Sprint']:fs_input(p,n,0)
            p.character_movement.stop_movement_immediately();p.stop_jumping()
            fs_test['index']+=1
            if fs_test['index']==len(fs_cases):fs_finish()
            else:fs_test.update(phase='place',next=now+.1)
    except Exception:fs_finish(traceback.format_exc())
    finally:fs_test['busy']=False
fs_test['handle']=u.register_slate_post_tick_callback(fs_tick)
print('Started',len(fs_cases),'footstep surface/gait cases')
