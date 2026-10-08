"""Roofed reference-inspired facility made entirely from the imported environment kit."""
import json, math
from pathlib import Path
import unreal as u

FM_ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False), 'Stop PIE before authoring'
fm_actors=u.get_editor_subsystem(u.EditorActorSubsystem)
fm_level=u.get_editor_subsystem(u.LevelEditorSubsystem)
fm_world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
assert fm_world.get_name()=='L_TraversalGym'
FM_ORIGIN=u.Vector(12600,8100,30)
FM_PREFIX='CR_Facility_'
fm_existing={a.get_actor_label():a for a in fm_actors.get_all_level_actors() if a.get_actor_label().startswith(FM_PREFIX)}
fm_catalog={r['name']:r for r in json.loads((FM_ROOT/'resources/EnvironmentModels.json').read_text())}
fm_meshes={n:u.load_asset(r['asset']) for n,r in fm_catalog.items()}
fm_used=set();fm_records=[]

def fm_actor(cls,name,section):
    label=FM_PREFIX+name
    a=fm_existing.get(label) or fm_actors.spawn_actor_from_class(cls,u.Vector())
    assert isinstance(a,cls),label
    a.set_actor_label(label);a.set_folder_path('Crusader/Facility Mockup/'+section)
    a.tags=['CrusaderFacilityMockup',section]
    fm_used.add(label)
    return a

def fm_mesh(name,model,center,size=None,rotation=None,scale=1.,section='Props',collision=True):
    mesh=fm_meshes[model];box=mesh.get_bounding_box();extent=box.max-box.min
    factor=u.Vector(*(size[i]/[extent.x,extent.y,extent.z][i] for i in range(3))) if size else u.Vector(scale,scale,scale)
    rot=rotation or u.Rotator()
    # Imported pivots are on the floor; align the actual rotated bounds, including
    # horizontal roof panels, without moving or editing the source mesh assets.
    offset=u.MathLibrary.transform_location(u.Transform(rotation=rot,scale=factor),(box.min+box.max)*.5)
    position=FM_ORIGIN+u.Vector(*center)-offset
    a=fm_actor(u.StaticMeshActor,name,section);c=a.static_mesh_component
    c.set_static_mesh(mesh);c.set_mobility(u.ComponentMobility.STATIC)
    a.set_actor_transform(u.Transform(location=position,rotation=rot,scale=factor),False,True)
    c.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
    c.set_editor_property('cast_shadow',True)
    fm_records.append(dict(actor=a.get_actor_label(),model=model,section=section,center=[center[0],center[1],center[2]],collision=collision))
    return a

def fm_prop(name,model,x,y,z=0,yaw=0,scale=1.,section='Props',collision=True):
    b=fm_meshes[model].get_bounding_box()
    # FBX's handedness conversion makes the kit's front face +Y in Unreal.
    return fm_mesh(name,model,(x,y,z+(b.max.z-b.min.z)*scale/2),rotation=u.Rotator(yaw=yaw+180),scale=scale,section=section,collision=collision)

def fm_wall(name,axis,fixed,start,end,yaw=0,bottom=0,top=600):
    count=math.ceil((end-start)/300);width=(end-start)/count
    for i in range(count):
        along=start+(i+.5)*width
        center=(along,fixed,(bottom+top)/2) if axis=='x' else (fixed,along,(bottom+top)/2)
        fm_mesh(name+'_'+str(i),'IndustrialStonePanel',center,(width+1,32,top-bottom),u.Rotator(yaw=yaw+180),section='Walls')

def fm_portal(name,x,y,yaw=0,width=600,height=450):
    fm_mesh(name,'IndustrialStargate',(x,y,height/2),(width,78,height),u.Rotator(yaw=yaw+180),section='Doorways')

def fm_light(name,pos,yaw=0,pitch=-90,power=16000,temp=4200,radius=1250,section='Lighting'):
    a=fm_actor(u.RectLight,name,section);a.set_actor_location(FM_ORIGIN+u.Vector(*pos),False,True)
    a.set_actor_rotation(u.Rotator(pitch=pitch,yaw=yaw),False)
    c=a.get_component_by_class(u.RectLightComponent);c.set_mobility(u.ComponentMobility.MOVABLE)
    c.set_editor_property('intensity_units',u.LightUnits.LUMENS);c.set_intensity(power*.16)
    c.set_editor_property('attenuation_radius',radius);c.set_editor_property('source_width',130.)
    c.set_editor_property('source_height',25.);c.set_editor_property('use_temperature',True)
    c.set_editor_property('temperature',float(temp));c.set_editor_property('cast_shadows',True)
    return a

