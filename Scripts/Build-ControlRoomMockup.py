"""Roomy, fully roofed Level2 control station in the traversal map."""
import json, math
from pathlib import Path
import unreal as u

cr_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
cr_actors=u.get_editor_subsystem(u.EditorActorSubsystem)
cr_world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
assert cr_world.get_name()=='L_TraversalGym'
cr_origin=u.Vector(20600,7900,30)
cr_prefix='CR_ControlRoom_'
cr_existing={a.get_actor_label():a for a in cr_actors.get_all_level_actors() if a.get_actor_label().startswith(cr_prefix)}
cr_catalog={r['name']:r for r in json.loads((cr_root/'resources/EnvironmentModels.json').read_text()) if r['category']=='Level2'}
cr_meshes={n:u.load_asset(r['asset']) for n,r in cr_catalog.items()}
cr_used=set();cr_records=[]

def cr_actor(cls,name,section):
    label=cr_prefix+name
    a=cr_existing.get(label) or cr_actors.spawn_actor_from_class(cls,u.Vector())
    assert isinstance(a,cls),label
    a.set_actor_label(label);a.set_folder_path('Crusader/Control Room/'+section)
    a.tags=['CrusaderControlRoom',section];cr_used.add(label)
    return a

def cr_mesh(name,model,center,size=None,rotation=None,scale=1.,section='Equipment',collision=True):
    mesh=cr_meshes[model];box=mesh.get_bounding_box();extent=box.max-box.min
    factor=u.Vector(*(size[i]/[extent.x,extent.y,extent.z][i] for i in range(3))) if size else u.Vector(scale,scale,scale)
    rot=rotation or u.Rotator()
    offset=u.MathLibrary.transform_location(u.Transform(rotation=rot,scale=factor),(box.min+box.max)*.5)
    a=cr_actor(u.StaticMeshActor,name,section);c=a.static_mesh_component
    c.set_static_mesh(mesh);c.set_mobility(u.ComponentMobility.STATIC)
    a.set_actor_transform(u.Transform(location=cr_origin+u.Vector(*center)-offset,rotation=rot,scale=factor),False,True)
    c.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
    cr_records.append(dict(actor=a.get_actor_label(),model=model,section=section,center=list(center),collision=collision))
    return a

def cr_prop(name,model,x,y,z=0,yaw=0,scale=1.,section='Equipment'):
    box=cr_meshes[model].get_bounding_box()
    return cr_mesh(name,model,(x,y,z+(box.max.z-box.min.z)*scale/2),rotation=u.Rotator(yaw=yaw+180),scale=scale,section=section)

def cr_wall(name,axis,fixed,start,end,yaw=0,bottom=0,top=660):
    count=math.ceil((end-start)/300);width=(end-start)/count
    levels=[(bottom,330),(330,top)] if bottom<330<top else [(bottom,top)]
    for tier,(low,high) in enumerate(levels):
        for i in range(count):
            along=start+(i+.5)*width
            center=(along,fixed,(low+high)/2) if axis=='x' else (fixed,along,(low+high)/2)
            model='BlueSlateShowcase' if low>=330 else ['IndustrialWallPanel','IndustrialVentWall','IndustrialWallPanel','TriangularBastion'][i%4]
            cr_mesh(f'{name}_{tier}_{i}',model,center,(width+3,42,high-low+2),u.Rotator(yaw=yaw+180),section='Walls')

def cr_light(name,x,y,power=6800,temp=4400,z=615,radius=1900):
    a=cr_actor(u.RectLight,name,'Lighting');a.set_actor_location(cr_origin+u.Vector(x,y,z),False,True)
    a.set_actor_rotation(u.Rotator(pitch=-90),False)
    c=a.get_component_by_class(u.RectLightComponent);c.set_mobility(u.ComponentMobility.MOVABLE)
    c.set_editor_property('intensity_units',u.LightUnits.LUMENS);c.set_intensity(float(power))
    c.set_editor_property('attenuation_radius',float(radius));c.set_editor_property('source_width',180.)
    c.set_editor_property('source_height',70.);c.set_editor_property('use_temperature',True)
    c.set_editor_property('temperature',float(temp));c.set_editor_property('cast_shadows',True)

# Cross-shaped shell: 42x30m hall, command alcove, lobby, service and storage bays.
cr_rects={'Hall':(-2100,2100,-1500,1500),'Command':(-900,900,1500,2100),
          'Lobby':(-900,900,-2100,-1500),'Service':(-3000,-2100,-600,600),
          'Storage':(2100,3000,-900,900)}
