"""Place every new human visual and connect the station to district patrols."""
import json
from pathlib import Path
import unreal as u

cc_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
cc_actors=u.get_editor_subsystem(u.EditorActorSubsystem)
cc_existing={a.get_actor_label():a for a in cc_actors.get_all_level_actors()}
assert 'CR_ControlRoom_MainEntrance' in cc_existing
cc_origin=u.Vector(20600,7900,30)
cc_prefix='CR_ControlCrowd_'

def cc_actor(cls,name,pos,section,yaw=0):
    label=cc_prefix+name
    a=cc_existing.get(label) or cc_actors.spawn_actor_from_class(cls,cc_origin+u.Vector(*pos),u.Rotator(yaw=yaw))
    a.set_actor_label(label);a.set_actor_location(cc_origin+u.Vector(*pos),False,True)
    a.set_actor_rotation(u.Rotator(yaw=yaw),False);a.set_folder_path('Crusader/Control Room/Crowd/'+section)
    a.tags=['CrusaderControlRoomCrowd'];return a

cc_areas={}
for name,pos,radius in [('SouthWalk',(-3000,-3150,0),300),('WestWalk',(-4300,150,0),250),
                       ('Entrance',(0,-2450,0),140),('Lobby',(0,-1720,0),260),
                       ('Hall',(0,-500,0),650),('Operations',(0,650,0),650),
                       ('Command',(0,1370,0),170),('Service',(-2480,0,0),280),('Storage',(2490,0,0),260)]:
    area=cc_actor(u.CRCrowdArea,'Area_'+name,pos,'Areas')
    area.set_editor_property('radius',float(radius));area.bounds.set_sphere_radius(float(radius),True)
    area.set_editor_property('wander_chance',.65)
    area.set_editor_property('allow_guards',True);area.set_editor_property('allow_civilians',True)
    cc_areas[name]=area
for name,neighbours in {'SouthWalk':['Entrance','WestWalk'],'WestWalk':['SouthWalk','Service'],
                       'Entrance':['SouthWalk','Lobby'],'Lobby':['Entrance','Hall'],
                       'Hall':['Lobby','Operations','Service','Storage'],
                       'Operations':['Hall','Command','Service','Storage'],'Command':['Operations'],
                       'Service':['WestWalk','Hall','Operations'],'Storage':['Hall','Operations']}.items():
    cc_areas[name].set_editor_property('neighbours',[cc_areas[n] for n in neighbours])
depot=cc_existing['CR_Crowd_Depot']
for name in ['SouthWalk','WestWalk']:
    neighbours=list(depot.neighbours)
    if cc_areas[name] not in neighbours:neighbours.append(cc_areas[name])
    depot.set_editor_property('neighbours',neighbours)
    cc_areas[name].set_editor_property('neighbours',list(cc_areas[name].neighbours)+[depot])

cc_spawns=[]
for name,role,home,pos,yaw in [
    ('ArmoredSentinel','GuardRifle','Lobby',(-180,-1660,94),90),
    ('AstronautSentinel','GuardPistol','Service',(-2450,-80,94),0),
    ('CrimsonVanguard','GuardShotgun','Command',(-350,1280,94),180),
    ('MaintenanceWorker','Civilian','Service',(-2310,130,94),-90),
    ('RuggedMiner','Civilian','Storage',(2480,170,94),180),
    ('RustboundExplorer','Civilian','Hall',(-620,-560,94),90),
    ('CrimsonAuthority','Civilian','Command',(350,1290,94),180),
    ('CrusaderOperative','Civilian','Operations',(-700,550,94),0),
    ('GraySentinel','Civilian','Hall',(550,-610,94),-90),
    ('RuggedSurvivor','Civilian','Operations',(730,610,94),180)]:
    bp=u.load_asset('/Game/Crusader/AI/B_'+role)
    visual=u.load_asset('/Game/Crusader/Characters/'+name+'/BP_'+name)
    assert bp and visual and not u.CRBlueprintTools.has_blueprint_errors(visual),name
    pawn=cc_actor(bp.generated_class(),name,pos,'Residents',yaw)
    pawn.crowd_agent.set_editor_property('home_area',cc_areas[home])
    # A single selected entry guarantees every newly imported character is present.
    pawn.crowd_agent.set_editor_property('visuals',[visual.generated_class()])
    cc_spawns.append(dict(actor=pawn.get_actor_label(),visual=name,role=role,home=home,
                          position=[pawn.get_actor_location().x,pawn.get_actor_location().y,pawn.get_actor_location().z]))
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
manifest=dict(map='/Game/Maps/L_TraversalGym',areas={n:dict(position=[a.get_actor_location().x,a.get_actor_location().y,a.get_actor_location().z],radius=a.radius,neighbours=[v.get_actor_label() for v in a.neighbours]) for n,a in cc_areas.items()},spawns=cc_spawns,district_connections=['Depot'])
(cc_root/'resources/ControlRoomCrowd.json').write_text(json.dumps(manifest,indent=2)+'\n')
path=cc_root/'resources/CrowdDistrict.json';district=json.loads(path.read_text())
district['areas']['Depot']['neighbours']=[a.get_actor_label() for a in depot.neighbours]
path.write_text(json.dumps(district,indent=2)+'\n')
names={r['visual'] for r in cc_spawns}
for rel in ['resources/NPCAdditions.json','mockups/AssetSources.json']:
    path=cc_root/rel;rows=json.loads(path.read_text())
    for row in rows:
        if row.get('name') in names:
            row['imported']=True;row['asset']='/Game/Crusader/Characters/'+row['name']+'/'+row['name']
    path.write_text(json.dumps(rows,indent=2)+'\n')
print('CONTROL_ROOM_CROWD_CONFIGURED',len(cc_spawns),'unique new NPCs',len(cc_areas),'connected areas')
