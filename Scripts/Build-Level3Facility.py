"""Build the roofed three-storey Mars facility from the imported Level3 kit."""
import json,math
from pathlib import Path
import unreal as u

l3_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
l3_world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
assert l3_world.get_name()=='L_TraversalGym'
l3_actors=u.get_editor_subsystem(u.EditorActorSubsystem)
l3_prefix='CR_Level3_';l3_origin=u.Vector(33000,7900,30)
l3_existing={a.get_actor_label():a for a in l3_actors.get_all_level_actors() if a.get_actor_label().startswith(l3_prefix)}
l3_catalog={r['name']:r for r in json.loads((l3_root/'resources/EnvironmentModels.json').read_text()) if r['category']=='Level3'}
l3_meshes={n:u.load_asset(r['asset']) for n,r in l3_catalog.items()}
assert len(l3_meshes)==74 and all(l3_meshes.values())
l3_used=set();l3_records=[];l3_floor_samples=[];l3_roof_samples=[];l3_stairs=[]
l3_collision_records=[]
l3_cube=u.load_asset('/Engine/BasicShapes/Cube.Cube')
l3_metal=u.load_asset('/Game/Crusader/Effects/Surfaces/PM_Metal')

def l3_actor(cls,name,section):
    label=l3_prefix+name
    a=l3_existing.get(label) or l3_actors.spawn_actor_from_class(cls,u.Vector())
    assert isinstance(a,cls),label
    a.set_actor_label(label);a.set_folder_path('Crusader/Three Storey Facility/'+section)
    a.tags=['CrusaderLevel3',section];l3_used.add(label)
    return a

def l3_mesh(name,model,center,size=None,rot=None,scale=1.,section='Equipment',collision=True):
    mesh=l3_meshes[model];box=mesh.get_bounding_box();dims=box.max-box.min
    factor=u.Vector(*(size[i]/[dims.x,dims.y,dims.z][i] for i in range(3))) if size else u.Vector(scale,scale,scale)
    rot=rot or u.Rotator()
    offset=u.MathLibrary.transform_location(u.Transform(rotation=rot,scale=factor),(box.min+box.max)*.5)
    a=l3_actor(u.StaticMeshActor,name,section);c=a.static_mesh_component
    c.set_static_mesh(mesh);c.set_mobility(u.ComponentMobility.STATIC)
    a.set_actor_transform(u.Transform(location=l3_origin+u.Vector(*center)-offset,rotation=rot,scale=factor),False,True)
    c.set_collision_profile_name('BlockAll' if collision else 'NoCollision')
    l3_records.append(dict(actor=a.get_actor_label(),model=model,center=list(center),section=section,collision=collision))
    return a

def l3_prop(name,model,x,y,z=0,yaw=0,scale=1.,section='Equipment'):
    box=l3_meshes[model].get_bounding_box()
    return l3_mesh(name,model,(x,y,z+(box.max.z-box.min.z)*scale/2),rot=u.Rotator(yaw=yaw+180),scale=scale,section=section)

def l3_panel(name,model,x,y,z,width=600,height=330,yaw=0,thickness=42,section='Walls'):
    return l3_mesh(name,model,(x,y,z),(width,thickness,height),u.Rotator(yaw=yaw+180),section=section)

def l3_wall(name,axis,fixed,start,end,base=0,yaw=0,bottom=0,top=660,models=None):
    models=models or ['BlueTanIndustrialWall','WallPanel','WallCVentPanel','PlainWall']
    count=math.ceil((end-start)/600);width=(end-start)/count
    tiers=[(bottom,330),(330,top)] if bottom<330<top else [(bottom,top)]
    for tier,(low,high) in enumerate(tiers):
        for i in range(count):
            p=start+(i+.5)*width
            x,y=(p,fixed) if axis=='x' else (fixed,p)
            model='QuantumViewport' if low>=330 and high-low>=300 and i%3==1 else models[i%len(models)]
            # Thin storey bands overlap the source panel's bevelled end caps.
            overlap=50 if high-low<100 else 5
            l3_panel(f'{name}_{tier}_{i}',model,x,y,base+(low+high)/2,width+overlap,high-low+2,yaw)

