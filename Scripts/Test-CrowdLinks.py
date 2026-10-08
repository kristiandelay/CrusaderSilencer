"""Navigation must choose the authored smart link and resume after traversal."""
import json,time,traceback
from pathlib import Path
import unreal as u
# Humanoid fixtures; mechanical pawns are covered by Test-RobotGameplay.py.
nl_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
nl_test=dict(index=0,phase='place',next=0,busy=False,results=[],deadline=time.monotonic()+180)
nl_cases=[dict(role=role,start=[2590,-800,94],goal=[3110,-800,0]) for role in ['Guard','Civilian']]
def nl_finish(error=None):
    u.unregister_slate_post_tick_callback(nl_test['handle']);nl_test.update(finished=True,error=error)
    (nl_root/'Artifacts/Environment/crowd-links.json').write_text(json.dumps(dict(passed=not error,error=error,results=nl_test['results']),indent=2))
def nl_tick(dt):
    if nl_test['busy']:return
    nl_test['busy']=True
    try:
        assert time.monotonic()<nl_test['deadline'],'Navigation link timed out'
        ws=u.EditorLevelLibrary.get_pie_worlds(False)
        if not ws:return
        case=nl_cases[nl_test['index']];now=u.GameplayStatics.get_time_seconds(ws[0])
        p=next(a for a in u.GameplayStatics.get_all_actors_of_class(ws[0],u.CRTraversalCharacter) if a.crowd_agent.enabled and not isinstance(a,u.CRRobotCharacter) and a.crowd_agent.guard==(case['role']=='Guard'))
        ctrl=p.get_controller()
        if now<nl_test['next']:return
        if nl_test['phase']=='place':
            ctrl.stop_movement();p.character_movement.stop_movement_immediately()
            p.crowd_agent.set_editor_property('current_area',None);p.crowd_agent.set_editor_property('threat',None)
            p.crowd_agent.set_editor_property('desired_speed',220.);p.crowd_agent.set_editor_property('destination',u.Vector(*case['goal']))
            p.set_actor_location(u.Vector(*case['start']),False,True)
            nl_test.update(phase='move',next=now+1,before=p.crowd_agent.traversals_started)
        elif nl_test['phase']=='move':
            assert ctrl.move_to_location(u.Vector(*case['goal']),30)==u.PathFollowingRequestResult.REQUEST_SUCCESSFUL
            nl_test.update(phase='check',next=now+8)
        else:
            assert p.crowd_agent.traversals_started>nl_test['before']
            assert p.get_actor_location().x>2950 and ctrl.get_move_status()==u.PathFollowingStatus.IDLE,p.get_actor_location()
            nl_test['results'].append(dict(role=case['role'],smart_link_traversed=True,path_resumed=True,ended_x=p.get_actor_location().x))
            nl_test['index']+=1
            if nl_test['index']==len(nl_cases):nl_finish()
            else:nl_test.update(phase='place',next=now+.5)
    except Exception:nl_finish(traceback.format_exc())
    finally:nl_test['busy']=False
nl_test['handle']=u.register_slate_post_tick_callback(nl_tick)
