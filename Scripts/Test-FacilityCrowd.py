"""Observe real facility patrols, room circulation, loadouts and district routes."""
import json, math, time, traceback
from pathlib import Path
import unreal as u

fct_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
fct_world=u.EditorLevelLibrary.get_pie_worlds(False)[0]
fct_npcs=[a for a in u.GameplayStatics.get_all_actors_of_class(fct_world,u.CRTraversalCharacter) if a.get_actor_label().startswith('CR_FacilityCrowd_')]
assert len(fct_npcs)==6 and all(p.crowd_agent.initialized for p in fct_npcs)
fct_report=dict(passed=False,loadouts=[],routes=[],patrols=[])
fct_areas=[a for a in u.GameplayStatics.get_all_actors_of_class(fct_world,u.CRCrowdArea) if a.get_actor_label().startswith('CR_FacilityCrowd_')]
for area in fct_areas:
    for neighbour in area.neighbours:
        path=u.NavigationSystemV1.find_path_to_location_synchronously(fct_world,area.get_actor_location(),neighbour.get_actor_location())
        fct_report['routes'].append(dict(start=area.get_actor_label(),end=neighbour.get_actor_label(),complete=bool(path and path.is_valid() and not path.is_partial()),reciprocal=area in neighbour.neighbours))
for p in fct_npcs:
    item=p.baseline_equipment.get_active_item()
    weapon=p.equipment_manager.get_first_instance_of_type(u.BaselineWeaponInstance)
    fct_report['loadouts'].append(dict(actor=p.get_actor_label(),guard=p.crowd_agent.guard,armed=bool(item),weapon=weapon.effects_profile.get_name() if weapon else None,visual=p.crowd_agent.selected_visual.get_name()))
assert all(r['complete'] and r['reciprocal'] for r in fct_report['routes'])
assert all(r['guard']==r['armed'] for r in fct_report['loadouts'])
assert len({r['weapon'] for r in fct_report['loadouts'] if r['guard']})==3

def fct_room(pos):
    if pos.y<6600:return 'Outside'
    if pos.x<12300 and pos.y<7800:return 'Checkpoint'
    if pos.x>13200 and pos.y>8400:return 'Office'
    if pos.y>7900:return 'Laboratory'
    return 'Hall'

fct_tracks={p.get_actor_label():dict(last=p.get_actor_location(),distance=0.,rooms=set(),areas=set(),min_z=99999.,max_z=-99999.) for p in fct_npcs}
fct_test=dict(start=u.GameplayStatics.get_time_seconds(fct_world),next=0,busy=False,deadline=time.monotonic()+150)

def fct_finish(error=None):
    u.unregister_slate_post_tick_callback(fct_test['handle'])
    fct_test.update(finished=True,error=error)
    fct_report['error']=error;fct_report['passed']=error is None
    (fct_root/'Artifacts/FacilityMockup/crowd-validation.json').write_text(json.dumps(fct_report,indent=2)+'\n')
    print('FACILITY_CROWD_VALIDATION',json.dumps(fct_report))

def fct_tick(dt):
    if fct_test['busy']:return
    fct_test['busy']=True
    try:
        assert time.monotonic()<fct_test['deadline'],'Facility patrol observation timed out'
        now=u.GameplayStatics.get_time_seconds(fct_world)
        if now<fct_test['next']:return
        fct_test['next']=now+.25
        for p in fct_npcs:
            data=fct_tracks[p.get_actor_label()];pos=p.get_actor_location()
            data['distance']+=math.hypot(pos.x-data['last'].x,pos.y-data['last'].y)
            data['last']=pos;data['rooms'].add(fct_room(pos))
            data['areas'].add(p.crowd_agent.current_area.get_actor_label())
            data['min_z']=min(data['min_z'],pos.z);data['max_z']=max(data['max_z'],pos.z)
            assert p.crowd_agent.state in (u.CRCrowdState.IDLE,u.CRCrowdState.PATROL),(p.get_actor_label(),p.crowd_agent.state)
        if now-fct_test['start']<75:return
        for p in fct_npcs:
            data=fct_tracks[p.get_actor_label()]
            fct_report['patrols'].append(dict(actor=p.get_actor_label(),guard=p.crowd_agent.guard,travel_cm=round(data['distance'],1),rooms=sorted(data['rooms']),areas=sorted(data['areas']),area_visits=p.crowd_agent.area_visits,min_z=round(data['min_z'],1),max_z=round(data['max_z'],1)))
        fct_report['observed_seconds']=round(now-fct_test['start'],1)
        assert all(r['travel_cm']>250 for r in fct_report['patrols']), 'An NPC failed to patrol'
        assert all(60<r['min_z'] and r['max_z']<220 for r in fct_report['patrols']), 'An NPC left the walkable floor'
        for guard in [True,False]:
            assert any(r['guard']==guard and len(r['rooms'])>1 for r in fct_report['patrols']), 'Role did not circulate between rooms'
        fct_finish()
    except Exception:fct_finish(traceback.format_exc())
    finally:fct_test['busy']=False

fct_test['handle']=u.register_slate_post_tick_callback(fct_tick)
print('FACILITY_PATROLS_OBSERVING',len(fct_npcs),'NPCs',len(fct_report['routes']),'verified area connections')