def l3_floor_rect(name,x0,x1,y0,y1,z,section='Floors',model='IndustrialFloorPanel',samples=True):
    nx=math.ceil((x1-x0)/600);ny=math.ceil((y1-y0)/600)
    w=(x1-x0)/nx;d=(y1-y0)/ny
    # A continuous kit-panel underside closes tiny decorative openings/seams.
    backing=l3_mesh(name+'_Backing','CeilingA',((x0+x1)/2,(y0+y1)/2,z-32),(x1-x0+4,12,y1-y0+4),u.Rotator(roll=90),section=section)
    l3_detail_collision(backing)
    for ix in range(nx):
        for iy in range(ny):
            x=x0+(ix+.5)*w;y=y0+(iy+.5)*d
            tile=l3_mesh(f'{name}_{ix}_{iy}',model,(x,y,z-13),(w+5,d+5,26),section=section)
            l3_detail_collision(tile)
            if samples:l3_floor_samples.append([x,y,z])
    l3_collision_box(name+'_WalkSurface',u.Vector((x0+x1)/2,(y0+y1)/2,z-8),u.Vector(x1-x0+4,y1-y0+4,16),u.Rotator())

def l3_ceiling(name,x0,x1,y0,y1,z,section='Ceilings'):
    nx=math.ceil((x1-x0)/600);ny=math.ceil((y1-y0)/600)
    for ix in range(nx):
        for iy in range(ny):
            x=x0+(ix+.5)*(x1-x0)/nx;y=y0+(iy+.5)*(y1-y0)/ny
            l3_mesh(f'{name}_{ix}_{iy}','CeilingA',(x,y,z+12),((x1-x0)/nx+6,24,(y1-y0)/ny+6),u.Rotator(roll=90),section=section)
            l3_roof_samples.append([x,y,z])

def l3_light(name,x,y,z,power=8500,temp=4400,radius=1800,pitch=-90,yaw=0):
    a=l3_actor(u.RectLight,name,'Lighting');a.set_actor_location(l3_origin+u.Vector(x,y,z),False,True)
    a.set_actor_rotation(u.Rotator(pitch=pitch,yaw=yaw),False)
    c=a.get_component_by_class(u.RectLightComponent);c.set_mobility(u.ComponentMobility.MOVABLE)
    c.set_editor_property('intensity_units',u.LightUnits.LUMENS);c.set_intensity(float(power))
    for key,value in [('attenuation_radius',float(radius)),('source_width',220.),('source_height',95.),('use_temperature',True),('temperature',float(temp)),('cast_shadows',True)]:c.set_editor_property(key,value)

def l3_rail(name,x,y,z,width,yaw=0):
    rail=l3_panel(name,'IndustrialLightBarrier',x,y,z+60,width,120,yaw,30,'Railings')
    rail.static_mesh_component.set_collision_response_to_channel(u.CollisionChannel.ECC_CAMERA,u.CollisionResponseType.ECR_IGNORE)

def l3_fill(name,x,y,z,power=3500,radius=1600):
    a=l3_actor(u.PointLight,name,'Lighting');a.set_actor_location(l3_origin+u.Vector(x,y,z),False,True)
    c=a.get_component_by_class(u.PointLightComponent);c.set_mobility(u.ComponentMobility.MOVABLE)
    c.set_editor_property('intensity_units',u.LightUnits.LUMENS);c.set_intensity(float(power))
    for key,value in [('attenuation_radius',float(radius)),('source_radius',100.),('use_temperature',True),('temperature',4900.),('cast_shadows',False),('specular_scale',.15)]:c.set_editor_property(key,value)

