"""Fracture selected original furniture, retaining editor-only source actors for rebuilding.

Run in L_TraversalGym outside Play. Existing GC assets are reused; set
BD_REBUILD_COLLECTIONS=True before exec to intentionally refracture source meshes.
"""
import json
from pathlib import Path
import unreal as u

assert not u.EditorLevelLibrary.get_pie_worlds(False)
bd_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
bd_world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
assert bd_world.get_name()=='L_TraversalGym'
bd_actors=u.get_editor_subsystem(u.EditorActorSubsystem)
bd_existing={a.get_actor_label():a for a in bd_actors.get_all_level_actors()}
# Recover from interrupted authoring without retaining overlapping copies.
for bd_duplicate in bd_actors.get_all_level_actors():
    if bd_duplicate.get_actor_label().startswith('CR_Breakable_') and bd_existing[bd_duplicate.get_actor_label()]!=bd_duplicate:
        bd_actors.destroy_actor(bd_duplicate)
bd_lib=u.EditorAssetLibrary
bd_tools=u.AssetToolsHelpers.get_asset_tools()
bd_folder='/Game/Crusader/Destruction/Furniture'
bd_lib.make_directory(bd_folder)
bd_pack='/Game/NextGenDestruction'

# Explicit selection keeps walls, roofs and the main command consoles intact.
# Each compound includes the props resting on it, preventing floating accessories.
bd_groups=[('Facility_LabSupplyA',['LabSupplyA','LabSupplyB'],'LabSupplyStack',32,75),
           ('Facility_OfficeDesk',['OfficeDesk','OfficeMonitor','OfficeKeyboard','OfficeTerminal'],'OfficeDeskSet',40,90),
           ('Facility_OfficeDrawer',['OfficeDrawer','OfficeStorage'],'OfficeStorageSet',28,45)]
for bd_name in ['ContainmentCrate','OfficeChair','OfficeCrate','CheckpointCrate','FreightSupplies_0','FreightSupplies_1']:
    bd_groups.append(('Facility_'+bd_name,[bd_name],None,24,35 if bd_name=='OfficeChair' else 65))
for bd_name in ['CommandTerminal_0','CommandTerminal_1','OperationsCrate_0','OperationsCrate_1',
                'ServiceLocker_0','ServiceLocker_1','ServiceLocker_2','ServiceWorkstation',
                'StorageBarrel_0','StorageBarrel_1','StorageBarrel_2','StorageCrate_0',
                'StorageCrate_1','StorageCrate_2','LobbyTerminal_0','LobbyTerminal_1','LobbySupply_0','LobbySupply_1']:
    bd_groups.append(('ControlRoom_'+bd_name,[bd_name],None,24,65))

bd_mat_path=bd_folder+'/M_FracturedMetal'
bd_interior=u.load_asset(bd_mat_path) if bd_lib.does_asset_exist(bd_mat_path) else bd_tools.create_asset('M_FracturedMetal',bd_folder,u.Material,u.MaterialFactoryNew())
# Named material is authored once; the outside keeps the imported texture materials.
if not bd_lib.get_metadata_tag(bd_interior,'CrusaderFractureInterior'):
    bd_color=u.MaterialEditingLibrary.create_material_expression(bd_interior,u.MaterialExpressionConstant3Vector,-320,0)
    bd_color.set_editor_property('constant',u.LinearColor(.045,.052,.065,1))
    u.MaterialEditingLibrary.connect_material_property(bd_color,'',u.MaterialProperty.MP_BASE_COLOR)
    for bd_property,bd_value,bd_y in [(u.MaterialProperty.MP_METALLIC,.65,140),(u.MaterialProperty.MP_ROUGHNESS,.8,240)]:
        bd_expr=u.MaterialEditingLibrary.create_material_expression(bd_interior,u.MaterialExpressionConstant,-320,bd_y)
        bd_expr.set_editor_property('r',bd_value)
        u.MaterialEditingLibrary.connect_material_property(bd_expr,'',bd_property)
    u.MaterialEditingLibrary.recompile_material(bd_interior)
    bd_lib.set_metadata_tag(bd_interior,'CrusaderFractureInterior','1')
    bd_lib.save_loaded_asset(bd_interior,False)

