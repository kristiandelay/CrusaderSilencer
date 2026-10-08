"""Validate solid floors/ceilings, connected nav, stairs and a real player walkthrough."""
import hashlib,json,math,time,traceback
from pathlib import Path
import unreal as u

lt_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
lt_out=lt_root/'Artifacts/Level3';lt_out.mkdir(exist_ok=True)
lt_world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
lt_pawn=u.GameplayStatics.get_player_pawn(lt_world,0)
lt_origin=u.Vector(33000,7900,30)
lt_manifest=json.loads((lt_root/'resources/Level3Facility.json').read_text())
lt_report=dict(passed=False,checks=[],walkthrough=[],manifest_sha256=hashlib.sha256((lt_root/'resources/Level3Facility.json').read_bytes()).hexdigest())
# The shared PIE suite counts result cases; keep its contract alongside the
# richer named checks consumed by the facility content validator.
lt_report['results']=lt_report['checks']
lt_test=dict(next=0,busy=False,index=0,phase='walk',deadline=time.monotonic()+650,leg_start=time.monotonic())
lt_ramp_samples=[]

def lt_sample_stairs():
    pos=lt_pawn.get_actor_location()-lt_origin;velocity=lt_pawn.get_velocity()
    if abs(velocity.y)<40:return
    candidates=[]
    for stair in lt_manifest['stairs']:
        sx,sy,sz=stair['start'];ex,ey,ez=stair['end']
        fraction=(pos.y-sy)/(ey-sy)
        if abs(pos.x-sx)>230 or not .12<fraction<.88:continue
        floor=sz+(ez-sz)*fraction
        residual=pos.z-lt_pawn.capsule_component.get_scaled_capsule_half_height()-floor
        if abs(residual)<200:candidates.append((abs(residual),residual,stair['actor'],velocity.y*(ey-sy)>0))
    if candidates:
        _,residual,actor,up=min(candidates)
        lt_ramp_samples.append(dict(actor=actor,direction='up' if up else 'down',offset_cm=residual))

def lt_check(name,passed,**details):lt_report['checks'].append(dict(name=name,passed=bool(passed),**details))
def lt_trace(start,end):
    hit=u.SystemLibrary.line_trace_single(lt_world,lt_origin+u.Vector(*start),lt_origin+u.Vector(*end),u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[lt_pawn],u.DrawDebugTrace.NONE)
    return hit.to_dict() if hit else None

floor_misses=[]
for x,y,z in lt_manifest['floor_samples']:
    hit=lt_trace((x,y,z+100),(x,y,z-60))
    if not hit or not hit['hit_actor'].get_actor_label().startswith('CR_Level3_'):floor_misses.append([x,y,z])
lt_check('Solid floor tiles on three storeys',not floor_misses,samples=len(lt_manifest['floor_samples']),misses=floor_misses)
roof_misses=[]
for x,y,z in lt_manifest['ceiling_samples']:
    hit=lt_trace((x,y,z-70),(x,y,z+65))
    if not hit or not hit['hit_actor'].get_actor_label().startswith('CR_Level3_'):roof_misses.append([x,y,z])
lt_check('Enclosed ceilings and roof',not roof_misses,samples=len(lt_manifest['ceiling_samples']),misses=roof_misses)

for level in range(3):
    z=level*720
    for name,(x,y) in {'Hall':(0,-500),'West':(-2250,0),'East':(2400,0),'Command':(0,650),'StairLobby':(4000,-1750)}.items():
        path=u.NavigationSystemV1.find_path_to_location_synchronously(lt_world,u.Vector(20600,4750,30),lt_origin+u.Vector(x,y,z+10))
        lt_check(f'L{level+1} {name} reachable from previous building',path and path.is_valid() and not path.is_partial(),points=len(path.path_points) if path else 0)
    hit=u.SystemLibrary.capsule_trace_single(lt_world,lt_origin+u.Vector(3050,-1725,z+100),lt_origin+u.Vector(3650,-1725,z+100),30,86,u.TraceTypeQuery.TRACE_TYPE_QUERY1,False,[lt_pawn],u.DrawDebugTrace.NONE)
    lt_check(f'L{level+1} stair doorway clearance',hit is None,blocker=hit.to_dict()['hit_actor'].get_actor_label() if hit else None)

lt_npcs=[a for a in u.GameplayStatics.get_all_actors_of_class(lt_world,u.CRTraversalCharacter) if a.get_actor_label().startswith('CR_Level3Crowd_')]
lt_tracks={a.get_actor_label():[u.Vector(a.get_actor_location().x,a.get_actor_location().y,a.get_actor_location().z),0.,a.get_actor_location().z] for a in lt_npcs}
lt_check('Nine residents across all floors',len(lt_npcs)==9,count=len(lt_npcs))
for a in lt_npcs:
    lt_check(a.get_actor_label()+' correct loadout',a.crowd_agent.guard==bool(a.baseline_equipment.get_active_item()))
for area in u.GameplayStatics.get_all_actors_of_class(lt_world,u.CRCrowdArea):
    if not area.get_actor_label().startswith('CR_Level3Crowd_'):continue
    for neighbour in area.neighbours:
        path=u.NavigationSystemV1.find_path_to_location_synchronously(lt_world,area.get_actor_location(),neighbour.get_actor_location())
        lt_check(area.get_actor_label()+' to '+neighbour.get_actor_label(),path and path.is_valid() and not path.is_partial())

lt_route=[('Entry',0,-2400,0,True),('L1 Hall',0,-500,0,True),('L1 West approach',-2250,0,0,True),
          ('L1 Maintenance',-2230,1550,0,True),('L1 West exit',-2250,0,0,False)]