cr_cells=[]
for room,(x0,x1,y0,y1) in cr_rects.items():
    # The decorative four-quadrant slabs have a small opening at their centre.
    # Continuous kit-panel backing closes those openings for bullets and light.
    cr_mesh('FloorBacking_'+room,'BlueSlateShowcase',((x0+x1)/2,(y0+y1)/2,-20),
            (x1-x0+8,14,y1-y0+8),u.Rotator(roll=90),section='Floor')
    cr_mesh('RoofBacking_'+room,'BlueSlateShowcase',((x0+x1)/2,(y0+y1)/2,688),
            (x1-x0+8,14,y1-y0+8),u.Rotator(roll=90),section='Roof')
    for ix,x in enumerate(range(x0+150,x1,300)):
        for iy,y in enumerate(range(y0+150,y1,300)):
            cr_mesh(f'Floor_{room}_{ix}_{iy}','MidnightCircuitSlab',(x,y,-9),(303,303,18),section='Floor')
            cr_mesh(f'Roof_{room}_{ix}_{iy}','MidnightCircuitSlab',(x,y,672),(310,310,24),u.Rotator(roll=180),section='Roof')
            cr_cells.append([x,y])

# Every boundary is enclosed except the generous main and service entrances.
for side,x,y0,y1,yaw in [('WestSouth',-2100,-1500,-600,90),('WestNorth',-2100,600,1500,90),
                        ('EastSouth',2100,-1500,-900,-90),('EastNorth',2100,900,1500,-90),
                        ('CommandWest',-900,1500,2100,90),('CommandEast',900,1500,2100,-90),
                        ('LobbyWest',-900,-2100,-1500,90),('LobbyEast',900,-2100,-1500,-90),
                        ('StorageEast',3000,-900,900,-90)]:
    cr_wall(side,'y',x,y0,y1,yaw)
for side,y,x0,x1,yaw in [('NorthWest',1500,-2100,-900,0),('NorthEast',1500,900,2100,0),
                        ('SouthWest',-1500,-2100,-900,180),('SouthEast',-1500,900,2100,180),
                        ('CommandRear',2100,-900,900,0),('StorageNorth',900,2100,3000,0),
                        ('StorageSouth',-900,2100,3000,180),('ServiceNorth',600,-3000,-2100,0),
                        ('ServiceSouth',-600,-3000,-2100,180),('EntryLeft',-2100,-900,-400,180),
                        ('EntryRight',-2100,400,900,180)]:
    cr_wall(side,'x',y,x0,x1,yaw)
cr_wall('EntryHeader','x',-2100,-400,400,180,bottom=510)
cr_mesh('MainEntrance','WallG',(0,-2100,255),(800,75,510),section='Entrances')
cr_wall('ServiceEntrySouth','y',-3000,-600,-400,90)
cr_wall('ServiceEntryNorth','y',-3000,400,600,90)
cr_wall('ServiceEntryHeader','y',-3000,-400,400,90,bottom=510)
cr_mesh('ServiceEntrance','WallG',(-3000,0,255),(800,75,510),u.Rotator(yaw=90),section='Entrances')

# Partial divisions mark rooms without constricting their routes or sightlines.
for name,x,y0,y1,yaw in [('StorageDividerSouth',2100,-900,-600,-90),('StorageDividerNorth',2100,600,900,-90)]:
    cr_wall(name,'y',x,y0,y1,yaw)
cr_wall('StorageHeader','y',2100,-600,600,-90,bottom=540)
cr_wall('ServiceHeader','y',-2100,-600,600,90,bottom=540)

# Reference focal point: U-shaped console looking out over the central hall.
cr_prop('MainCommandConsole','CommandNexus',0,1690,scale=.78,section='Command')
for i,x in enumerate([-630,630]):
    cr_prop('CommandTerminal_'+str(i),'RetroCyberConsole',x,1830,scale=1.,section='Command')
    cr_prop('CommandVent_'+str(i),'BronzeVentilationPanel',x,2070,z=335,scale=.9,section='Command')
cr_prop('CommandRearDisplay','WallCControlPanel',0,2070,z=335,scale=.9,section='Command')
for i,x in enumerate([-1650,1650]):
    cr_prop('OperationsConsole_'+str(i),'CommandNexus',x,825,yaw=90 if x<0 else -90,scale=.72,section='Operations')
    cr_prop('OperationsTerminal_'+str(i),'RetroServerTerminal',x,1280,yaw=0,section='Operations')
    cr_prop('OperationsCrate_'+str(i),'BlueSteelVault',x,150,scale=.8,section='Operations')
for i,y in enumerate([-850,-430]):
    cr_prop('EastWallComputer_'+str(i),'WallCControlPanel',2050,y,yaw=-90,scale=.85,section='Operations')
for i,x in enumerate([-900,900]):
    cr_prop('HallConsole_'+str(i),'CommandNexus',x,-650,yaw=90 if x<0 else -90,scale=.72,section='Operations')