def fm_wall_light(name,x,y,z,yaw):
    fm_prop(name+'_Fixture','IndustrialLEDWorkLight',x,y,z,yaw,scale=.85,section='Lighting')
    facing=u.MathLibrary.transform_location(u.Transform(rotation=u.Rotator(yaw=yaw)),u.Vector(0,-1,0))
    fm_light(name+'_Light',(x+facing.x*30,y+facing.y*30,z+18),yaw=yaw-90,pitch=-35,power=11000,radius=1050)

# A 36 x 30 metre shell. All walkable floors, approach and roof are kit meshes.
for ix in range(12):
    for iy in range(10):
        x=-1650+300*ix;y=-1350+300*iy
        fm_mesh(f'Floor_{ix:02}_{iy:02}','MarbledSteelTile',(x,y,-9),(301,301,18),section='Floor')
        # Overlap the bevelled corners enough to close the seams completely.
        fm_mesh(f'Roof_{ix:02}_{iy:02}','SmokyMetalPanel',(x,y,612),(306,24,306),u.Rotator(roll=90),section='Roof')
for ix in range(2):
    for iy in range(4):
        fm_mesh(f'Approach_{ix}_{iy}','MarbledSteelTile',(-1350+ix*300,-1650-iy*300,-24 if iy==3 else -9),(301,301,18),section='Approach')

fm_wall('North','x',1500,-1800,1800)
fm_wall('West','y',-1800,-1500,1500,90)
fm_wall('East','y',1800,-1500,1500,-90)
# Entrance at the left checkpoint; a closed freight shutter reproduces the front bay.
for i,(start,end) in enumerate([(-1800,-1500),(-900,600),(1500,1800)]):
    fm_wall('South_'+str(i),'x',-1500,start,end,180)
fm_wall('EntryHeader','x',-1500,-1500,-900,180,bottom=450)
fm_wall('FreightHeader','x',-1500,600,1500,180,bottom=450)
fm_portal('EntryFrame',-1200,-1500,180)
for i,x in enumerate([825,1275]):
    fm_mesh('FreightShutter_'+str(i),'IndustrialShutterPanel',(x,-1500,225),(450,55,450),u.Rotator(yaw=180),section='Doorways')
fm_mesh('FreightHazardThreshold','HazardStripeBarrier',(1050,-1560,5),(900,35,10),section='Doorways')

# Checkpoint vestibule, with two generous routes into the main room.
for i,(start,end) in enumerate([(-1800,-1500),(-900,-300)]):fm_wall('CheckpointNorth_'+str(i),'x',-300,start,end)
fm_wall('CheckpointNorthHeader','x',-300,-1500,-900,bottom=450)
fm_portal('CheckpointLabFrame',-1200,-300)
for i,(start,end) in enumerate([(-1500,-1200),(-600,-300)]):fm_wall('CheckpointEast_'+str(i),'y',-300,start,end,-90)
fm_wall('CheckpointEastHeader','y',-300,-1200,-600,-90,bottom=450)
fm_portal('CheckpointHallFrame',-300,-900,90)

# Office in the back right, with a 6 m doorway onto the central circulation space.
fm_wall('OfficeWest','y',600,300,1500,90)
fm_wall('OfficeFrontLeft','x',300,600,850,180)
fm_wall('OfficeFrontRight','x',300,1450,1800,180)
fm_wall('OfficeHeader','x',300,850,1450,180,bottom=450)
fm_portal('OfficeFrame',1150,300,180)

# Structural columns and roof ribs leave at least 5.7 m underneath them.
posts=[(-1800,-1500),(-1800,-300),(-1800,600),(-1800,1500),(-600,1500),(600,1500),(1800,1500),(1800,300),(1800,-600),(1800,-1500),(-300,-1500),(-300,-300),(600,300)]
for i,(x,y) in enumerate(posts):fm_mesh('Column_'+str(i),'ObsidianPillar',(x,y,300),(65,65,600),section='Structure')
for iy,y in enumerate([-900,0,900]):
    for ix in range(6):fm_mesh(f'RoofRib_{ix}_{iy}','ObsidianPillar',(-1500+ix*600,y,600),(50,60,601),u.Rotator(pitch=90),section='Roof')