def l3_detail_collision(actor):
    # Retain exact visible geometry for shots, grenades and foot placement.
    # Character capsules and cameras use the continuous surfaces below.
    c=actor.static_mesh_component
    c.set_collision_response_to_channel(u.CollisionChannel.ECC_PAWN,u.CollisionResponseType.ECR_IGNORE)
    c.set_collision_response_to_channel(u.CollisionChannel.ECC_CAMERA,u.CollisionResponseType.ECR_IGNORE)
    c.set_mobility(u.ComponentMobility.MOVABLE)
    assert u.CRBlueprintTools.set_property_text(c,'bCanEverAffectNavigation','False')
    c.set_mobility(u.ComponentMobility.STATIC)

def l3_collision_box(name,center,size,rotation,guard=False):
    a=l3_actor(u.StaticMeshActor,name,'Walking Collision');c=a.static_mesh_component
    c.set_static_mesh(l3_cube);c.set_mobility(u.ComponentMobility.STATIC)
    a.set_actor_transform(u.Transform(location=l3_origin+center,rotation=rotation,scale=size/100.),False,True)
    c.set_collision_profile_name('BlockAll')
    c.set_collision_enabled(u.CollisionEnabled.QUERY_ONLY)
    c.set_collision_response_to_all_channels(u.CollisionResponseType.ECR_IGNORE)
    c.set_collision_response_to_channel(u.CollisionChannel.ECC_PAWN,u.CollisionResponseType.ECR_BLOCK)
    if not guard:c.set_collision_response_to_channel(u.CollisionChannel.ECC_CAMERA,u.CollisionResponseType.ECR_BLOCK)
    c.set_phys_material_override(l3_metal)
    c.set_visibility(False);c.set_cast_shadow(False);a.set_actor_hidden_in_game(True)
    a.set_is_temporarily_hidden_in_editor(True)
    assert u.CRBlueprintTools.set_property_text(a,'bHiddenEd','True')
    l3_collision_records.append(dict(actor=a.get_actor_label(),guard=guard,size=[size.x,size.y,size.z]))
    return a

# Measure the imported mesh, including Unreal's handedness conversion, rather
# than assuming that Blender's ascending local Y direction survives FBX import.
l3_probe=l3_actors.spawn_actor_from_class(u.StaticMeshActor,l3_origin+u.Vector(0,0,4000))
try:
    l3_probe.static_mesh_component.set_static_mesh(l3_meshes['IndustrialStaircase'])
    l3_probe.static_mesh_component.set_collision_profile_name('BlockAll')
    l3_heights=[]
    for y in [-500,500]:
        hit=u.SystemLibrary.line_trace_single(l3_world,l3_origin+u.Vector(0,y,5000),l3_origin+u.Vector(0,y,3900),
            u.TraceTypeQuery.TRACE_TYPE_QUERY1,True,[],u.DrawDebugTrace.NONE)
        assert hit and hit.to_dict()['hit_actor']==l3_probe,'Cannot measure imported staircase collision'
        l3_heights.append(hit.to_dict()['impact_point'].z-l3_origin.z-4000)
    l3_stair_low=min(l3_heights);l3_stair_high=max(l3_heights)
    l3_stair_yaw=0 if l3_heights[0]<l3_heights[1] else 180
    assert 400<l3_stair_high-l3_stair_low<700,l3_heights
finally:l3_actors.destroy_actor(l3_probe)