def lt_stair_route(base):
    return [(f'Floor {base//720+1} stair approach',2750,-1725,base,True),('Stair lobby',3800,-1725,base,True),
            ('Lower first tread',3800,-1310,base+12,False),('Lower flight',3800,-670,base+125,True),
            ('Lower resting landing',3800,-200,base+180,False),('Lower upper run',3800,500,base+300,True),
            ('Switchback west',3800,1250,base+360,False),('Switchback east',4800,1250,base+360,True),
            ('Upper lower run',4800,430,base+455,True),('Upper resting landing',4800,-200,base+540,False),
            ('Upper flight',4800,-860,base+665,True),('Upper lobby',4800,-1750,base+720,False),
            ('Upper doorway',2800,-1725,base+720,True)]
for level in range(2):
    lt_route+=lt_stair_route(level*720)
    z=(level+1)*720
    lt_route += [(f'L{level+2} Hall',0,-500,z,True),(f'L{level+2} Focal room',0,650,z,True),
                 ('Bay approach',0,0,z,False),(f'L{level+2} East',2350,0,z,True)]
# Return through both staircases to prove descending works as well.
for level in [1,0]:
    lt_route += list(reversed(lt_stair_route(level*720)))
lt_route += [('Ground exit',0,-2450,0,True),('Outside',0,-3100,0,True)]
lt_pawn.character_movement.stop_movement_immediately()
lt_pawn.set_actor_location(lt_origin+u.Vector(0,-3200,100),False,True)
lt_controller=lt_pawn.get_controller();lt_controller.set_ignore_look_input(True);lt_controller.set_ignore_move_input(True)
u.SystemLibrary.execute_console_command(lt_world,'God',lt_controller)

def lt_finish(error=None):
    lt_pawn.character_movement.stop_movement_immediately()
    lt_controller.set_ignore_look_input(False);lt_controller.set_ignore_move_input(False)
    u.unregister_slate_post_tick_callback(lt_test['handle']);lt_test.update(finished=True,error=error)
    lt_report['patrols']=[dict(actor=name,distance_cm=row[1],minimum_z=row[2]) for name,row in lt_tracks.items()]
    lt_check('Residents continue patrolling',all(r[1]>200 for r in lt_tracks.values()))
    lt_check('Residents stay on facility floors',all(r[2]>45 for r in lt_tracks.values()))
    lt_report['smooth_stairs']=[]
    for stair in lt_manifest['stairs']:
        for direction in ['up','down']:
            values=[r['offset_cm'] for r in lt_ramp_samples if r['actor']==stair['actor'] and r['direction']==direction]
            metric=dict(actor=stair['actor'],direction=direction,samples=len(values),
                        max_offset_cm=max(map(abs,values)) if values else None,
                        offset_range_cm=max(values)-min(values) if values else None)
            lt_report['smooth_stairs'].append(metric)
            lt_check(stair['actor']+' smooth '+direction,len(values)>=3 and max(map(abs,values))<8 and max(values)-min(values)<4,**metric)
    lt_report.update(passed=error is None and all(r['passed'] for r in lt_report['checks']),error=error,walkthrough_completed=lt_test['index']==len(lt_route))
    (lt_out/'walkthrough.json').write_text(json.dumps(lt_report,indent=2)+'\n')
    print('LEVEL3_WALKTHROUGH_FINISHED',lt_report['passed'],error)

def lt_tick(delta):
    if lt_test['busy']:return
    lt_test['busy']=True
    try:
        assert time.monotonic()<lt_test['deadline'],'Facility walkthrough timed out'
        lt_sample_stairs()
        for npc in lt_npcs:
            pos=npc.get_actor_location();row=lt_tracks[npc.get_actor_label()]
            row[1]+=(pos-row[0]).length();row[0]=u.Vector(pos.x,pos.y,pos.z);row[2]=min(row[2],pos.z)
        now=u.GameplayStatics.get_time_seconds(lt_world)
        if now<lt_test['next']:return
        name,x,y,z,measure=lt_route[lt_test['index']]
        pos=lt_pawn.get_actor_location();target=lt_origin+u.Vector(x,y,z)
        dx=target.x-pos.x;dy=target.y-pos.y;distance=math.hypot(dx,dy)
        if lt_test['phase']=='walk':
            assert time.monotonic()-lt_test['leg_start']<30,('Stuck',name,str(pos),str(target))
            if distance>45:
                lt_controller.set_control_rotation(u.Rotator(yaw=math.degrees(math.atan2(dy,dx))))
                lt_pawn.add_movement_input(u.Vector(dx/distance,dy/distance,0),1.,True)
            else:
                lt_pawn.character_movement.stop_movement_immediately()
                lt_test.update(phase='measure',next=now+(.65 if measure else .05))
        else:
            camera=lt_controller.player_camera_manager.get_camera_location();boom=math.hypot(camera.x-pos.x,camera.y-pos.y)
            lt_report['walkthrough'].append(dict(stop=name,position=[pos.x,pos.y,pos.z],expected_floor_z=target.z,camera_distance_cm=boom))
            lt_check(name+' correct floor',35<pos.z-target.z<160,actual=pos.z-target.z)
            if measure:lt_check(name+' camera room',boom>240,distance_cm=boom)
            lt_test['index']+=1
            if lt_test['index']==len(lt_route):lt_finish();return
            lt_test.update(phase='walk',next=0,leg_start=time.monotonic())
    except Exception:lt_finish(traceback.format_exc())
    finally:lt_test['busy']=False
lt_test['handle']=u.register_slate_post_tick_callback(lt_tick)
print('LEVEL3_INITIAL_CHECKS',len(lt_report['checks']),[r for r in lt_report['checks'] if not r['passed']])
exec(compile((lt_root/'Scripts/Capture-Level3Facility.py').read_text(),'Capture-Level3Facility.py','exec'),globals())