bd_bp_path=bd_folder+'/B_CRDestructibleFurniture'
bd_bp=u.load_asset(bd_bp_path) if bd_lib.does_asset_exist(bd_bp_path) else bd_lib.duplicate_asset('/Game/Crusader/Destruction/B_CRDestructible',bd_bp_path)
bd_cdo=u.get_default_object(bd_bp.generated_class())
bd_cdo.set_editor_property('block_navigation_until_broken',True)
bd_cdo.set_editor_property('weapon_contact_strain',2000000.)
assert u.CRBlueprintTools.set_property_text(bd_cdo,'IntactNavigation',bd_cdo.get_component_by_class(u.CRDestructibleNavigation).get_path_name())
bd_sub=u.get_engine_subsystem(u.SubobjectDataSubsystem)
bd_dl=u.SubobjectDataBlueprintFunctionLibrary
for bd_h in bd_sub.k2_gather_subobject_data_for_blueprint(bd_bp):
    bd_obj=bd_dl.get_object(bd_dl.get_data(bd_h))
    if isinstance(bd_obj,u.GeometryCollectionComponent):
        assert u.CRBlueprintTools.set_property_text(bd_obj,'bEnableDamageFromCollision','False')
        # The intact cluster blocks characters; released pieces do not catch feet/cameras.
        assert u.CRBlueprintTools.set_property_text(bd_obj,'CollisionProfilePerLevel','("CRDestructible","IgnoreCharChaos","IgnoreCharChaos","IgnoreCharChaos")')
u.BlueprintEditorLibrary.compile_blueprint(bd_bp)
assert not u.CRBlueprintTools.has_blueprint_errors(bd_bp)
bd_lib.save_loaded_asset(bd_bp,False)

def bd_asset_property(obj,key,asset):
    assert asset is not None,key
    assert u.CRBlueprintTools.set_property_text(obj,key,asset.get_path_name()),key