# The main rooms are 66 x 54 m. The east stair tower is 20 x 36 m.
# Each occupied floor has 6.6 m clear height, with a 0.6 m service slab above.
for level in range(3):
    z=level*720;prefix=f'L{level+1}_'
    l3_floor_rect(prefix+'Floor',-3300,3300,-2700,2700,z)
    l3_ceiling(prefix+'Ceiling',-3300,3300,-2700,2700,z+660)
    l3_floor_rect(prefix+'StairLobby',3300,5300,-2100,-1350,z)
    l3_wall(prefix+'North','x',2700,-3300,3300,z,0,models=['BlueTanIndustrialWall','HazardWallPanel','WallDControlPanel','PlainWall'])
    if level==0:
        l3_wall(prefix+'SouthWest','x',-2700,-3300,-600,z,180)
        l3_wall(prefix+'SouthEast','x',-2700,600,3300,z,180)
        l3_wall(prefix+'EntryHeader','x',-2700,-600,600,z,180,bottom=510)
        l3_panel(prefix+'MainEntrance','IndustrialPortalFrame',0,-2700,z+255,1200,510,0,100,'Entrances')
        l3_wall(prefix+'WestSouth','y',-3300,-2700,-500,z,90)
        l3_wall(prefix+'WestNorth','y',-3300,500,2700,z,90)
        l3_wall(prefix+'WestHeader','y',-3300,-500,500,z,90,bottom=510)
        l3_panel(prefix+'WestEntrance','SlidingDoorOpen',-3300,0,z+255,1000,510,90,90,'Entrances')
    else:
        l3_wall(prefix+'South','x',-2700,-3300,3300,z,180)
        l3_wall(prefix+'West','y',-3300,-2700,2700,z,90)
    l3_wall(prefix+'EastSouth','y',3300,-2700,-2100,z,-90)
    l3_wall(prefix+'EastNorth','y',3300,-1350,2700,z,-90)
    l3_wall(prefix+'StairHeader','y',3300,-2100,-1350,z,-90,bottom=510)
    l3_panel(prefix+'StairEntrance','IndustrialPortalFrame',3300,-1725,z+255,750,510,90,90,'Entrances')
    l3_wall(prefix+'TowerEast','y',5300,-2100,1650,z,-90)
    l3_wall(prefix+'TowerNorth','x',1650,3300,5300,z,0)
    l3_wall(prefix+'TowerSouth','x',-2100,3300,5300,z,180)
    if level<2:
        # The stair shaft has no full intermediate slab, so its outer envelope
        # needs explicit floor-depth bands between the 6.6 m wall tiers.
        for name,axis,fixed,start,end,yaw in [('NorthBand','x',2700,-3300,3300,0),
                ('SouthBand','x',-2700,-3300,3300,180),('WestBand','y',-3300,-2700,2700,90),
                ('EastBand','y',3300,-2700,2700,-90),('TowerEastBand','y',5300,-2100,1650,-90),
                ('TowerNorthBand','x',1650,3300,5300,0),('TowerSouthBand','x',-2100,3300,5300,180)]:
            l3_wall(prefix+name,axis,fixed,start,end,z,yaw,bottom=660,top=720,models=['PlainWall'])
    # Side bays retain 19 m of width; a broad cross-corridor stays open in front.
    l3_wall(prefix+'WestBayDivider','y',-1400,500,2700,z,-90,
            models=['IndustrialMetalPanel','IndustrialVentPanel01','IndustrialBatteryPanel'])
    l3_wall(prefix+'EastBayDivider','y',1400,500,2700,z,90,
            models=['PlainWall','PowerCell','WallDControlPanel'])
    for i,x in enumerate([-3300,-1400,1400,3300,5300]):
        for j,y in enumerate([-2700,2700] if x<5300 else [-2100,1650]):
            if x==5300 and y==2700:continue
            l3_mesh(prefix+f'Post_{i}_{j}','LuminousIronPillar',(x,y,z+330),(110,110,660),section='Structure')
    for i,x in enumerate([-3280,3280]):
        l3_mesh(prefix+'CornerReturn_'+str(i),'MarsWallG',(x,2670,z+330),(160,160,660),u.Rotator(yaw=90 if x<0 else 0),section='Structure')
    for i,x in enumerate([-2250,0,2250]):
        for j,y in enumerate([-1750,-300,1350]):
            l3_light(prefix+f'Light_{i}_{j}',x,y,z+620,10500,4200+level*400,radius=1950)
    l3_light(prefix+'StairLight',4300,-500,z+635,10000,4700,1700)
    l3_light(prefix+'CeilingBounce',0,-450,z+350,2200,4400,3000,pitch=90)
    for i,x in enumerate([-2250,0,2250]):
        for j,y in enumerate([-1250,1450]):l3_fill(prefix+f'Fill_{i}_{j}',x,y,z+290)
    l3_fill(prefix+'StairFill',4300,100,z+300,4500,1650)
    # Readable existing kit markings and modular fascia identify each floor.
    l3_prop(prefix+'MarsBanner','MarsResearchDivisionSign',-920,2653,z+330,scale=1.7,section='Signage')
    l3_prop(prefix+'EmergencyCall','EmergencyCallBox',3225,-1000,z+160,yaw=-90,section='Signage')
    for i,x in enumerate([-2350,0,2350]):
        l3_prop(prefix+f'WallLamp_{i}','IndustrialWallLight',x,-2645,z+420,yaw=180,scale=1.3,section='Lighting Fixtures')

