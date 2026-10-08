"""Observe all ten new residents, posture, loadouts and linked patrol routes."""
import json, math, time, traceback
from pathlib import Path
import unreal as u

cct_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
cct_out=cct_root/'Artifacts/ControlRoom';cct_out.mkdir(exist_ok=True)
cct_world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
cct_npcs=[a for a in u.GameplayStatics.get_all_actors_of_class(cct_world,u.CRTraversalCharacter) if a.get_actor_label().startswith('CR_ControlCrowd_')]
cct_manifest=json.loads((cct_root/'resources/ControlRoomCrowd.json').read_text())
assert len(cct_npcs)==10 and all(p.crowd_agent.initialized for p in cct_npcs)
cct_report=dict(passed=False,loadouts=[],routes=[],patrols=[])
for area in [a for a in u.GameplayStatics.get_all_actors_of_class(cct_world,u.CRCrowdArea) if a.get_actor_label().startswith('CR_ControlCrowd_')]:
    for neighbour in area.neighbours:
        path=u.NavigationSystemV1.find_path_to_location_synchronously(cct_world,area.get_actor_location(),neighbour.get_actor_location())
        cct_report['routes'].append(dict(start=area.get_actor_label(),end=neighbour.get_actor_label(),complete=bool(path and path.is_valid() and not path.is_partial()),reciprocal=area in neighbour.neighbours))
for p in cct_npcs:
    expected=next(r for r in cct_manifest['spawns'] if r['actor']==p.get_actor_label())
    visual=p.selected_visual_override.child_actor
    weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
    assert expected['visual'] in visual.get_class().get_name(),expected
    cct_report['loadouts'].append(dict(actor=p.get_actor_label(),guard=p.crowd_agent.guard,armed=bool(p.baseline_equipment.get_active_item()),weapon=weapon.effects_profile.get_name() if weapon else None,visual=visual.get_class().get_name()))
assert all(r['guard']==r['armed'] for r in cct_report['loadouts'])
assert len({r['weapon'] for r in cct_report['loadouts'] if r['guard']})==3
cct_tracks={p.get_actor_label():dict(last=p.get_actor_location(),distance=0.,areas=set(),min_z=99999.,max_z=-99999.,lean=[],gait=[],steps_start=p.footsteps.steps_played) for p in cct_npcs}
cct_test=dict(start=u.GameplayStatics.get_time_seconds(cct_world),next=0,busy=False,deadline=time.monotonic()+200)

def cct_finish(error=None):
    u.unregister_slate_post_tick_callback(cct_test['handle']);cct_test.update(finished=True,error=error)
    cct_report.update(error=error,passed=error is None and all(r['complete'] and r['reciprocal'] for r in cct_report['routes']))
    (cct_out/'crowd.json').write_text(json.dumps(cct_report,indent=2)+'\n')
    print('CONTROL_ROOM_CROWD',cct_report['passed'],error)

def cct_tick(dt):
    if cct_test['busy']:return
    cct_test['busy']=True
    try:
        assert time.monotonic()<cct_test['deadline'],'Patrol observation timed out'
        now=u.GameplayStatics.get_time_seconds(cct_world)
        if now<cct_test['next']:return
        cct_test['next']=now+.25
        for p in cct_npcs:
            row=cct_tracks[p.get_actor_label()];pos=p.get_actor_location()
            row['distance']+=math.hypot(pos.x-row['last'].x,pos.y-row['last'].y);row['last']=pos
            if p.crowd_agent.current_area:row['areas'].add(p.crowd_agent.current_area.get_actor_label())
            row['min_z']=min(row['min_z'],pos.z);row['max_z']=max(row['max_z'],pos.z)
            if p.get_velocity().length()>100:
                mesh=p.baseline_equipment.get_presentation_mesh();delta=mesh.get_socket_location('head')-mesh.get_socket_location('pelvis')
                row['lean'].append(math.degrees(math.atan2(math.hypot(delta.x,delta.y),delta.z)))
                row['gait'].append(str(p.mesh.get_anim_instance().get_editor_property('Gait')))
        if now-cct_test['start']<75:return
        for p in cct_npcs:
            row=cct_tracks[p.get_actor_label()]
            cct_report['patrols'].append(dict(actor=p.get_actor_label(),travel_cm=row['distance'],areas=sorted(row['areas']),min_z=row['min_z'],max_z=row['max_z'],mean_lean=sum(row['lean'])/max(1,len(row['lean'])),gaits=sorted(set(row['gait'])),steps=p.footsteps.steps_played-row['steps_start']))
        assert all(r['travel_cm']>250 for r in cct_report['patrols']),'Resident failed to patrol'
        assert all(60<r['min_z'] and r['max_z']<230 for r in cct_report['patrols']),'Resident left floor'
        assert all(r['mean_lean']<24 and r['gaits'] and all('WALK' in g for g in r['gaits']) for r in cct_report['patrols']),'Bent or wrong walking gait'
        assert all(r['steps']>0 for r in cct_report['patrols']),'Missing footsteps'
        assert any(len(r['areas'])>1 for r in cct_report['patrols']),'No area changes'
        cct_finish()
    except Exception:cct_finish(traceback.format_exc())
    finally:cct_test['busy']=False
cct_test['handle']=u.register_slate_post_tick_callback(cct_tick)
print('CONTROL_ROOM_CROWD_OBSERVING',json.dumps(cct_report['routes']))