cr_prop('ServiceAirlock','IndustrialAirlockDoor',-2560,552,scale=.9,section='Service')
cr_prop('ServiceCorner','IronboundBastion',-2840,425,yaw=0,scale=1.0,section='Service')
for i,x in enumerate([-2690,-2490,-2290]):
    cr_prop('ServiceLocker_'+str(i),'BlackEquipmentCase',x,-530,scale=1.45,yaw=180,section='Service')
cr_prop('ServiceWorkstation','RetroCyberConsole',-2390,350,scale=.9,section='Service')
for i,(x,y) in enumerate([(2740,640),(2860,620),(2800,430)]):
    cr_prop('StorageBarrel_'+str(i),'RustyRadioactiveBarrel',x,y,scale=.9,section='Storage')
for i,(x,y) in enumerate([(2640,-655),(2810,-650),(2770,-480)]):
    cr_prop('StorageCrate_'+str(i),'IndustrialCargoCrate' if i%2==0 else 'BlueSteelVault',x,y,scale=.9,section='Storage')
for i in range(4):cr_prop('StorageBattery_'+str(i),'OldBattery',2900,-100+i*85,section='Storage')
for i,x in enumerate([-670,670]):
    cr_prop('LobbyTerminal_'+str(i),'RetroCyberConsole',x,-1740,yaw=90 if x<0 else -90,scale=.85,section='Lobby')
    cr_prop('LobbySupply_'+str(i),'IndustrialCargoCrate',x,-1960,scale=.8,section='Lobby')
for i,x in enumerate([-1350,0,1350]):
    for j,y in enumerate([-900,300,1200]):cr_light(f'HallLight_{i}_{j}',x,y)
for name,x,y in [('Command',0,1770),('Lobby',0,-1770),('Storage',2580,0),('Service',-2530,0)]:
    cr_light(name+'Light',x,y,5200,4900 if name=='Command' else 4100,radius=1300)
for i,x in enumerate([-1100,1100]):
    cr_light('CeilingBounce_'+str(i),x,0,1900,4600,z=380,radius=2300)
    cr_existing_light=next(a for a in cr_actors.get_all_level_actors() if a.get_actor_label()==cr_prefix+'CeilingBounce_'+str(i))
    cr_existing_light.set_actor_rotation(u.Rotator(pitch=90),False)

# Broad raised walkways connect both entrances to the existing crowd floor.
cr_approach_cells=set()
for x in range(-5850,151,300):
    for y in [-3450,-3150,-2850]:cr_approach_cells.add((x,y))
for x in [-150,150,450]:
    for y in [-2550,-2250]:cr_approach_cells.add((x,y))
for x in range(-5850,-3000,300):
    for y in [-150,150,450]:cr_approach_cells.add((x,y))
for x in [-5850,-5550,-5250]:
    for y in range(-2550,-150,300):cr_approach_cells.add((x,y))
for i,(x,y) in enumerate(sorted(cr_approach_cells)):
    cr_mesh('Approach_'+str(i),'RuneChocolateBar',(x,y,-15),(304,304,30),section='Approach')
for i,(x,y) in enumerate([(-4500,-3150),(-3000,-3150),(-1500,-3150),(-4200,150)]):
    cr_light('ApproachLight_'+str(i),x,y,3500,4300,z=650,radius=1600)

nav=cr_actor(u.NavMeshBoundsVolume,'Navigation','Navigation')
nav.set_actor_location(cr_origin+u.Vector(-1400,-900,350),False,True)
nav.set_actor_scale3d(u.Vector(51,36,6))
navsys=u.NavigationSystemV1.get_navigation_system(cr_world)
if navsys:navsys.on_navigation_bounds_updated(nav)
u.SystemLibrary.execute_console_command(cr_world,'RebuildNavigation')
for label,a in cr_existing.items():
    if label not in cr_used:cr_actors.destroy_actor(a)
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
manifest=dict(map='/Game/Maps/L_TraversalGym',origin=[20600,7900,30],footprint_cm=[6000,4200],wall_height_cm=660,roof_underside_cm=660,main_door_width_cm=800,door_height_cm=510,rooms=cr_rects,roof_samples=cr_cells,mesh_actors=cr_records,actor_count=len(cr_used),entrance=[20600,5800,130],district_connection=[14750,4750,30])
(cr_root/'resources/ControlRoomMockup.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('CONTROL_ROOM_BUILT',len(cr_used),'actors',len(cr_records),'Level2 mesh instances')
if (cr_root/'resources/BuildingDestruction.json').exists():
    exec(compile((cr_root/'Scripts/Build-BuildingDestruction.py').read_text(),'Build-BuildingDestruction.py','exec'),globals())