# Use four shallow kit runs per storey, in two wide switchback flights.
# Measured central first/last tread heights are 91.4 and 607 cm in the export.
# Fitting these endpoints makes 180 cm per run with ~24 cm risers, avoiding
# the giant steps produced by scaling one nine-step asset to a whole storey.
l3_stair_box=l3_meshes['IndustrialStaircase'].get_bounding_box()
l3_stair_dims=l3_stair_box.max-l3_stair_box.min
for level in range(2):
    base=720*level
    for i,(x,start_y,end_y,start_z) in enumerate([(3800,-1350,-300,0),(3800,-100,950,180),
                                                (4800,950,-100,360),(4800,-300,-1350,540)]):
        sign=1 if end_y>start_y else -1;yaw=l3_stair_yaw+(0 if sign==1 else 180)
        sy=1050/1050.;sz=180/(l3_stair_high-l3_stair_low)
        factor=u.Vector(700/l3_stair_dims.x,sy,sz)
        # Source centreline y=-525 is the lower tread, y=525 the upper.
        transform=u.Transform(location=l3_origin+u.Vector(x,(start_y+end_y)/2,base+start_z-l3_stair_low*sz),rotation=u.Rotator(yaw=yaw),scale=factor)
        a=l3_actor(u.StaticMeshActor,f'Stair_{level}_{i}','Stairs')
        a.static_mesh_component.set_static_mesh(l3_meshes['IndustrialStaircase'])
        a.static_mesh_component.set_mobility(u.ComponentMobility.STATIC)
        a.static_mesh_component.set_collision_profile_name('BlockAll')
        a.set_actor_transform(transform,False,True)
        l3_detail_collision(a)
        # A tilted box gives the capsule one continuous plane while the source
        # stair mesh keeps its treads, railings, weapon hits and foot IK detail.
        angle=math.degrees(math.atan2(180.,1050.))
        # Unreal's positive roll sends local +Y downward.
        ramp_rotation=u.Rotator(roll=-angle,yaw=0 if sign==1 else 180)
        ramp_axis=u.MathLibrary.transform_direction(u.Transform(rotation=ramp_rotation),u.Vector(0,1,0))
        assert ramp_axis.z>0 and ramp_axis.y*sign>0
        normal=u.MathLibrary.transform_direction(u.Transform(rotation=ramp_rotation),u.Vector(0,0,1))
        top_center=u.Vector(x,(start_y+end_y)/2,base+start_z+90)
        length=math.hypot(1050,180)+5
        l3_collision_box(f'StairRamp_{level}_{i}',top_center-normal*8,u.Vector(630,length,16),ramp_rotation)
        for side in [-1,1]:
            l3_collision_box(f'StairGuard_{level}_{i}_{side}',top_center+u.Vector(side*328,0,0)+normal*55,
                             u.Vector(35,length,110),ramp_rotation,guard=True)
        l3_records.append(dict(actor=a.get_actor_label(),model='IndustrialStaircase',section='Stairs',collision=True))
        l3_stairs.append(dict(actor=a.get_actor_label(),level=level+1,start=[x,start_y,base+start_z],end=[x,end_y,base+start_z+180],width_cm=700))
    l3_floor_rect(f'StairMidA_{level}',3450,4150,-305,-95,base+180,'Stairs',samples=False)
    l3_floor_rect(f'StairTurn_{level}',3450,5150,945,1650,base+360,'Stairs',samples=False)
    l3_floor_rect(f'StairMidB_{level}',4450,5150,-305,-95,base+540,'Stairs',samples=False)
    l3_rail(f'StairTurnRail_{level}',4300,1610,base+360,1660)
    l3_rail(f'StairTurnEdge_{level}',4300,955,base+360,285)
    for x in [3455,5145]:l3_rail(f'StairTurnSide_{level}_{x}',x,1280,base+360,630,90)
    # Guard the gap between the two flights at each accessible upper lobby.
    l3_rail(f'StairLobbyRail_{level}',4300,-1340,base+720,300)
