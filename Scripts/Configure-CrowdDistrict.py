"""Shared Lyra/GASP guard and civilian pawns, connected tethers and tactical cover."""
import json
from pathlib import Path
import unreal as u

ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
lib=u.EditorAssetLibrary;tools=u.AssetToolsHelpers.get_asset_tools()
actors=u.get_editor_subsystem(u.EditorActorSubsystem);level=u.get_editor_subsystem(u.LevelEditorSubsystem)
world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world();assert world.get_name()=='L_TraversalGym'
existing={a.get_actor_label():a for a in actors.get_all_level_actors()}
folder='/Game/Crusader/AI'
parent=u.load_asset('/Game/Crusader/Characters/B_CRTraversalPawn').generated_class()
def save(obj):
    if isinstance(obj,u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(obj);assert not u.CRBlueprintTools.has_blueprint_errors(obj)
    assert lib.save_loaded_asset(obj,only_if_is_dirty=False)
classes={}
manager=u.load_asset('/Game/Blueprints/AC_VisualOverrideManager')
assert u.CRBlueprintTools.configure_crowd_visual_gate(manager);save(manager)
for role,weapon in [('GuardRifle','Rifle'),('GuardPistol','Pistol'),('GuardShotgun','Shotgun'),('Civilian',None)]:
    name='B_'+role
    if lib.does_asset_exist(folder+'/'+name):bp=u.load_asset(folder+'/'+name)
    else:
        factory=u.BlueprintFactory();factory.set_editor_property('parent_class',parent);bp=tools.create_asset(name,folder,u.Blueprint,factory)
    cdo=u.get_default_object(bp.generated_class());cdo.set_editor_property('auto_possess_ai',u.AutoPossessAI.PLACED_IN_WORLD_OR_SPAWNED);cdo.set_editor_property('ai_controller_class',u.CRCrowdController)
    cdo.physical_interaction.set_editor_property('auto_recover',True)
    extension=cdo.get_component_by_class(u.LyraPawnExtensionComponent)
    assert u.CRBlueprintTools.set_property_text(extension,'PawnData',"/Script/LyraGame.LyraPawnData'/Game/Crusader/System/PawnData_CRTraversal.PawnData_CRTraversal'")
    agent=cdo.crowd_agent;agent.set_editor_property('enabled',True);agent.set_editor_property('guard',bool(weapon))
    names=['ObsidianSentinel','RegalCommander','TheSteadfastOfficer'] if weapon else ['UrbanTrailblazer']
    agent.set_editor_property('visuals',[u.load_asset('/Game/Crusader/Characters/'+n+'/BP_'+n).generated_class() for n in names])
    agent.set_editor_property('patrol_speed',220.0 if weapon else 175.0)
    agent.set_editor_property('run_speed',680.0 if weapon else 700.0)
    agent.set_editor_property('combat_range',900.0 if weapon=='Shotgun' else 1450.0 if weapon=='Rifle' else 1150.0)
    path='/Game/Crusader/Weapons/BlackIronRifle/ID_BlackIronRifle' if weapon=='Rifle' else '/Game/Baseline/Weapons/'+str(weapon)+'/ID_'+str(weapon)
    agent.set_editor_property('weapons',[u.load_asset(path).generated_class()] if weapon else [])
    save(bp);classes[role]=bp.generated_class()
def fixture(cls,name,position,rotation=u.Rotator(),district=True):
    if district:position=(position[0]+4500,position[1],position[2])
    label='CR_Crowd_'+name
    actor=existing.get(label) or actors.spawn_actor_from_class(cls,u.Vector(*position),rotation)
    actor.set_actor_label(label);actor.set_actor_location(u.Vector(*position),False,True);actor.set_actor_rotation(rotation,False)
    actor.set_folder_path('Crusader/Crowd District');return actor
def sign(name,text,position,size=42,yaw=90):
    a=fixture(u.TextRenderActor,name,position,u.Rotator(yaw=yaw));a.text_render.set_text(text);a.text_render.set_world_size(size);a.text_render.set_horizontal_alignment(u.HorizTextAligment.EHTA_CENTER)
def mesh(name,path,position,scale=(1,1,1),yaw=0):
    a=fixture(u.StaticMeshActor,name,position,u.Rotator(yaw=yaw));a.static_mesh_component.set_static_mesh(u.load_asset(path));a.set_actor_scale3d(u.Vector(*scale));a.static_mesh_component.set_collision_profile_name('BlockAll');return a
floor=mesh('DistrictFloor','/Engine/BasicShapes/Cube',(7900,1600,-25),(83,76,.5))
floor.static_mesh_component.set_material(0,u.load_asset('/Game/Crusader/Effects/Range/M_RangeFloor'))
floor.static_mesh_component.set_phys_material_override(u.load_asset('/Game/Crusader/Effects/Surfaces/PM_Concrete'))
connector=mesh('Connector','/Engine/BasicShapes/Cube',(3350,-900,-25),(19,12,.5));connector.static_mesh_component.set_material(0,u.load_asset('/Game/Crusader/Effects/Range/M_RangeFloor'))
areas={}
for name,pos,radius in [('Commons',(6000,0,0),1100),('Market',(9600,0,0),1100),('Depot',(9800,3500,0),1200),('Refuge',(5700,3400,0),1000)]:
    a=fixture(u.CRCrowdArea,name,pos);a.set_editor_property('radius',float(radius));a.set_editor_property('wander_chance',.28)
    a.bounds.set_sphere_radius(float(radius),True);areas[name]=a
    sign(name+'Sign',name.upper()+' / CROWD AREA',(pos[0],pos[1]-1250,230),45)
for name,others in {'Commons':['Market','Refuge'],'Market':['Commons','Depot'],'Depot':['Market','Refuge'],'Refuge':['Commons','Depot']}.items():
    # Preserve connections to separately authored extensions such as the facility.
    extensions=[a for a in areas[name].neighbours if a and a not in areas.values()]
    areas[name].set_editor_property('neighbours',[areas[o] for o in others]+extensions)
models={r['name']:r['asset'] for r in json.loads((ROOT/'resources/EnvironmentModels.json').read_text())}
for name,model,pos,yaw in [
 ('CommonsCrate1','IndustrialCargoCrate01',(6500,450,0),20),('CommonsCrate2','IndustrialStorageCrate',(5400,700,0),0),
 ('MarketDesk','VintageMilitaryDesk',(9950,400,0),180),('MarketConsole','Hero',(9000,650,0),0),
 ('DepotCover1','IndustrialCargoCrate02',(10200,2900,0),0),('DepotCover2','IndustrialCargoCrate01',(9450,3000,0),30),
 ('DepotCover3','IndustrialCargoCrate01',(10500,3800,0),0),('DepotCover4','IndustrialCargoCrate02',(9000,3900,0),15),
 ('RefugeShelf','IndustrialMetalBookshelf',(6000,4000,0),0),('RefugePillar','ObsidianPillar',(5300,2850,0),0),
 ('DistrictGate','IndustrialStargate',(4250,-900,0),90)]:
    mesh(name,models[model],pos,yaw=yaw)
spawns=[]
layout=[('GuardRifle','Commons',(6250,-300,94)),('GuardPistol','Market',(9300,-350,94)),('GuardShotgun','Depot',(9900,3300,94)),
        ('GuardRifle','Depot',(9400,3650,94)),('GuardPistol','Refuge',(5800,3700,94)),('GuardShotgun','Market',(10000,-100,94)),
        ('Civilian','Commons',(5600,-350,94)),('Civilian','Commons',(6100,400,94)),('Civilian','Market',(9300,450,94)),
        ('Civilian','Market',(10000,650,94)),('Civilian','Refuge',(5500,3500,94)),('Civilian','Refuge',(6200,3200,94))]
for i,(role,area,pos) in enumerate(layout):
    a=fixture(classes[role],role+'_'+str(i+1),pos,u.Rotator(yaw=(i*71)%360));a.crowd_agent.set_editor_property('home_area',areas[area])
    spawns.append(dict(actor=a.get_actor_label(),role=role,area=area,position=[pos[0]+4500,pos[1],pos[2]]))
sign('Entrance','CROWD DISTRICT\nArmed guards / unarmed civilians\nGunfire provokes guards and makes civilians flee',(4150,-1400,260),35)
nav=fixture(u.NavMeshBoundsVolume,'Navigation',(5300,1400,450));nav.set_actor_scale3d(u.Vector(80,45,8))
# Endpoints are floor contacts, matching the player's measured traversal routes.
links=[]
for name,action,start,end,both in [
 ('Hurdle','Vault',(2730,-800,0),(3020,-800,0),True),
 ('Mantle','Climb',(4300,-970,0),(4300,-800,100),False),
 ('Climb','Climb',(2700,-1770,0),(2700,-1590,250),False),
 ('Vault','Vault',(4810,-800,350),(5350,-800,0),False)]:
    link=fixture(u.CRCrowdTraversalLink,'Route_'+name,start,district=False)
    link.set_editor_property('action',action);link.set_editor_property('bidirectional',both)
    link.set_editor_property('start',u.Vector());link.set_editor_property('end',u.Vector(*[b-a for a,b in zip(start,end)]))
    link.rerun_construction_scripts() if hasattr(link,'rerun_construction_scripts') else None
    links.append(dict(name=name,action=action,start=start,end=end,bidirectional=both))
print('NAV_BOUNDS',nav.get_actor_bounds(False))
navsys=u.NavigationSystemV1.get_navigation_system(world)
if navsys:navsys.on_navigation_bounds_updated(nav)
u.SystemLibrary.execute_console_command(world,'RebuildNavigation')
assert level.save_current_level()
(ROOT/'resources/CrowdDistrict.json').write_text(json.dumps(dict(map='/Game/Maps/L_TraversalGym',areas={n:dict(position=[a.get_actor_location().x,a.get_actor_location().y,a.get_actor_location().z],radius=a.radius,neighbours=[x.get_actor_label() for x in a.neighbours]) for n,a in areas.items()},spawns=spawns,traversal_links=links),indent=2))
print('CROWD_DISTRICT_CONFIGURED',len(spawns),'NPCs',len(areas),'linked areas')
