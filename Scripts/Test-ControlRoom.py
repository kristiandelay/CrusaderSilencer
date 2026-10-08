"""Real navigation, floor/roof collision and third-person walkthrough of Level2."""
import json, math, time, traceback
from pathlib import Path
import unreal as u

ct_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
ct_out=ct_root/'Artifacts/ControlRoom';ct_out.mkdir(exist_ok=True)
ct_world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
ct_pawn=u.GameplayStatics.get_player_pawn(ct_world,0)
ct_origin=u.Vector(20600,7900,30)
ct_manifest=json.loads((ct_root/'resources/ControlRoomMockup.json').read_text())
ct_report=dict(passed=False,checks=[],walkthrough=[])

def ct_check(name,passed,**details):ct_report['checks'].append(dict(name=name,passed=bool(passed),**details))
def ct_trace(x,y,z,end):
    hit=u.SystemLibrary.line_trace_single(ct_world,ct_origin+u.Vector(x,y,z),ct_origin+u.Vector(x,y,end),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[ct_pawn],u.DrawDebugTrace.NONE,True)
    return hit.to_dict() if hit else None

ct_catalog={r['asset'] for r in json.loads((ct_root/'resources/EnvironmentModels.json').read_text()) if r['category']=='Level2'}
ct_meshes=[a for a in u.GameplayStatics.get_all_actors_of_class(ct_world,u.StaticMeshActor) if a.get_actor_label().startswith('CR_ControlRoom_')]
ct_check('Imported Level2 kit only',bool(ct_meshes) and all(a.static_mesh_component.static_mesh.get_path_name() in ct_catalog for a in ct_meshes),instances=len(ct_meshes))
ct_misses=[]
ct_samples=ct_manifest['roof_samples']+[[x+150,y+150] for x,y in ct_manifest['roof_samples'] if [x+300,y+300] in ct_manifest['roof_samples']]
for x,y in ct_samples:
    hit=ct_trace(x,y,575,750)
    if not hit or not hit['hit_actor'].get_actor_label().startswith('CR_ControlRoom_'):ct_misses.append([x,y])
ct_check('Solid roof at tile centres and seams',not ct_misses,samples=len(ct_samples),misses=ct_misses)
ct_rooms={'Lobby':(0,-1750),'Hall':(0,-500),'Operations':(0,600),'Command':(0,1330),'Service':(-2490,0),'Storage':(2490,0)}
for name,(x,y) in ct_rooms.items():
    hit=ct_trace(x,y,170,-90)
    ct_check(name+' walkable kit floor',hit and hit['hit_actor'].get_actor_label().startswith('CR_ControlRoom_Floor'),height=hit['impact_point'].z if hit else None)
    path=u.NavigationSystemV1.find_path_to_location_synchronously(ct_world,u.Vector(14300,3500,30),ct_origin+u.Vector(x,y,25))
    ct_check(name+' reachable from district',path and path.is_valid() and not path.is_partial(),points=len(path.path_points) if path else 0)
for name,start,end in [('Main entrance',(0,-2370),(0,-1800)),('West entrance',(-3280,0),(-2690,0)),('Service route',(-2370,0),(-1820,0)),('Storage route',(1830,0),(2370,0))]:
    hit=u.SystemLibrary.capsule_trace_single(ct_world,ct_origin+u.Vector(*start,100),ct_origin+u.Vector(*end,100),30,86,u.TraceTypeQuery.TRACE_TYPE_QUERY1,False,[ct_pawn],u.DrawDebugTrace.NONE,True)
    ct_check(name+' standing clearance',hit is None,blocker=hit.to_dict()['hit_actor'].get_actor_label() if hit else None)

ct_route=[('Entrance',0,-1790),('Main hall',0,-650),('Operations',0,600),('Command',0,1290),
          ('Command exit',0,500),('Storage approach',1450,0),('Storage',2500,0),('Storage exit',1450,0),
          ('Cross hall',0,0),('Service approach',-1450,0),('Service',-2500,0),('West exit',-3370,0)]
ct_pawn.character_movement.stop_movement_immediately();ct_pawn.set_actor_location(ct_origin+u.Vector(0,-2650,100),False,True)
ct_test=dict(index=0,phase='walk',next=0,deadline=time.monotonic()+210,busy=False,leg_start=time.monotonic())

def ct_finish(error=None):
    ct_pawn.character_movement.stop_movement_immediately();u.unregister_slate_post_tick_callback(ct_test['handle'])
    ct_report.update(error=error,passed=error is None and all(c['passed'] for c in ct_report['checks']),walkthrough_completed=ct_test['index']==len(ct_route))
    (ct_out/'walkthrough.json').write_text(json.dumps(ct_report,indent=2)+'\n')
    ct_test['finished']=True;print('CONTROL_ROOM_WALKTHROUGH',ct_report['passed'],error)

def ct_tick(dt):
    if ct_test['busy']:return
    ct_test['busy']=True
    try:
        assert time.monotonic()<ct_test['deadline'],'Walkthrough timed out'
        now=u.GameplayStatics.get_time_seconds(ct_world)
        if now<ct_test['next']:return
        name,x,y=ct_route[ct_test['index']];pos=ct_pawn.get_actor_location();target=ct_origin+u.Vector(x,y,0)
        dx=target.x-pos.x;dy=target.y-pos.y;distance=math.hypot(dx,dy)
        controller=ct_pawn.get_controller()
        if ct_test['phase']=='walk':
            assert time.monotonic()-ct_test['leg_start']<35,'Stuck at '+name+' '+str(pos)
            assert 60<pos.z<250,'Player left floor at '+name
            if distance>45:
                controller.set_control_rotation(u.Rotator(yaw=math.degrees(math.atan2(dy,dx))))
                ct_pawn.add_movement_input(u.Vector(dx/distance,dy/distance,0),1,True)
            else:
                ct_pawn.character_movement.stop_movement_immediately();ct_test.update(phase='measure',next=now+.8)
        else:
            camera=controller.player_camera_manager.get_camera_location();boom=math.hypot(camera.x-pos.x,camera.y-pos.y)
            ct_report['walkthrough'].append(dict(stop=name,position=[pos.x,pos.y,pos.z],camera_distance_cm=boom))
            ct_check(name+' camera clearance',boom>260,distance_cm=boom)
            ct_test['index']+=1
            if ct_test['index']==len(ct_route):ct_finish();return
            ct_test.update(phase='walk',next=0,leg_start=time.monotonic())
    except Exception:ct_finish(traceback.format_exc())
    finally:ct_test['busy']=False
ct_test['handle']=u.register_slate_post_tick_callback(ct_tick)
print('CONTROL_ROOM_CHECKS',json.dumps(ct_report['checks']))
