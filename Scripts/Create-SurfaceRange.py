"""Idempotent shooting surface fixtures, south of the traversal and slide lanes."""
import json
from pathlib import Path
import unreal as u

assert not u.EditorLevelLibrary.get_pie_worlds(False)
ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
level=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world().get_name()=='L_TraversalGym'
actors=u.get_editor_subsystem(u.EditorActorSubsystem)
lib=u.EditorAssetLibrary;tools=u.AssetToolsHelpers.get_asset_tools()
folder='/Game/Crusader/Effects/Range'
existing={a.get_actor_label():a for a in actors.get_all_level_actors()}
cube=u.load_asset('/Engine/BasicShapes/Cube')
materials='/Game/BulletImpactVFX/Test_Scene/TestSceneProps/Materials/'

def fixture(cls,name,location,rotation=u.Rotator()):
    label='CR_SurfaceRange_'+name
    actor=existing.get(label) or actors.spawn_actor_from_class(cls,u.Vector(*location),rotation)
    assert actor,label
    actor.set_actor_label(label);actor.set_actor_location(u.Vector(*location),False,True);actor.set_actor_rotation(rotation,False)
    actor.set_folder_path('Crusader/Surface Range')
    return actor
def paint(name,color,roughness=.7,metallic=0):
    path=folder+'/M_'+name
    mat=u.load_asset(path) if lib.does_asset_exist(path) else tools.create_asset('M_'+name,folder,u.Material,u.MaterialFactoryNew())
    u.MaterialEditingLibrary.delete_all_material_expressions(mat)
    value=u.MaterialEditingLibrary.create_material_expression(mat,u.MaterialExpressionConstant3Vector)
    value.constant=u.LinearColor(*color,1)
    u.MaterialEditingLibrary.connect_material_property(value,'',u.MaterialProperty.MP_BASE_COLOR)
    for prop,number in [(u.MaterialProperty.MP_ROUGHNESS,roughness),(u.MaterialProperty.MP_METALLIC,metallic)]:
        node=u.MaterialEditingLibrary.create_material_expression(mat,u.MaterialExpressionConstant);node.r=number
        u.MaterialEditingLibrary.connect_material_property(node,'',prop)
    u.MaterialEditingLibrary.recompile_material(mat);lib.save_loaded_asset(mat)
    return mat
dark=paint('RangeFrame',(.022,.028,.035),.55,.4)
floor=paint('RangeFloor',(.12,.13,.15),.85)
stripe=paint('FiringLine',(.8,.4,.035),.75)
def box(name,location,scale,mat,physical=None):
    actor=fixture(u.StaticMeshActor,name,location)
    component=actor.static_mesh_component
    component.set_static_mesh(cube);component.set_material(0,mat)
    component.set_collision_profile_name('BlockAll')
    if physical:component.set_phys_material_override(physical)
    actor.set_actor_scale3d(u.Vector(*scale))
    return actor
def sign(name,text,location,size=27):
    actor=fixture(u.TextRenderActor,name,location,u.Rotator(yaw=90))
    actor.text_render.set_text(text);actor.text_render.set_world_size(size)
    actor.text_render.set_horizontal_alignment(u.HorizTextAligment.EHTA_CENTER)
    actor.text_render.set_text_render_color(u.Color(240,240,225,255))
    return actor

box('Floor',(1200,-6425,-20),(36,24, .4),floor)
box('FiringLine',(1200,-5510,1),(34,.055,.025),stripe)
box('Backstop',(1200,-7170,210),(36,.3,4.2),dark)
sign('Title','SURFACE FIRING RANGE',(1200,-7110,450),55)
sign('Instructions','SOLID PANELS / GROUND TRAYS\nCompare impacts, sounds and bullet trails',(1200,-7080,390),25)
sign('Entry','SURFACE RANGE\nWeapons / fire line',(1100,-5260,260),34)
sign('Directions','SURFACE RANGE\nSouth of the slide lane',(1200,-3500,220),32)

panels=[('Concrete','Inst_Concrete_02'),('Glass','M_Window'),('Metal','Inst_Metal_Box'),('Wood','Inst_PineTree_Bark'),('Brick','Inst_Brick_Wall'),('Rubber','Inst_Tire'),('Fabric','Inst_Carptet'),('Rock','M_Rock'),('Ceramic','M_Tile_AlpinePatch'),('Drywall','M_Sheetrock')]
trays=[('Dirt','Inst_GroundRevealRock'),('Sand','M_Sand'),('Water','M_Cave_Water_A'),('Snow',None),('Ice','M_IceChunks_01'),('Mud','Inst_MudWet')]
records=[]
for i,(name,material) in enumerate(panels):
    x=-290+i*330
    physical=u.load_asset('/Game/Crusader/Effects/Surfaces/PM_'+name);assert physical
    mat=u.load_asset(materials+material);assert mat,material
    box(name+'_Frame',(x,-6965,157),(2.93,.4,3.14),dark)
    target=box(name,(x,-6935,170),(2.55,.22,2.55),mat,physical)
    sign(name+'_Label',name.upper(),(x,-6890,320),29)
    records.append(dict(name=name,actor=target.get_actor_label(),target=[x,-6920,170],standing=[x,-5710,94],surface=int(physical.get_editor_property('surface_type').value)))
for i,(name,material) in enumerate(trays):
    x=-150+i*540
    physical=u.load_asset('/Game/Crusader/Effects/Surfaces/PM_'+name);assert physical
    mat=u.load_asset(materials+material) if material else paint('Snow',(.85,.9,.95),.9)
    assert mat,material
    box(name+'_Tray',(x,-6210,12),(4.4,4.4,.24),dark)
    target=box(name,(x,-6210,24),(4.05,4.05,.12),mat,physical)
    sign(name+'_Label',name.upper(),(x,-6440,105),29)
    records.append(dict(name=name,actor=target.get_actor_label(),target=[x,-6210,31],standing=[x,-5650,94],surface=int(physical.get_editor_property('surface_type').value)))

for kind,name,x in [('Rifle','BlackIronRifle',-280),('Pistol','FuturisticPistol',30),('Shotgun','TitanBreaker',340)]:
    path='/Game/Crusader/Weapons/BlackIronRifle/ID_BlackIronRifle' if kind=='Rifle' else f'/Game/Baseline/Weapons/{kind}/ID_{kind}'
    item=u.load_asset(path).generated_class()
    pickup=fixture(u.BaselineWeaponPickup,'Pickup_'+kind,(x,-5370,55))
    pickup.set_editor_property('item_definition',item)
    pickup.display_mesh.set_skeletal_mesh_asset(u.load_asset(f'/Game/Crusader/Weapons/{name}/{name}'))
    pickup.display_mesh.set_material(0,u.load_asset(f'/Game/Crusader/Weapons/{name}/M_{name}'))
    sign('PickupLabel_'+kind,kind.upper()+' / E',(x,-5370,115),23)
assert level.save_current_level()
(ROOT/'resources/SurfaceRange.json').write_text(json.dumps(dict(map='/Game/Maps/L_TraversalGym',targets=records),indent=2))
print('SURFACE_RANGE_COMPLETE',len(records),'targets')
