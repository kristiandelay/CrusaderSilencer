"""Opposing streams must pass each other and reach their destinations."""
import json,time,traceback,math
from pathlib import Path
import unreal as u
# Humanoid fixtures; mechanical pawns are covered by Test-RobotGameplay.py.
av_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
av_test=dict(phase='place',next=0,busy=False,results=[],deadline=time.monotonic()+150)
def av_vec(v):return [v.x,v.y,v.z]
def av_finish(error=None):
    u.unregister_slate_post_tick_callback(av_test['handle']);av_test.update(finished=True,error=error)
    (av_root/'Artifacts/Environment/crowd-avoidance.json').write_text(json.dumps(dict(passed=not error,error=error,results=av_test['results']),indent=2))
def av_tick(dt):
    if av_test['busy']:return
    av_test['busy']=True
    try:
        assert time.monotonic()<av_test['deadline'],'Crowd crossing timed out'
        ws=u.EditorLevelLibrary.get_pie_worlds(False)
        if not ws:return
        now=u.GameplayStatics.get_time_seconds(ws[0])
        # This fixture intentionally measures the original twelve-agent crossing.
        npcs=sorted([p for p in u.GameplayStatics.get_all_actors_of_class(ws[0],u.CRTraversalCharacter) if p.crowd_agent.enabled and not isinstance(p,u.CRRobotCharacter) and p.crowd_agent.home_area and p.crowd_agent.home_area.get_actor_label().startswith('CR_Crowd_')],key=lambda p:p.get_name())
        if len(npcs)!=12 or not all(p.crowd_agent.initialized for p in npcs) or not u.GameplayStatics.get_player_pawn(ws[0],0):return
        if av_test['phase']=='cross':
            positions=[p.get_actor_location() for p in npcs]
            av_test['minimum_separation']=min(av_test['minimum_separation'],min((a-b).length() for i,a in enumerate(positions) for b in positions[i+1:]))
            for p in npcs:av_test['lateral'][p.get_name()]=max(av_test['lateral'][p.get_name()],abs(p.get_actor_location().y-av_test['start'][p.get_name()][1]))
        if now<av_test['next']:return
        if av_test['phase']=='place':
            player=u.GameplayStatics.get_player_pawn(ws[0],0);player.set_actor_location(u.Vector(1100,-5700,94),False,True)
            av_test.update(start={},goals={},lateral={},minimum_separation=9999.)
            for i,p in enumerate(npcs):
                p.get_controller().stop_movement();p.character_movement.stop_movement_immediately();p.un_crouch()
                for key,value in [('Threat','None'),('CurrentArea','None'),('DesiredSpeed','220')]:
                    assert u.CRBlueprintTools.set_property_text(p.crowd_agent,key,value)
                # Six opposing pairs occupy a clear part of the authored district.
                y=-1700+(i%6)*125;start=u.Vector(11200 if i<6 else 12400,y,94);goal=u.Vector(12400 if i<6 else 11200,y,0)
                p.set_actor_location(start,False,True)
                assert u.CRBlueprintTools.set_property_text(p.crowd_agent,'Destination',goal.export_text())
                av_test['start'][p.get_name()]=av_vec(start);av_test['goals'][p.get_name()]=av_vec(goal);av_test['lateral'][p.get_name()]=0
            av_test.update(phase='move',next=now+1)
        elif av_test['phase']=='move':
            for p in npcs:assert p.get_controller().move_to_location(u.Vector(*av_test['goals'][p.get_name()]),50)==u.PathFollowingRequestResult.REQUEST_SUCCESSFUL
            av_test.update(phase='cross',next=now+24)
        else:
            distances={p.get_name():math.dist(av_vec(p.get_actor_location())[:2],av_test['goals'][p.get_name()][:2]) for p in npcs}
            assert all(d<160 for d in distances.values()),distances
            assert av_test['minimum_separation']>55,av_test['minimum_separation']
            assert max(av_test['lateral'].values())>35,av_test['lateral']
            av_test['results'].append(dict(case='twelve_agent_opposing_streams',goal_distances=distances,minimum_separation=av_test['minimum_separation'],lateral_avoidance=av_test['lateral']));av_finish()
    except Exception:av_finish(traceback.format_exc())
    finally:av_test['busy']=False
av_test['handle']=u.register_slate_post_tick_callback(av_tick)
