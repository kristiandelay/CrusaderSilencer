"""Adapt the licensed Next Gen Destruction assets to Crusader collision and surfaces."""
import json
from pathlib import Path
import unreal as u

assert not u.EditorLevelLibrary.get_pie_worlds(False)
ds_root=Path(u.Paths.convert_relative_path_to_full(u.Paths.project_dir())).parent
ds_lib=u.EditorAssetLibrary
ds_pack='/Game/NextGenDestruction'
ds_path='/Game/Crusader/Destruction/B_CRDestructible'
ds_bp=u.load_asset(ds_path) if ds_lib.does_asset_exist(ds_path) else ds_lib.duplicate_asset(ds_pack+'/Blueprints/Actors/BP_BreakableObject',ds_path)
assert ds_bp
u.BlueprintEditorLibrary.reparent_blueprint(ds_bp,u.CRDestructibleActor)
ds_cdo=u.get_default_object(ds_bp.generated_class())
ds_cdo.set_editor_property('replicates',True)
ds_cdo.set_editor_property('net_cull_distance_squared',900000000.)
ds_sub=u.get_engine_subsystem(u.SubobjectDataSubsystem)
ds_data=u.SubobjectDataBlueprintFunctionLibrary
for handle in ds_sub.k2_gather_subobject_data_for_blueprint(ds_bp):
    obj=ds_data.get_object(ds_data.get_data(handle))
    if isinstance(obj,u.GeometryCollectionComponent):
        for key,val in [('bEnableReplication','True'),('bEnableAbandonAfterLevel','False'),('ReplicationAbandonAfterLevel','100'),
                        ('bNotifyGlobalBreaks','True'),('bNotifyGlobalCollisions','True'),('bNotifyGlobalTrailings','True'),
                        ('bCanEverAffectNavigation','False')]:
            assert u.CRBlueprintTools.set_property_text(obj,key,val),key
        obj.set_is_replicated(True)
        obj.set_collision_profile_name('CRDestructible')
        obj.set_editor_property('receives_decals',False) # decals cannot follow individual Chaos fragments
    elif isinstance(obj,u.StaticMeshComponent):
        obj.set_collision_profile_name('BlockAll')
u.BlueprintEditorLibrary.compile_blueprint(ds_bp)
assert not u.CRBlueprintTools.has_blueprint_errors(ds_bp)
assert ds_lib.save_loaded_asset(ds_bp,only_if_is_dirty=False)

# Keep each toolkit physical material's identity: the Chaos Niagara data
# interfaces filter by material object, while Crusader sounds use surface IDs.
ds_surfaces={'Concrete':2,'Glass':3,'Metal':4,'Wood':5,'Brick':6,'Plaster':17,'Generic':16,'NOFX':0}
for name,index in ds_surfaces.items():
    mat=u.load_asset(ds_pack+'/GeometryCollections/PhysMat/PM_'+name)
    assert mat
    assert u.CRBlueprintTools.set_property_text(mat,'SurfaceType','SurfaceType'+str(index) if index else 'SurfaceType_Default')
    assert ds_lib.save_loaded_asset(mat,only_if_is_dirty=False)

ds_checks=[]
for path in ds_lib.list_assets(ds_pack+'/Blueprints',recursive=True):
    asset=u.load_asset(path)
    if isinstance(asset,u.Blueprint):
        u.BlueprintEditorLibrary.compile_blueprint(asset)
        assert not u.CRBlueprintTools.has_blueprint_errors(asset),path
        ds_checks.append(path)
(ds_root/'Artifacts/Destruction/asset-checks.json').write_text(json.dumps(dict(blueprints=ds_checks,physical_surfaces=ds_surfaces),indent=2))
print('DESTRUCTION_CONFIGURED',len(ds_checks),'Blueprints')
