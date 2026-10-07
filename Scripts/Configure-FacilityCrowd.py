"""Populate the roofed facility and join its room tethers to the crowd district."""
import json
from pathlib import Path
import unreal as u

fcw_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False), 'Stop PIE before authoring'
fcw_actors=u.get_editor_subsystem(u.EditorActorSubsystem)
fcw_world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
assert fcw_world.get_name()=='L_TraversalGym'
fcw_existing={a.get_actor_label():a for a in fcw_actors.get_all_level_actors()}
assert 'CR_Facility_EntryFrame' in fcw_existing, 'Build the facility first'
fcw_prefix='CR_FacilityCrowd_'

def fcw_actor(cls,name,position,section,yaw=0):
    label=fcw_prefix+name
    actor=fcw_existing.get(label) or fcw_actors.spawn_actor_from_class(cls,u.Vector(*position),u.Rotator(yaw=yaw))
    actor.set_actor_label(label)
    actor.set_actor_location(u.Vector(*position),False,True)
    actor.set_actor_rotation(u.Rotator(yaw=yaw),False)
    actor.set_folder_path('Crusader/Facility Mockup/Crowd/'+section)
    actor.tags=['CrusaderFacilityCrowd']
    return actor

# Keep sampling circles inside the open circulation spaces. Navigation rejects
# furniture and walls; the office uses a smaller tether in front of the desk.
fcw_areas={}
for name,pos,radius,chance in [
    ('Approach',(11400,6060,30),230,.65),
    ('Checkpoint',(11400,7200,30),420,.55),
    ('Laboratory',(11490,8530,30),340,.55),
    ('Hall',(12950,7550,30),440,.55),
    ('Office',(13750,8720,30),240,.65)]:
    area=fcw_actor(u.CRCrowdArea,'Area_'+name,pos,'Areas')
    area.set_editor_property('radius',float(radius));area.bounds.set_sphere_radius(float(radius),True)
    area.set_editor_property('wander_chance',chance)
    area.set_editor_property('allow_guards',True);area.set_editor_property('allow_civilians',True)
    fcw_areas[name]=area

for name,neighbours in {
    'Approach':['Checkpoint'],
    'Checkpoint':['Approach','Laboratory','Hall'],
    'Laboratory':['Checkpoint','Hall'],
    'Hall':['Checkpoint','Laboratory','Office'],
    'Office':['Hall']}.items():
    fcw_areas[name].set_editor_property('neighbours',[fcw_areas[n] for n in neighbours])

# Bidirectional links preserve the district's existing patrol connections.
for district_name in ['Refuge','Depot']:
    district=fcw_existing['CR_Crowd_'+district_name]
    district_neighbours=list(district.neighbours)
    if fcw_areas['Approach'] not in district_neighbours:district_neighbours.append(fcw_areas['Approach'])
    district.set_editor_property('neighbours',district_neighbours)
    fcw_areas['Approach'].set_editor_property('neighbours',list(fcw_areas['Approach'].neighbours)+[district])

fcw_spawns=[]
for index,(role,home,pos,yaw) in enumerate([
    ('GuardRifle','Checkpoint',(11500,7190,120),90),
    ('GuardPistol','Office',(13860,8630,120),180),
    ('GuardShotgun','Laboratory',(11400,8600,120),0),
    ('Civilian','Laboratory',(11580,8270,120),90),
    ('Civilian','Office',(13570,8810,120),-90),
    ('Civilian','Hall',(13030,7650,120),180)]):
    cls=u.load_asset('/Game/Crusader/AI/B_'+role).generated_class()
    pawn=fcw_actor(cls,role+'_'+str(index+1),pos,'Residents',yaw)
    pawn.crowd_agent.set_editor_property('home_area',fcw_areas[home])
    fcw_spawns.append(dict(actor=pawn.get_actor_label(),role=role,home=home,position=list(pos)))

assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
fcw_manifest=dict(map='/Game/Maps/L_TraversalGym',areas={n:dict(position=[a.get_actor_location().x,a.get_actor_location().y,a.get_actor_location().z],radius=a.radius,wander_chance=a.wander_chance,neighbours=[v.get_actor_label() for v in a.neighbours]) for n,a in fcw_areas.items()},district_connections=['Refuge','Depot'],spawns=fcw_spawns)
(fcw_root/'resources/FacilityCrowd.json').write_text(json.dumps(fcw_manifest,indent=2)+'\n')
district_path=fcw_root/'resources/CrowdDistrict.json'
district_manifest=json.loads(district_path.read_text())
for name in ['Refuge','Depot']:
    district_manifest['areas'][name]['neighbours']=[a.get_actor_label() for a in fcw_existing['CR_Crowd_'+name].neighbours]
district_path.write_text(json.dumps(district_manifest,indent=2)+'\n')
print('FACILITY_CROWD_CONFIGURED',len(fcw_spawns),'NPCs',len(fcw_areas),'linked areas')