l3_floor_rect('TowerGround',3300,5300,-1350,1650,0,'Floors',samples=False)
l3_ceiling('TowerRoof',3300,5300,-2100,1650,2100,'Roof')
l3_floor_rect('WeatherRoofMain',-3300,3300,-2700,2700,2160,'Roof','ModularSlatePlatform',samples=False)
l3_floor_rect('WeatherRoofTower',3300,5300,-2100,1650,2160,'Roof','ModularSlatePlatform',samples=False)
for i,x in enumerate(range(-3000,3001,600)):
    for y in [-2700,2700]:l3_rail(f'RoofFascia_{i}_{y}',x,y,2160,600)

# L1: loading apron, service bays, power and pipes around a central reactor.
for i,(x,y,model) in enumerate([(-2700,-1950,'IroncladCargoCrate'),(-2450,-1700,'BlueCrate'),(-2860,-1470,'MarsRedCrate'),
                               (-2220,-2120,'BlueCrate'),(2200,-2250,'MarsToolLocker'),(2850,-2250,'IndustrialCabinet')]):
    l3_prop('L1_Storage_'+str(i),model,x,y,section='L1 Loading')
for i,y in enumerate([750,1400,2050]):
    l3_prop('L1_Maintenance_'+str(i),'IndustrialPowerCabinet',-2980,y,yaw=90,scale=1.25,section='L1 Maintenance')
    l3_prop('L1_Utility_'+str(i),['MarsCompactGenerator','ReactorModule','CompactMachineBlock'][i],2450,y,scale=1.15,section='L1 Utilities')
for i,x in enumerate([-700,0,700]):
    l3_prop('L1_Pipe_'+str(i),'IndustrialPipeManifold',x,2390,scale=1.35,section='L1 Reactor')
l3_prop('L1_Core','PowerCoreColumn',0,1550,scale=1.22,section='L1 Reactor')
l3_prop('L1_Reactor','ReactorModule',0,1020,scale=1.2,section='L1 Reactor')
l3_mesh('L1_HazardPad','IndustrialHazardFloor',(0,1490,3),(1250,1450,12),section='L1 Reactor')
for i,x in enumerate([-780,780]):
    l3_rail('L1_CoreRail_'+str(i),x,1510,0,1380,90)
    l3_prop('L1_Valve_'+str(i),'WallControlBox',x,2150,145,section='L1 Reactor')
for i,(x,y) in enumerate([(-2600,2480),(-2800,2470),(2640,2360),(2850,2360)]):
    l3_prop('L1_Canister_'+str(i),'MarsFuelCanister' if i<2 else 'WeatheredBlueOilDrum',x,y,section='L1 Utilities')
l3_prop('L1_Warning','DangerHighVoltageSign',0,2635,330,scale=1.6,section='Signage')
l3_prop('L1_Checkpoint','MarsPathfinderConsole',1000,-2490,yaw=180,section='L1 Loading')
l3_prop('L1_ServiceDesk','CRTComputerDesk',-2380,2270,section='L1 Maintenance')
l3_prop('L1_ServiceChair','SwivelChair',-2380,1980,yaw=180,section='L1 Maintenance')

# L2: command centre, server room and power management. Routes stay 8 m+ wide.
z=720
l3_prop('L2_Command','RetroCommandConsole',0,1710,z,scale=1.25,section='L2 Operations')
for i,x in enumerate([-790,790]):
    l3_prop('L2_CommandWing_'+str(i),'RetroCommandWorkbench',x,1950,z,yaw=-40 if x<0 else 40,section='L2 Operations')
    l3_prop('L2_Chair_'+str(i),'SwivelChair',x*.6,1390,z,yaw=180,section='L2 Operations')
