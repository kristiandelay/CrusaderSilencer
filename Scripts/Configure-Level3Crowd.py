"""Connect the three-storey facility to existing patrols and populate each floor."""
import json
from pathlib import Path
import unreal as u

lc_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
lc_editor=u.get_editor_subsystem(u.EditorActorSubsystem)
lc_existing={a.get_actor_label():a for a in lc_editor.get_all_level_actors()}
assert 'CR_Level3_L3_Floor_0_0' in lc_existing
lc_origin=u.Vector(33000,7900,30);lc_prefix='CR_Level3Crowd_'
lc_areas={};lc_spawns=[]

def lc_actor(cls,name,pos,section):
    label=lc_prefix+name
    a=lc_existing.get(label) or lc_editor.spawn_actor_from_class(cls,lc_origin+u.Vector(*pos))
    a.set_actor_label(label);a.set_actor_location(lc_origin+u.Vector(*pos),False,True)
    a.set_folder_path('Crusader/Three Storey Facility/Crowd/'+section)
    a.tags=['CrusaderLevel3Crowd'];return a

lc_specs=[('Promenade',(-6200,-3150,0),260),('Entrance',(0,-3050,0),220)]
for i in range(3):
    z=720*i;p=f'L{i+1}'
    lc_specs += [(p+'Hall',(0,-500,z),450),(p+'West',(-2230,0,z),280),
                 (p+'East',(2400,0,z),270),(p+'Command',(0,650,z),230),
                 (p+'StairLobby',(4000,-1750,z),130)]
    if i<2:lc_specs.append((p+'StairTurn',(4300,1260,z+360),100))
for name,pos,radius in lc_specs:
    a=lc_actor(u.CRCrowdArea,'Area_'+name,pos,'Areas')
    a.set_editor_property('radius',float(radius));a.bounds.set_sphere_radius(float(radius),True)
    a.set_editor_property('wander_chance',.6)
    a.set_editor_property('allow_guards',True);a.set_editor_property('allow_civilians',True)
    lc_areas[name]=a
lc_links={n:set() for n in lc_areas}
def lc_link(a,b):lc_links[a].add(b);lc_links[b].add(a)
lc_link('Promenade','Entrance');lc_link('Entrance','L1Hall')
for i in range(3):
    p=f'L{i+1}'
    for suffix in ['West','East','Command','StairLobby']:lc_link(p+'Hall',p+suffix)
    if i<2:
        lc_link(p+'StairLobby',p+'StairTurn');lc_link(p+'StairTurn',f'L{i+2}StairLobby')
for name,neighbours in lc_links.items():lc_areas[name].set_editor_property('neighbours',[lc_areas[n] for n in sorted(neighbours)])
outside=lc_existing['CR_ControlCrowd_Area_SouthWalk']
lc_areas['Promenade'].set_editor_property('neighbours',list(lc_areas['Promenade'].neighbours)+[outside])
previous=list(outside.neighbours)
if lc_areas['Promenade'] not in previous:outside.set_editor_property('neighbours',previous+[lc_areas['Promenade']])

for level,guard,civs in [(1,('ArmoredSentinel','GuardRifle'),['MaintenanceWorker','RuggedMiner']),
                        (2,('AstronautSentinel','GuardPistol'),['CrusaderOperative','GraySentinel']),
                        (3,('CrimsonVanguard','GuardShotgun'),['CrimsonAuthority','RuggedSurvivor'])]:
    for i,(name,role,home,pos) in enumerate([(guard[0],guard[1],f'L{level}Hall',(-350,-500,720*(level-1)+94)),
                                            (civs[0],'Civilian',f'L{level}West',(-2200,0,720*(level-1)+94)),
                                            (civs[1],'Civilian',f'L{level}East',(2250,0,720*(level-1)+94))]):
        bp=u.load_asset('/Game/Crusader/AI/B_'+role)
        visual=u.load_asset('/Game/Crusader/Characters/'+name+'/BP_'+name)
        assert bp and visual
        a=lc_actor(bp.generated_class(),f'L{level}_{name}',pos,'Residents')
        a.crowd_agent.set_editor_property('home_area',lc_areas[home])
        a.crowd_agent.set_editor_property('visuals',[visual.generated_class()])
        lc_spawns.append(dict(actor=a.get_actor_label(),visual=name,role=role,level=level,home=home))
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
manifest=dict(map='/Game/Maps/L_TraversalGym',spawns=lc_spawns,areas={n:dict(position=[a.get_actor_location().x,a.get_actor_location().y,a.get_actor_location().z],radius=a.radius,neighbours=[v.get_actor_label() for v in a.neighbours]) for n,a in lc_areas.items()})
(lc_root/'resources/Level3Crowd.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('LEVEL3_CROWD_CONFIGURED',len(lc_spawns),'residents',len(lc_areas),'areas')