# Main laboratory consoles, storage and the secured platform from the reference.
for i,y in enumerate([0,410,820]):
    fm_prop('LabConsole_'+str(i),'Hero',-1670,y,yaw=90,scale=1.3,section='Laboratory')
    fm_prop('LabStop_'+str(i),'RedHandStopSign',-1770,y,215,90,.95,section='Laboratory',collision=False)
    fm_wall_light('LabWall_'+str(i),-1760,y,365,90)
fm_prop('LabPower','IndustrialPowerBox',-1700,1220,130,90,section='Laboratory')
for i,y in enumerate([-50,60,170]):fm_prop('LabCylinder_'+str(i),'SilverCylinder',-1490,y-400,scale=1.2,section='Laboratory')
fm_prop('LabSupplyA','IndustrialCargoCrate01',-1450,1200,scale=1.1,section='Laboratory')
fm_prop('LabSupplyB','IndustrialStorageCrate',-1450,1200,103,scale=1.1,section='Laboratory')

cx,cy=-540,850
fm_mesh('ContainmentPlatform','IndustrialLandingPlatform',(cx,cy,42),(590,590,84),section='Containment')
fm_mesh('ContainmentHatch','RedIndustrialHatch',(cx,cy,64),(275,275,20),section='Containment')
# Match the user's fitted front-left post and lowered central hatch.
post_x,post_y=210,210
beacon_bounds=fm_meshes['RedBeacon'].get_bounding_box()
beacon_extent=beacon_bounds.max-beacon_bounds.min
for i,(dx,dy) in enumerate([(-post_x,-post_y),(post_x,-post_y),(-post_x,post_y),(post_x,post_y)]):
    post=fm_mesh('ContainmentPost_'+str(i),'IndustrialEnergyCell',(cx+dx,cy+dy,185),(72,72,370),section='Containment')
    beacon=fm_mesh('ContainmentBeacon_'+str(i),'RedBeacon',(cx+dx,cy+dy-40.5,250+beacon_extent.z*.55/2),(beacon_extent.x*.825,beacon_extent.y*.825,beacon_extent.z*.55),u.Rotator(yaw=180),section='Containment',collision=False)
    beacon.attach_to_actor(post,'',u.AttachmentRule.KEEP_WORLD,u.AttachmentRule.KEEP_WORLD,u.AttachmentRule.KEEP_WORLD,False)
for level,z in enumerate([160,255]):
    fm_mesh('RailRear_'+str(level),'HazardStripeBarrier',(cx,cy+post_y,z),(post_x*2,6,6),section='Containment')
    for side,dx in [('Left',-post_x),('Right',post_x)]:
        fm_mesh('Rail'+side+'_'+str(level),'HazardStripeBarrier',(cx+dx,cy,z),(post_y*2,6,6),u.Rotator(yaw=90),section='Containment')
fm_prop('ContainmentControl','RuggedDataCore',cx+380,cy-210,95,180,1.2,section='Containment')
fm_prop('ContainmentCrate','IndustrialCargoCrate02',cx+570,cy+370,scale=1.0,section='Containment')
fm_prop('ContainmentSign','RedHandStopSign',cx,1458,220,section='Containment',collision=False)
fm_light('ContainmentAmber',(cx,cy,415),power=9500,temp=2500,radius=760)

# Office: central desk, freestanding terminal, chair and cabinets, with full walkways.
fm_prop('OfficeDesk','VintageMilitaryDesk',1170,920,yaw=180,scale=1.8,section='Office')
fm_prop('OfficeMonitor','HeroMonitor',1180,930,112,180,.95,section='Office')
fm_prop('OfficeKeyboard','RuggedCommandKeyboard',1180,970,112,180,1.0,section='Office')
fm_prop('OfficeTerminal','RuggedControlModule',1340,920,112,180,.6,section='Office')
fm_prop('OfficeChair','OliveExecutiveOfficeChair',1170,1160,yaw=0,scale=1.1,section='Office')
fm_prop('OfficeShelf','IndustrialMetalBookshelf',890,1410,scale=1.25,section='Office')
fm_prop('OfficeDrawer','IndustrialMetalNightstand',1550,1390,scale=1.2,section='Office')
fm_prop('OfficeStorage','IndustrialStorageCrate',1550,1390,85,scale=.8,section='Office')
fm_prop('OfficeWallDisplay','GeometricPrismInterface',1760,890,240,-90,2.4,section='Office',collision=False)
fm_prop('OfficeCrate','IndustrialCargoCrate01',1660,520,yaw=-90,scale=.85,section='Office')
fm_prop('OfficeDataCore','RuggedDataCore',880,1410,170,scale=.65,section='Office')
fm_wall_light('OfficeNorth',1230,1460,380,0)
fm_wall_light('OfficeEast',1760,750,380,-90)
fm_prop('OfficeVent','WeatheredMetalVent',630,1050,400,90,1.3,section='Office',collision=False)