for i,y in enumerate([850,1300,1750,2200]):
    l3_prop('L2_Server_'+str(i),'ObsidianServerRack',-3010,y,z,yaw=90,scale=1.25,section='L2 Servers')
for i,x in enumerate([-2630,-2130]):l3_prop('L2_TechDesk_'+str(i),'CRTComputerDesk',x,2370,z,section='L2 Servers')
for i,y in enumerate([1000,1750]):
    l3_prop('L2_PowerUnit_'+str(i),'MarsCompactGenerator',2460,y,z,scale=1.25,section='L2 Power')
    l3_prop('L2_PowerConsole_'+str(i),'MarsPathfinderConsole',1820,y,z,yaw=90,section='L2 Power')
for i,x in enumerate([-2350,2350]):
    l3_prop('L2_AnalysisDesk_'+str(i),'RetroCommandWorkbench',x,-2220,z,yaw=90 if x<0 else -90,scale=1.2,section='L2 Analysis')
    l3_prop('L2_AnalysisChair_'+str(i),'SwivelChair',x+(-280 if x>0 else 280),-2220,z,yaw=90 if x>0 else -90,section='L2 Analysis')
l3_panel('L2_RearDisplay','WallDControlPanel',0,2650,z+420,1700,420,section='L2 Operations')

# L3: central containment cylinder, medbay and research benches.
z=1440
l3_prop('L3_Containment','PowerCoreColumn',0,1590,z,scale=1.25,section='L3 Containment')
l3_mesh('L3_ContainmentPad','HazardPlate',(0,1570,z+2),(1300,1300,12),section='L3 Containment')
for i,x in enumerate([-860,860]):
    l3_prop('L3_ContainmentConsole_'+str(i),'MarsPathfinderConsole',x,1320,z,yaw=-25 if x<0 else 25,section='L3 Containment')
    l3_rail('L3_ContainmentRail_'+str(i),x,1800,z,800,90)
for i,y in enumerate([1050,1940]):l3_prop('L3_Medbay_'+str(i),'CyberneticMedbayRecliner',-2520,y,z,yaw=90,scale=1.25,section='L3 Medbay')
l3_prop('L3_MedicalConsole','CRTComputerDesk',-1980,2440,z,section='L3 Medbay')
for i,y in enumerate([1000,2100]):
    l3_prop('L3_ResearchBench_'+str(i),'RetroCommandWorkbench',2460,y,z,yaw=-90,scale=1.1,section='L3 Research')
    l3_prop('L3_ResearchChair_'+str(i),'SwivelChair',2100,y,z,yaw=-90,section='L3 Research')
for i,x in enumerate([-2380,2380]):
    l3_prop('L3_ObservationDesk_'+str(i),'CRTComputerDesk',x,-2250,z,yaw=90 if x<0 else -90,scale=1.1,section='L3 Observation')
    l3_prop('L3_Specimen_'+str(i),'MarsIndustrialPowerCell',x,-1000,z,scale=1.25,section='L3 Observation')
l3_prop('L3_ResearchBanner','MarsResearchDivisionSign',0,2640,z+340,scale=1.65,section='Signage')

# Kit variants decorate service niches and facades without obstructing circulation.
variants=['BlastDoor','FortressGate','IndustrialPowerCore','IndustrialPowerShutter','IndustrialReactorPanel',
          'IndustrialSciFiBlastDoor','IndustrialCargoPanel','MarsIndustrialCargoCrate','QuantumVaultDoor',
          'NeonGateway','ReinforcedPanel','IndustrialVentPanel02','SolarPanel','IndustrialAccessPanel']
