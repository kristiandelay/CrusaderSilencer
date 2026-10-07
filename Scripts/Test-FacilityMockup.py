"""PIE walkthrough, navigation, roof coverage and camera checks for the facility."""
import json, math, time, traceback
from pathlib import Path
import unreal as u

ft_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
ft_world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
ft_pawn=u.GameplayStatics.get_player_pawn(ft_world,0)
ft_origin=u.Vector(12600,8100,30)
ft_report=dict(passed=False,checks=[],walkthrough=[])

def ft_check(name,passed,**details):
    ft_report['checks'].append(dict(name=name,passed=bool(passed),**details))

def ft_trace(x,y,z,end_z):
    hit=u.SystemLibrary.line_trace_single(ft_world,ft_origin+u.Vector(x,y,z),ft_origin+u.Vector(x,y,end_z),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[ft_pawn],u.DrawDebugTrace.NONE,True)
    return hit.to_dict() if hit else None

# Geometry provenance, roof coverage (including tile seams) and actual floor hits.
ft_catalog={r['asset'] for r in json.loads((ft_root/'resources/EnvironmentModels.json').read_text())}
ft_meshes=[a for a in u.GameplayStatics.get_all_actors_of_class(ft_world,u.StaticMeshActor) if a.get_actor_label().startswith('CR_Facility_')]
ft_check('Existing imported kit only',bool(ft_meshes) and all(a.static_mesh_component.static_mesh.get_path_name() in ft_catalog for a in ft_meshes),instances=len(ft_meshes))
ft_roof_points=[(-1650+300*x,-1350+300*y) for x in range(12) for y in range(10)]
ft_roof_points += [(-1500+300*x,-1200+300*y) for x in range(11) for y in range(9)]
ft_roof_misses=[]
for x,y in ft_roof_points:
    hit=ft_trace(x,y,520,720)
    if not hit or not hit['hit_actor'].get_actor_label().startswith(('CR_Facility_Roof','CR_Facility_Column','CR_Facility_Office','CR_Facility_Checkpoint')):
        ft_roof_misses.append([x,y,hit['hit_actor'].get_actor_label() if hit else None])
ft_check('Roof covers room centres and tile seams',not ft_roof_misses,samples=len(ft_roof_points),misses=ft_roof_misses)
ft_rooms={'Checkpoint':(-1200,-800),'Laboratory':(-1050,400),'Main hall':(0,-100),'Office':(1150,600),'Freight bay':(1000,-950)}
for name,(x,y) in ft_rooms.items():
    hit=ft_trace(x,y,180,-100)
    ft_check(name+' imported floor',hit and hit['hit_actor'].get_actor_label().startswith('CR_Facility_Floor'),height_cm=round(hit['impact_point'].z,2) if hit else None)
    path=u.NavigationSystemV1.find_path_to_location_synchronously(ft_world,u.Vector(11400,5500,50),ft_origin+u.Vector(x,y,25))
    ft_check(name+' reachable from crowd approach',path and path.is_valid() and not path.is_partial(),path_points=len(path.path_points) if path else 0)

for name,start,end in [('Entrance',(-1200,-1740),(-1200,-1260)),('Lab doorway',(-1200,-540),(-1200,-60)),('Checkpoint side doorway',(-540,-900),(-60,-900)),('Office doorway',(1150,60),(1150,540))]:
    hit=u.SystemLibrary.capsule_trace_single(ft_world,ft_origin+u.Vector(*start,100),ft_origin+u.Vector(*end,100),30,86,u.TraceTypeQuery.TRACE_TYPE_QUERY1,False,[ft_pawn],u.DrawDebugTrace.NONE,True)
    ft_check(name+' standing capsule clearance',hit is None,blocker=hit.to_dict()['hit_actor'].get_actor_label() if hit else None)

# Move the real player with movement input, without teleporting between rooms.
ft_route=[('Entrance',-1200,-1250),('Checkpoint',-1200,-750),('Laboratory',-1200,100),('Containment aisle',-1050,400),('Main hall',0,0),('Office approach',1150,0),('Office',1150,600),('Office exit',1150,0),('Freight bay',850,-900),('Checkpoint side doorway',-850,-900),('Exit',-1200,-1800)]
ft_pawn.character_movement.stop_movement_immediately()
ft_pawn.set_actor_location(u.Vector(11400,5350,130),False,True)
ft_pawn.get_controller().set_control_rotation(u.Rotator(yaw=90))
ft_test=dict(index=0,phase='walk',next=0,deadline=time.monotonic()+150,busy=False,leg_start=time.monotonic())

def ft_finish(error=None):
    ft_pawn.character_movement.stop_movement_immediately()
    u.unregister_slate_post_tick_callback(ft_test['handle'])
    ft_report['error']=error
    ft_report['passed']=error is None and all(c['passed'] for c in ft_report['checks'])
    ft_report['walkthrough_completed']=ft_test['index']==len(ft_route)
    (ft_root/'Artifacts/FacilityMockup/validation.json').write_text(json.dumps(ft_report,indent=2)+'\n')
    ft_test['finished']=True
    print('FACILITY_VALIDATION',json.dumps(ft_report))

def ft_tick(dt):
    if ft_test['busy']:return
    ft_test['busy']=True
    try:
        assert time.monotonic()<ft_test['deadline'],'Walkthrough exceeded time limit'
        now=u.GameplayStatics.get_time_seconds(ft_world)
        if now<ft_test['next']:return
        name,x,y=ft_route[ft_test['index']]
        pos=ft_pawn.get_actor_location();target=ft_origin+u.Vector(x,y,0)
        dx=target.x-pos.x;dy=target.y-pos.y;distance=math.hypot(dx,dy)
        controller=ft_pawn.get_controller()
        if ft_test['phase']=='walk':
            assert time.monotonic()-ft_test['leg_start']<30,'Stuck approaching '+name+' at '+str(pos)
            assert 60<pos.z<250,'Player left walkable floor at '+name
            if distance>45:
                controller.set_control_rotation(u.Rotator(yaw=math.degrees(math.atan2(dy,dx))))
                ft_pawn.add_movement_input(u.Vector(dx/distance,dy/distance,0),1.,True)
            else:
                ft_pawn.character_movement.stop_movement_immediately()
                ft_test.update(phase='measure',next=now+.6)
        else:
            camera=controller.player_camera_manager.get_camera_location()
            boom=math.hypot(camera.x-pos.x,camera.y-pos.y)
            ft_report['walkthrough'].append(dict(stop=name,position=[round(pos.x,1),round(pos.y,1),round(pos.z,1)],camera_distance_cm=round(boom,1)))
            ft_check(name+' third-person camera clearance',boom>260,camera_distance_cm=round(boom,1))
            ft_test['index']+=1
            if ft_test['index']==len(ft_route):ft_finish();return
            ft_test.update(phase='walk',next=0,leg_start=time.monotonic())
    except Exception:
        ft_finish(traceback.format_exc())
    finally:ft_test['busy']=False

ft_test['handle']=u.register_slate_post_tick_callback(ft_tick)
print('FACILITY_WALKTHROUGH_STARTED',json.dumps(ft_report['checks']))