# Entry/security room echoes the smaller terminal bay in the image.
fm_prop('CheckpointConsole','Hero',-570,-430,yaw=0,scale=1.3,section='Checkpoint')
fm_prop('CheckpointMonitor','HeroMonitor',-570,-430,140,scale=.65,section='Checkpoint')
fm_prop('CheckpointCrate','IndustrialCargoCrate01',-620,-1340,yaw=180,section='Checkpoint')
fm_prop('CheckpointPoster','RedHandStopSign',-1760,-830,210,90,section='Checkpoint',collision=False)
fm_prop('CheckpointSwitch','WeatheredDoubleSwitch',-345,-470,150,90,.7,section='Checkpoint',collision=False)
fm_wall_light('CheckpointWest',-1760,-920,355,90)
fm_wall_light('CheckpointNorth',-570,-340,355,0)

# Repeated vents, status indicators and practical ceiling lighting.
for i,x in enumerate([-1150,200,1180]):
    fm_prop('NorthVent_'+str(i),'WeatheredMetalVent',x,1465,455,scale=1.5,section='Wall Details',collision=False)
    fm_wall_light('NorthFixture_'+str(i),x,1455,380,0)
for i,(x,y) in enumerate([(-1050,0),(0,0),(950,-850),(-900,1150),(1150,1100)]):
    fm_light('CeilingFill_'+str(i),(x,y,535),power=22000,temp=4500,radius=1450)
    fm_mesh('CeilingFixture_'+str(i),'IndustrialLEDWorkLight',(x,y,550),(170,27,49),u.Rotator(roll=90),section='Lighting',collision=False)
fm_prop('FreightAlert','AlertSignal',1650,-1540,295,0,1.5,section='Exterior',collision=False)
fm_prop('FreightAccess','RuggedDataCore',1575,-1540,120,0,1.0,section='Exterior',collision=False)
fm_prop('FreightBeacon','RedBeacon',1570,-1540,250,0,.9,section='Exterior',collision=False)
fm_prop('EntryAlert','AlertSignal',-1200,-1550,410,0,1.35,section='Exterior',collision=False)
fm_wall_light('EntranceLamp',-1200,-1560,480,0)
fm_wall_light('FreightLamp',1050,-1560,490,0)
for i,x in enumerate([-700,1550]):fm_prop('FreightSupplies_'+str(i),'IndustrialCargoCrate02',x,-1270,scale=.9,section='Freight Bay')

# Navigation helper is invisible; no engine primitive meshes are used in the build.
nav=fm_actor(u.NavMeshBoundsVolume,'Navigation','Navigation')
nav.set_actor_location(FM_ORIGIN+u.Vector(0,-500,340),False,True);nav.set_actor_scale3d(u.Vector(20,23,5))
navsys=u.NavigationSystemV1.get_navigation_system(fm_world)
if navsys:navsys.on_navigation_bounds_updated(nav)
u.SystemLibrary.execute_console_command(fm_world,'RebuildNavigation')
for label,a in fm_existing.items():
    if label not in fm_used:fm_actors.destroy_actor(a)
assert fm_level.save_current_level()
camera=FM_ORIGIN+u.Vector(-1160,-2220,245)
rotation=u.MathLibrary.find_look_at_rotation(camera,FM_ORIGIN+u.Vector(-900,100,260))
u.get_editor_subsystem(u.UnrealEditorSubsystem).set_level_viewport_camera_info(camera,rotation)
manifest=dict(map='/Game/Maps/L_TraversalGym',origin=[12600,8100,30],footprint_cm=[3600,3000],wall_height_cm=600,roof_underside_cm=600,minimum_beam_headroom_cm=570,door_frame_width_cm=600,entrance=[11400,6550,130],approach_from=[11400,5400,100],sections=['Laboratory','Containment','Office','Checkpoint','Freight Bay'],mesh_actors=fm_records,actor_count=len(fm_used))
(FM_ROOT/'resources/FacilityMockup.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('FACILITY_BUILT',len(fm_used),'actors',len(fm_records),'kit mesh instances')
if (FM_ROOT/'resources/BuildingDestruction.json').exists():
    exec(compile((FM_ROOT/'Scripts/Build-BuildingDestruction.py').read_text(),'Build-BuildingDestruction.py','exec'),globals())