for i,model in enumerate(variants):
    floor=i//5;floor=min(floor,2);j=i%5;x=[-2850,-2100,-1200,1200,2400][j]
    # Thin framed service panels remain attached to the south interior wall.
    if model in ['ReinforcedPanel','IndustrialVentPanel02','SolarPanel','IndustrialAccessPanel']:
        l3_mesh('ServiceDetail_'+str(i),model,(x,-2635,720*floor+165),(480,285,24),u.Rotator(roll=90,yaw=180),section='Service Details')
    else:l3_panel('ServiceDetail_'+str(i),model,x,-2635,720*floor+165,480,285,180,24,'Service Details')
for i,model in enumerate(['ArcanePowerCell','GoldenStasisPillar','PerforatedMetalColumn','CylindricalGlassCapsule']):
    l3_mesh('FacadeColumn_'+str(i),model,(-3150+i*2100,-2720,1020),(100,100,1980),section='Exterior')
for i,model in enumerate(['ExtendedMagazine','IndustrialTriadFrame']):
    l3_panel('EntryBrace_'+str(i),model,(-750 if i==0 else 750),-2770,380,270,340,0,100,'Exterior')
for i,model in enumerate(['IndustrialVentGrate','IndustrialVentGrille']):
    l3_panel('L1_MaintenanceVent_'+str(i),model,-3240,1000+i*1100,400,350,220,90,24,'L1 Maintenance')
for i,model in enumerate(['RadioactiveBarrel','UtilityTurretFloor']):
    l3_prop('L1_UtilitySpare_'+str(i),model,2920,-850+i*480,section='L1 Utilities')
l3_rail('EntranceSafetyWest',-1900,-2940,0,1800)
l3_rail('EntranceSafetyEast',1900,-2940,0,1800)
l3_panel('LoadingYellowRail','YellowSafetyRailing',-3050,-1750,60,1300,120,90,20,'L1 Loading')

# Shared outside promenade joins the existing control-room approach at y=4750.
l3_floor_rect('Promenade',-12400,600,-3600,-2700,0,'Approach','ModularSteelFloorPanel',samples=False)
l3_floor_rect('EntryApron',-3300,3300,-3450,-2700,0,'Approach','ModularSteelFloorPanel',samples=False)
l3_floor_rect('WestApron',-4300,-3300,-2700,600,0,'Approach','ModularSteelFloorPanel',samples=False)
for i,x in enumerate(range(-11200,1,2000)):l3_light('PromenadeLight_'+str(i),x,-3150,700,4500,4400,1700)
for i,x in enumerate([-2700,0,2700]):l3_light('FacadeWash_'+str(i),x,-3250,1880,14000,4800,2900,pitch=-55,yaw=90)

nav=l3_actor(u.NavMeshBoundsVolume,'Navigation','Navigation')
nav.set_actor_location(l3_origin+u.Vector(-3500,-750,1100),False,True)
nav.set_actor_scale3d(u.Vector(92,36,14))
navsys=u.NavigationSystemV1.get_navigation_system(l3_world)
if navsys:navsys.on_navigation_bounds_updated(nav)
u.SystemLibrary.execute_console_command(l3_world,'RebuildNavigation')
for label,a in l3_existing.items():
    if label not in l3_used:l3_actors.destroy_actor(a)
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
manifest=dict(map='/Game/Maps/L_TraversalGym',origin=[33000,7900,30],storeys=3,main_footprint_cm=[6600,5400],
    overall_footprint_cm=[8600,5400],floor_elevations_cm=[0,720,1440],clear_height_cm=660,stair_run_width_cm=700,
    entrance=[33000,5200,130],floor_samples=l3_floor_samples,ceiling_samples=l3_roof_samples,stairs=l3_stairs,
    meshes=l3_records,walking_collision=l3_collision_records,actor_count=len(l3_used),models_used=sorted({r['model'] for r in l3_records}),stair_profile=dict(low=l3_stair_low,high=l3_stair_high,yaw=l3_stair_yaw),
    rooms=['L1 Loading / Reactor / Maintenance / Utilities','L2 Operations / Servers / Power / Analysis','L3 Containment / Medbay / Research / Observation'])
(l3_root/'resources/Level3Facility.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('LEVEL3_FACILITY_BUILT',len(l3_used),'actors',len(manifest['models_used']),'kit models')