bd_records=[];bd_collections={};bd_primary_scales={}
for bd_label,bd_names,bd_custom,bd_cells,bd_mass in bd_groups:
    bd_building=bd_label.split('_')[0]
    bd_sources=[bd_existing['CR_'+bd_building+'_'+name] for name in bd_names]
    assert all(isinstance(a,u.StaticMeshActor) for a in bd_sources)
    bd_base_name=bd_custom or bd_sources[0].static_mesh_component.static_mesh.get_name()
    bd_scale=bd_sources[0].get_actor_scale3d()
    assert abs(bd_scale.x-bd_scale.y)<.001 and abs(bd_scale.x-bd_scale.z)<.001,'Furniture requires uniform source scale'
    bd_scale_value=round(bd_scale.x,5)
    bd_primary_scales.setdefault(bd_base_name,bd_scale_value)
    bd_name=bd_base_name if bd_primary_scales[bd_base_name]==bd_scale_value else bd_base_name+'_S'+str(round(bd_scale_value*100))
    bd_gc_path=bd_folder+'/GC_'+bd_name
    bd_signature=json.dumps([dict(mesh=a.static_mesh_component.static_mesh.get_path_name(),
        materials=[m.get_path_name() for m in a.static_mesh_component.get_materials()],
        relative=u.MathLibrary.make_relative_transform(a.get_actor_transform(),bd_sources[0].get_actor_transform()).export_text())
        for a in bd_sources],sort_keys=True)
    # UE 5.8's GC factory opens a Dataflow template dialog even through Python.
    # Use a plain kit collection as an asset container; the native authoring tool
    # replaces its complete geometry/materials with the selected source meshes.
    bd_container=bd_folder+'/GC_'+bd_base_name if bd_name!=bd_base_name else bd_pack+'/GeometryCollections/Wood/GC_Chair'
    bd_gc=u.load_asset(bd_gc_path) if bd_lib.does_asset_exist(bd_gc_path) else bd_lib.duplicate_asset(bd_container,bd_gc_path)
    if bd_name not in bd_collections and (globals().get('BD_REBUILD_COLLECTIONS',False) or
        bd_lib.get_metadata_tag(bd_gc,'CrusaderSource').replace('-0.000000','0.000000')!=bd_signature.replace('-0.000000','0.000000')):
        bd_pieces=u.CRDestructionTools.build_furniture_collection(bd_gc,bd_sources,bd_interior,bd_cells,723,bd_mass)
        assert 8<=bd_pieces<=180,(bd_name,bd_pieces)
        # Keep debris long enough to see the result, then shrink sleeping fragments.
        for bd_key,bd_value in [('bRemoveOnMaxSleep','True'),('MaximumSleepTime','(X=12,Y=18)'),('RemovalDuration','(X=2,Y=3)')]:
            assert u.CRBlueprintTools.set_property_text(bd_gc,bd_key,bd_value),bd_key
        bd_lib.set_metadata_tag(bd_gc,'CrusaderSource',bd_signature)
        bd_lib.set_metadata_tag(bd_gc,'CrusaderBakedScale','1')
        assert bd_lib.save_loaded_asset(bd_gc,False)
    bd_pieces=u.CRDestructionTools.get_rigid_piece_count(bd_gc)
    assert bd_pieces>=8
    bd_baked_scale=float(bd_lib.get_metadata_tag(bd_gc,'CrusaderBakedScale') or '1')
    if abs(bd_baked_scale-bd_scale_value)>.00001:
        bd_hulls=u.CRDestructionTools.bake_furniture_scale(bd_gc,bd_scale_value/bd_baked_scale)
        assert bd_hulls>=bd_pieces,(bd_name,bd_hulls)
        bd_lib.set_metadata_tag(bd_gc,'CrusaderBakedScale',str(bd_scale_value))
        bd_lib.set_metadata_tag(bd_gc,'CrusaderCollisionVersion','1')
        bd_lib.set_metadata_tag(bd_gc,'CrusaderConvexCount',str(bd_hulls))
        assert bd_lib.save_loaded_asset(bd_gc,False)
    if bd_lib.get_metadata_tag(bd_gc,'CrusaderCollisionVersion')!='1':
        bd_hulls=u.CRDestructionTools.rebuild_furniture_physics(bd_gc)
        assert bd_hulls>=bd_pieces,(bd_name,'Missing collision hulls',bd_hulls,bd_pieces)
        bd_lib.set_metadata_tag(bd_gc,'CrusaderCollisionVersion','1')
        bd_lib.set_metadata_tag(bd_gc,'CrusaderConvexCount',str(bd_hulls))
        assert bd_lib.save_loaded_asset(bd_gc,False)
    bd_collections[bd_name]=dict(asset=bd_gc_path,pieces=bd_pieces,
        convex_hulls=int(bd_lib.get_metadata_tag(bd_gc,'CrusaderConvexCount')))
    bd_data_path=bd_folder+'/DA_'+bd_name
    bd_data=u.load_asset(bd_data_path) if bd_lib.does_asset_exist(bd_data_path) else bd_lib.duplicate_asset(bd_pack+'/Blueprints/DataAssets/Destructible/DA_Chair_Wood',bd_data_path)
    for bd_key,bd_asset in [('GeometryCollection',bd_gc),('Physical Material',u.load_asset(bd_pack+'/GeometryCollections/PhysMat/PM_Metal')),
        ('BreakSound',u.load_asset(bd_pack+'/Audio/Destruction/Metal/Metal_Hit_01')),
        ('BulletImpactSound',u.load_asset(bd_pack+'/Audio/Destruction/Metal/BulletImpact_Metal_Cue')),
        ('PiecesCollisionSound',u.load_asset(bd_pack+'/Audio/Destruction/Metal/Metal_Hit_02')),
        ('BreakingVFX',u.load_asset(bd_pack+'/FX/Destruction/Spawnable/NS_BulletImpact_Metal'))]:
        bd_asset_property(bd_data,bd_key,bd_asset)
    for bd_key,bd_value in [('HasKinematicPieces','False'),('Removal on Sleep','True'),('OverrideMaterials','()'),
        ('OptionalStaticMesh','None'),('SwitchMatOnBreak','False'),('OverrideDamageThresholds','False'),
        ('DamageRadius','0.65'),('BreakSoundFreqMin','0.2'),('BreakSoundFreqMax','0.4')]:
        assert u.CRBlueprintTools.set_property_text(bd_data,bd_key,bd_value),bd_key
    assert bd_lib.save_loaded_asset(bd_data,False)

    bd_proxy_label='CR_Breakable_'+bd_label
    bd_actor=bd_existing.get(bd_proxy_label) or bd_actors.spawn_actor_from_class(bd_bp.generated_class(),bd_sources[0].get_actor_location())
    assert isinstance(bd_actor,u.CRDestructibleActor)
    bd_actor.set_actor_label(bd_proxy_label)
    bd_actor.set_folder_path('Crusader/Destructible Furniture/'+bd_building)
    bd_actor.tags=['CrusaderBuildingDestruction',bd_building]
    bd_actor.set_editor_property('weapon_contact_strain',2000000.)
    assert u.CRBlueprintTools.set_property_text(bd_actor,'IntactNavigation',bd_actor.get_component_by_class(u.CRDestructibleNavigation).get_path_name())
    bd_actor.set_editor_property('DataAsset',bd_data)
    bd_placement=bd_sources[0].get_actor_transform()
    bd_placement.scale3d=u.Vector(1,1,1)
    bd_actor.set_actor_transform(bd_placement,False,True)
    bd_geometry=bd_actor.get_destructible_geometry()
    assert bd_geometry.rest_collection==bd_gc
    # Retain source transforms/materials for authoring only, excluded from PIE/cooks.
    # This also lets the existing building generators rebuild their source meshes.
    for bd_source in bd_sources:
        bd_source.set_editor_property('is_editor_only_actor',True)
        bd_source.set_actor_hidden_in_game(True)
        bd_source.set_is_temporarily_hidden_in_editor(True)
        assert u.CRBlueprintTools.set_property_text(bd_source,'bHiddenEd','True')
        bd_source.static_mesh_component.set_collision_profile_name('NoCollision')
        assert u.CRBlueprintTools.set_property_text(bd_source.static_mesh_component,'bCanEverAffectNavigation','False')
        bd_source.set_folder_path('Crusader/Destructible Furniture/Editor Sources/'+bd_building)
    bd_center,bd_extent=bd_actor.get_actor_bounds(False)
    bd_records.append(dict(actor=bd_proxy_label,name=bd_name,building=bd_building,
        sources=[a.get_actor_label() for a in bd_sources],geometry=bd_gc_path,preset=bd_data_path,pieces=bd_pieces,
        center=[bd_center.x,bd_center.y,bd_center.z],extent=[bd_extent.x,bd_extent.y,bd_extent.z],
        transform=bd_actor.get_actor_transform().export_text()))
    print('FURNITURE',bd_proxy_label,bd_pieces)

for bd_nav in u.GameplayStatics.get_all_actors_of_class(bd_world,u.RecastNavMesh):
    assert u.CRBlueprintTools.set_property_text(bd_nav,'RuntimeGeneration','Dynamic')
u.SystemLibrary.execute_console_command(bd_world,'RebuildNavigation')
assert u.get_editor_subsystem(u.LevelEditorSubsystem).save_current_level()
(bd_root/'resources/BuildingDestruction.json').write_text(json.dumps(dict(map='/Game/Maps/L_TraversalGym',
    blueprint=bd_bp_path,collections=bd_collections,targets=bd_records),indent=2)+'\n')
print('BUILDING_DESTRUCTION_BUILT',len(bd_records),'actors',len(bd_collections),'collections')
