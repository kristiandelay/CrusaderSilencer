"""Walkable sound surfaces and an environment model gallery in the traversal gym."""
import json
from pathlib import Path
import unreal as u

ROOT=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
assert not u.EditorLevelLibrary.get_pie_worlds(False)
actors=u.get_editor_subsystem(u.EditorActorSubsystem);level=u.get_editor_subsystem(u.LevelEditorSubsystem)
assert u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world().get_name()=='L_TraversalGym'
lib=u.EditorAssetLibrary;tools=u.AssetToolsHelpers.get_asset_tools()
existing={a.get_actor_label():a for a in actors.get_all_level_actors()}
cube=u.load_asset('/Engine/BasicShapes/Cube')
floor=u.load_asset('/Game/Crusader/Effects/Range/M_RangeFloor');frame=u.load_asset('/Game/Crusader/Effects/Range/M_RangeFrame')

def fixture(cls,name,location,rotation=u.Rotator()):
    label='CR_Additions_'+name
    actor=existing.get(label) or actors.spawn_actor_from_class(cls,u.Vector(*location),rotation)
    actor.set_actor_label(label);actor.set_actor_location(u.Vector(*location),False,True);actor.set_actor_rotation(rotation,False)
    actor.set_folder_path('Crusader/Environment Tests');return actor
def box(name,location,scale,mat,physical=None):
    a=fixture(u.StaticMeshActor,name,location);a.static_mesh_component.set_static_mesh(cube)
    a.static_mesh_component.set_material(0,mat);a.set_actor_scale3d(u.Vector(*scale));a.static_mesh_component.set_collision_profile_name('BlockAll')
    if physical:a.static_mesh_component.set_phys_material_override(physical)
    return a
def sign(name,text,location,size=28,yaw=90):
    a=fixture(u.TextRenderActor,name,location,u.Rotator(yaw=yaw));a.text_render.set_text(text);a.text_render.set_world_size(size)
    a.text_render.set_horizontal_alignment(u.HorizTextAligment.EHTA_CENTER);return a
def paint(name,color):
    path='/Game/Crusader/Effects/Range/M_Walk_'+name
    mat=u.load_asset(path) if lib.does_asset_exist(path) else tools.create_asset('M_Walk_'+name,'/Game/Crusader/Effects/Range',u.Material,u.MaterialFactoryNew())
    u.MaterialEditingLibrary.delete_all_material_expressions(mat)
    node=u.MaterialEditingLibrary.create_material_expression(mat,u.MaterialExpressionConstant3Vector);node.constant=u.LinearColor(*color,1)
    u.MaterialEditingLibrary.connect_material_property(node,'',u.MaterialProperty.MP_BASE_COLOR)
    rough=u.MaterialEditingLibrary.create_material_expression(mat,u.MaterialExpressionConstant);rough.r=.8
    u.MaterialEditingLibrary.connect_material_property(rough,'',u.MaterialProperty.MP_ROUGHNESS)
    u.MaterialEditingLibrary.recompile_material(mat);lib.save_loaded_asset(mat);return mat

box('WalkFloor',(7800,-6300,-20),(68,44,.4),floor)
box('WalkConnector',(4100,-5700,-20),(24,7,.4),floor)
sign('WalkTitle','FOOTSTEP SURFACES / WALK - SPRINT - CROUCH - JUMP',(7800,-8500,200),48)
surfaces=json.loads((ROOT/'resources/FootstepSurfaces.json').read_text())['surfaces']
range_targets={r['name']:existing.get(r['actor']) for r in json.loads((ROOT/'resources/SurfaceRange.json').read_text())['targets']}
colors={'Grass':(.13,.24,.045),'Gravel':(.21,.2,.17),'Leaves':(.26,.17,.055),'Carpet':(.09,.13,.2),'BrokenGlass':(.17,.3,.32),'WetSand':(.3,.23,.13),'DeepWater':(.035,.13,.2),'GlassOnMetal':(.25,.29,.31),'GlassOnWood':(.25,.2,.13),'HighGrass':(.12,.2,.025)}
records=[]
for i,entry in enumerate(surfaces):
    name=entry['name'];x=5000+(i%9)*700;y=-4900-(i//9)*1400
    original=range_targets.get(name)
    mat=original.static_mesh_component.get_material(0) if original else paint(name,colors.get(name,(.27,.28,.3)))
    physical=u.load_asset('/Game/Crusader/Effects/Surfaces/PM_'+name)
    pad=box('Walk_'+name,(x,y,3),(6,11,.06),mat,physical)
    sign('WalkLabel_'+name,name.upper(),(x,y-620,70),30)
    records.append(dict(name=name,surface=entry['id'],actor=pad.get_actor_label(),start=[x,y+420,100],end=[x,y-420,100]))
box('GalleryFloor',(7100,-11600,-20),(55,59,.4),floor)
box('GalleryConnector',(7400,-9100,-20),(7,14,.4),floor)
sign('GalleryTitle','CRUSADER ENVIRONMENT / 33 MODELS',(7100,-8800,190),52)
models=json.loads((ROOT/'resources/EnvironmentModels.json').read_text())
for i,entry in enumerate(models):
    x=5000+(i%6)*800;y=-9700-(i//6)*900
    a=fixture(u.StaticMeshActor,'Model_'+entry['name'],(x,y,0),u.Rotator(yaw=180))
    a.static_mesh_component.set_static_mesh(u.load_asset(entry['asset']));a.static_mesh_component.set_collision_profile_name('BlockAll')
    sign('ModelLabel_'+entry['name'],entry['name'],(x,y-340,25),22)
    if entry['name']=='IndustrialCargoCrate01':
        a.static_mesh_component.set_mobility(u.ComponentMobility.MOVABLE)
        a.tags=['BulletHoleAttachmentTest']
assert level.save_current_level()
(ROOT/'resources/EnvironmentTestAreas.json').write_text(json.dumps(dict(map='/Game/Maps/L_TraversalGym',footstep_surfaces=records,gallery_models=33),indent=2))
print('ENVIRONMENT_TEST_AREAS_COMPLETE',len(records),'walk surfaces',len(models),'models')
